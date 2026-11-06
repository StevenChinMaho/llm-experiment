#!/usr/bin/env python3
"""E4、E5 評估腳本：對 llama-server 送題、重複、程式批改、統計（docs/experiment-plan.md）。

只用標準函式庫。思考預算是伺服器端設定（--reasoning-budget），腳本只負責記錄。

用法：
  # 送題（每個條件一個 --label；中斷後用同樣指令重跑會跳過已完成的）
  python3 run_eval.py --url http://127.0.0.1:8000 --label iq4xs_b16384 \
      --questions eval/aime_2026.json eval/questions.json:hard --reps 3 --max-tokens 20000 \
      --out results/raw/e4_.../results.jsonl
  # 只重算統計
  python3 run_eval.py --summarize results/raw/e4_.../results.jsonl
  # E5：讓模型可以呼叫計算工具（--tool calculator）
  python3 run_eval.py --url http://127.0.0.1:8000 --label iq3xxs_b4096_tool --tool calculator \\
      --questions eval/e5_questions.json --reps 2 --max-tokens 8192 --out results/raw/e5_.../results.jsonl
  # 批改器自我測試（用標準答案組成假回應，確認全部判對）
  python3 run_eval.py --self-test --questions eval/aime_2026.json eval/questions.json:easy eval/questions.json:hard

時間指標：TTFT＝送出到第一個 token（思考或答案）；TTA＝送出到第一個答案 token（思考結束後）；total＝到回應結束。
"""
import argparse
import ast
import datetime
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.request
from decimal import Decimal, localcontext
from fractions import Fraction

# ---------------------------------------------------------------- 計算工具（E5）

CALC_TOOL = {"type": "function", "function": {
    "name": "calculator",
    "description": "精確計算數學算式並回傳結果。整數與分數為精確計算，不會有浮點誤差。"
                   "支援 + - * / // % ** 與括號，以及函式 pow(a,b) pow(a,b,m) comb(n,k) factorial(n) sqrt(x) "
                   "log(x) log(x,b) log2(x) log10(x) exp(x) floor(x) ceil(x) round(x) abs(x) min(...) max(...)，常數 pi、e。"
                   "次方請用 **，不要用 ^。",
    "parameters": {"type": "object", "required": ["expression"],
                   "properties": {"expression": {"type": "string", "description": "要計算的算式，例如 987654321*123456789"}}}}}
MAX_EXPONENT = 100000
MAX_RESULT_BITS = 2000000


def _to_float(x):
    return float(x)


def _pow(a, b):
    if isinstance(b, Fraction) and b.denominator == 1:
        b = int(b)
    if isinstance(a, float) or isinstance(b, (float, Fraction)):
        return _to_float(a) ** _to_float(b)
    if abs(b) > MAX_EXPONENT:
        raise ValueError(f"指數太大（上限 {MAX_EXPONENT}）")
    base_bits = max(Fraction(a).numerator.bit_length(), Fraction(a).denominator.bit_length())
    if base_bits * abs(b) > MAX_RESULT_BITS:
        raise ValueError("結果太大")
    return Fraction(a) ** b


def _pow_mod(a, b, m=None):
    if m is None:
        return _pow(a, b)
    return pow(int(a), int(b), int(m))


def _factorial(n):
    if int(n) > 20000:
        raise ValueError("太大")
    return math.factorial(int(n))


def _floatfn(fn):
    return lambda *args: fn(*[_to_float(x) for x in args])


CALC_FUNCS = {"pow": _pow_mod, "comb": lambda n, k: math.comb(int(n), int(k)) if int(n) <= 100000 else 1 / 0, "factorial": _factorial,
              "sqrt": _floatfn(math.sqrt), "log": _floatfn(math.log), "log2": _floatfn(math.log2),
              "log10": _floatfn(math.log10), "exp": _floatfn(math.exp),
              "floor": lambda x: math.floor(x), "ceil": lambda x: math.ceil(x),
              "round": lambda x: math.floor(Fraction(x) + Fraction(1, 2)) if not isinstance(x, float) else round(x),
              "abs": abs, "min": min, "max": max}
CALC_NAMES = {"pi": math.pi, "e": math.e}


