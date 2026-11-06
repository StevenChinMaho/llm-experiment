#!/usr/bin/env bash
# E4 批次：停常駐容器 → 依序跑「量化 × 思考預算」→ 結束時一定把常駐容器啟動回來。中斷後用同樣指令重跑會接續。
#
# 用法：MODELS=/llama/models run_e4_batch.sh --root ~/e4/e4_svr --quants "UD-Q2_K_XL UD-IQ3_XXS" \
#         --budgets "1024 4096 16384" --reps 2 [--stop llama] [--until 12:50] \
#         [--suffix _mtp4 --extra "--spec-type draft-mtp --spec-draft-model /models/MTP/mtp-Qwen3.8-27B-Q4_0.gguf --spec-draft-n-max 4"]
# 短預算排前面，先拿到完整的 1024、4096，最耗時的 16384 放最後。
# --until 是今天的截止時間：時間一到就中止當下那題（已完成的題目都保留），下次用同樣指令接續。
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT="" QUANTS="" BUDGETS="1024 4096 16384" REPS=2 STOP="" UNTIL="" SUFFIX="" EXTRA=""
while [ $# -gt 0 ]; do
  case "$1" in
    --root) ROOT=$2; shift 2 ;;
    --quants) QUANTS=$2; shift 2 ;;
    --budgets) BUDGETS=$2; shift 2 ;;
    --reps) REPS=$2; shift 2 ;;
    --stop) STOP=$2; shift 2 ;;
    --until) UNTIL=$2; shift 2 ;;
    --suffix) SUFFIX=$2; shift 2 ;;
    --extra) EXTRA=$2; shift 2 ;;
    *) echo "未知參數 $1" >&2; exit 2 ;;
  esac
done
[ -n "$ROOT" ] && [ -n "$QUANTS" ] || { echo "需要 --root --quants" >&2; exit 2; }
mkdir -p "$ROOT"
LOG="$ROOT/batch.log"
log() { echo "$(date -Is) $*" | tee -a "$LOG"; }
DEADLINE=""
if [ -n "$UNTIL" ]; then   # 先檢查再動常駐容器，時間已過時什麼都不改
  DEADLINE=$(date -d "$UNTIL" +%s) || exit 2
  [ "$DEADLINE" -gt "$(date +%s)" ] || { log "截止時間 $UNTIL 已過，中止"; exit 2; }
  log "今天的截止時間：$UNTIL"
fi
restore() { if [ -n "$STOP" ]; then docker start "$STOP" >/dev/null && log "已重新啟動 $STOP"; fi; log BATCH_END; }
trap restore EXIT
trap 'log 收到中止訊號; exit 130' INT TERM HUP

if [ -n "$STOP" ]; then log "停止常駐容器 $STOP"; docker stop "$STOP" >/dev/null; sleep 5; fi
apps=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader)
[ -z "$apps" ] || { log "GPU 上還有其他程式：$apps，中止"; exit 1; }

failed=""
for b in $BUDGETS; do
  for q in $QUANTS; do
    label="$(echo "${q#UD-}" | tr 'A-Z' 'a-z' | tr -d '_')_b$b$SUFFIX"
    limit=()
    if [ -n "$DEADLINE" ]; then
      left=$((DEADLINE - $(date +%s)))
      [ "$left" -gt 0 ] || { log "到達截止時間，下次接續"; exit 0; }
      limit=(timeout --signal=TERM --kill-after=60 "$left")
    fi
    log "開始 $label"
    "${limit[@]}" "$HERE/run_e4.sh" --model "Qwen3.8-27B-$q.gguf" --budget "$b" --label "$label" --reps "$REPS" \
        --out "$ROOT/$label" --extra "-fit off $EXTRA"
    rc=$?
    case "$rc" in
      0) log "完成 $label" ;;
      124|137|143) log "到達截止時間，$label 未完成，下次接續"; exit 0 ;;
      *) log "失敗 $label（重跑同樣指令會接續）"; failed="$failed $label" ;;
    esac
  done
done
log "失敗條件：${failed:-無}"
[ -z "$failed" ]
