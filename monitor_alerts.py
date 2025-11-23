# monitor_alerts.py
import time
import threading

from monitor_config import config
from monitor_stats import get_stats
from monitor_telegram import send_telegram_message

ALERT_COOLDOWN_SEC = 300  # 5 menit
_last_ram_alert = 0
_last_temp_alert = 0


def alert_monitor_loop():
    """Loop background: cek RAM & suhu, kirim alert ke Telegram."""
    global _last_ram_alert, _last_temp_alert
    while True:
        try:
            if not config.get("alerts_enabled", True):
                time.sleep(60)
                continue

            cpu, ram, disk, uptime_sec, temp_val = get_stats()
            now = time.time()

            # RAM ALERT
            if ram is not None and uptime_sec is not None:
                ram_percent = ram.percent
                if (
                    ram_percent >= config.get("ram_threshold", 90)
                    and now - _last_ram_alert > ALERT_COOLDOWN_SEC
                ):
                    msg = (
                        "🚨 <b>STB RAM ALERT</b>\n\n"
                        f"💾 RAM: <b>{ram_percent:.1f}%</b>\n"
                        f"⏱ Uptime: {uptime_sec/3600:.2f} jam\n"
                    )
                    send_telegram_message(msg)
                    _last_ram_alert = now

            # TEMP ALERT
            if temp_val is not None and uptime_sec is not None:
                if (
                    temp_val >= config.get("temp_threshold", 75)
                    and now - _last_temp_alert > ALERT_COOLDOWN_SEC
                ):
                    msg = (
                        "🔥 <b>STB TEMPERATURE ALERT</b>\n\n"
                        f"🌡 Suhu CPU: <b>{temp_val:.1f}°C</b>\n"
                        f"⏱ Uptime: {uptime_sec/3600:.2f} jam\n"
                    )
                    send_telegram_message(msg)
                    _last_temp_alert = now

        except Exception as e:
            print("alert_monitor_loop error:", e)

        time.sleep(60)


def start_alert_monitor():
    """Dipanggil sekali dari main untuk start thread alert."""
    t = threading.Thread(target=alert_monitor_loop, daemon=True)
    t.start()
