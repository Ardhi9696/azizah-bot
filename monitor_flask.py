# monitor_flask.py
from flask import Flask, Response, redirect, request, url_for

from monitor_config import config, save_config
from monitor_stats import get_stats
from monitor_bot import bot_is_running, bot_start, bot_stop, bot_restart
from monitor_alerts import start_alert_monitor

app = Flask(__name__)

# Start background alert loop
start_alert_monitor()


@app.route("/")
def dashboard():
    cpu, ram, disk, uptime_sec, temp_val = get_stats()
    alerts_enabled = config.get("alerts_enabled", True)
    ram_th = config.get("ram_threshold", 90)
    temp_th = config.get("temp_threshold", 75)
    bot_running = bot_is_running()

    # CPU display
    cpu_display = "N/A (no access)" if cpu is None else f"{cpu:.1f}%"

    # Temp display
    temp_display = "Not available" if temp_val is None else f"{temp_val:.1f}°C"

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


@app.route("/alerts/toggle")
def route_alerts_toggle():
    enable = request.args.get("enable", "1")
    config["alerts_enabled"] = enable == "1"
    save_config(config)
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    # Flask tetap run di root (lewat su -c) & tmux yang ngejaga di luar
    app.run(host="0.0.0.0", port=8000)
