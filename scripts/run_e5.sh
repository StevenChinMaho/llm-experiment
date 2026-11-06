#!/usr/bin/env bash
# E5 計算工具：同一批題目（e5_questions 12 題＋E8、H7）比較無工具與有工具，結束時一定把常駐容器啟動回來。
# 中斷後用同樣指令重跑會接續。需要同資料夾有 run_e4.sh；題目與評估腳本從 ~/qwen-eval/ 讀。
#
# 用法：MODELS=/llama/models run_e5.sh --root ~/e5/e5_svr --model Qwen3.8-27B-UD-IQ3_XXS.gguf --budget 4096 --reps 2 [--stop llama]
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT="" MODEL="" BUDGET=4096 REPS=2 STOP=""
while [ $# -gt 0 ]; do
  case "$1" in
    --root) ROOT=$2; shift 2 ;;
    --model) MODEL=$2; shift 2 ;;
    --budget) BUDGET=$2; shift 2 ;;
    --reps) REPS=$2; shift 2 ;;
    --stop) STOP=$2; shift 2 ;;
    *) echo "未知參數 $1" >&2; exit 2 ;;
  esac
done
[ -n "$ROOT" ] && [ -n "$MODEL" ] || { echo "需要 --root --model" >&2; exit 2; }
mkdir -p "$ROOT"
LOG="$ROOT/batch.log"
log() { echo "$(date -Is) $*" | tee -a "$LOG"; }
restore() { if [ -n "$STOP" ]; then docker start "$STOP" >/dev/null && log "已重新啟動 $STOP"; fi; log BATCH_END; }
trap restore EXIT
trap 'log 收到中止訊號; exit 130' INT TERM HUP

if [ -n "$STOP" ]; then log "停止常駐容器 $STOP"; docker stop "$STOP" >/dev/null; sleep 5; fi
apps=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader)
[ -z "$apps" ] || { log "GPU 上還有其他程式：$apps，中止"; exit 1; }

QS="eval/e5_questions.json eval/questions.json:easy eval/questions.json:hard"
IDS="T1 T2 T3 T4 T5 T6 T7 T8 T9 T10 T11 T12 E8 H7"
quant=$(echo "${MODEL#Qwen3.8-27B-UD-}" | sed 's/\.gguf$//' | tr 'A-Z' 'a-z' | tr -d '_')
failed=""
for arm in notool tool; do
  label="${quant}_b${BUDGET}_$arm"
  args="--ids $IDS"
  [ "$arm" = tool ] && args="$args --tool calculator"
  log "開始 $label"
  if "$HERE/run_e4.sh" --model "$MODEL" --budget "$BUDGET" --label "$label" --reps "$REPS" --out "$ROOT/$label" \
      --questions "$QS" --extra "-fit off" --eval-extra "$args"; then
    log "完成 $label"
  else
    log "失敗 $label（重跑同樣指令會接續）"; failed="$failed $label"
  fi
done
log "失敗條件：${failed:-無}"
[ -z "$failed" ]
