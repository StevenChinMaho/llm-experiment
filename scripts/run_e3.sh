#!/usr/bin/env bash
# E3 品質：llama-perplexity 的 KL 散度與困惑度（docs/experiment-plan.md E3）。在主力機 Ubuntu 執行。
#
# 模式：
#   base：用基準模型（Q8_0）跑一次，存下 logits 到 --kld-file，同時得到基準困惑度
#   kld ：用量化模型對 --kld-file 計算 KL 散度（同時得到困惑度）
# 用法：
#   run_e3.sh --mode base --model Qwen3.8-27B-Q8_0.gguf --kld-file /nvme477/llama/models/kld/q8_0_c2048_n<chunks>.kld \
#             --chunks 4 --out ~/e3/<run_id>
#   run_e3.sh --mode kld  --model Qwen3.8-27B-UD-IQ3_XXS.gguf --kld-file <同上> --chunks <同上> --out ~/e3/<run_id>
# GPU 層數不手動指定，讓 fit 機制自動決定（E3 量的是品質，與速度無關）；實際層數會記在 log 裡。
set -euo pipefail

IMAGE=ghcr.io/ggml-org/llama.cpp@sha256:3f7b5ae419f81c940b6171e004ee780091787a9cdb1c413b192fcb338a2d8590  # full-cuda13-b11347
MODELS=/nvme477/llama/models
DATA=$HOME/wikitext-2-raw
MODE="" MODEL="" KLD="" CHUNKS=-1 OUT="" CTX=2048 TMIN=240 EXTRA=""
while [ $# -gt 0 ]; do
  case "$1" in
    --mode) MODE=$2; shift 2 ;;
    --model) MODEL=$2; shift 2 ;;
    --kld-file) KLD=$2; shift 2 ;;
    --chunks) CHUNKS=$2; shift 2 ;;
    --ctx) CTX=$2; shift 2 ;;
    --out) OUT=$2; shift 2 ;;
    --timeout-min) TMIN=$2; shift 2 ;;
    --extra) EXTRA=$2; shift 2 ;;
    *) echo "未知參數 $1" >&2; exit 2 ;;
  esac
done
[ -n "$MODE" ] && [ -n "$MODEL" ] && [ -n "$KLD" ] && [ -n "$OUT" ] || { echo "需要 --mode --model --kld-file --out" >&2; exit 2; }
mkdir -p "$OUT" "$(dirname "$KLD")"
LOG="$OUT/run.log"
log() { echo "$(date -Is) $*" | tee -a "$LOG"; }

{
  echo "mode=$MODE"; echo "hostname=$(hostname)"; echo "start=$(date -Is)"; echo "kernel=$(uname -r)"
  echo "gpu=$(nvidia-smi --query-gpu=name,driver_version,memory.total,display_active --format=csv,noheader)"
  echo "image=$IMAGE"; echo "model=$MODEL"; echo "kld_file=$KLD"; echo "chunks=$CHUNKS"; echo "ctx=$CTX"; echo "extra=$EXTRA"
  echo "dataset_sha256=$(sha256sum "$DATA/wiki.test.raw" | cut -d' ' -f1)"
  echo "java_procs=$(pgrep -c java || true)"; echo "free_m:"; free -m
  echo "gpu_apps_before:"; nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv,noheader
} > "$OUT/env.txt"
side="$MODELS/$MODEL.sha256"
[ -s "$side" ] || (cd "$MODELS" && sha256sum "$MODEL" > "$MODEL.sha256")
cp "$side" "$OUT/model.sha256"

nvidia-smi --query-gpu=timestamp,temperature.gpu,power.draw,clocks.sm,memory.used,utilization.gpu \
  --format=csv -l 1 > "$OUT/gpu_log.csv" &
SMI_PID=$!
trap 'kill $SMI_PID 2>/dev/null || true; log END' EXIT

kld_in_container=/models/${KLD#"$MODELS"/}
case "$MODE" in
  base) mode_args=(--kl-divergence-base "$kld_in_container") ;;
  kld)  mode_args=(--kl-divergence-base "$kld_in_container" --kl-divergence) ;;
  *) echo "mode 只能是 base 或 kld" >&2; exit 2 ;;
esac

log "開始 $MODE：$MODEL chunks=$CHUNKS"
t0=$(date +%s)
# shellcheck disable=SC2086
if timeout "${TMIN}m" docker run --rm --gpus all -v "$MODELS":/models -v "$DATA":/data:ro \
     --entrypoint /app/llama-perplexity "$IMAGE" \
     -m "/models/$MODEL" -f /data/wiki.test.raw -c "$CTX" -b 2048 -ub 2048 -fa on -lv 4 --chunks "$CHUNKS" \
     "${mode_args[@]}" $EXTRA > "$OUT/perplexity.log" 2>&1; then
  log "完成，耗時 $(( $(date +%s) - t0 )) 秒"
else
  log "失敗或逾時（exit $?），log 最後幾行："; tail -8 "$OUT/perplexity.log" | tee -a "$LOG"
fi
[ -f "$KLD" ] && log "基準檔大小：$(stat -c %s "$KLD") bytes"
grep -E "Final estimate|offloaded|KL divergence|Same top|Mean|PPL" "$OUT/perplexity.log" | tail -20 | tee -a "$LOG" || true
log "ALL_DONE"
