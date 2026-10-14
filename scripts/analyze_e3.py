#!/usr/bin/env python3
"""整理 E3（llama-perplexity KL 散度）結果：表格＋品質與速度的權衡圖。

用法：python scripts/analyze_e3.py
讀取 results/raw/e3_main_*_20261014/perplexity.log 與 results/processed/e1_{svr,main}.csv
輸出：results/processed/e3_main.csv/.md、results/figures/e3_quality_speed.png
"""
import csv
import glob
import os
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

PAT = {
    "ppl_q": r"Mean PPL\(Q\)\s*:\s*([\d.]+)\s*±\s*([\d.]+)",
    "ppl_base": r"Mean PPL\(base\)\s*:\s*([\d.]+)\s*±\s*([\d.]+)",
    "ppl_ratio": r"Mean PPL\(Q\)/PPL\(base\)\s*:\s*([\d.]+)\s*±\s*([\d.]+)",
    "kld_mean": r"Mean\s+KLD:\s*([\d.]+)\s*±\s*([\d.]+)",
    "kld_99": r"99\.0%\s+KLD:\s*([\d.]+)",
    "kld_median": r"Median\s+KLD:\s*([\d.]+)",
    "same_top_p": r"Same top p:\s*([\d.]+)\s*±\s*([\d.]+)",
    "rms_dp": r"RMS Δp\s*:\s*([\d.]+)\s*±\s*([\d.]+)",
}
COLOR = {"RTX 3060": "#2a78d6", "RTX 5060 Ti": "#eb6834"}
TEXT, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def parse(path):
    t = open(path, encoding="utf-8", errors="replace").read()
    out = {}
    for k, p in PAT.items():
        m = re.search(p, t)
        out[k] = tuple(float(x) for x in m.groups()) if m else None
    return out


