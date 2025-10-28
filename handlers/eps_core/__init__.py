# handlers/eps_core/__init__.py

# --- Driver
from .driver import setup_driver

# --- Utils
from .utils import normalize_birthday

# --- Auth
from .auth import login_with, verifikasi_tanggal_lahir

# Coba ambil akses_progress dari navigator, kalau tidak ada fallback ke scraper
try:
    from .navigator import akses_progress  # type: ignore
except Exception:
    from .scraper import akses_progress  # fallback

# --- Formatter
from .formatter import format_data

__all__ = [
    "setup_driver",
    "normalize_birthday",
    "login_with",
    "verifikasi_tanggal_lahir",
    "akses_progress",
    "format_data",
]
