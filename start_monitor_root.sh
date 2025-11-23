#!/system/bin/sh
su -c "/data/data/com.termux/files/usr/bin/tmux new-session -d -s monitor \
'cd /data/data/com.termux/files/home/Azizah-Bot && /data/data/com.termux/files/usr/bin/python3 monitor_flask.py'"
