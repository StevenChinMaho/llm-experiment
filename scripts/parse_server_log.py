#!/usr/bin/env python3
"""從 llama-server 的啟動 log（-lv 4）抽出記憶體配置，並與 KV cache 公式比對（docs/findings-so-far.md §3）。

用法：python parse_server_log.py <log> [<log> ...] [--csv out.csv]
也可以 import：from parse_server_log import parse
"""
import csv
import re
import sys

KV_BYTES_PER_TOKEN_Q8 = 16 * 2048 * 1.0625  # 16 層 × (K+V 各 1024) × q8_0 每元素 1.0625 bytes = 34,816 B

FIELDS = {
    "n_ctx": r"llama_context: n_ctx\s+=\s+(\d+)",
    "offloaded": r"offloaded (\d+)/(\d+) layers to GPU",
    "cuda_model_mib": r"CUDA0 model buffer size =\s+([\d.]+) MiB",
    "cpu_mapped_mib": r"CPU_Mapped model buffer size =\s+([\d.]+) MiB",
    "kv_mib": r"CUDA0 KV buffer size =\s+([\d.]+) MiB",
    "rs_mib": r"CUDA0 RS buffer size =\s+([\d.]+) MiB",
    "cuda_compute_mib": r"CUDA0 compute buffer size =\s+([\d.]+) MiB",
    "host_compute_mib": r"CUDA_Host compute buffer size =\s+([\d.]+) MiB",
    "fit_projected_mib": r"projected to use (\d+) MiB of device memory vs\. (\d+) MiB of free",
    "oom": r"(cudaMalloc failed: out of memory)",
    "loaded": r"(llama_server: model loaded)",
}


def parse(path):
    t = open(path, encoding="utf-8", errors="replace").read()
    r = {"log": path}
    for k, p in FIELDS.items():
        m = re.search(p, t)
        if not m:
            r[k] = None
        elif k == "offloaded":
            r[k] = f"{m.group(1)}/{m.group(2)}"
        elif k == "fit_projected_mib":
            r[k], r["fit_free_mib"] = int(m.group(1)), int(m.group(2))
        elif k in ("oom", "loaded"):
            r[k] = True
        elif k == "n_ctx":
            r[k] = int(m.group(1))
        else:
            r[k] = float(m.group(1))
    r.setdefault("fit_free_mib", None)
    if r["n_ctx"] and r["kv_mib"] is not None:
        pred = r["n_ctx"] * KV_BYTES_PER_TOKEN_Q8 / 2**20
        r["kv_formula_mib"] = round(pred, 2)
        r["kv_err_mib"] = round(r["kv_mib"] - pred, 2)
    else:
        r["kv_formula_mib"] = r["kv_err_mib"] = None
    parts = [r[k] for k in ("cuda_model_mib", "kv_mib", "rs_mib", "cuda_compute_mib")]
    r["cuda_sum_mib"] = round(sum(parts), 2) if all(p is not None for p in parts) else None
    return r


def main():
    args = sys.argv[1:]
    out = None
    if "--csv" in args:
        i = args.index("--csv"); out = args[i + 1]; del args[i:i + 2]
    rows = [parse(p) for p in args]
    for r in rows:
        print({k: v for k, v in r.items() if v is not None})
    if out:
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    main()
