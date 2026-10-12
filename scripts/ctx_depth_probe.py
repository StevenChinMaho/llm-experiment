#!/usr/bin/env python3
"""Context 大小 × 深度 對推論速度與 GPU 記憶體的影響（解 Windows 可跑 83K、Linux 不行的謎）。

做法：同一個 llama-server 執行檔、同一個模型，只改 -c。每個 -c 啟動一次伺服器，
用 /completion 送「剛好 depth 個 token」的 prompt（token id 陣列），固定生成 n_gen 個 token
（ignore_eos、不用 prompt cache），記錄伺服器回報的 pp／tg 速度，以及每次量測後的
GPU 專用／共享記憶體（Windows 效能計數器）與 nvidia-smi。

只用標準函式庫。輸出到 --out 資料夾：
  env.json            環境資訊（GPU、驅動、執行檔版本、模型實體路徑、指令）
  results.jsonl       每次量測一筆
  summary.csv         每個 (ctx, depth) 的平均與標準差
  gpu_log.csv         nvidia-smi 每秒紀錄（溫度、功耗、時脈、VRAM）
  server_c<ctx>.log   llama-server 的 --log-file
  probe.log           本腳本的進度
"""
import argparse
import csv
import datetime
import json
import os
import platform
import random
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request

WORDS = (
    "the of and to in is that for it as was with be by on not he this are or his from at which "
    "but have an they you were her she there had been one all we can their has more when will "
    "would who so if no out up said what its about into than them only other new some could time "
    "these two may then do first any my now such like our over man me even most made after also "
    "did many before must through back years where much your way well down should because each "
    "just those people how too little state good very make world still own see men work long get "
    "here between both life being under never day same another know while last might us great old "
    "year off come since against go came right used take three memory model token speed context "
    "graphics card network server window kernel driver cache layer weight matrix vector compute"
).split()


