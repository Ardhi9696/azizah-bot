# monitor_telegram.py
import urllib.parse
import urllib.request

from monitor_config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def send_telegram_message(text: str):
    """Kirim pesan ke Telegram (monitoring bot)."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials not set, skip sending.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }
    try:
        encoded = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(url, data=encoded)
        with urllib.request.urlopen(req, timeout=10) as resp:
            print("Telegram response:", resp.read().decode("utf-8"))
    except Exception as e:
        print("Error sending Telegram message:", e)
