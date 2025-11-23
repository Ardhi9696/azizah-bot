#!/system/bin/sh
su -c "/data/data/com.termux/files/usr/bin/tmux new-session -d -s monitor \
'cd /data/data/com.termux/files/home/Azizah-Bot && /data/data/com.termux/files/usr/bin/node monitor_server.js'"
