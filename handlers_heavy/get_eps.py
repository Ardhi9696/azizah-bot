# get_eps.py
import shlex
import os
import re
import json
import logging
import asyncio
from typing import Dict

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ContextTypes

# --- EPS core (hanya yang dibutuhkan) ---
from handlers_heavy.eps_core.session_manager import (
    with_session_async,
    with_session_sync_wrapper,
)
from handlers_heavy.eps_core.scraper import akses_progress
from handlers_heavy.eps_core.formatter import format_data
from handlers_heavy.eps_core.utils import normalize_birthday

# --- Cache utils ---
from handlers.cache_utils import (
    CACHE_AUTO_FILE,
    CACHE_MANUAL_FILE,
    _load_cache,
    _save_cache,
    _get_last_snapshot_for_account,
    _append_snapshot_for_account,
    _now_jakarta_iso,
    _data_equal,
)

# ====== CONFIG LOGGING ======
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ====== ENV / CONFIG ======
load_dotenv()

ACCOUNTS_FILE = os.path.join("config", "eps_accounts.json")


def load_eps_accounts() -> Dict[int, Dict[str, str]]:
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
            logger.info(f"📘 Memuat akun EPS dari {ACCOUNTS_FILE}")

            parsed: Dict[int, Dict[str, str]] = {}
            for k, v in data.items():
                try:
                    parsed[int(k)] = v
                except (ValueError, TypeError):
                    logger.warning(f"⚠️ Melewati entry akun dengan key tidak valid: {k}")
                    continue
            return parsed
    except Exception as e:
        logger.error(f"❌ Gagal memuat {ACCOUNTS_FILE}: {e}")
        return {}


def load_allowed_ids_from_env() -> set[int]:
    raw = os.getenv("EPS_USER", "") or ""
    parts = [p.strip() for p in re.split(r"[,\s]+", raw) if p.strip()]
    ids = set()
    for p in parts:
        try:
            ids.add(int(p))
        except ValueError:
            pass
    if ids:
        logger.info(f"👤 Whitelist tambahan dari .env: {', '.join(map(str, ids))}")
    return ids


EPS_ACCOUNTS = load_eps_accounts()
ALLOWED_IDS = set(EPS_ACCOUNTS.keys()) | load_allowed_ids_from_env()

logger.info(f"✅ Total akun EPS terdaftar: {len(EPS_ACCOUNTS)}")
logger.info(f"✅ Total ID Telegram diizinkan: {len(ALLOWED_IDS)}")


# ====== UTIL TELEGRAM ======
async def _ensure_authorized_dm(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """Hanya boleh di DM & ID harus terdaftar di whitelist."""
    if update.effective_chat.type != "private":
        await update.message.reply_text(
            "❌ Perintah ini hanya bisa di chat pribadi (DM)."
        )
        return False

    uid = update.effective_user.id if update.effective_user else None
    if uid not in ALLOWED_IDS:
        logger.warning(f"[{uid}] mencoba akses tanpa izin.")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Akses ditolak. ID belum terdaftar.",
        )
        return False
    return True


# handlers/get_eps.py


async def _send_long_html(context, chat_id: int, html_text: str, limit: int = 4096):
    parts = [html_text[i : i + limit] for i in range(0, len(html_text), limit)]
    for p in parts:
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=p,
                parse_mode="HTML",
                read_timeout=60,  # Tambahkan timeout lebih lama
                write_timeout=60,
                connect_timeout=60,
            )
            await asyncio.sleep(1)  # Delay antar pesan
        except Exception as e:
            logger.error(f"Error sending message part: {e}")
            # Continue dengan part berikutnya


def _parse_args(text: str):
    # /eps -> auto; /eps USER PASS TGL -> manual
    try:
        tokens = shlex.split(text)
    except ValueError:
        return []
    return tokens[1:]  # buang nama command


def _display_time_gmt7() -> str:
    from datetime import datetime

    try:
        import pytz

        tz = pytz.timezone("Asia/Jakarta")
        return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S GMT+7")
    except Exception:
        # fallback kalau pytz tidak ada
        from datetime import timezone, timedelta

        jkt = timezone(timedelta(hours=7))
        return datetime.now(jkt).strftime("%Y-%m-%d %H:%M:%S %z")


# ====== ASYNC SCRAPING FUNCTION ======
async def _scrape_eps_data(page):
    """Async function untuk scraping data EPS"""
    return await akses_progress(page, prefer_row2=True)


