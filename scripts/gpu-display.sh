#!/usr/bin/env bash
# 切換 NVIDIA 獨顯的螢幕輸出（主力機 Ubuntu 用）。
#
# 原理：對 /sys/class/drm/<接頭>/status 寫入 off，強制把接頭當成「已拔線」；寫入 detect 恢復自動偵測。
# 不用重開機，重開機後自動恢復成接上的狀態。接頭名稱每次開機可能改變，所以每次都重新偵測。
#
# 用法：
#   gpu-display          互動選單
#   gpu-display status   只顯示狀態
#   gpu-display off      關閉獨顯輸出（需要 sudo）
#   gpu-display on       恢復獨顯輸出（需要 sudo）
set -euo pipefail

NVIDIA=0x10de

vendor_name() {
  case "$1" in
    0x10de) echo "NVIDIA 獨顯" ;;
    0x1002) echo "AMD 內顯" ;;
    0x8086) echo "Intel 內顯" ;;
    *) echo "未知($1)" ;;
  esac
}

# 每行輸出：接頭路徑 vendor 偵測狀態 啟用狀態
connectors() {
  local c n card
  for c in /sys/class/drm/card*-*; do
    [ -f "$c/status" ] || continue
    n=${c##*/}
    card=${n%%-*}
    printf '%s %s %s %s\n' "$c" \
      "$(cat "/sys/class/drm/$card/device/vendor" 2>/dev/null || echo '?')" \
      "$(cat "$c/status")" \
      "$(cat "$c/enabled" 2>/dev/null || echo '?')"
  done
}

show_status() {
  echo "== 有接螢幕的接頭 =="
  local found=0 path v s e
  while read -r path v s e; do
    [ "$s" = connected ] || continue
    found=1
    printf '  %-18s %-12s %s\n' "${path##*/}" "$(vendor_name "$v")" "$( [ "$e" = enabled ] && echo '輸出中' || echo '未輸出')"
  done < <(connectors)
  [ "$found" = 1 ] || echo "  （沒有）"
  if command -v nvidia-smi >/dev/null; then
    echo "== nvidia-smi =="
    nvidia-smi --query-gpu=display_active,memory.used,power.draw --format=csv,noheader \
      | awk -F', ' '{printf "  顯示輸出：%s　VRAM：%s　功耗：%s\n", $1, $2, $3}'
  fi
}

turn_off() {
  local path v s e n=0
  while read -r path v s e; do
    [ "$v" = "$NVIDIA" ] && [ "$s" = connected ] || continue
    echo "關閉 ${path##*/} ..."
    sudo sh -c "echo off > '$path/status'"
    n=$((n + 1))
  done < <(connectors)
  if [ "$n" = 0 ]; then
    echo "獨顯上沒有正在連接的螢幕，不需要關閉。"
  else
    echo "完成。注意：本機螢幕上的文字 console 原本在獨顯上，現在會看不到；SSH 不受影響。"
    echo "想讓 console 改到內顯顯示：sudo apt install fbset && sudo con2fbmap 1 1"
  fi
}

turn_on() {
  local path v s e n=0
  while read -r path v s e; do
    [ "$v" = "$NVIDIA" ] || continue
    sudo sh -c "echo detect > '$path/status'"
    n=$((n + 1))
  done < <(connectors)
  echo "已將 $n 個獨顯接頭恢復為自動偵測（有接線的會重新輸出）。"
}

pause_then_status() { sleep 2; echo; show_status; }

case "${1:-menu}" in
  status) show_status ;;
  off) turn_off; pause_then_status ;;
  on) turn_on; pause_then_status ;;
  menu)
    show_status
    echo
    echo "1) 關閉獨顯輸出"
    echo "2) 恢復獨顯輸出"
    echo "q) 離開"
    read -rp "選擇：" ans
    case "$ans" in
      1) turn_off; pause_then_status ;;
      2) turn_on; pause_then_status ;;
      *) echo "離開，未做任何變更。" ;;
    esac
    ;;
  *) echo "用法：$0 [status|off|on]" >&2; exit 2 ;;
esac
