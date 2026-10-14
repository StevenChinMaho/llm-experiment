#!/usr/bin/env python3
"""E1 圖：(a) 權重大小 vs tg（深度 0，兩張 GPU）；(b) 部分卸載的 GPU 層數 vs tg。

用法：python scripts/plot_e1.py results/processed/e1_svr.csv results/processed/e1_main.csv
輸出：results/figures/e1_tg_vs_size.png（300 dpi）
"""
import csv
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# 參考色盤 categorical 前兩格（淺色），已驗證
COLOR = {"RTX 3060": "#2a78d6", "RTX 5060 Ti": "#eb6834"}
TEXT, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def load(paths):
    rows = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            rows += list(csv.DictReader(f))
    for r in rows:
        r["gpu"] = r["gpu"].replace("NVIDIA GeForce ", "")
        r["ngl"] = int(r["ngl"]); r["depth"] = int(r["depth"]); r["tps"] = float(r["tps_mean"])
        r["gib"] = int(r["model_bytes"]) / 2**30
    return rows


def main():
    rows = [r for r in load(sys.argv[1:]) if r["test"] == "tg128" and r["depth"] == 0]
    plt.rcParams.update({"font.family": ["Microsoft JhengHei", "DejaVu Sans"], "font.size": 10,
                         "axes.edgecolor": MUTED, "axes.labelcolor": TEXT, "xtick.color": MUTED, "ytick.color": MUTED,
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 4.4), dpi=300)

    for gpu, color in COLOR.items():
        full = sorted([r for r in rows if r["gpu"] == gpu and r["ngl"] >= 99], key=lambda r: r["gib"])
        part = [r for r in rows if r["gpu"] == gpu and r["ngl"] < 99]
        best = max(part, key=lambda r: r["ngl"]) if part else None
        a.plot([r["gib"] for r in full], [r["tps"] for r in full], color=color, lw=2, marker="o", ms=6,
               mec="white", mew=1.2, label=f"{gpu}：全部放進 GPU")
        for r in full:
            a.annotate(r["quant"].removeprefix("UD-"), (r["gib"], r["tps"]), xytext=(0, 8), textcoords="offset points",
                       ha="center", fontsize=7.5, color=MUTED)
        if best:
            a.plot([full[-1]["gib"], best["gib"]], [full[-1]["tps"], best["tps"]], color=color, lw=1.5, ls="--")
            a.plot([best["gib"]], [best["tps"]], marker="o", ms=7, mfc="white", mec=color, mew=2,
                   label=f"{gpu}：部分卸載（{best['ngl']} 層在 GPU）")
            a.annotate(f"{best['quant'].removeprefix('UD-')}\n{best['tps']:.1f}", (best["gib"], best["tps"]),
                       xytext=(8, -4), textcoords="offset points", fontsize=7.5, color=TEXT)
        pts = sorted(part, key=lambda r: r["ngl"])
        if pts:
            b.plot([r["ngl"] for r in pts], [r["tps"] for r in pts], color=color, lw=2, marker="o", ms=6,
                   mec="white", mew=1.2, label=f"{gpu}（{pts[0]['quant'].removeprefix('UD-')}）")
            b.annotate(f"{pts[-1]['tps']:.1f}", (pts[-1]["ngl"], pts[-1]["tps"]), xytext=(6, 0),
                       textcoords="offset points", va="center", fontsize=8, color=TEXT)

    a.set_title("(a) 權重大小與生成速度（context 深度 0）", loc="left", fontsize=11, color=TEXT)
    a.set_xlabel("模型檔大小（GiB）"); a.set_ylabel("生成速度 tg（tok/s）")
    b.set_title("(b) 部分卸載：放在 GPU 的層數與生成速度", loc="left", fontsize=11, color=TEXT)
    b.set_xlabel("GPU 上的層數（共 66 層）"); b.set_ylabel("生成速度 tg（tok/s）")
    for ax in (a, b):
        ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
    a.set_ylim(0, 46)                                     # 留空間給最上面的標籤
    a.legend(frameon=False, fontsize=8.5, loc="upper right")
    b.set_ylim(0, 20)
    b.set_xlim(42, 65)
    b.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(4))
    b.legend(frameon=False, fontsize=8.5, loc="lower right")
    fig.suptitle("E1 速度：Qwen3.8-27B，llama.cpp b11347，llama-bench（每點 5 次，部分卸載 3 次）",
                 fontsize=11.5, color=TEXT, x=0.01, ha="left")
    fig.tight_layout()
    out = "results/figures/e1_tg_vs_size.png"
    fig.savefig(out, dpi=300, facecolor="white")
    print("wrote", out)


if __name__ == "__main__":
    main()
