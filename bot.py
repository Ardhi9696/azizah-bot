import os
import logging
from telegram import Update
from logging.handlers import TimedRotatingFileHandler
from colorlog import ColoredFormatter
from dotenv import load_dotenv
from telegram.ext import (
    Application,
    ContextTypes,
)

from handlers.register_handlers import register_handlers


logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Formatter
color_formatter = ColoredFormatter(
    "%(log_color)s%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    log_colors={
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold_red",
    },
)

file_formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S"
)

# Hapus handler lama
if logger.hasHandlers():
    logger.handlers.clear()

# === Buat folder logs/ jika belum ada ===
try:
    os.makedirs("logs", exist_ok=True)
except Exception as e:
    print(f"[Logger] ⚠️ Gagal membuat folder logs/: {e}")
    # Fallback ke folder saat ini
    LOG_PATH = "log.txt"
    ERROR_LOG_PATH = "error.log"
else:
    LOG_PATH = "logs/log.txt"
    ERROR_LOG_PATH = "logs/error.log"

# Log ke file harian
file_handler = TimedRotatingFileHandler(
    LOG_PATH, when="midnight", backupCount=7, encoding="utf-8"
)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Log error khusus
error_handler = logging.FileHandler(ERROR_LOG_PATH, mode="a", encoding="utf-8")
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(file_formatter)
logger.addHandler(error_handler)

# Log ke terminal
console_handler = logging.StreamHandler()
console_handler.setFormatter(color_formatter)
logger.addHandler(console_handler)

# Matikan log verbose dari lib lain
for name in [
    "httpx",
    "telegram.vendor.ptb_urllib3.urllib3",
    "telegram.ext._application",
]:
    logging.getLogger(name).setLevel(logging.WARNING)


def mask_token(token: str) -> str:
    if not token or len(token) < 10:
        return "[TOKEN INVALID]"
    return token[:5] + "****" + token[-3:]


# ===== Load .env =====
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    logger.critical("❌ BOT_TOKEN tidak ditemukan di .env. Keluar.")
    exit(1)


async def error_handler_function(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error("🚨 Terjadi error saat memproses update:", exc_info=context.error)


# ===== Main Program =====
def main():
    application = Application.builder().token(TOKEN).build()
    application.add_error_handler(error_handler_function)

    # === Register Handlers ===
    register_handlers(application)

    logger.info("✅ Azizah_Bot aktif dan siap digunakan.")
    application.run_polling()


if __name__ == "__main__":
    main()
