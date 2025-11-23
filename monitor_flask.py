from flask import Flask, Response, redirect, request, url_for
import os, time, json, threading
import psutil
import urllib.parse
import urllib.request
import subprocess

app = Flask(__name__)

# ==========================
# KONFIGURASI UMUM
# ==========================

TERMUX_HOME = "/data/data/com.termux/files/home"
TMUX_BIN = "/data/data/com.termux/files/usr/bin/tmux"

BOT_DIR = f"{TERMUX_HOME}/Azizah-Bot"
BOT_COMMAND = "python3 run.py"   # kalau main file-nya lain, ganti di sini

# 🔔 TELEGRAM UNTUK ALERT
TELEGRAM_BOT_TOKEN = "7777245606:AAEo9fS7AH7Of9DSngYPEtfECS1Hbmh2j9Q"
TELEGRAM_CHAT_ID = "7088612068"

# File config untuk simpan toggle dll
CONFIG_FILE = f"{TERMUX_HOME}/monitor_config.json"

DEFAULT_CONFIG = {
    "alerts_enabled": True,
    "ram_threshold": 90,   # persen
    "temp_threshold": 75,  # derajat C
}

# variabel runtime alert
last_ram_alert = 0
last_temp_alert = 0
ALERT_COOLDOWN_SEC = 300  # 5 menit

# ==========================
# UTIL: CONFIG
# ==========================

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                cfg = DEFAULT_CONFIG.copy()
                cfg.update(data)
                return cfg
        except Exception as e:
            print("Config load error:", e)
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f)
    except Exception as e:
        print("Config save error:", e)

config = load_config()

# ==========================
# UTIL: TEMPERATUR & STATS
# ==========================