# ====== HANDLER UTAMA ======
async def eps_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # DM-only + whitelist
    if not await _ensure_authorized_dm(update, context):
        return

    uid = update.effective_user.id
    chat_id = update.effective_chat.id
    message_id = update.message.message_id
    args = _parse_args(update.message.text)

    logger.info(f"\n=== 🚀 Command /eps dipanggil oleh UID={uid} ===")

    # Pesan progress (reply ke command); akan DIHAPUS setelah selesai
    wait_msg = await update.message.reply_text("⏳ Mohon tunggu, sedang mengecek EPS…")
    wait_msg_id = wait_msg.message_id

    async def _delete_wait_message():
        """Hapus pesan 'mohon tunggu'"""
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=wait_msg_id)
            logger.info(f"[{uid}] Pesan 'mohon tunggu' dihapus.")
        except Exception:
            pass

    async def _delete_command_message():
        """Hapus pesan command (hanya untuk mode manual)"""
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            logger.info(f"[{uid}] Pesan command dihapus (keamanan mode manual).")
        except Exception:
            pass

    # ========== MODE MANUAL ==========
    if len(args) >= 3:
        username, password, birthday_raw = args[0], args[1], args[2]
        birthday = normalize_birthday(birthday_raw)
        account_key = (username or "").lower().strip()

        logger.info(f"[{uid}] Mode: MANUAL | user={username} | bday={birthday}")

        try:
            # Gunakan async session manager
            data = await with_session_async(
                user_key=account_key,
                username=username,
                password=password,
                birthday=birthday,
                fn=_scrape_eps_data,  # Async function
                ttl_sec=90 * 60,  # 90 menit
                auto_cleanup=True,
                logger_=logger,
            )

            logger.info(f"[{uid}] ✅ Data progres berhasil diambil (session OK).")

            # simpan cache manual
            cache = _load_cache(CACHE_MANUAL_FILE)
            entry = {
                "telegram_id": uid,
                "checked_at": _now_jakarta_iso(),
                "aktif_ref_id": data.get("aktif_ref_id"),
                "data": data,
                "mode": "manual",
                "username_used": username,
            }
            _append_snapshot_for_account(cache, uid, account_key, entry)
            _save_cache(CACHE_MANUAL_FILE, cache)
            logger.info(f"[{uid}] 💾 Cache manual disimpan.")

            # HAPUS PESAN "MOHON TUNGGU" DAN PESAN COMMAND
            await _delete_wait_message()
            await _delete_command_message()

            msg = format_data(data) + f"\n\n<i>⏱️ Dicek pada: {_display_time_gmt7()}</i>"
            await _send_long_html(context, uid, msg)

            logger.info(f"[{uid}] 📤 Hasil dikirim ke Telegram.")
            logger.info(
                f"[{uid}] ✅ NAMA: {data.get('nama','-')} | REF: {data.get('aktif_ref_id','-')} | STATUS: MANUAL"
            )
        except Exception as e:
            logger.exception(f"[{uid}] EPS manual error: {e}")
            # HAPUS PESAN "MOHON TUNGGU" DAN PESAN COMMAND MESKI ERROR
            await _delete_wait_message()
            await _delete_command_message()
            await context.bot.send_message(uid, f"❌ Terjadi kesalahan: {e}")
        return

    # ========== MODE AUTO ==========
    logger.info(f"[{uid}] Mode: AUTO")

    creds = EPS_ACCOUNTS.get(uid)
    if not creds:
        await _delete_wait_message()
        await context.bot.send_message(
            uid, "❌ Akun EPS kamu belum terdaftar di config/eps_accounts.json."
        )
        logger.warning(f"[{uid}] Tidak ada kredensial di config.")
        return

    username = (creds.get("username") or "").strip()
    password = (creds.get("password") or "").strip()
    birthday = normalize_birthday(creds.get("birthday", ""))
    account_key = username.lower()

    try:
        # Gunakan async session manager
        data = await with_session_async(
            user_key=account_key,
            username=username,
            password=password,
            birthday=birthday,
            fn=_scrape_eps_data,  # Async function
            ttl_sec=90 * 60,  # 90 menit
            auto_cleanup=True,
            logger_=logger,
        )
        logger.info(f"[{uid}] ✅ Data progres berhasil diambil (session OK).")

        # status cache
        cache = _load_cache(CACHE_AUTO_FILE)
        last = _get_last_snapshot_for_account(cache, uid, account_key)
        if last and _data_equal(last.get("data", {}), data):
            status = "(BELUM ADA PROGRES)"
            logger.info(f"[{uid}] 🔁 Tidak ada perubahan dari cache terakhir.")
        else:
            status = "(NEW PROGRESS)" if last else ""
            logger.info(f"[{uid}] 🆕 Data baru terdeteksi.")

        # simpan snapshot
        entry = {
            "telegram_id": uid,
            "checked_at": _now_jakarta_iso(),
            "aktif_ref_id": data.get("aktif_ref_id"),
            "data": data,
            "mode": "auto",
            "username_used": username,
        }
        _append_snapshot_for_account(cache, uid, account_key, entry)
        _save_cache(CACHE_AUTO_FILE, cache)

        # HAPUS HANYA PESAN "MOHON TUNGGU" SAJA
        await _delete_wait_message()

        msg = format_data(data, status=status)
        msg += f"\n\n<i>⏱️ Dicek pada: {_display_time_gmt7()}</i>"
        await _send_long_html(context, uid, msg)

        logger.info(f"[{uid}] 📤 Hasil dikirim ke Telegram.")
        logger.info(
            f"[{uid}] ✅ NAMA: {data.get('nama','-')} | REF: {data.get('aktif_ref_id','-')} | STATUS: {status or 'FIRST SNAPSHOT'}"
        )

    except Exception as e:
        logger.exception(f"[{uid}] EPS auto error: {e}")
        # HAPUS HANYA PESAN "MOHON TUNGGU" SAJA
        await _delete_wait_message()
        await context.bot.send_message(uid, f"❌ Terjadi kesalahan: {e}")
