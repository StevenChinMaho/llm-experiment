#!/usr/bin/env python3
"""整理 MTP 掃描結果（scripts/run_mtp.sh 的輸出）：速度、接受率、VRAM、遞迴狀態、greedy 是否逐字相同。

用法：python scripts/analyze_mtp.py <輸出名稱> <run 資料夾> [...]
輸出：results/processed/<輸出名稱>.md
"""
import json
import os
import re
import statistics
import sys


def main():
    name, dirs = sys.argv[1], sys.argv[2:]
    recs, rs, vram = [], {}, {}
    for d in dirs:
        p = os.path.join(d, "results.jsonl")
        if os.path.exists(p):
            recs += [dict(json.loads(l), _dir=os.path.basename(d)) for l in open(p, encoding="utf-8")]
        log = open(os.path.join(d, "run.log"), encoding="utf-8").read()
        for m in re.finditer(r"(mtp_\w+?) 就緒：nvidia-smi (\d+) MiB", log):
            vram.setdefault(m.group(1), int(m.group(2)))
        for f in os.listdir(d):
            m = re.fullmatch(r"server_(mtp_\w+)\.log", f)
            if m:
                t = open(os.path.join(d, f), encoding="utf-8", errors="replace").read()
                r = re.search(r"CUDA0 RS buffer size =\s+([\d.]+) MiB", t)
                if r:
                    rs.setdefault(m.group(1), float(r.group(1)))
    labels = ["mtp_off"] + sorted({r["label"] for r in recs if re.fullmatch(r"mtp_n\d+", r["label"])},
                                  key=lambda s: int(s[5:]))
    base_tg = {}
    lines = [f"資料來源：{', '.join('`results/raw/' + os.path.basename(d) + '/`' for d in dirs)}。"
             "關閉思考、max_tokens 512；一般取樣每類 2 次＋greedy（temperature 0）1 次。tg 為兩次一般取樣的平均。", ""]
    lines.append("| 條件 | 遞迴狀態 (MiB) | 啟動後 VRAM (MiB) | tg 程式碼 | tg 數學 | tg 中文問答 | 接受率 程式碼 | 接受率 數學 | 接受率 中文問答 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for lb in labels:
        cells = []
        for kind in ("code", "math", "chat"):
            xs = [r for r in recs if r["label"] == lb and r["kind"] == kind]
            tg = statistics.mean(r["tg_tps"] for r in xs) if xs else None
            if lb == "mtp_off" and tg:
                base_tg.setdefault(kind, tg)
            sp = f" (×{tg / base_tg[kind]:.2f})" if tg and kind in base_tg and lb != "mtp_off" else ""
            cells.append(f"{tg:.2f}{sp}" if tg else "—")
        acc = []
        for kind in ("code", "math", "chat"):
            xs = [r for r in recs if r["label"] == lb and r["kind"] == kind and r.get("draft_n")]
            acc.append(f"{sum(r['draft_n_accepted'] for r in xs) / sum(r['draft_n'] for r in xs):.3f}" if xs else "—")
        lines.append(f"| {lb} | {rs.get(lb, '')} | {vram.get(lb, '')} | " + " | ".join(cells + acc) + " |")

    lines += ["", "**greedy 輸出與 mtp_off 是否逐字相同：**", ""]
    g = {}
    for r in recs:
        if r["label"].endswith("_greedy"):
            g.setdefault((r["label"], r["kind"]), r["content"])
    lines.append("| 條件 | 程式碼 | 數學 | 中文問答 |")
    lines.append("|---|---|---|---|")
    for lb in labels[1:]:
        cells = []
        for kind in ("code", "math", "chat"):
            a, b = g.get(("mtp_off_greedy", kind)), g.get((f"{lb}_greedy", kind))
            if a is None or b is None:
                cells.append("—")
            elif a == b:
                cells.append("相同")
            else:
                i = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
                cells.append(f"第 {i} 字起不同")
        lines.append(f"| {lb} | " + " | ".join(cells) + " |")
    md = "\n".join(lines) + "\n"
    os.makedirs("results/processed", exist_ok=True)
    open(f"results/processed/{name}.md", "w", encoding="utf-8", newline="\n").write(md)
    print(md)


if __name__ == "__main__":
    main()
