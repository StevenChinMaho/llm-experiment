#!/usr/bin/env python3
"""期中報告補充圖：E1 生成速度 vs context 深度、E4 校準的每題思考長度與對錯（300 dpi）。

用法：python scripts/plot_midterm_extra.py
輸出：results/figures/e1_tg_vs_depth.png、results/figures/e4_calib_think.png
"""
import csv
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

TEXT, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
QCOLOR = {"UD-IQ2_XXS": "#2a78d6", "UD-Q2_K_XL": "#eb6834", "UD-IQ3_XXS": "#1baf7a", "UD-IQ4_XS": "#eda100"}
plt.rcParams.update({"font.family": ["Microsoft JhengHei", "DejaVu Sans"], "font.size": 10,
                     "axes.edgecolor": MUTED, "axes.labelcolor": TEXT, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.unicode_minus": False})


def depth_figure():
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.0), dpi=300, sharey=True)
    for ax, (path, title) in zip(axes, (("results/processed/e1_main.csv", "(a) RTX 5060 Ti 16GB"),
                                         ("results/processed/e1_svr.csv", "(b) RTX 3060 12GB"))):
        rows = [r for r in csv.DictReader(open(path, encoding="utf-8")) if r["test"] == "tg128" and int(r["ngl"]) >= 99]
        for q, color in QCOLOR.items():
            pts = sorted((int(r["depth"]) / 1024, float(r["tps_mean"])) for r in rows if r["quant"] == q)
            if not pts:
                continue
            xs, ys = zip(*pts)
            ax.plot(xs, ys, color=color, lw=2, marker="o", ms=5, mec="white", mew=1.2, label=q.removeprefix("UD-"))
        ax.set_title(title, loc="left", fontsize=11, color=TEXT)
        ax.set_xlabel("context 深度（K token）"); ax.set_xlim(-1, 34)
        ax.legend(frameon=False, fontsize=8.5, loc="lower left", ncol=2)
        ax.set_xticks([0, 4, 16, 32])
        ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True); ax.set_ylim(0, 45)
    axes[0].set_ylabel("生成速度 tg（tok/s）")
    fig.tight_layout()
    fig.savefig("results/figures/e1_tg_vs_depth.png", dpi=300, facecolor="white")


def calib_figure():
    recs = [json.loads(l) for l in open("results/raw/e4_calib_main_iq4xs_b16384_20261014/results.jsonl", encoding="utf-8")]
    recs = [r for r in recs if r.get("event") == "answer"]
    fig, ax = plt.subplots(figsize=(11, 3.6), dpi=300)
    xs = range(len(recs))
    for i, r in zip(xs, recs):
        ok = r["correct"]
        ax.bar(i, r["n_reasoning_chunks"], width=0.72, color="#2a78d6" if ok else "#eb6834", edgecolor="white", linewidth=1)
        if not ok:
            ax.text(i, r["n_reasoning_chunks"] + 350, "×", ha="center", va="bottom", fontsize=11, color=TEXT, fontweight="bold")
    for y, label in ((16384, "思考預算 16,384"), (4096, "4,096"), (1024, "1,024")):
        ax.axhline(y, color=MUTED, lw=1, ls="--")
        ax.text(-0.5, y + 250, label, ha="left", va="bottom", fontsize=8, color=MUTED)
    ax.axvline(29.5, color=MUTED, lw=0.8)
    ax.text(14.5, 18600, "AIME 2026（30 題）", ha="center", fontsize=9, color=TEXT)
    ax.text(33.5, 18600, "自行設計（8 題）", ha="center", fontsize=9, color=TEXT)
    ax.set_xticks(list(xs))
    ax.set_xticklabels([r["qid"].replace("A26-", "") for r in recs], rotation=90, fontsize=7)
    ax.set_ylabel("思考 token 數"); ax.set_ylim(0, 19800); ax.set_xlim(-0.8, len(recs) - 0.2)
    ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(facecolor="#2a78d6", label="答對"), Patch(facecolor="#eb6834", label="答錯（×）")],
              frameon=False, fontsize=8.5, loc="upper left", bbox_to_anchor=(0.0, 1.16), ncol=2)
    fig.tight_layout()
    fig.savefig("results/figures/e4_calib_think.png", dpi=300, facecolor="white")


if __name__ == "__main__":
    depth_figure()
    calib_figure()
    print("wrote results/figures/e1_tg_vs_depth.png, e4_calib_think.png")