def _calc(node):
    if isinstance(node, ast.Expression):
        return _calc(node.body)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        v = node.value
        return v if isinstance(v, int) else Fraction(Decimal(repr(v)))   # 0.0375 視為精確小數
    if isinstance(node, ast.Name) and node.id in CALC_NAMES:
        return CALC_NAMES[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        v = _calc(node.operand)
        return v if isinstance(node.op, ast.UAdd) else -v
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.BitXor):
            raise ValueError("次方請用 **，不要用 ^")
        a, b = _calc(node.left), _calc(node.right)
        if isinstance(node.op, ast.Pow):
            return _pow(a, b)
        if isinstance(node.op, ast.Div):
            return a / b if isinstance(a, float) or isinstance(b, float) else Fraction(a) / Fraction(b)
        ops = {ast.Add: lambda: a + b, ast.Sub: lambda: a - b, ast.Mult: lambda: a * b,
               ast.FloorDiv: lambda: a // b, ast.Mod: lambda: a % b}
        if type(node.op) in ops:
            return ops[type(node.op)]()
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in CALC_FUNCS and not node.keywords:
        return CALC_FUNCS[node.func.id](*[_calc(x) for x in node.args])
    raise ValueError(f"不支援的語法：{type(node).__name__}")


def _calc_format(v):
    if isinstance(v, Fraction):
        if v.denominator == 1:
            return str(v.numerator)
        with localcontext() as ctx:
            ctx.prec = 40
            return str((Decimal(v.numerator) / Decimal(v.denominator)).normalize())
    return str(v)


def calculator(expression):
    """安全地計算算式（只走語法樹，不用 eval）。錯誤以字串回傳，讓模型可以修正後重試。"""
    if not isinstance(expression, str) or len(expression) > 500:
        return "錯誤：算式必須是 500 字以內的字串"
    try:
        expr = expression.translate(str.maketrans("×÷，", "*/,")).replace(",", "") if "(" not in expression else \
            expression.translate(str.maketrans("×÷", "*/"))
        return _calc_format(_calc(ast.parse(expr.strip(), mode="eval")))
    except Exception as e:
        return f"錯誤：{type(e).__name__}: {e}"


# ---------------------------------------------------------------- 題目載入


def load_questions(specs):
    """spec 為 `檔案` 或 `檔案:題組`。回傳 [(question_dict, prompt_text)]。"""
    out = []
    for spec in specs:
        path, _, set_name = spec.partition(":")
        d = json.load(open(path, encoding="utf-8"))
        if "sets" in d:
            sets = [set_name] if set_name else list(d["sets"])
            qs = [q for s in sets for q in d["sets"][s]]
        else:
            qs = d["questions"]
        for q in qs:
            if q["grading"] == "python_tests":
                prompt = q["prompt"] + "\n\n" + d["code_instruction"]
            elif q.get("no_answer_instruction"):
                prompt = q["prompt"]
            else:
                prompt = q["prompt"] + "\n\n" + d["answer_instruction"]
            out.append((q, prompt))
    ids = [q["id"] for q, _ in out]
    assert len(ids) == len(set(ids)), "題號重複"
    return out


# ---------------------------------------------------------------- 擷取與批改


def norm(s):
    """全形轉半形、去空白、去句尾標點。"""
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", "", s)
    return s.strip("。.，,")


def answer_line(text):
    """取最後一個「答案：」之後的內容（同一行）。找不到回傳 None。"""
    t = unicodedata.normalize("NFKC", text)
    hits = re.findall(r"答案\s*[:：]\s*(.+)", t)
    if not hits:
        return None
    ans = hits[-1].strip()
    ans = re.sub(r"^\$+|\$+$", "", ans).strip()                     # 去掉 LaTeX 的 $…$
    m = re.fullmatch(r"\\boxed\{(.*)\}", ans)
    return m.group(1) if m else ans


def parse_int(s):
    m = re.search(r"-?\d[\d,]*", s.replace(" ", ""))
    return int(m.group(0).replace(",", "")) if m else None


def parse_fraction(s):
    s = norm(s)
    m = re.search(r"\\d?frac\{(-?\d+)\}\{(\d+)\}", s)
    if m:
        return Fraction(int(m.group(1)), int(m.group(2)))
    m = re.search(r"(-?\d+)/(\d+)", s)
    if m:
        return Fraction(int(m.group(1)), int(m.group(2)))
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return Fraction(m.group(0)) if m else None


# multi_field：欄位名稱 → 題目要求的中文標籤（依 eval/questions.json 各題的「請依格式回答」）
FIELD_LABELS = {"length": ["長度"], "count": ["個數", "條數"], "person": ["人"], "drink": ["飲料"],
                "distance": ["距離"], "n": ["n"]}


def parse_multi(ans, gold):
    a = unicodedata.normalize("NFKC", ans)
    got = {}
    for field, want in gold.items():
        if field == "possible":
            got[field] = None if not re.search(r"能", a) else (not re.search(r"不能", a))
            continue
        val = None
        for label in FIELD_LABELS.get(field, [field]):
            m = re.search(re.escape(label) + r"\s*[=＝:：]\s*([^,，;；\s]+)", a)
            if m:
                val = m.group(1).strip("。.")
                break
        if val is not None and isinstance(want, int):
            val = parse_int(val)
        got[field] = val
    return got


def extract_json(text):
    """取最後一個能解析的 {...} 物件。"""
    t = re.sub(r"```(?:json)?", "", text)
    for m in reversed(list(re.finditer(r"\{[^{}]*\}", t, re.S))):
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
    return None


def extract_code(text):
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text, re.S)
    return blocks[-1] if blocks else None


