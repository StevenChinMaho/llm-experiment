#!/usr/bin/env python3
"""整理 E1（llama-bench）結果：表格（CSV＋Markdown），含衍生指標。

用法：python scripts/analyze_e1.py <輸出名稱> <run 資料夾> [<run 資料夾> ...]
例：  python scripts/analyze_e1.py e1_svr results/raw/e1_svr_20261013-1537 results/raw/e1_svr_20261013-1600_partial2

衍生指標（推導值，報告中要標明）：
- 頻寬使用率 = model_size（bytes）× tg ÷ 理論頻寬。model_size 含 token embedding 等每個 token 只讀一小部分的張量，
  所以這是「把整個檔案當成每 token 都讀一遍」的近似值
- J/token（只算深度 0 的 tg）= 該測試期間 GPU 功耗的中位數 ÷ tg。期間 = 本測試開始到下一個測試開始，
  只取 utilization > 50% 的秒數；含暖機那一次。只是 GPU 功耗，不含 CPU 與整機
"""
import csv
import datetime as dt
import glob
import json
import os
import statistics
import sys

PEAK_GBPS = {"NVIDIA GeForce RTX 3060": 360.0, "NVIDIA GeForce RTX 5060 Ti": 448.0}


def load_gpu_log(path):
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for r in csv.reader(f):
            try:
                t = dt.datetime.strptime(r[0].strip(), "%Y/%m/%d %H:%M:%S.%f")
                out.append((t, float(r[2].split()[0]), int(r[6].split()[0])))
            except (ValueError, IndexError):
                pass
    return out


def main():
    name, dirs = sys.argv[1], sys.argv[2:]
    rows = []
    for d in dirs:
        # llama-bench 的 test_time 是 UTC；gpu_log 是機器本地時間（UTC+8）
        gpu = [(t - dt.timedelta(hours=8), p, u) for t, p, u in load_gpu_log(os.path.join(d, "gpu_log.csv"))]
        tests = []
        for f in sorted(glob.glob(os.path.join(d, "*.json"))):
            try:
                data = json.load(open(f, encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue  # 失敗的條件（例如 OOM）沒有 JSON 內容
            for r in data:
                r["_file"] = os.path.basename(f)
                r["_t0"] = dt.datetime.strptime(r["test_time"], "%Y-%m-%dT%H:%M:%SZ")
                tests.append(r)
        tests.sort(key=lambda r: r["_t0"])
        for i, r in enumerate(tests):
            t_end = tests[i + 1]["_t0"] if i + 1 < len(tests) else r["_t0"] + dt.timedelta(seconds=120)
            kind = "pp" if r["n_prompt"] else "tg"
            tg = r["avg_ts"] if kind == "tg" else None
            peak = PEAK_GBPS.get(r["gpu_info"])
            # 部分卸載時 GPU 大多在等 CPU，使用率常低於 50%，所以門檻放寬為 > 5%
            min_util = 50 if r["n_gpu_layers"] >= 99 else 5
            power = [p for t, p, u in gpu if r["_t0"] <= t < t_end and u > min_util]
            med_power = statistics.median(power) if len(power) >= 3 else None
            rows.append({
                "gpu": r["gpu_info"], "build": r["build_number"],
                # 用檔名而不是 model_type：UD-Q2_K_XL 的內部標籤是「Q2_K - Medium」，容易混淆
                "quant": os.path.basename(r["model_filename"]).removeprefix("Qwen3.8-27B-").removesuffix(".gguf"),
                "model_bytes": r["model_size"],
                "ngl": r["n_gpu_layers"], "test": f"{kind}{r['n_prompt'] or r['n_gen']}", "depth": r["n_depth"],
                "n": len(r["samples_ts"]), "tps_mean": round(r["avg_ts"], 2), "tps_sd": round(r["stddev_ts"], 2),
                "bw_util_pct": round(r["model_size"] * tg / 1e9 / peak * 100, 1) if (tg and peak and r["n_gpu_layers"] >= 99) else "",
                "gpu_power_w_median": round(med_power, 1) if (med_power and kind == "tg" and r["n_depth"] == 0) else "",
                "j_per_token": round(med_power / tg, 2) if (med_power and tg and r["n_depth"] == 0) else "",
                "source": f"{os.path.basename(d)}/{r['_file']}",
            })
    os.makedirs("results/processed", exist_ok=True)
    with open(f"results/processed/{name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(f"results/processed/{name}.md", "w", encoding="utf-8") as f:
        f.write(f"資料來源：{', '.join('`' + d + '`' for d in dirs)}。llama-bench，平均 ± 標準差。"
                "頻寬使用率與 J/token 為推導值（定義見 scripts/analyze_e1.py）。\n\n")
        f.write("| GPU | 量化 | ngl | 測試 | 深度 | tok/s | 頻寬使用率 | GPU 功耗 (W) | J/token |\n")
        f.write("|---|---|---:|---|---:|---:|---:|---:|---:|\n")
        for r in rows:
            f.write(f"| {r['gpu'].replace('NVIDIA GeForce ', '')} | {r['quant']} | {r['ngl']} | {r['test']} | {r['depth']} "
                    f"| {r['tps_mean']} ± {r['tps_sd']} | {r['bw_util_pct']}{'%' if r['bw_util_pct'] != '' else ''} "
                    f"| {r['gpu_power_w_median']} | {r['j_per_token']} |\n")
    print(f"wrote results/processed/{name}.csv/.md ({len(rows)} rows)")


if __name__ == "__main__":
    main()
