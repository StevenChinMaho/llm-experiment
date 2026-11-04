#!/usr/bin/env bash
# E4 批次：停常駐容器 → 依序跑「量化 × 思考預算」→ 結束時一定把常駐容器啟動回來。中斷後用同樣指令重跑會接續。
#
# 用法：MODELS=/llama/models run_e4_batch.sh --root ~/e4/e4_svr --quants "UD-Q2_K_XL UD-IQ3_XXS" \
#         --budgets "1024 4096 16384" --reps 2 [--stop llama]
# 短預算排前面，先拿到完整的 1024、4096，最耗時的 16384 放最後。
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT="" QUANTS="" BUDGETS="1024 4096 16384" REPS=2 STOP=""
while [ $# -gt 0 ]; do
  case "$1" in
    --root) ROOT=$2; shift 2 ;;
    --quants) QUANTS=$2; shift 2 ;;
    --budgets) BUDGETS=$2; shift 2 ;;
    --reps) REPS=$2; shift 2 ;;
    --stop) STOP=$2; shift 2 ;;
    *) echo "未知參數 $1" >&2; exit 2 ;;
  esac
done
[ -n "$ROOT" ] && [ -n "$QUANTS" ] || { echo "需要 --root --quants" >&2; exit 2; }
mkdir -p "$ROOT"
LOG="$ROOT/batch.log"
log() { echo "$(date -Is) $*" | tee -a "$LOG"; }
restore() { if [ -n "$STOP" ]; then docker start "$STOP" >/dev/null && log "已重新啟動 $STOP"; fi; log BATCH_END; }
trap restore EXIT
trap 'log 收到中止訊號; exit 130' INT TERM HUP

if [ -n "$STOP" ]; then log "停止常駐容器 $STOP"; docker stop "$STOP" >/dev/null; sleep 5; fi
apps=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader)
[ -z "$apps" ] || { log "GPU 上還有其他程式：$apps，中止"; exit 1; }

failed=""
for b in $BUDGETS; do
  for q in $QUANTS; do
    label="$(echo "${q#UD-}" | tr 'A-Z' 'a-z' | tr -d '_')_b$b"
    log "開始 $label"
    if "$HERE/run_e4.sh" --model "Qwen3.8-27B-$q.gguf" --budget "$b" --label "$label" --reps "$REPS" \
        --out "$ROOT/$label" --extra "-fit off"; then
      log "完成 $label"
    else
      log "失敗 $label（重跑同樣指令會接續）"; failed="$failed $label"
    fi
  done
done
log "失敗條件：${failed:-無}"
[ -z "$failed" ]
