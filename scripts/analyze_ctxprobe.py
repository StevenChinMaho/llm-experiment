#!/usr/bin/env python3
"""整理 ctx_depth_probe.py 的輸出：表格（CSV＋Markdown）與圖（PNG 300 dpi）。

用法：python scripts/analyze_ctxprobe.py results/raw/ctxprobe_win_iq4xs_20261012
輸出：results/processed/<資料夾名>.csv、.md；results/figures/<資料夾名>.png
"""
import csv
import datetime as dt
import json
import os
import statistics
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# 參考色盤 categorical 前三格（淺色模式；文件註明前三格 all-pairs 通過驗證）
COLORS = {49152: "#2a78d6", 65536: "#eb6834", 83536: "#1baf7a"}
TEXT, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def load(raw):
    rows = [json.loads(l) for l in open(os.path.join(raw, "results.jsonl"), encoding="utf-8")]
    gpu = []
    for r in csv.reader(open(os.path.join(raw, "gpu_log.csv"), encoding="utf-8")):
        try:
            gpu.append((dt.datetime.strptime(r[0].strip(), "%Y/%m/%d %H:%M:%S.%f"),
                        float(r[2].split()[0])))
        except (ValueError, IndexError):
            pass
    return rows, gpu


def prefill_power(r, gpu):
    """該次量測 prefill 階段（扣掉生成時間）的平均功耗；樣本不足 3 秒回傳 None。"""
    end = dt.datetime.fromisoformat(r["time"])
    start = end - dt.timedelta(seconds=r["wall_s"])
    pp_end = end - dt.timedelta(seconds=r["predicted_n"] / r["tg_tps"])
    xs = [p for t, p in gpu if start + dt.timedelta(seconds=1) <= t <= pp_end - dt.timedelta(seconds=1)]
    return statistics.mean(xs) if len(xs) >= 3 else None


def main():
    raw = sys.argv[1].rstrip("/\\")
    name = os.path.basename(raw)
    rows, gpu = load(raw)
    loaded = {r["ctx"]: r for r in rows if r.get("event") == "loaded"}
    groups = {}
    for r in rows:
        if r.get("event") == "measure":
            groups.setdefault((r["ctx"], r["depth"]), []).append(r)

    table = []
    for (ctx, depth), rs in sorted(groups.items()):
        sd = lambda xs: statistics.stdev(xs) if len(xs) > 1 else 0.0
        pp = [r["pp_tps"] for r in rs]
        tg = [r["tg_tps"] for r in rs]
        pw = [p for p in (prefill_power(r, gpu) for r in rs) if p is not None]
        table.append({
            "ctx": ctx, "n_ctx": rs[0]["n_ctx"], "depth": depth, "n": len(rs),
            "pp_mean": round(statistics.mean(pp), 1), "pp_sd": round(sd(pp), 1),
            "tg_mean": round(statistics.mean(tg), 2), "tg_sd": round(sd(tg), 2),
            "prefill_power_w": round(statistics.mean(pw), 1) if pw else "",
            "dedicated_mib": loaded[ctx].get("dedicated_mib"), "shared_mib": loaded[ctx].get("shared_mib"),
        })

    os.makedirs("results/processed", exist_ok=True)
    os.makedirs("results/figures", exist_ok=True)
    with open(f"results/processed/{name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(table[0]))
        w.writeheader()
        w.writerows(table)
    with open(f"results/processed/{name}.md", "w", encoding="utf-8") as f:
        f.write(f"資料來源：`results/raw/{name}/`（每點 {table[0]['n']} 次，平均 ± 標準差；"
                "prefill 功耗為 nvidia-smi 每秒取樣於 prefill 期間的平均，空白＝prefill 不足 3 秒）\n\n")
        f.write("| -c | 深度 | pp (tok/s) | tg (tok/s) | prefill 功耗 (W) | 專用 VRAM (MiB) | 共享 (MiB) |\n")
        f.write("|---:|---:|---:|---:|---:|---:|---:|\n")
        for t in table:
            f.write(f"| {t['ctx']} | {t['depth']} | {t['pp_mean']} ± {t['pp_sd']} | {t['tg_mean']} ± {t['tg_sd']} "
                    f"| {t['prefill_power_w']} | {t['dedicated_mib']} | {t['shared_mib']} |\n")

    plt.rcParams.update({"font.family": ["Microsoft JhengHei", "DejaVu Sans"], "font.size": 10,
                         "axes.edgecolor": MUTED, "axes.labelcolor": TEXT, "xtick.color": MUTED,
                         "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2), dpi=300)
    panels = [("pp_mean", "讀 prompt 速度 pp（tok/s）", "(a) Prefill"),
              ("tg_mean", "生成速度 tg（tok/s）", "(b) 生成"),
              ("prefill_power_w", "prefill 期間 GPU 功耗（W）", "(c) Prefill 功耗")]
    for ax, (key, ylabel, title) in zip(axes, panels):
        for ctx, color in COLORS.items():
            pts = [(t["depth"] / 1000, t[key]) for t in table if t["ctx"] == ctx and t[key] != ""]
            if not pts:
                continue
            xs, ys = zip(*pts)
            shr = loaded[ctx].get("shared_mib")
            ax.plot(xs, ys, color=color, lw=2, marker="o", ms=5, mec="white", mew=1.2,
                    label=f"-c {ctx}（共享 {shr:.0f} MiB）")
            # 49152 與 65536 幾乎重疊，只在 65536（較長）的線尾合併標示；83536 在 (b) 也與其他重疊
            if ctx == 65536 and key != "tg_mean":
                ax.annotate("-c 49152／65536", (xs[-1], ys[-1]), xytext=(0, 9), textcoords="offset points",
                            ha="center", fontsize=8.5, color=TEXT)
            elif ctx == 83536 and key != "tg_mean":
                ax.annotate("-c 83536", (xs[-1], ys[-1]), xytext=(0, 9), textcoords="offset points",
                            ha="center", fontsize=8.5, color=TEXT)
        if key == "tg_mean":
            ax.text(0.97, 0.93, "三種 -c 在同深度幾乎重疊", transform=ax.transAxes, ha="right",
                    fontsize=8.5, color=MUTED)
        ax.set_title(title, loc="left", fontsize=11, color=TEXT)
        ax.set_xlabel("context 深度（千 token）")
        ax.set_ylabel(ylabel)
        ax.set_ylim(bottom=0)
        ax.set_xlim(0, 92)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
    axes[0].legend(frameon=False, fontsize=8.5, loc="upper right")
    fig.suptitle("RTX 5060 Ti 16GB／Windows：context 大小超出 VRAM 時，prefill 變慢、生成不受影響"
                 "（Qwen3.8-27B UD-IQ4_XS，llama.cpp b10751）", fontsize=11.5, color=TEXT, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(f"results/figures/{name}.png", dpi=300, facecolor="white")
    print(f"wrote results/processed/{name}.csv/.md, results/figures/{name}.png")


if __name__ == "__main__":
    main()
