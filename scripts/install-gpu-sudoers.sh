#!/bin/sh
# 主力機 Ubuntu 只需執行一次：sudo sh install-gpu-sudoers.sh
# 讓實驗帳號不用密碼就能做三件事：切換 NVIDIA 獨顯輸出、重新開機（重開後預設回 Windows）、關機（時段收工用）。
# 移除：sudo rm /etc/sudoers.d/gpu-display /usr/local/sbin/gpu-display-root
set -eu
[ "$(id -u)" = 0 ] || { echo "請用 sudo 執行" >&2; exit 1; }
USER_NAME=ubuntukururinpa
HELPER=/usr/local/sbin/gpu-display-root

# 輔助程式放在只有 root 能改的位置，只接受 off 或 on，其他參數一律拒絕
TMP=$(mktemp)
cat > "$TMP" <<'EOF'
#!/bin/sh
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
case "${1:-}" in
  off) act=off; want=connected ;;
  on) act=detect; want=disconnected ;;
  *) echo "用法：gpu-display-root off|on" >&2; exit 2 ;;
esac
for c in /sys/class/drm/card*-*; do
  [ -f "$c/status" ] || continue
  n=${c##*/}
  card=${n%%-*}
  [ "$(cat "/sys/class/drm/$card/device/vendor")" = 0x10de ] || continue
  if [ "$(cat "$c/status")" = "$want" ]; then
    echo "$act" > "$c/status"
    echo "$n: $act"
  fi
done
EOF
install -o root -g root -m 755 "$TMP" "$HELPER"

# 先用 visudo 檢查語法，通過才安裝，避免寫壞 sudo 設定
cat > "$TMP" <<EOF
$USER_NAME ALL=(root) NOPASSWD: $HELPER off, $HELPER on, /usr/bin/systemctl reboot, /usr/bin/systemctl poweroff
EOF
visudo -cf "$TMP"
install -o root -g root -m 440 "$TMP" /etc/sudoers.d/gpu-display
rm -f "$TMP"
echo "安裝完成：$(cat /etc/sudoers.d/gpu-display)"