def log(out, msg):
    line = f"{datetime.datetime.now().isoformat(timespec='seconds')} {msg}"
    print(line, flush=True)
    with open(os.path.join(out, "probe.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def http(url, payload=None, timeout=3600):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=120).stdout.strip()
    except Exception as e:  # 記錄失敗本身也是資訊
        return f"ERROR: {e}"


def win_gpu_mem(pid):
    """回傳 {'dedicated_mib':…, 'shared_mib':…}，只加總 NVIDIA 那張卡（取專用量最大的 LUID）。"""
    if platform.system() != "Windows":
        return {}
    ps = (
        f"(Get-Counter '\\GPU Process Memory(pid_{pid}_*)\\Dedicated Usage',"
        f"'\\GPU Process Memory(pid_{pid}_*)\\Shared Usage' -ErrorAction SilentlyContinue).CounterSamples"
        " | ForEach-Object { $_.InstanceName + '|' + $_.Path.Split('\\')[-1] + '|' + [int64]$_.CookedValue }"
    )
    raw = run(["powershell", "-NoProfile", "-Command", ps])
    by_luid = {}
    for line in raw.splitlines():
        parts = line.strip().split("|")
        if len(parts) != 3:
            continue
        inst, kind, val = parts
        luid = inst.split("_luid_")[-1]
        d = by_luid.setdefault(luid, {"dedicated_mib": 0.0, "shared_mib": 0.0})
        key = "dedicated_mib" if "dedicated" in kind.lower() else "shared_mib"
        d[key] += int(val) / 2**20
    if not by_luid:
        return {"raw": raw}
    best = max(by_luid.values(), key=lambda d: d["dedicated_mib"])
    return {k: round(v, 1) for k, v in best.items()}


def smi_mem():
    s = run(["nvidia-smi", "--query-gpu=memory.used,temperature.gpu,power.draw,clocks.sm",
             "--format=csv,noheader,nounits"])
    try:
        used, temp, power, clk = [x.strip() for x in s.split(",")]
        return {"smi_used_mib": int(used), "temp_c": int(temp), "power_w": float(power), "sm_mhz": int(clk)}
    except ValueError:
        return {"smi_raw": s}


def make_tokens(base, need, seed=12345):
    rnd = random.Random(seed)
    tokens = []
    while len(tokens) < need:
        text = " ".join(rnd.choice(WORDS) for _ in range(20000)) + ".\n"
        tokens += http(f"{base}/tokenize", {"content": text, "add_special": False})["tokens"]
    return tokens[:need]


def start_server(a, ctx, port):
    logf = os.path.join(a.out, f"server_c{ctx}.log")
    cmd = [a.server, "-m", a.model, "-ngl", "99", "-c", str(ctx), "-fa", "on", "-np", "1",
           "-ctk", "q8_0", "-ctv", "q8_0", "--no-mmproj", "--cache-ram", "0",
           "--ctx-checkpoints", "0", "-lv", "4", "--log-file", logf,
           "--host", "127.0.0.1", "--port", str(port)]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    for _ in range(300):
        if proc.poll() is not None:
            return proc, base, cmd, f"server exited with code {proc.returncode}"
        try:
            if http(f"{base}/health", timeout=5).get("status") == "ok":
                return proc, base, cmd, None
        except Exception:
            pass
        time.sleep(1)
    return proc, base, cmd, "server not healthy after 300 s"


def tail(path, n=15):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.readlines()[-n:]
    except OSError:
        return []


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--server", required=True, help="llama-server 執行檔路徑")
    p.add_argument("--model", required=True)
    p.add_argument("--ctx", default="49152,65536,83536")
    p.add_argument("--depths", default="1000,16000,32000,48000,64000,80000")
    p.add_argument("--reps", type=int, default=3)
    p.add_argument("--n-gen", type=int, default=128)
    p.add_argument("--port", type=int, default=8090)
    p.add_argument("--out", required=True)
    p.add_argument("--note", default="", help="寫進 env.json 的備註（例如 llama.cpp build、執行環境）")
    a = p.parse_args()
    os.makedirs(a.out, exist_ok=True)
    ctxs = [int(x) for x in a.ctx.split(",")]
    depths = [int(x) for x in a.depths.split(",")]

    env = {
        "start": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "host": platform.node(), "os": platform.platform(), "python": sys.version.split()[0],
        "gpu": run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total,display_active",
                    "--format=csv,noheader"]),
        "server": a.server, "server_version": run([a.server, "--version"]),
        "model": a.model, "model_realpath": os.path.realpath(a.model),
        "model_bytes": os.path.getsize(a.model), "args": vars(a), "note": a.note,
    }
    with open(os.path.join(a.out, "env.json"), "w", encoding="utf-8") as f:
        json.dump(env, f, ensure_ascii=False, indent=2)
    log(a.out, f"env: {env['gpu']} | {env['model_realpath']}")

    smi = subprocess.Popen(
        ["nvidia-smi", "--query-gpu=timestamp,temperature.gpu,power.draw,clocks.sm,memory.used,utilization.gpu",
         "--format=csv", "-l", "1", "-f", os.path.join(a.out, "gpu_log.csv")])

    tokens = None
    res_path = os.path.join(a.out, "results.jsonl")
    try:
        for ctx in ctxs:
            log(a.out, f"=== start server -c {ctx}")
            proc, base, cmd, err = start_server(a, ctx, a.port)
            rec0 = {"ctx": ctx, "cmd": cmd}
            if err:
                rec0.update({"event": "start_failed", "error": err,
                             "log_tail": tail(os.path.join(a.out, f"server_c{ctx}.log"))})
                log(a.out, f"start failed: {err}")
                with open(res_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec0, ensure_ascii=False) + "\n")
                if proc.poll() is None:
                    proc.terminate(); proc.wait(30)
                continue
            try:
                n_ctx = http(f"{base}/props").get("default_generation_settings", {}).get("n_ctx", ctx)
                rec0.update({"event": "loaded", "n_ctx": n_ctx, **win_gpu_mem(proc.pid), **smi_mem()})
                with open(res_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec0, ensure_ascii=False) + "\n")
                log(a.out, f"loaded n_ctx={n_ctx} mem={rec0}")
                if tokens is None:
                    tokens = make_tokens(base, max(depths))
                    log(a.out, f"prepared {len(tokens)} tokens")
                http(f"{base}/completion", {"prompt": tokens[:64], "n_predict": 16, "cache_prompt": False})  # 暖機
                for depth in depths:
                    if depth + a.n_gen + 8 > n_ctx:
                        continue
                    for rep in range(1, a.reps + 1):
                        t0 = time.time()
                        r = http(f"{base}/completion", {
                            "prompt": tokens[:depth], "n_predict": a.n_gen, "ignore_eos": True,
                            "cache_prompt": False, "seed": rep})
                        tm = r.get("timings", {})
                        rec = {"event": "measure", "ctx": ctx, "n_ctx": n_ctx, "depth": depth, "rep": rep,
                               "prompt_n": tm.get("prompt_n"), "pp_tps": tm.get("prompt_per_second"),
                               "predicted_n": tm.get("predicted_n"), "tg_tps": tm.get("predicted_per_second"),
                               "wall_s": round(time.time() - t0, 2),
                               "time": datetime.datetime.now().isoformat(timespec="seconds"),
                               **win_gpu_mem(proc.pid), **smi_mem()}
                        with open(res_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        log(a.out, f"c={ctx} d={depth} r={rep} pp={rec['pp_tps']:.1f} tg={rec['tg_tps']:.2f} "
                                   f"ded={rec.get('dedicated_mib')} shr={rec.get('shared_mib')} T={rec.get('temp_c')}")
            except Exception as e:
                log(a.out, f"ERROR during c={ctx}: {e!r}")
                with open(res_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"event": "error", "ctx": ctx, "error": repr(e)}) + "\n")
            finally:
                proc.terminate()
                try:
                    proc.wait(60)
                except subprocess.TimeoutExpired:
                    proc.kill()
                time.sleep(5)
    finally:
        smi.terminate()

    rows = [json.loads(l) for l in open(res_path, encoding="utf-8")]
    groups = {}
    for r in rows:
        if r.get("event") == "measure":
            groups.setdefault((r["ctx"], r["depth"]), []).append(r)
    with open(os.path.join(a.out, "summary.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ctx", "depth", "n", "pp_mean", "pp_sd", "tg_mean", "tg_sd", "dedicated_mib", "shared_mib"])
        for (ctx, depth), rs in sorted(groups.items()):
            pp = [r["pp_tps"] for r in rs]; tg = [r["tg_tps"] for r in rs]
            sd = lambda xs: statistics.stdev(xs) if len(xs) > 1 else 0.0
            w.writerow([ctx, depth, len(rs), f"{statistics.mean(pp):.1f}", f"{sd(pp):.1f}",
                        f"{statistics.mean(tg):.3f}", f"{sd(tg):.3f}",
                        rs[-1].get("dedicated_mib"), rs[-1].get("shared_mib")])
    log(a.out, "ALL_DONE")


if __name__ == "__main__":
    main()
