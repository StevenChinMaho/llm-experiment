#!/usr/bin/env bash
# E4：啟動 llama-server（指定量化與思考預算）→ run_eval.py 送題 → 關閉伺服器。在主力機 Ubuntu 執行。
#
# 用法：
#   run_e4.sh --model Qwen3.8-27B-UD-IQ4_XS.gguf --budget 16384 --label iq4xs_b16384 --reps 1 \
#             --out ~/e4/<run_id> [--ctx 32768] [--max-tokens 18432] [--extra "--spec-type draft-mtp ..."]
# 腳本與題目從 ~/qwen-eval/ 讀（scripts/run_eval.py、eval/*.json）。
set -euo pipefail

IMAGE=ghcr.io/ggml-org/llama.cpp@sha256:936e9d2afab78662a05fd300c4a829ba931777bcd8372334da629b468511f90e  # server-cuda13-b11347
MODELS=/nvme477/llama/models
EVAL=$HOME/qwen-eval
MODEL="" BUDGET="" LABEL="" REPS=1 OUT="" CTX=32768 MAXTOK="" EXTRA="" PORT=8000 QUESTIONS="eval/aime_2026.json eval/questions.json:hard"
while [ $# -gt 0 ]; do
  case "$1" in
    --model) MODEL=$2; shift 2 ;;
    --budget) BUDGET=$2; shift 2 ;;
    --label) LABEL=$2; shift 2 ;;
    --reps) REPS=$2; shift 2 ;;
    --out) OUT=$2; shift 2 ;;
    --ctx) CTX=$2; shift 2 ;;
    --max-tokens) MAXTOK=$2; shift 2 ;;
    --questions) QUESTIONS=$2; shift 2 ;;
    --extra) EXTRA=$2; shift 2 ;;
    *) echo "未知參數 $1" >&2; exit 2 ;;
  esac
done
[ -n "$MODEL" ] && [ -n "$BUDGET" ] && [ -n "$LABEL" ] && [ -n "$OUT" ] || { echo "需要 --model --budget --label --out" >&2; exit 2; }
MAXTOK=${MAXTOK:-$((BUDGET + 4096))}   # 思考預算＋給答案的空間（校準時 +2048 不夠，I-15 被截斷）
mkdir -p "$OUT"
LOG="$OUT/run.log"
log() { echo "$(date -Is) $*" | tee -a "$LOG"; }
NAME=llama-e4

SERVER_ARGS=(-m "/models/$MODEL" -ngl 99 -c "$CTX" -fa on -np 1 -ctk q8_0 -ctv q8_0 --cache-ram 0
             --jinja --no-reasoning-preserve --reasoning-budget "$BUDGET" -lv 4 --port 8080)
# shellcheck disable=SC2206
[ -n "$EXTRA" ] && SERVER_ARGS+=($EXTRA)
{
  echo "hostname=$(hostname)"; echo "start=$(date -Is)"; echo "kernel=$(uname -r)"
  echo "gpu=$(nvidia-smi --query-gpu=name,driver_version,memory.total,display_active --format=csv,noheader)"
  echo "image=$IMAGE"; echo "model=$MODEL"; echo "budget=$BUDGET"; echo "ctx=$CTX"; echo "max_tokens=$MAXTOK"
  echo "label=$LABEL"; echo "reps=$REPS"; echo "questions=$QUESTIONS"
  echo "server_args=${SERVER_ARGS[*]}"
  echo "eval_script_sha256=$(sha256sum "$EVAL/scripts/run_eval.py" | cut -d' ' -f1)"
  echo "java_procs=$(pgrep -c java || true)"
  echo "gpu_apps_before:"; nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv,noheader
} > "$OUT/env.txt"
side="$MODELS/$MODEL.sha256"
[ -s "$side" ] || (cd "$MODELS" && sha256sum "$MODEL" > "$MODEL.sha256")
cp "$side" "$OUT/model.sha256"

nvidia-smi --query-gpu=timestamp,temperature.gpu,power.draw,clocks.sm,memory.used,utilization.gpu \
  --format=csv -l 1 > "$OUT/gpu_log.csv" &
SMI_PID=$!
cleanup() {
  kill "$SMI_PID" 2>/dev/null || true
  docker logs "$NAME" > "$OUT/server.log" 2>&1 || true
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  log END
}
trap cleanup EXIT

docker rm -f "$NAME" >/dev/null 2>&1 || true
log "啟動伺服器：${SERVER_ARGS[*]}"
docker run -d --name "$NAME" --gpus all -v "$MODELS":/models -p 127.0.0.1:$PORT:8080 "$IMAGE" "${SERVER_ARGS[@]}" >/dev/null
for _ in $(seq 1 180); do
  curl -sf "http://127.0.0.1:$PORT/health" >/dev/null && break
  docker ps -q --filter "name=^$NAME$" | grep -q . || { log "伺服器啟動失敗"; docker logs "$NAME" 2>&1 | tail -8 | tee -a "$LOG"; exit 1; }
  sleep 2
done
log "伺服器就緒：$(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"

cd "$EVAL"
# shellcheck disable=SC2086
python3 scripts/run_eval.py --url "http://127.0.0.1:$PORT" --label "$LABEL" --questions $QUESTIONS --reps "$REPS" \
  --max-tokens "$MAXTOK" --thinking on --out "$OUT/results.jsonl" \
  --note "model=$MODEL budget=$BUDGET ctx=$CTX image=$IMAGE" 2>&1 | tee -a "$OUT/eval.log"
log "ALL_DONE"
