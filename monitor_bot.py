# monitor_bot.py
import subprocess
from monitor_config import TMUX_BIN, BOT_DIR, BOT_COMMAND

SESSION_NAME = "telebot"  # nama tmux session untuk bot


def bot_is_running():
    """Cek apakah tmux session bot masih ada."""
    try:
        proc = subprocess.run(
            [TMUX_BIN, "has-session", "-t", SESSION_NAME],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        running = proc.returncode == 0
        print(f"[BOT] bot_is_running={running}")
        return running
    except Exception as e:
        print("[BOT] bot_is_running error:", e)
        return False


def bot_start():
    """Start bot di dalam tmux (tidak blok Flask)."""
    if bot_is_running():
        msg = "Bot sudah berjalan."
        print("[BOT]", msg)
        return msg

    try:
        cmd = f"cd {BOT_DIR} && {BOT_COMMAND}"
        print("[BOT] START cmd:", cmd)

        subprocess.Popen(
            [TMUX_BIN, "new-session", "-d", "-s", SESSION_NAME, cmd],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        msg = "Bot berhasil dimulai (tmux session dibuat)."
        print("[BOT]", msg)
        return msg
    except Exception as e:
        msg = f"Gagal start bot: {e}"
        print("[BOT] bot_start error:", e)
        return msg


def bot_stop():
    """Stop bot = kill tmux session."""
    if not bot_is_running():
        msg = "Bot sudah dalam keadaan mati."
        print("[BOT]", msg)
        return msg

    try:
        print("[BOT] STOP session:", SESSION_NAME)
        subprocess.run(
            [TMUX_BIN, "kill-session", "-t", SESSION_NAME],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        msg = "Bot berhasil dihentikan (tmux session di-kill)."
        print("[BOT]", msg)
        return msg
    except Exception as e:
        msg = f"Gagal stop bot: {e}"
        print("[BOT] bot_stop error:", e)
        return msg


def bot_restart():
    """Restart bot = stop lalu start lagi."""
    msg1 = bot_stop()
    msg2 = bot_start()
    msg = msg1 + " " + msg2
    print("[BOT] RESTART:", msg)
    return msg