def main():
    rows = []
    for d in sorted(glob.glob("results/raw/e3_main_UD-*_20261014")):
        q = re.search(r"e3_main_(UD-[^_]+(?:_[A-Z]+)*)_2026", d).group(1)
        r = parse(os.path.join(d, "perplexity.log"))
        rows.append({"quant": q, "ppl": r["ppl_q"][0], "ppl_err": r["ppl_q"][1], "ppl_ratio": r["ppl_ratio"][0],
                     "kld_mean": r["kld_mean"][0], "kld_err": r["kld_mean"][1], "kld_median": r["kld_median"][0],
                     "kld_p99": r["kld_99"][0], "same_top_p": r["same_top_p"][0], "same_top_p_err": r["same_top_p"][1],
                     "rms_dp": r["rms_dp"][0], "source": d})
    base = parse("results/raw/e3_main_UD-IQ3_XXS_20261014/perplexity.log")["ppl_base"]
    base_final = re.search(r"Final estimate: PPL = ([\d.]+) \+/- ([\d.]+)",
                           open("results/raw/e3_main_q8base_20261014/perplexity.log", encoding="utf-8").read())
    order = ["UD-IQ2_XXS", "UD-Q2_K_XL", "UD-IQ3_XXS", "UD-IQ4_XS", "UD-Q4_K_XL"]
    rows.sort(key=lambda r: order.index(r["quant"]))

    os.makedirs("results/processed", exist_ok=True)
    with open("results/processed/e3_main.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    with open("results/processed/e3_main.md", "w", encoding="utf-8") as f:
        f.write("資料來源：`results/raw/e3_main_*_20261014/perplexity.log`。WikiText-2 raw 測試集，297,193 token，"
                "145 個 chunk，-c 2048；基準為 Q8_0（")
        f.write(f"基準跑的 Final estimate PPL = {base_final.group(1)} ± {base_final.group(2)}；"
                f"KLD 模式中重算的 Mean PPL(base) = {base[0]} ± {base[1]}）。\n\n")
        f.write("| 量化 | 困惑度 | PPL(Q)/PPL(base) | 平均 KLD | KLD 中位數 | KLD 99% | Same top p | RMS Δp |\n")
        f.write("|---|---:|---:|---:|---:|---:|---:|---:|\n")
        for r in rows:
            f.write(f"| {r['quant']} | {r['ppl']:.4f} ± {r['ppl_err']:.4f} | {r['ppl_ratio']:.4f} | "
                    f"{r['kld_mean']:.6f} ± {r['kld_err']:.6f} | {r['kld_median']:.6f} | {r['kld_p99']:.4f} | "
                    f"{r['same_top_p']:.3f}% | {r['rms_dp']:.3f}% |\n")

    # 品質（KLD，對數軸）vs 速度（tg @ 深度 0）
    speed = {}
    for p in ("results/processed/e1_svr.csv", "results/processed/e1_main.csv"):
        for r in csv.DictReader(open(p, encoding="utf-8")):
            if r["test"] == "tg128" and r["depth"] == "0":
                gpu = r["gpu"].replace("NVIDIA GeForce ", "")
                key = (gpu, r["quant"])
                if int(r["ngl"]) >= speed.get(key, (-1, 0))[0]:
                    speed[key] = (int(r["ngl"]), float(r["tps_mean"]))
    plt.rcParams.update({"font.family": ["Microsoft JhengHei", "DejaVu Sans"], "font.size": 10,
                         "axes.edgecolor": MUTED, "axes.labelcolor": TEXT, "xtick.color": MUTED, "ytick.color": MUTED,
                         "axes.spines.top": False, "axes.spines.right": False, "axes.unicode_minus": False})
    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 4.6), dpi=300)
    sizes = {"UD-IQ2_XXS": 6.77, "UD-Q2_K_XL": 9.15, "UD-IQ3_XXS": 10.18, "UD-IQ4_XS": 13.27, "UD-Q4_K_XL": 16.35}
    a.plot([sizes[r["quant"]] for r in rows], [r["kld_mean"] for r in rows], color=MUTED, lw=2, marker="o", ms=6,
           mec="white", mew=1.2, label="平均 KL 散度（左軸）")
    for r in rows:
        a.annotate(f"{r['quant'].removeprefix('UD-')}\n{r['kld_mean']:.3f}", (sizes[r["quant"]], r["kld_mean"]),
                   xytext=(6, 4), textcoords="offset points", fontsize=7.5, color=TEXT)
    a.set_yscale("log"); a.set_xlabel("模型檔大小（GiB）"); a.set_ylabel("平均 KL 散度（對 Q8_0，對數軸）")
    a.set_title("(a) 權重越小，與原模型的差距越大", loc="left", fontsize=11, color=TEXT)
    a.grid(axis="y", color=GRID, lw=0.8, which="both"); a.set_axisbelow(True)
    a.set_xlim(5.5, 18.5)
    a.set_ylim(0.009, 0.45)                               # 上方留空間給 IQ2_XXS 的標籤

    kld = {r["quant"]: r["kld_mean"] for r in rows}
    for gpu, color in COLOR.items():
        pts = [(kld[q], speed[(gpu, q)][1], q, speed[(gpu, q)][0]) for q in order if (gpu, q) in speed]
        full = [p for p in pts if p[3] >= 99]
        part = [p for p in pts if p[3] < 99]
        b.plot([p[0] for p in full], [p[1] for p in full], color=color, lw=2, marker="o", ms=6, mec="white", mew=1.2,
               label=f"{gpu}：全部放進 GPU")
        for p in part:
            b.plot([full[-1][0], p[0]], [full[-1][1], p[1]], color=color, lw=1.5, ls="--")
            b.plot([p[0]], [p[1]], marker="o", ms=7, mfc="white", mec=color, mew=2, ls="none",
                   label=f"{gpu}：部分卸載（{p[3]} 層）")
        for p in pts:
            b.annotate(p[2].removeprefix("UD-"), (p[0], p[1]), xytext=(5, 5), textcoords="offset points",
                       fontsize=7.5, color=MUTED)
    b.set_xscale("log"); b.invert_xaxis()
    b.set_xlabel("平均 KL 散度（對數軸，越往右品質越好）"); b.set_ylabel("生成速度 tg（tok/s，深度 0）")
    b.set_title("(b) 品質與速度的取捨（右上方較佳）", loc="left", fontsize=11, color=TEXT)
    b.set_ylim(0, 46); b.grid(axis="y", color=GRID, lw=0.8); b.set_axisbelow(True)
    b.legend(frameon=False, fontsize=8, loc="lower left")
    # 對數軸改用一般小數標示（字型沒有上標負號，10^-1 會顯示成亂碼）
    ticks = [0.01, 0.02, 0.05, 0.1, 0.2]
    for ax, axis in ((a, a.yaxis), (b, b.xaxis)):
        axis.set_major_locator(matplotlib.ticker.FixedLocator(ticks))
        axis.set_major_formatter(matplotlib.ticker.FixedFormatter([str(t) for t in ticks]))
        axis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    fig.suptitle("E3 品質 × E1 速度：Qwen3.8-27B，WikiText-2（145 chunk，c=2048），基準 Q8_0，llama.cpp b11347",
                 fontsize=11.5, color=TEXT, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig("results/figures/e3_quality_speed.png", dpi=300, facecolor="white")
    print(open("results/processed/e3_main.md", encoding="utf-8").read())
    print("wrote results/processed/e3_main.csv/.md, results/figures/e3_quality_speed.png")


if __name__ == "__main__":
    main()