HARNESS = r'''
import json, sys
sys.setrecursionlimit(10000)
ns = {}
src = open("solution.py", encoding="utf-8").read()
exec(compile(src, "solution.py", "exec"), ns)
fn = ns[sys.argv[1]]
tests = json.load(open("tests.json", encoding="utf-8"))
res = []
for t in tests:
    try:
        got = fn(*t["input"])
        res.append({"ok": got == t["expected"], "got": repr(got)[:200]})
    except Exception as e:
        res.append({"ok": False, "got": "EXC " + type(e).__name__ + ": " + str(e)[:150]})
print(json.dumps(res))
'''


SANDBOX_IMAGE = None   # --sandbox-image：在無網路、唯讀、非 root 的容器裡執行模型寫的程式


def run_python_tests(code, q, timeout=10):
    """在暫存目錄的獨立子行程執行（python -I、清空環境變數、限時）；指定 SANDBOX_IMAGE 時改在隔離容器內執行。"""
    for tok in q.get("forbidden_tokens", []):
        if tok in code:
            return False, f"使用了禁止的 {tok}"
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, "solution.py"), "w", encoding="utf-8").write(code)
        open(os.path.join(d, "tests.json"), "w", encoding="utf-8").write(json.dumps(q["tests"], ensure_ascii=False))
        open(os.path.join(d, "harness.py"), "w", encoding="utf-8").write(HARNESS)
        if SANDBOX_IMAGE:
            os.chmod(d, 0o755)
            for name in os.listdir(d):
                os.chmod(os.path.join(d, name), 0o644)
            cmd = ["docker", "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL",
                   "--security-opt", "no-new-privileges", "--memory", "512m", "--pids-limit", "64",
                   "--user", "65534:65534", "-v", f"{d}:/w:ro", "-w", "/w", SANDBOX_IMAGE,
                   "timeout", str(timeout), "python", "-I", "harness.py", q["function"]]
            outer = timeout + 60   # 含容器啟動時間；模型程式的時限由容器內的 timeout 負責
        else:
            cmd, outer = [sys.executable, "-I", "harness.py", q["function"]], timeout
        try:
            p = subprocess.run(cmd, cwd=d, capture_output=True, text=True, timeout=outer,
                               env={"PATH": os.environ.get("PATH", "")})
        except subprocess.TimeoutExpired:
            return False, f"逾時 {timeout}s"
        if p.returncode in (124, 143):   # 容器內 timeout 終止
            return False, f"逾時 {timeout}s"
        if p.returncode != 0:
            return False, "執行錯誤：" + p.stderr.strip().splitlines()[-1][:200] if p.stderr.strip() else "執行錯誤"
        res = json.loads(p.stdout.strip().splitlines()[-1])
        n_ok = sum(r["ok"] for r in res)
        return n_ok == len(res), f"{n_ok}/{len(res)} 測資通過"


