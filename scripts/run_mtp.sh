#!/usr/bin/env bash
# MTP 推測解碼正式量測：掃 --spec-draft-n-max，記錄速度、接受率、VRAM、遞迴狀態，並用 greedy 比對輸出是否相同。
# 需要同一資料夾有 mtp_probe.py 與 parse_server_log.py。
#
# 用法：run_mtp.sh --models-dir /llama/models --model Qwen3.8-27B-UD-IQ3_XXS.gguf --out ~/mtp/<run_id> \
#                  [--ctx 16384] [--nmax "1 2 3 4 6"] [--stop-container llama]
set -uo pipefail  # 不用 -e：單一條件失敗時要繼續跑下一個
HERE=$(cd "$(dirname "$0")" && pwd)
IMAGE=ghcr.io/ggml-org/llama.cpp@sha256:936e9d2afab78662a05fd300c4a829ba931777bcd8372334da629b468511f90e  # server-cuda13-b11347
MODELS="" MODEL="" OUT="" CTX=16384 NMAX="1 2 3 4 6" STOP="" PORT=8012 NAME=llama-mtp
while [ $# -gt 0 ]; do
  case "$1" in
    --models-dir) MODELS=$2; shift 2 ;;
    --model) MODEL=$2; shift 2 ;;
    --out) OUT=$2; shift 2 ;;
    --ctx) CTX=$2; shift 2 ;;
    --nmax) NMAX=$2; shift 2 ;;
    --stop-container) STOP=$2; shift 2 ;;
    *) echo "未知參數 $1" >&2; exit 2 ;;
  esac
done
mkdir -p "$OUT"
LOG="$OUT/run.log"
log() { echo "$(date -Is) $*" | tee -a "$LOG"; }
{
  echo "hostname=$(hostname)"; echo "start=$(date -Is)"
  echo "gpu=$(nvidia-smi --query-gpu=name,driver_version,memory.total,display_active --format=csv,noheader)"
  echo "image=$IMAGE"; echo "model=$MODEL"; echo "ctx=$CTX"; echo "nmax=$NMAX"
  echo "java_procs=$(pgrep -c java || true)"
} > "$OUT/env.txt"
(cd "$MODELS" && { [ -s "$MODEL.sha256" ] || sha256sum "$MODEL" > "$MODEL.sha256"; } && cat "$MODEL.sha256"; sha256sum MTP/mtp-Qwen3.8-27B-Q4_0.gguf) > "$OUT/models.sha256"

nvidia-smi --query-gpu=timestamp,temperature.gpu,power.draw,clocks.sm,memory.used,utilization.gpu --format=csv -l 1 > "$OUT/gpu_log.csv" &
SMI_PID=$!
restore() {
  kill "$SMI_PID" 2>/dev/null || true
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  if [ -n "$STOP" ]; then docker start "$STOP" >/dev/null && log "已重新啟動 $STOP"; fi
  log END
}
trap restore EXIT
if [ -n "$STOP" ]; then docker stop "$STOP" >/dev/null; sleep 5; fi

run_cond() {  # run_cond <標籤> [MTP 參數...]
  local label=$1; shift
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  log "啟動 $label：$*"
  docker run -d --name "$NAME" --gpus all -v "$MODELS":/models -p 127.0.0.1:$PORT:8080 "$IMAGE" \
    -m "/models/$MODEL" -ngl 99 -c "$CTX" -fa on -np 1 -ctk q8_0 -ctv q8_0 --cache-ram 0 --jinja \
    --no-reasoning-preserve -lv 4 --port 8080 "$@" >/dev/null
  for _ in $(seq 1 120); do
    curl -sf "http://127.0.0.1:$PORT/health" >/dev/null && break
    if ! docker ps -q --filter "name=^$NAME$" | grep -q .; then
      docker logs "$NAME" > "$OUT/server_$label.log" 2>&1
      log "$label 啟動失敗：$(grep -m1 -aE 'out of memory|error' "$OUT/server_$label.log" || echo unknown)"
      return 0
    fi
    sleep 2
  done
  log "$label 就緒：nvidia-smi $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"
  python3 "$HERE/mtp_probe.py" --url "http://127.0.0.1:$PORT" --label "$label" --out "$OUT/results.jsonl" --reps 2 | tee -a "$LOG"
  python3 "$HERE/mtp_probe.py" --url "http://127.0.0.1:$PORT" --label "${label}_greedy" --out "$OUT/results.jsonl" \
    --reps 1 --temperature 0 | tee -a "$LOG"
  echo "{\"label\": \"$label\", \"vram_mib\": $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)}" >> "$OUT/vram.jsonl"
  docker logs "$NAME" > "$OUT/server_$label.log" 2>&1
  python3 "$HERE/parse_server_log.py" "$OUT/server_$label.log" | tee -a "$LOG"
  docker rm -f "$NAME" >/dev/null
  sleep 3
}

run_cond mtp_off
for n in $NMAX; do
  run_cond "mtp_n$n" --spec-type draft-mtp --spec-draft-model /models/MTP/mtp-Qwen3.8-27B-Q4_0.gguf --spec-draft-n-max "$n"
done
log "ALL_DONE"
