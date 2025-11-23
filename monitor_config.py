# monitor_config.py
import os
import json

# ===== PATH DASAR & KONFIGUM ==========
TERMUX_HOME = "/data/data/com.termux/files/home"
TMUX_BIN    = "/data/data/com.termux/files/usr/bin/tmux"

# Folder & command bot kamu
BOT_DIR      = f"{TERMUX_HOME}/Azizah-Bot"
BOT_COMMAND  = "python3 run.py"   # kalau entry-nya bot.py atau lain, ganti di sini

# 🔔 TELEGRAM UNTUK ALERT
TELEGRAM_BOT_TOKEN = "7777245606:AAEo9fS7AH7Of9DSngYPEtfECS1Hbmh2j9Q"
TELEGRAM_CHAT_ID   = "7088612068"

# File config alert (toggle, threshold, dll)
CONFIG_FILE = os.path.join(TERMUX_HOME, "monitor_config.json")

DEFAULT_CONFIG = {
    "alerts_enabled": True,
    "ram_threshold": 90,   # persen
    "temp_threshold": 75,  # derajat C
}


def load_config():
    """Load config dari file, merge dengan DEFAULT_CONFIG."""
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
    """Simpan config ke file JSON."""
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f)
    except Exception as e:
        print("Config save error:", e)


# global shared config dict
config = load_config()
