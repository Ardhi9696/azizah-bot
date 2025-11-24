#!/data/data/com.termux/files/usr/bin/sh

# Simple tmux controller for the Telegram bot (session: telebot)
# Usage: sh boot-stb.sh start|stop|restart|status

TMUX="/data/data/com.termux/files/usr/bin/tmux"
PYTHON="/data/data/com.termux/files/usr/bin/python3"
BOT_DIR="/data/data/com.termux/files/home/Azizah-Bot"
SESSION="telebot"

start_bot() {
  $TMUX has-session -t "$SESSION" 2>/dev/null
  if [ $? -eq 0 ]; then
    echo "Bot already running in tmux session '$SESSION'."
    return 0
  fi
  echo "Starting bot in tmux session '$SESSION'..."
  $TMUX new-session -d -s "$SESSION" "cd $BOT_DIR && git pull && $PYTHON run.py"
}

stop_bot() {
  $TMUX has-session -t "$SESSION" 2>/dev/null
  if [ $? -ne 0 ]; then
    echo "Bot session '$SESSION' not running."
    return 0
  fi
  echo "Stopping bot session '$SESSION'..."
  $TMUX kill-session -t "$SESSION"
}

case "$1" in
  start) start_bot ;;
  stop) stop_bot ;;
  restart) stop_bot; sleep 1; start_bot ;;
  status)
    $TMUX has-session -t "$SESSION" 2>/dev/null
    if [ $? -eq 0 ]; then
      echo "Bot is running in tmux session '$SESSION'."
    else
      echo "Bot is not running."
    fi
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status}"
    exit 1
    ;;
esac
