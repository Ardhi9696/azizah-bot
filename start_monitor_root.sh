#!/system/bin/sh

TMUX="/data/data/com.termux/files/usr/bin/tmux"
NODE="/data/data/com.termux/files/usr/bin/node"
BOT_DIR="/data/data/com.termux/files/home/Azizah-Bot"

# Cari socket tmux milik user biasa (untuk kontrol bot)
TMUX_SOCKET=$($TMUX display-message -p '#{socket_path}' 2>/dev/null | head -n 1)
[ -z "$TMUX_SOCKET" ] && TMUX_SOCKET=$(find /data/data/com.termux/files/usr -type s -name default 2>/dev/null | head -n 1)

# Jalankan monitor sebagai root di tmux "monitor", sambil meneruskan TMUX_SOCKET supaya bisa kontrol bot
su -c "$TMUX has-session -t monitor 2>/dev/null || TMUX_SOCKET=$TMUX_SOCKET $TMUX new-session -d -s monitor \"cd $BOT_DIR && TMUX_SOCKET=$TMUX_SOCKET $NODE monitor_server.js\""
