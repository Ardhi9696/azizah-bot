#!/system/bin/sh

# Controller tmux untuk web monitor (root). Session: monitor
# Usage: sh boot-web.sh start|stop|restart|status

TMUX="/data/data/com.termux/files/usr/bin/tmux"
NODE="/data/data/com.termux/files/usr/bin/node"
BOT_DIR="/data/data/com.termux/files/home/Azizah-Bot"
SESSION="monitor"

start_monitor() {
  su -c "$TMUX has-session -t $SESSION 2>/dev/null"
  if [ $? -eq 0 ]; then
    echo "Monitor already running in tmux session '$SESSION'."
    return 0
  fi
  echo "Starting monitor (root) in tmux session '$SESSION'..."
  su -c "$TMUX new-session -d -s $SESSION \"cd $BOT_DIR && $NODE monitor/server.js\""
}

stop_monitor() {
  su -c "$TMUX has-session -t $SESSION 2>/dev/null"
  if [ $? -ne 0 ]; then
    echo "Monitor session '$SESSION' not running."
    return 0
  fi
  echo "Stopping monitor session '$SESSION'..."
  su -c "$TMUX kill-session -t $SESSION"
}

case "$1" in
  start) start_monitor ;;
  stop) stop_monitor ;;
  restart) stop_monitor; sleep 1; start_monitor ;;
  status)
    su -c "$TMUX has-session -t $SESSION 2>/dev/null"
    if [ $? -eq 0 ]; then
      echo "Monitor is running in tmux session '$SESSION' (root)."
    else
      echo "Monitor is not running."
    fi
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status}"
    exit 1
    ;;
esac
