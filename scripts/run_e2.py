#!/usr/bin/env python3
"""E2 記憶體：在目標機器上反覆啟動 llama-server（-lv 4 -fit off），
(1) 在固定的 -c 下記錄記憶體配置（驗證 KV 公式）；(2) 二分搜尋全 GPU 時的最大 -c。

成功的定義：伺服器啟動、log 有 "model loaded"、全部的層都在 GPU（offloaded N/N），且能完成一次短的 /completion。
注意：記憶體在啟動時一次配置完成（findings §2），所以不另外做滿長度的 prefill。

用法（在 kururinpa-svr 或主力機上，需要 docker 與 parse_server_log.py 在同一資料夾）：
  python3 run_e2.py --machine svr --models-dir /llama/models --out ~/e2/<run_id> \
      --models Qwen3.8-27B-UD-IQ3_XXS.gguf ... [--fixed 4096,16384,32768,65536] [--stop-container llama]
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_server_log import parse  # noqa: E402

IMAGE = "ghcr.io/ggml-org/llama.cpp@sha256:936e9d2afab78662a05fd300c4a829ba931777bcd8372334da629b468511f90e"
NAME = "llama-e2"
PORT = 8011


def sh(cmd, check=False):
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def smi(q="memory.used"):
    return sh(["nvidia-smi", f"--query-gpu={q}", "--format=csv,noheader,nounits"]).stdout.strip()


def try_ctx(a, model, ctx, tag):
    sh(["docker", "rm", "-f", NAME])
    args = ["-m", f"/models/{model}", "-ngl", "99", "-c", str(ctx), "-fa", "on", "-np", "1", "-ctk", "q8_0",
            "-ctv", "q8_0", "--cache-ram", "0", "--jinja", "-lv", "4", "-fit", "off", "--port", "8080"]
    sh(["docker", "run", "-d", "--name", NAME, "--gpus", "all", "-v", f"{a.models_dir}:/models", "-p",
        f"127.0.0.1:{PORT}:8080", IMAGE] + args, check=True)
    ok, reason, mem = False, "", None
    for _ in range(150):
        time.sleep(2)
        running = sh(["docker", "ps", "-q", "--filter", f"name=^{NAME}$"]).stdout.strip()
        if not running:
            reason = "exited"
            break
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=3) as r:
                if json.load(r).get("status") == "ok":
                    mem = smi()
                    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/completion", headers={"Content-Type": "application/json"},
                                                 data=json.dumps({"prompt": "Hello, my name is", "n_predict": 4}).encode())
                    with urllib.request.urlopen(req, timeout=120) as rr:
                        ok = bool(json.load(rr).get("content") is not None)
                    reason = "ok" if ok else "completion failed"
                    break
        except Exception:
            continue
    else:
        reason = "timeout"
    logf = os.path.join(a.out, f"{tag}_{model.removeprefix('Qwen3.8-27B-').removesuffix('.gguf')}_c{ctx}.log")
    with open(logf, "w", encoding="utf-8") as f:
        f.write(sh(["docker", "logs", NAME]).stdout + sh(["docker", "logs", NAME]).stderr)
    sh(["docker", "rm", "-f", NAME])
    time.sleep(3)
    rec = parse(logf)
    # 「全部的層都在 GPU」：各量化檔的層數不一定相同（UD-IQ2_XXS 是 65/65，其他是 66/66），所以不寫死
    off = rec.get("offloaded")
    all_on_gpu = bool(off) and off.split("/")[0] == off.split("/")[1]
    ok = ok and all_on_gpu and not rec.get("oom")
    rec.update({"event": tag, "model": model, "ctx_requested": ctx, "ok": ok, "reason": reason,
                "smi_used_mib": int(mem) if mem else None, "time": datetime.datetime.now().isoformat(timespec="seconds")})
    with open(os.path.join(a.out, "results.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"{tag} {model} -c {ctx}: {'OK' if ok else 'FAIL'} ({reason}) n_ctx={rec.get('n_ctx')} kv={rec.get('kv_mib')} "
          f"compute={rec.get('cuda_compute_mib')} smi={mem}", flush=True)
    return ok


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--machine", required=True)
    p.add_argument("--models-dir", required=True)
    p.add_argument("--models", nargs="+", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--fixed", default="4096,16384,32768,65536")
    p.add_argument("--lo", type=int, default=4096)
    p.add_argument("--hi", type=int, default=262144)
    p.add_argument("--step", type=int, default=1024, help="二分搜尋的解析度")
    p.add_argument("--stop-container", default="")
    a = p.parse_args()
    os.makedirs(a.out, exist_ok=True)
    env = {"machine": a.machine, "hostname": os.uname().nodename, "start": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
           "gpu": smi("name,driver_version,memory.total,display_active"), "image": IMAGE, "args": vars(a),
           "java_procs": sh(["pgrep", "-c", "java"]).stdout.strip() or "0",
           "docker_ps_before": sh(["docker", "ps", "--format", "{{.Names}} {{.Status}}"]).stdout}
    json.dump(env, open(os.path.join(a.out, "env.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if a.stop_container:
        sh(["docker", "stop", a.stop_container]); time.sleep(5)
    print("GPU 開始前：", smi("memory.used,utilization.gpu"), flush=True)
    try:
        for model in a.models:
            for ctx in [int(x) for x in a.fixed.split(",")]:
                try_ctx(a, model, ctx, "fixed")
            lo, hi = a.lo, a.hi
            if not try_ctx(a, model, lo, "search"):
                print(f"{model}：連 -c {lo} 都放不下", flush=True); continue
            if try_ctx(a, model, hi, "search"):
                print(f"{model}：-c {hi}（原生上限）也放得下", flush=True); continue
            while hi - lo > a.step:
                mid = (lo + hi) // 2 // 256 * 256
                if try_ctx(a, model, mid, "search"):
                    lo = mid
                else:
                    hi = mid
            print(f"RESULT {model} max_ctx≈{lo}（{hi} 失敗）", flush=True)
            with open(os.path.join(a.out, "results.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps({"event": "max_ctx", "model": model, "max_ok": lo, "min_fail": hi}) + "\n")
    finally:
        sh(["docker", "rm", "-f", NAME])
        if a.stop_container:
            sh(["docker", "start", a.stop_container]); print("已重新啟動", a.stop_container, flush=True)
        print("ALL_DONE", flush=True)


if __name__ == "__main__":
    main()