def grade(q, content):
    """回傳 (correct, extracted, detail)。extracted 為 None 代表擷取失敗。"""
    g = q["grading"]
    if g == "python_tests":
        code = extract_code(content)
        if code is None:
            return False, None, "找不到程式碼區塊"
        ok, detail = run_python_tests(code, q)
        return ok, code[:2000], detail
    if g == "json_fields":
        obj = extract_json(content)
        if obj is None:
            return False, None, "找不到 JSON"
        ok = all(norm(str(obj.get(k, ""))) == norm(str(v)) for k, v in q["answer"].items())
        return ok, obj, ""
    ans = answer_line(content)
    if ans is None:
        return False, None, "沒有「答案：」那一行"
    if g == "exact_int":
        v = parse_int(ans)
        return v == q["answer"], v, ans
    if g == "exact_text":
        return norm(ans) == norm(q["answer"]), ans, ""
    if g == "fraction":
        v = parse_fraction(ans)
        return v is not None and v == Fraction(q["answer"]), str(v), ans
    if g == "multi_field":
        got = parse_multi(ans, q["answer"])
        return got == q["answer"], got, ans
    raise ValueError(f"未知的批改方式 {g}")


# ---------------------------------------------------------------- 送題（串流）


def api_headers():
    h = {"Content-Type": "application/json"}
    if os.environ.get("LLAMA_API_KEY"):   # 只有對常駐服務試跑時需要；實驗容器沒有設 key
        h["Authorization"] = "Bearer " + os.environ["LLAMA_API_KEY"]
    return h


def ask(url, prompt, max_tokens, thinking, seed, timeout, messages=None, tools=None, t0=None):
    payload = {"messages": messages or [{"role": "user", "content": prompt}], "stream": True, "max_tokens": max_tokens,
               "cache_prompt": False, "seed": seed, "stream_options": {"include_usage": True},
               "chat_template_kwargs": {"enable_thinking": thinking}}
    if tools:
        payload["tools"] = tools
    req = urllib.request.Request(f"{url}/v1/chat/completions", data=json.dumps(payload).encode(), headers=api_headers())
    t0 = time.monotonic() if t0 is None else t0
    ttft = tta = None
    reasoning, content = [], []
    n_reason_chunks = n_content_chunks = 0
    finish = usage = timings = None
    tool_parts = {}
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            ev = json.loads(data)
            usage = ev.get("usage") or usage
            timings = ev.get("timings") or timings
            for ch in ev.get("choices", []):
                delta = ch.get("delta", {})
                rc, c = delta.get("reasoning_content"), delta.get("content")
                now = time.monotonic() - t0
                if rc:
                    reasoning.append(rc); n_reason_chunks += 1
                    ttft = ttft if ttft is not None else now
                if c:
                    content.append(c); n_content_chunks += 1
                    ttft = ttft if ttft is not None else now
                    tta = tta if tta is not None else now
                for tc in delta.get("tool_calls") or []:
                    part = tool_parts.setdefault(tc.get("index", 0), {"id": "", "name": "", "arguments": ""})
                    part["id"] = tc.get("id") or part["id"]
                    fn = tc.get("function") or {}
                    part["name"] = fn.get("name") or part["name"]
                    part["arguments"] += fn.get("arguments") or ""
                finish = ch.get("finish_reason") or finish
    return {"reasoning": "".join(reasoning), "content": "".join(content), "ttft_s": ttft, "tta_s": tta,
            "total_s": time.monotonic() - t0, "finish_reason": finish, "usage": usage, "timings": timings,
            "n_reasoning_chunks": n_reason_chunks, "n_content_chunks": n_content_chunks,
            "tool_parts": [tool_parts[k] for k in sorted(tool_parts)]}


MAX_TOOL_ROUNDS = 12


