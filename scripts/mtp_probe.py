#!/usr/bin/env python3
"""MTP 推測解碼可行性測試：對已啟動的 llama-server 送三類題目，記錄 tg 與草稿接受率。

用法：python3 mtp_probe.py --url http://127.0.0.1:8000 --label mtp_on --out results.jsonl [--reps 2]
同一份題目分別對「MTP 開」與「MTP 關」的伺服器各跑一次，再比較。只用標準函式庫。
"""
import argparse
import datetime
import json
import time
import urllib.request

PROMPTS = {
    "code": "用 Python 寫一個函式 merge_intervals(intervals)，合併重疊的區間並回傳排序後的結果。附上三個測試案例。",
    "math": "一個等差數列的第 3 項是 17、第 10 項是 52。求第 25 項與前 25 項的和，列出計算過程。",
    "chat": "用三段文字向高中生介紹台灣的地形特色，以及它如何影響各地的氣候。",
}


def post(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.load(r)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8000")
    p.add_argument("--label", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--reps", type=int, default=2)
    p.add_argument("--max-tokens", type=int, default=512)
    p.add_argument("--temperature", type=float, default=None, help="不給就用模型內建值；0 = greedy（用來比對 MTP 是否無損）")
    p.add_argument("--thinking", choices=["on", "off"], default="off")
    a = p.parse_args()
    for kind, text in PROMPTS.items():
        for rep in range(1, a.reps + 1):
            t0 = time.time()
            r = post(f"{a.url}/v1/chat/completions", {
                "messages": [{"role": "user", "content": text}],
                "max_tokens": a.max_tokens, "seed": rep, "cache_prompt": False,
                "chat_template_kwargs": {"enable_thinking": a.thinking == "on"},
                **({"temperature": a.temperature} if a.temperature is not None else {})})
            tm = r.get("timings", {})
            rec = {"label": a.label, "kind": kind, "rep": rep,
                   "time": datetime.datetime.now().isoformat(timespec="seconds"),
                   "wall_s": round(time.time() - t0, 2),
                   "completion_tokens": r.get("usage", {}).get("completion_tokens"),
                   "tg_tps": tm.get("predicted_per_second"), "pp_tps": tm.get("prompt_per_second"),
                   "draft_n": tm.get("draft_n"), "draft_n_accepted": tm.get("draft_n_accepted"),
                   "timings_raw": tm,
                   "temperature": a.temperature, "thinking": a.thinking,
                   "content": r["choices"][0]["message"].get("content") or "",
                   "reasoning": r["choices"][0]["message"].get("reasoning_content") or ""}
            if rec["draft_n"]:
                rec["accept_rate"] = round(rec["draft_n_accepted"] / rec["draft_n"], 3)
            with open(a.out, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"{a.label} {kind} r{rep}: tg={rec['tg_tps']:.2f} tok={rec['completion_tokens']} "
                  f"draft={rec['draft_n']} acc={rec['draft_n_accepted']} rate={rec.get('accept_rate')}", flush=True)


if __name__ == "__main__":
    main()
