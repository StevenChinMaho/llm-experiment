#!/usr/bin/env bash
# E1 速度實驗：以 full 映像的 llama-bench 量 pp／tg（全 GPU 掃 context 深度；部分卸載掃 -ngl）。
# 在目標機器上執行（kururinpa-svr 或主力機 Ubuntu），輸出到 OUT 資料夾。
#
# 用法：
#   run_e1.sh --machine svr --models-dir /llama/models --out ~/e1/<run_id> \
#             --full "Qwen3.8-27B-UD-IQ2_XXS.gguf Qwen3.8-27B-UD-IQ3_XXS.gguf" \
#             --partial "Qwen3.8-27B-UD-IQ4_XS.gguf" --ngl "56 52 48 44" \
#             [--stop-container llama] [--depths 0,4096,16384,32768] [--reps 5] [--timeout-min 60]
set -euo pipefail

IMAGE=ghcr.io/ggml-org/llama.cpp@sha256:3f7b5ae419f81c940b6171e004ee780091787a9cdb1c413b192fcb338a2d8590  # full-cuda13-b11347
MACHINE="" MODELS_DIR="" OUT="" FULL="" PARTIAL="" NGL="56 52 48 44" STOP="" DEPTHS="0,4096,16384,32768" REPS=5 PREPS=3 TMIN=60
while [ $# -gt 0 ]; do
  case "$1" in
    --machine) MACHINE=$2; shift 2 ;;
    --models-dir) MODELS_DIR=$2; shift 2 ;;
    --out) OUT=$2; shift 2 ;;
    --full) FULL=$2; shift 2 ;;
    --partial) PARTIAL=$2; shift 2 ;;
    --ngl) NGL=$2; shift 2 ;;
    --stop-container) STOP=$2; shift 2 ;;
    --depths) DEPTHS=$2; shift 2 ;;
    --reps) REPS=$2; shift 2 ;;
    --timeout-min) TMIN=$2; shift 2 ;;
    *) echo "未知參數 $1" >&2; exit 2 ;;
  esac
done
[ -n "$MACHINE" ] && [ -n "$MODELS_DIR" ] && [ -n "$OUT" ] || { echo "需要 --machine --models-dir --out" >&2; exit 2; }
mkdir -p "$OUT"
LOG="$OUT/run.log"
log() { echo "$(date -Is) $*" | tee -a "$LOG"; }

# ---- 環境資訊（CLAUDE.md 規則 5）----
{
  echo "machine=$MACHINE"
  echo "hostname=$(hostname)"
  echo "start=$(date -Is)"
  echo "kernel=$(uname -r)"
  echo "gpu=$(nvidia-smi --query-gpu=name,driver_version,memory.total,display_active --format=csv,noheader)"
  echo "nvidia_module=$(head -1 /proc/driver/nvidia/version)"
  echo "image=$IMAGE"
  echo "java_procs=$(pgrep -c java || true)"
  echo "uptime=$(uptime)"
  echo "free_m:"; free -m
  echo "docker_ps_before:"; docker ps --format '{{.Names}} {{.Image}} {{.Status}}'
  echo "args: full=[$FULL] partial=[$PARTIAL] ngl=[$NGL] depths=$DEPTHS reps=$REPS partial_reps=$PREPS timeout_min=$TMIN"
} > "$OUT/env.txt"

# 模型 sha256（每個檔案只算一次，存在旁邊的 .sha256）
: > "$OUT/models.sha256"
for f in $FULL $PARTIAL; do
  side="$MODELS_DIR/$f.sha256"
  if [ ! -s "$side" ]; then log "計算 sha256：$f"; (cd "$MODELS_DIR" && sha256sum "$f" > "$f.sha256"); fi
  cat "$side" >> "$OUT/models.sha256"
done

# ---- 停常駐容器，結束時（包括出錯）一定開回來 ----
restore() {
  [ -n "${SMI_PID:-}" ] && kill "$SMI_PID" 2>/dev/null || true
  if [ -n "$STOP" ]; then log "重新啟動容器 $STOP"; docker start "$STOP" >/dev/null || log "警告：$STOP 啟動失敗"; fi
  log "END"
}
trap restore EXIT
if [ -n "$STOP" ]; then log "停止容器 $STOP"; docker stop "$STOP" >/dev/null; sleep 5; fi
nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader > "$OUT/gpu_idle_before.txt"
log "GPU 開始前：$(cat "$OUT/gpu_idle_before.txt")"

# 用重新導向而不是 -f：-f 會緩衝到行程結束才寫入，重新導向每秒即時寫入（2026-10-13 實測）
nvidia-smi --query-gpu=timestamp,temperature.gpu,power.draw,clocks.sm,clocks.mem,memory.used,utilization.gpu \
  --format=csv -l 1 > "$OUT/gpu_log.csv" &
SMI_PID=$!

bench() {  # bench <名稱> <llama-bench 參數...>
  local name=$1; shift
  log "開始 $name：llama-bench $*"
  if timeout "${TMIN}m" docker run --rm --gpus all -v "$MODELS_DIR":/models --entrypoint /app/llama-bench "$IMAGE" \
       "$@" -o json > "$OUT/$name.json" 2> "$OUT/$name.stderr"; then
    log "完成 $name"
  else
    log "失敗或逾時 $name（exit $?），stderr 最後幾行："; tail -5 "$OUT/$name.stderr" | tee -a "$LOG"
  fi
}

for f in $FULL; do
  q=$(echo "$f" | sed -E 's/^Qwen3\.8-27B-(UD-)?//; s/\.gguf$//')
  bench "full_$q" -m "/models/$f" -ngl 99 -fa on -ctk q8_0 -ctv q8_0 -p 512 -n 128 -d "$DEPTHS" -r "$REPS"
done
for f in $PARTIAL; do
  q=$(echo "$f" | sed -E 's/^Qwen3\.8-27B-(UD-)?//; s/\.gguf$//')
  for n in $NGL; do
    bench "partial_${q}_ngl$n" -m "/models/$f" -ngl "$n" -fa on -ctk q8_0 -ctv q8_0 -p 512 -n 128 -d 0 -r "$PREPS"
  done
done
log "ALL_DONE"