def ask_with_tools(url, prompt, max_tokens, thinking, seed, timeout):
    """模型呼叫工具 → 程式計算 → 把結果回傳給模型，重複到模型作答。

    max_tokens 是所有回合合計的上限；--reasoning-budget 是伺服器對每個回合各自套用，所以合計思考量以 max_tokens 為準。
    回傳的 content 只留最後一回合（批改對象），tta_s 是最後一回合第一個答案 token 的時間（使用者實際等到答案）。
    """
    t0 = time.monotonic()
    messages = [{"role": "user", "content": prompt}]
    reasoning, calls = [], []
    n_reason = n_content = used = rounds = 0
    ttft = None
    while True:
        rounds += 1
        r = ask(url, prompt, max_tokens - used, thinking, seed, timeout, messages=messages, tools=[CALC_TOOL], t0=t0)
        ttft = ttft if ttft is not None else r["ttft_s"]
        reasoning.append(r["reasoning"])
        n_reason += r["n_reasoning_chunks"]; n_content += r["n_content_chunks"]
        used += (r["usage"] or {}).get("completion_tokens", r["n_reasoning_chunks"] + r["n_content_chunks"])
        parts = r["tool_parts"]
        if not parts or r["finish_reason"] == "length" or rounds >= MAX_TOOL_ROUNDS or used >= max_tokens:
            finish = r["finish_reason"] if not parts else "tool_limit"
            return {"reasoning": "\n".join(reasoning), "content": r["content"], "ttft_s": ttft, "tta_s": r["tta_s"],
                    "total_s": time.monotonic() - t0, "finish_reason": finish, "usage": {"completion_tokens": used},
                    "timings": r["timings"], "n_reasoning_chunks": n_reason, "n_content_chunks": n_content,
                    "n_rounds": rounds, "tool_calls": calls}
        tool_msgs = []
        for i, p in enumerate(parts):
            p["id"] = p["id"] or f"call_{rounds}_{i}"
            try:
                expr = json.loads(p["arguments"]).get("expression")
            except (json.JSONDecodeError, AttributeError):
                expr = None
            result = calculator(expr) if p["name"] == "calculator" else f"錯誤：沒有工具 {p['name']}"
            calls.append({"round": rounds, "name": p["name"], "arguments": p["arguments"], "result": result,
                          "time_s": round(time.monotonic() - t0, 1)})
            tool_msgs.append({"role": "tool", "tool_call_id": p["id"], "content": result})
        messages.append({"role": "assistant", "content": r["content"] or "",
                         "tool_calls": [{"id": p["id"], "type": "function",
                                         "function": {"name": p["name"], "arguments": p["arguments"]}} for p in parts]})
        messages.extend(tool_msgs)


def server_info(url):
    info = {}
    for path in ("/props", "/v1/models"):
        try:
            with urllib.request.urlopen(urllib.request.Request(url + path, headers=api_headers()), timeout=10) as r:
                info[path] = json.load(r)
        except Exception as e:
            info[path] = f"ERROR {e}"
    p = info.get("/props")
    if isinstance(p, dict):  # 只留重點，避免把整個 chat template 存進每個檔
        info["/props"] = {k: p[k] for k in ("model_path", "build_info", "total_slots", "default_generation_settings",
                                             "modalities") if k in p}
    return info


# ---------------------------------------------------------------- 統計


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def summarize(path):
    recs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    latest = {}   # 同一題重跑時以最後一筆為準；仍然是連線或伺服器錯誤的不列入答對率
    for r in recs:
        if r.get("event") == "answer":
            latest[(r["label"], r["qid"], r["rep"])] = r
    errors = [r for r in latest.values() if r.get("error")]
    recs = [r for r in latest.values() if not r.get("error")]
    if errors:
        print(f"注意：{len(errors)} 筆因伺服器錯誤未完成，未列入統計：", [(r["qid"], r["rep"]) for r in errors][:10])
    by_label = {}
    for r in recs:
        by_label.setdefault(r["label"], []).append(r)
    lines = [f"資料來源：`{path}`（{len(recs)} 筆）。答對率附 Wilson 95% 信賴區間。", ""]
    lines.append("| 條件 | 題數×次數 | 答對率 | 95% CI | 擷取失敗 | 截斷 | 平均思考 chunk | 平均 TTA (s) | 平均總耗時 (s) |")
    lines.append("|---|---:|---:|---|---:|---:|---:|---:|---:|")
    for label, rs in sorted(by_label.items()):
        n = len(rs); k = sum(r["correct"] for r in rs)
        lo, hi = wilson(k, n)
        fail = sum(r["extracted"] is None for r in rs); trunc = sum(r["finish_reason"] == "length" for r in rs)
        mean = lambda xs: sum(xs) / len(xs) if xs else float("nan")
        tta = mean([r["tta_s"] for r in rs if r["tta_s"] is not None])
        lines.append(f"| {label} | {n} | {k / n:.1%} | [{lo:.1%}, {hi:.1%}] | {fail} | {trunc} | "
                     f"{mean([r['n_reasoning_chunks'] for r in rs]):.0f} | {tta:.1f} | {mean([r['total_s'] for r in rs]):.1f} |")
    lines += ["", "各題答對次數（條件 × 題號）：", ""]
    qids = sorted({r["qid"] for r in recs})
    lines.append("| 題號 | " + " | ".join(sorted(by_label)) + " |")
    lines.append("|---|" + "---:|" * len(by_label))
    for qid in qids:
        cells = []
        for label in sorted(by_label):
            rs = [r for r in by_label[label] if r["qid"] == qid]
            cells.append(f"{sum(r['correct'] for r in rs)}/{len(rs)}")
        lines.append(f"| {qid} | " + " | ".join(cells) + " |")
    md = "\n".join(lines) + "\n"
    out = os.path.splitext(path)[0] + "_summary.md"
    open(out, "w", encoding="utf-8").write(md)
    print(md)
    print(f"wrote {out}")