def get_cpu_temp_value():
    paths = [
        "/sys/class/thermal/thermal_zone0/temp",
        "/sys/devices/virtual/thermal/thermal_zone0/temp"
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                t = int(open(p).read()) / 1000
                return float(f"{t:.1f}")
            except Exception:
                pass
    return None

def get_stats():
    # CPU
    try:
        cpu = psutil.cpu_percent()
    except Exception:
        cpu = None

    # RAM
    try:
        ram = psutil.virtual_memory()
    except Exception:
        ram = None

    # Disk
    try:
        disk = psutil.disk_usage('/')
    except Exception:
        disk = None

    # Uptime
    try:
        uptime_sec = time.time() - psutil.boot_time()
    except Exception:
        uptime_sec = None

    temp_val = get_cpu_temp_value()
    return cpu, ram, disk, uptime_sec, temp_val

# ==========================
# UTIL: TELEGRAM
# ==========================

def send_telegram_message(text: str):
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

# ==========================
# UTIL: KONTROL BOT (tmux)
# ==========================

def bot_is_running():
    try:
        proc = subprocess.run(
            [TMUX_BIN, "has-session", "-t", "telebot"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return proc.returncode == 0
    except Exception as e:
        print("bot_is_running error:", e)
        return False

def bot_start():
    if bot_is_running():
        return "Bot sudah berjalan."

    try:
        cmd = f"cd {BOT_DIR} && {BOT_COMMAND}"
        subprocess.Popen(
            [TMUX_BIN, "new-session", "-d", "-s", "telebot", cmd],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return "Bot berhasil dimulai."
    except Exception as e:
        print("bot_start error:", e)
        return f"Gagal start bot: {e}"

def bot_stop():
    if not bot_is_running():
        return "Bot sudah dalam keadaan mati."

    try:
        subprocess.run(
            [TMUX_BIN, "kill-session", "-t", "telebot"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return "Bot berhasil dihentikan."
    except Exception as e:
        print("bot_stop error:", e)
        return f"Gagal stop bot: {e}"

def bot_restart():
    msg1 = bot_stop()
    msg2 = bot_start()
    return msg1 + " " + msg2

# ==========================
# BACKGROUND ALERT LOOP
# ==========================

def alert_monitor_loop():
    global last_ram_alert, last_temp_alert, config
    while True:
        try:
            if not config.get("alerts_enabled", True):
                time.sleep(60)
                continue

            cpu, ram, disk, uptime_sec, temp_val = get_stats()
            now = time.time()

            # RAM ALERT
            if ram is not None:
                ram_percent = ram.percent
                if (
                    ram_percent >= config.get("ram_threshold", 90)
                    and now - last_ram_alert > ALERT_COOLDOWN_SEC
                ):
                    msg = (
                        "🚨 <b>STB RAM ALERT</b>\n\n"
                        f"💾 RAM: <b>{ram_percent:.1f}%</b>\n"
                        f"⏱ Uptime: {uptime_sec/3600:.2f} jam\n"
                    )
                    send_telegram_message(msg)
                    last_ram_alert = now

            # TEMP ALERT
            if temp_val is not None:
                if (
                    temp_val >= config.get("temp_threshold", 75)
                    and now - last_temp_alert > ALERT_COOLDOWN_SEC
                ):
                    msg = (
                        "🔥 <b>STB TEMPERATURE ALERT</b>\n\n"
                        f"🌡 Suhu CPU: <b>{temp_val:.1f}°C</b>\n"
                        f"⏱ Uptime: {uptime_sec/3600:.2f} jam\n"
                    )
                    send_telegram_message(msg)
                    last_temp_alert = now

        except Exception as e:
            print("alert_monitor_loop error:", e)

        time.sleep(60)

# start background thread
threading.Thread(target=alert_monitor_loop, daemon=True).start()

# ==========================
# ROUTES
# ==========================

@app.route("/")
def dashboard():
    cpu, ram, disk, uptime_sec, temp_val = get_stats()
    alerts_enabled = config.get("alerts_enabled", True)
    ram_th = config.get("ram_threshold", 90)
    temp_th = config.get("temp_threshold", 75)
    bot_running = bot_is_running()

    # CPU display
    if cpu is None:
        cpu_display = "N/A (no access)"
    else:
        cpu_display = f"{cpu:.1f}%"

    # Temp display
    if temp_val is None:
        temp_display = "Not available"
    else:
        temp_display = f"{temp_val:.1f}°C"

    # RAM display
    if ram is not None:
        ram_total = f"{ram.total/1e9:.2f} GB"
        ram_used = f"{ram.used/1e9:.2f} GB"
        ram_percent = f"{ram.percent:.1f}%"
    else:
        ram_total = ram_used = ram_percent = "N/A"

    # Disk display
    if disk is not None:
        disk_total = f"{disk.total/1e9:.2f} GB"
        disk_used = f"{disk.used/1e9:.2f} GB"
        disk_percent = f"{disk.percent:.1f}%"
    else:
        disk_total = disk_used = disk_percent = "N/A"

    # Uptime display
    if uptime_sec is not None:
        uptime_display = f"{uptime_sec/3600:.2f} jam"
    else:
        uptime_display = "N/A"

    bot_status_text = "🟢 Running" if bot_running else "🔴 Stopped"

    html = f"""
    <html>
    <head>
        <meta http-equiv="refresh" content="5">
        <title>STB Monitor</title>
        <style>
            body {{
                font-family: system-ui, -apple-system, BlinkMacSystemFont, Arial;
                padding: 20px;
                background: #020617;
                color: #e5e7eb;
            }}
            .card {{
                background: #020617;
                border-radius: 12px;
                padding: 16px 20px;
                margin-bottom: 16px;
                box-shadow: 0 10px 25px rgba(0,0,0,0.4);
                border: 1px solid #1f2937;
            }}
            h1 {{
                margin-bottom: 20px;
            }}
            h2 {{
                margin-top: 0;
                margin-bottom: 8px;
            }}
            .muted {{
                color: #9ca3af;
                font-size: 13px;
            }}
            .btn {{
                display: inline-block;
                padding: 6px 12px;
                margin-right: 6px;
                margin-top: 4px;
                border-radius: 6px;
                text-decoration: none;
                font-size: 14px;
                border: 1px solid #374151;
                background: #111827;
                color: #e5e7eb;
            }}
            .btn:hover {{
                background: #1f2937;
            }}
            .btn-danger {{
                border-color: #b91c1c;
                color: #fecaca;
            }}
            .btn-danger:hover {{
                background: #7f1d1d;
            }}
            .tag-on {{
                color: #bbf7d0;
            }}
            .tag-off {{
                color: #fecaca;
            }}
        </style>
    </head>
    <body>
        <h1>📊 STB Monitoring Dashboard</h1>

        <div class="card">
            <h2>⚙️ CPU</h2>
            <p><b>Usage:</b> {cpu_display}</p>
            <p><b>Temperature:</b> {temp_display}</p>
            <p class="muted">Jika tertulis N/A, Android membatasi akses /proc.</p>
        </div>

        <div class="card">
            <h2>🧠 Memory</h2>
            <p><b>Total:</b> {ram_total}</p>
            <p><b>Used:</b> {ram_used}</p>
            <p><b>Percent:</b> {ram_percent}</p>
        </div>

        <div class="card">
            <h2>💾 Storage</h2>
            <p><b>Total:</b> {disk_total}</p>
            <p><b>Used:</b> {disk_used}</p>
            <p><b>Percent:</b> {disk_percent}</p>
        </div>

        <div class="card">
            <h2>⏱️ Uptime</h2>
            <p>{uptime_display}</p>
            <p class="muted">Auto refresh setiap 5 detik</p>
        </div>

        <div class="card">
            <h2>🤖 Bot Control</h2>
            <p><b>Status:</b> {bot_status_text}</p>
            <a class="btn" href="/bot/start">Start</a>
            <a class="btn btn-danger" href="/bot/stop">Stop</a>
            <a class="btn" href="/bot/restart">Restart</a>
        </div>

        <div class="card">
            <h2>🔔 Alerts</h2>
            <p>
              Status:
              {"<span class='tag-on'>🟢 ON</span>" if alerts_enabled else "<span class='tag-off'>🔴 OFF</span>"}
            </p>
            <p>RAM threshold: <b>{ram_th}%</b><br>
               Temp threshold: <b>{temp_th}°C</b></p>
            <p>
            {"<a class='btn btn-danger' href='/alerts/toggle?enable=0'>Matikan Alerts</a>" if alerts_enabled
              else "<a class='btn' href='/alerts/toggle?enable=1'>Nyalakan Alerts</a>"}
            </p>
            <p class="muted">Notifikasi dikirim ke Telegram jika RAM &ge; threshold atau suhu &ge; threshold (cooldown 5 menit).</p>
        </div>

    </body>
    </html>
    """
    return Response(html, mimetype="text/html")

# ---- routes kontrol bot ----

@app.route("/bot/start")
def route_bot_start():
    msg = bot_start()
    print(msg)
    return redirect(url_for("dashboard"))

@app.route("/bot/stop")
def route_bot_stop():
    msg = bot_stop()
    print(msg)
    return redirect(url_for("dashboard"))

@app.route("/bot/restart")
def route_bot_restart():
    msg = bot_restart()
    print(msg)
    return redirect(url_for("dashboard"))

# ---- toggle alerts ----

@app.route("/alerts/toggle")
def route_alerts_toggle():
    enable = request.args.get("enable", "1")
    config["alerts_enabled"] = enable == "1"
    save_config(config)
    return redirect(url_for("dashboard"))

# ==========================
# MAIN
# ==========================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
