import sys
import subprocess
import platform
import shutil
import os
from dotenv import load_dotenv


REQUIRED_PYTHON = (3, 10)
REQUIREMENTS_FILE = "requirements.txt"
BOT_FILE = "bot.py"


def check_env():
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("[!] BOT_TOKEN belum diatur di .env")
        sys.exit(1)


def check_python_version():
    current_version = sys.version_info
    print(f"[✔] Python Version: {sys.version.split()[0]}")
    if current_version < REQUIRED_PYTHON:
        print(f"[!] Python {REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]}+ diperlukan.")
        sys.exit(1)


def check_os():
    os_name = platform.system()
    print(f"[✔] OS Terdeteksi: {os_name}")
    return os_name


def check_pip():
    if not shutil.which("pip"):
        print("[!] pip tidak ditemukan di PATH. Install Python dengan pip.")
        sys.exit(1)


def install_requirements():
    if not os.path.exists(REQUIREMENTS_FILE):
        print(f"[!] File {REQUIREMENTS_FILE} tidak ditemukan.")
        sys.exit(1)

    print("[...] Mengecek dan menginstal dependensi...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS_FILE]
        )
        print("[✔] Semua dependensi sudah terinstal.")
    except subprocess.CalledProcessError:
        print("[!] Gagal install requirements.")
        sys.exit(1)


def jalankan_bot():
    print("[🚀] Menjalankan bot...")
    subprocess.run([sys.executable, BOT_FILE])


# Tambahkan di main setelah install_requirements()
if __name__ == "__main__":
    print("📦 Setup Lingkungan Bot Telegram\n" + "-" * 40)
    check_python_version()
    check_os()
    check_pip()
    install_requirements()
    jalankan_bot()