# ---------------------------------------------------------------- 自我測試


REF_CODE = {  # 只用於 --self-test，確認 python_tests 批改流程正確
    "compress": "def compress(s):\n    out=[]\n    i=0\n    while i<len(s):\n        j=i\n        while j<len(s) and s[j]==s[i]: j+=1\n"
                "        out.append(s[i]+(str(j-i) if j-i>1 else ''))\n        i=j\n    r=''.join(out)\n    return r if len(r)<len(s) else s\n",
    "evaluate": "def evaluate(s):\n    t=s.replace(' ','');i=0\n    def num():\n        nonlocal i\n        if t[i]=='-': i+=1; return -num()\n"
                "        if t[i]=='(':\n            i+=1; v=expr(); i+=1; return v\n        j=i\n        while i<len(t) and t[i].isdigit(): i+=1\n        return int(t[j:i])\n"
                "    def term():\n        nonlocal i\n        v=num()\n        while i<len(t) and t[i] in '*/':\n            op=t[i]; i+=1; w=num()\n"
                "            v = v*w if op=='*' else int(v/w)\n        return v\n    def expr():\n        nonlocal i\n        v=term()\n"
                "        while i<len(t) and t[i] in '+-':\n            op=t[i]; i+=1; w=term(); v = v+w if op=='+' else v-w\n        return v\n    return expr()\n",
}
LABEL_FMT = {"length": "長度", "count": "個數", "person": "人", "drink": "飲料", "distance": "距離"}


def fake_response(q):
    g, a = q["grading"], q.get("answer")
    if g == "python_tests":
        return "```python\n" + REF_CODE[q["function"]] + "```"
    if g == "json_fields":
        return "```json\n" + json.dumps(a, ensure_ascii=False) + "\n```"
    if g == "multi_field":
        if "possible" in a:
            body = ("能" if a["possible"] else "不能") + f"，n={a['n']}"
        else:
            labels = {k: LABEL_FMT[k] for k in a}
            if q["id"] == "H6":
                labels["count"] = "條數"
            body = "，".join(f"{labels[k]}={v}" for k, v in a.items())
        return f"推理過程……\n答案：{body}"
    return f"推理過程……\n答案：{a}"


def self_test(questions):
    bad = 0
    for q, _ in questions:
        ok, ext, detail = grade(q, fake_response(q))
        if not ok:
            bad += 1
        print(f"{'OK ' if ok else 'BAD'} {q['id']:10s} {q['grading']:13s} extracted={str(ext)[:60]!s} {detail}")
    # 幾個應該判錯的反例
    neg = [({"id": "neg1", "grading": "exact_int", "answer": 601}, "答案：600"),
           ({"id": "neg2", "grading": "exact_int", "answer": 601}, "我覺得是 601"),
           ({"id": "neg3", "grading": "fraction", "answer": "5/11"}, "答案：5/12")]
    for q, resp in neg:
        ok, _, _ = grade(q, resp)
        print(f"{'OK ' if not ok else 'BAD'} {q['id']} 應判錯 → {'判錯' if not ok else '判對'}")
        bad += ok
    calc_cases = [("987654321*123456789", "121932631112635269"), ("17**23", str(17**23)), ("pow(7,12345,1000003)", str(pow(7, 12345, 1000003))),
                  ("comb(60,25)", str(math.comb(60, 25))), ("1234567*1.0375**17", None), ("10/4", "2.5"), ("2^3", "錯誤"),
                  ("__import__('os')", "錯誤"), ("(1).real", "錯誤"), ("10**10**10", "錯誤"), ("80*log2(1+100)", None)]
    for expr, want in calc_cases:
        got = calculator(expr)
        ok = got.startswith("錯誤") if want == "錯誤" else (want is None and not got.startswith("錯誤")) or got == want
        bad += not ok
        print(f"{'OK ' if ok else 'BAD'} calculator({expr}) = {got[:50]}")
    print("自我測試", "全部通過" if bad == 0 else f"有 {bad} 項失敗")
    return bad == 0


