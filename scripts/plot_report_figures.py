#!/usr/bin/env python3
"""期中報告的示意圖：圖 1 研究架構、圖 5 執行進度甘特圖（300 dpi，繁體中文）。

用法：python scripts/plot_report_figures.py
輸出：results/figures/fig_architecture.png、results/figures/fig_gantt.png
"""
import datetime as dt

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

TEXT, MUTED, LINE = "#0b0b0b", "#52514e", "#9a9893"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"   # 參考色盤前三格（已驗證）
FILL = {"blue": "#e6eefa", "orange": "#fdebe2", "aqua": "#e2f5ee", "gray": "#f1f0ed"}
plt.rcParams.update({"font.family": ["Microsoft JhengHei", "DejaVu Sans"], "font.size": 10,
                     "axes.unicode_minus": False})


def box(ax, x, y, w, h, title, lines, edge, fill):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02",
                                linewidth=1.4, edgecolor=edge, facecolor=fill))
    ax.text(x + w / 2, y + h - 0.035, title, ha="center", va="top", fontsize=11, fontweight="bold", color=TEXT)
    ax.text(x + w / 2, y + h - 0.085, "\n".join(lines), ha="center", va="top", fontsize=8.8, color=TEXT,
            linespacing=1.45)


def arrow(ax, x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=14, color=LINE, lw=1.4))


def architecture():
    fig, ax = plt.subplots(figsize=(10, 6.2), dpi=300)
    ax.set_xlim(0, 1); ax.set_ylim(-0.03, 1.0); ax.axis("off")
    box(ax, 0.22, 0.82, 0.56, 0.16, "部署：兩台消費級顯示卡，只差在硬體",
        ["RTX 3060 12GB ／ RTX 5060 Ti 16GB", "同驅動版本、同推論引擎映像 digest、同模型檔 SHA-256"], LINE, FILL["gray"])
    cols = [
        (0.02, "資源成本（兩台都量）", ["E1 速度：生成／讀取 prompt、", "context 深度、部分卸載", "E2 記憶體：最大 context、", "記憶體模型與預測驗證"],
         BLUE, FILL["blue"], "RQ1、RQ2"),
        (0.35, "品質代價（與硬體無關）", ["E3 KL 散度與困惑度", "（WikiText-2，基準 Q8_0）", "E4 任務答對率", "（量化 × 思考預算）"],
         ORANGE, FILL["orange"], "RQ1、RQ3"),
        (0.68, "加速與工具", ["MTP 推測解碼：", "加速倍數與 VRAM 代價", "E5 計算工具：", "修正大數運算錯誤"],
         AQUA, FILL["aqua"], "RQ2、RQ4"),
    ]
    for x, title, lines, edge, fill, rq in cols:
        box(ax, x, 0.42, 0.30, 0.30, title, lines, edge, fill)
        ax.text(x + 0.15, 0.44, rq, ha="center", va="bottom", fontsize=8.5, color=MUTED)
        arrow(ax, 0.5, 0.82, x + 0.15, 0.725)
        arrow(ax, x + 0.15, 0.42, 0.5, 0.33)
    box(ax, 0.20, 0.18, 0.60, 0.15, "權衡分析",
        ["品質 × 速度 × 記憶體的 Pareto 前緣；相同等待時間下的答對率"], LINE, FILL["gray"])
    arrow(ax, 0.5, 0.18, 0.5, 0.135)
    box(ax, 0.20, 0.0, 0.60, 0.13, "部署建議",
        ["12GB／16GB × 任務類型：量化等級、context 長度、MTP 設定"], LINE, FILL["gray"])
    fig.tight_layout()
    fig.savefig("results/figures/fig_architecture.png", dpi=300, facecolor="white")


def gantt():
    D = dt.date
    tasks = [  # (名稱, 開始, 結束, 已完成)
        ("統一兩台機器的執行環境", D(2026, 10, 12), D(2026, 10, 13), True),
        ("E1 速度、E2 記憶體", D(2026, 10, 13), D(2026, 10, 14), True),
        ("E3 品質、MTP 量測、E4 校準", D(2026, 10, 14), D(2026, 10, 14), True),
        ("期中計畫書撰寫與排版", D(2026, 10, 15), D(2026, 11, 6), False),
        ("E4 正式實驗（約 30 小時）", D(2026, 11, 9), D(2026, 12, 6), False),
        ("5060 Ti 上的 MTP 掃描", D(2026, 11, 9), D(2026, 11, 20), False),
        ("E5 計算工具", D(2026, 12, 7), D(2026, 12, 13), False),
        ("權衡分析與期末報告", D(2026, 12, 14), D(2026, 12, 31), False),
    ]
    fig, ax = plt.subplots(figsize=(10, 3.9), dpi=300)
    for i, (name, s, e, done) in enumerate(tasks):
        y = len(tasks) - 1 - i
        left = mdates.date2num(s); width = mdates.date2num(e + dt.timedelta(days=1)) - left
        ax.barh(y, width, left=left, height=0.55, color=MUTED if done else BLUE, edgecolor="white", linewidth=1.5)
    for d, label in ((D(2026, 11, 7), "期中繳交\n11/07"), (D(2027, 1, 2), "期末繳交\n01/02")):
        x = mdates.date2num(d)
        ax.axvline(x, color=ORANGE, lw=1.5, ls="--")
        ax.text(x, len(tasks) - 0.35, label, ha="center", va="bottom", fontsize=8.5, color=TEXT)
    # 任務名稱固定放在左側一欄，避免和長條、截止線重疊
    ax.set_yticks(range(len(tasks))); ax.set_yticklabels([t[0] for t in reversed(tasks)], fontsize=9, color=TEXT)
    ax.tick_params(axis="y", length=0)
    ax.set_ylim(-0.6, len(tasks) + 0.4)
    ax.set_xlim(mdates.date2num(D(2026, 10, 5)), mdates.date2num(D(2027, 1, 8)))
    ax.xaxis.set_major_locator(mdates.MonthLocator()); ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y/%m"))
    ax.tick_params(axis="x", colors=MUTED, labelsize=9)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(MUTED)
    ax.grid(axis="x", color="#e4e3df", lw=0.8); ax.set_axisbelow(True)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(facecolor=MUTED, label="已完成"), Patch(facecolor=BLUE, label="預定")], frameon=False,
              fontsize=9, loc="lower left", bbox_to_anchor=(0.0, 1.0), ncol=2)
    fig.tight_layout()
    fig.savefig("results/figures/fig_gantt.png", dpi=300, facecolor="white")


if __name__ == "__main__":
    architecture()
    gantt()
    print("wrote results/figures/fig_architecture.png, fig_gantt.png")
