#!/usr/bin/env python3
"""整理 E2（記憶體）結果：KV 公式驗證表、運算暫存隨 context 的變化、各量化的最大 context。

用法：python scripts/analyze_e2.py <輸出名稱> <run 資料夾> [<run 資料夾> ...]
輸出：results/processed/<輸出名稱>.csv/.md
"""
import json
import os
import sys

KIB_PER_TOKEN_KV = 34  # findings §3


def main():
    name, dirs = sys.argv[1], sys.argv[2:]
    recs, maxes = [], {}
    for d in dirs:
        for l in open(os.path.join(d, "results.jsonl"), encoding="utf-8"):
            r = json.loads(l)
            if r.get("event") == "max_ctx":
                maxes[r["model"]] = r
            elif r.get("ok") and r.get("event") in ("fixed", "search"):
                r["_dir"] = os.path.basename(d)
                recs.append(r)
    # 同一個（模型, n_ctx）只留一筆
    uniq = {}
    for r in recs:
        uniq.setdefault((r["model"], r["n_ctx"]), r)
    rows = sorted(uniq.values(), key=lambda r: (r["model"], r["n_ctx"]))

    lines = [f"資料來源：{', '.join('`results/raw/' + os.path.basename(d) + '/`' for d in dirs)}。"
             "llama-server b11347、-fit off、-fa on、KV q8_0、-np 1。單位 MiB。KV 公式值為推導值。", ""]
    lines.append("### KV cache：實測 vs 公式（每 token 34 KiB）")
    lines.append("")
    lines.append("| 量化 | n_ctx | 權重 (CUDA0) | KV 實測 | KV 公式 | 誤差 | 遞迴狀態 | 運算暫存 | 四項加總 | nvidia-smi |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        q = r["model"].removeprefix("Qwen3.8-27B-").removesuffix(".gguf")
        lines.append(f"| {q} | {r['n_ctx']} | {r['cuda_model_mib']} | {r['kv_mib']} | {r['kv_formula_mib']} | "
                     f"{r['kv_err_mib']} | {r['rs_mib']} | {r['cuda_compute_mib']} | {r['cuda_sum_mib']} | {r['smi_used_mib']} |")
    errs = [abs(r["kv_err_mib"]) for r in rows if r["kv_err_mib"] is not None]
    lines += ["", f"KV 公式最大絕對誤差：{max(errs):.2f} MiB（{len(errs)} 個點）。", ""]

    # 運算暫存：n_ctx ≥ 16384 時以 a + b·n_ctx 擬合（最小平方法，推導值）
    pts = sorted({(r["n_ctx"], r["cuda_compute_mib"]) for r in rows if r["n_ctx"] >= 16384})
    n = len(pts)
    if n >= 2:
        mx = sum(x for x, _ in pts) / n; my = sum(y for _, y in pts) / n
        b = sum((x - mx) * (y - my) for x, y in pts) / sum((x - mx) ** 2 for x, _ in pts)
        a = my - b * mx
        resid = max(abs(y - (a + b * x)) for x, y in pts)
        lines.append("### 運算暫存（CUDA0 compute buffer）與 context 的關係")
        lines.append("")
        lines.append(f"n_ctx ≥ 16384 的 {n} 個點擬合：compute ≈ {a:.2f} MiB ＋ {b * 1024:.3f} KiB × n_ctx"
                     f"（最大殘差 {resid:.2f} MiB）。n_ctx = 4096 時為 126.28 MiB，高於直線，推測有最低配置量。")
        lines.append(f"→ 每多 1 個 token 的 VRAM 成本 ≈ KV {KIB_PER_TOKEN_KV} KiB ＋ 運算暫存 {b * 1024:.1f} KiB ＝ "
                     f"{KIB_PER_TOKEN_KV + b * 1024:.1f} KiB（推導值）")
        lines.append("")

    lines.append("### 全 GPU 時的最大 context（二分搜尋，解析度 1024）")
    lines.append("")
    lines.append("| 量化 | 可啟動的最大 -c | 失敗的最小 -c | 最大時 nvidia-smi (MiB) |")
    lines.append("|---|---:|---:|---:|")
    for m, r in sorted(maxes.items()):
        best = uniq.get((m, r["max_ok"]))
        lines.append(f"| {m.removeprefix('Qwen3.8-27B-').removesuffix('.gguf')} | {r['max_ok']} | {r['min_fail']} | "
                     f"{best['smi_used_mib'] if best else ''} |")
    md = "\n".join(lines) + "\n"
    os.makedirs("results/processed", exist_ok=True)
    open(f"results/processed/{name}.md", "w", encoding="utf-8").write(md)
    import csv
    with open(f"results/processed/{name}.csv", "w", newline="", encoding="utf-8") as f:
        keys = ["model", "n_ctx", "cuda_model_mib", "cpu_mapped_mib", "kv_mib", "kv_formula_mib", "kv_err_mib", "rs_mib",
                "cuda_compute_mib", "host_compute_mib", "cuda_sum_mib", "smi_used_mib", "offloaded", "_dir"]
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
    print(md)


if __name__ == "__main__":
    main()