# ---------------------------------------------------------------- 主程式


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8000")
    p.add_argument("--label", help="條件名稱，例如 iq4xs_b16384")
    p.add_argument("--questions", nargs="+", default=["eval/aime_2026.json", "eval/questions.json:hard"])
    p.add_argument("--ids", nargs="*", help="只跑這些題號")
    p.add_argument("--reps", type=int, default=3)
    p.add_argument("--max-tokens", type=int, default=20000)
    p.add_argument("--thinking", choices=["on", "off"], default="on")
    p.add_argument("--timeout", type=int, default=3600, help="單題最長秒數")
    p.add_argument("--out")
    p.add_argument("--note", default="", help="記錄伺服器啟動參數、思考預算等")
    p.add_argument("--summarize", metavar="JSONL")
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--tool", choices=["calculator"], help="讓模型可以呼叫這個工具（E5）")
    p.add_argument("--sandbox-image", help="在此 Docker 映像的隔離容器內執行 python_tests（無網路、唯讀、非 root）")
    a = p.parse_args()

    sys.set_int_max_str_digits(0)   # 計算工具要輸出很長的整數
    if a.summarize:
        return summarize(a.summarize)
    global SANDBOX_IMAGE
    SANDBOX_IMAGE = a.sandbox_image
    questions = load_questions(a.questions)
    if a.self_test:
        sys.exit(0 if self_test(questions) else 1)
    if not (a.label and a.out):
        p.error("送題需要 --label 與 --out")
    if a.ids:
        questions = [(q, t) for q, t in questions if q["id"] in set(a.ids)]

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    done = set()
    if os.path.exists(a.out):
        for l in open(a.out, encoding="utf-8"):
            r = json.loads(l)
            if r.get("event") == "answer" and not r.get("error"):   # 連線或伺服器錯誤不算完成，重跑時會補做
                done.add((r["label"], r["qid"], r["rep"]))
    with open(a.out, "a", encoding="utf-8") as f:
        f.write(json.dumps({"event": "start", "time": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
                            "label": a.label, "args": vars(a), "server": server_info(a.url)}, ensure_ascii=False) + "\n")
    total = len(questions) * a.reps
    i = 0
    consecutive_errors = 0
    for rep in range(1, a.reps + 1):          # 外層是重複次數：每輪把所有題目答一遍，降低溫度漂移對單題的影響
        for q, prompt in questions:
            i += 1
            if (a.label, q["id"], rep) in done:
                continue
            t_start = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
            try:
                if a.tool:
                    resp = ask_with_tools(a.url, prompt, a.max_tokens, a.thinking == "on", rep, a.timeout)
                else:
                    resp = ask(a.url, prompt, a.max_tokens, a.thinking == "on", rep, a.timeout)
                    resp.pop("tool_parts", None)
                ok, ext, detail = grade(q, resp["content"])
                err = None
            except Exception as e:
                resp, ok, ext, detail, err = {}, False, None, "", repr(e)
            rec = {"event": "answer", "label": a.label, "qid": q["id"], "rep": rep, "time": t_start,
                   "grading": q["grading"], "gold": q.get("answer"), "correct": ok, "extracted": ext, "detail": detail,
                   "error": err, "prompt": prompt, **resp}
            with open(a.out, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
            tta = resp.get("tta_s")
            print(f"[{i}/{total}] {a.label} {q['id']} r{rep}: {'✓' if ok else '✗'} "
                  f"ext={str(ext)[:30]} TTA={'-' if tta is None else f'{tta:.1f}s'} total={resp.get('total_s', 0):.1f}s "
                  f"think={resp.get('n_reasoning_chunks')} finish={resp.get('finish_reason')} "
                  f"tools={len(resp.get('tool_calls', []))} {err or ''}", flush=True)
            consecutive_errors = consecutive_errors + 1 if err else 0
            if consecutive_errors >= 3:
                summarize(a.out)
                sys.exit("連續 3 題出錯，伺服器可能已中止；修好後用同樣指令重跑會補做")
    summarize(a.out)


if __name__ == "__main__":
    main()
