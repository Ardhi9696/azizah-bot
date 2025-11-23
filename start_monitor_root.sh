#!/system/bin/sh

TMUX="/data/data/com.termux/files/usr/bin/tmux"
NODE="/data/data/com.termux/files/usr/bin/node"
BOT_DIR="/data/data/com.termux/files/home/Azizah-Bot"

# Jalankan monitor sebagai root di tmux "monitor" (akses sensor root)
su -c "$TMUX has-session -t monitor 2>/dev/null || $TMUX new-session -d -s monitor \"cd $BOT_DIR && $NODE monitor_server.js\""
