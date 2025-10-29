import shlex
import os
import re
import json
import logging
from typing import Dict

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ContextTypes
from handlers.eps_core import (
    setup_driver,
    login_with,
    verifikasi_tanggal_lahir,
    normalize_birthday,
    akses_progress,
    format_data,
)


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
LOGIN_URL = "https://www.eps.go.kr/eo/langMain.eo?langCD=in"


def load_eps_accounts() -> Dict[int, Dict[str, str]]:
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
            logger.info(f"📘 Memuat akun EPS dari {ACCOUNTS_FILE}")
            return {int(k): v for k, v in data.items()}
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


async def _send_long_html(context, chat_id: int, html_text: str, limit: int = 4096):
    parts = [html_text[i : i + limit] for i in range(0, len(html_text), limit)]
    for p in parts:
        await context.bot.send_message(chat_id=chat_id, text=p, parse_mode="HTML")


def _parse_args(text: str):
    # /eps -> auto; /eps USER PASS TGL -> manual
    try:
        tokens = shlex.split(text)
    except ValueError:
        return []
    return tokens[1:]  # buang nama command


def _get_display_time():
    """Get current time in GMT+7 format for display only"""
    from datetime import datetime
    import pytz

    jakarta_tz = pytz.timezone("Asia/Jakarta")
    now = datetime.now(jakarta_tz)
    return now.strftime("%Y-%m-%d %H:%M:%S GMT+7")


# ====== HANDLER UTAMA ======
async def eps_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _ensure_authorized_dm(update, context):
        return
    uid = update.effective_user.id
    chat_id = update.effective_chat.id
    message_id = update.message.message_id
    args = _parse_args(update.message.text)

    logger.info(f"\n=== 🚀 Command /eps dipanggil oleh UID={uid} ===")

    # Kirim pesan "mohon tunggu" dan simpan message_id-nya
    wait_message = await update.message.reply_text(
        "⏳ Mohon tunggu, sedang dalam proses pengecekan EPS..."
    )
    wait_message_id = wait_message.message_id

    async def _delete_command():
        """Hapus pesan command (hanya untuk mode manual)"""
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            logger.info(f"[{uid}] Pesan command dihapus (keamanan).")
        except Exception:
            pass

    async def _delete_wait_message():
        """Hapus pesan 'mohon tunggu'"""
        try:
            await context.bot.delete_message(
                chat_id=chat_id, message_id=wait_message_id
            )
            logger.info(f"[{uid}] Pesan 'mohon tunggu' dihapus.")
        except Exception:
            pass

    # === MODE MANUAL jika ada 3 argumen ===
    if len(args) >= 3:
        username, password, birthday_raw = args[0], args[1], args[2]
        birthday = normalize_birthday(birthday_raw)
        account_key = (username or "").lower().strip()

        logger.info(
            f"[{uid}] Mode: MANUAL | Username: {username} | Birthday: {birthday}"
        )

        driver = setup_driver()
        try:
            logger.info(f"[{uid}] 🔑 Login EPS...")
            if not login_with(driver, username, password):
                await context.bot.send_message(
                    uid, "❌ Gagal login (cek username/password)."
                )
                logger.warning(f"[{uid}] Login gagal.")
                await _delete_wait_message()
                await _delete_command()  # Hapus command di mode manual
                return

            if not verifikasi_tanggal_lahir(driver, birthday):
                await context.bot.send_message(
                    uid, "❌ Verifikasi tanggal lahir gagal. Format YYMMDD/ YYYYMMDD."
                )
                logger.warning(f"[{uid}] Verifikasi tanggal lahir gagal.")
                await _delete_wait_message()
                await _delete_command()  # Hapus command di mode manual
                return

            logger.info(f"[{uid}] 📦 Mengambil data progres EPS...")
            data = akses_progress(driver, prefer_row2=True)
            logger.info(f"[{uid}] ✅ Data progres berhasil diambil.")

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

            # Hapus pesan "mohon tunggu" sebelum kirim hasil
            await _delete_wait_message()

            msg = format_data(data) + f"\n\n<i>⏱️ Dicek pada: {_get_display_time()}</i>"
            await _send_long_html(context, uid, msg)
            logger.info(f"[{uid}] 📤 Hasil dikirim ke Telegram.")
            logger.info(
                f"[{uid}] ✅ NAMA: {data.get('nama','-')} | REF: {data.get('aktif_ref_id','-')} | STATUS: MANUAL"
            )

        except Exception as e:
            logger.exception(f"[{uid}] EPS manual error: {e}")
            await context.bot.send_message(uid, f"❌ Terjadi kesalahan: {e}")
            await _delete_wait_message()
            await _delete_command()  # Hapus command di mode manual bahkan jika error
        finally:
            driver.quit()
            await _delete_command()  # Pastikan command dihapus di mode manual
        return

    # === MODE AUTO (tanpa argumen) ===
    logger.info(f"[{uid}] Mode: AUTO")

    creds = EPS_ACCOUNTS.get(uid)
    if not creds:
        await context.bot.send_message(
            uid, "❌ Akun EPS kamu belum terdaftar di config/eps_accounts.json."
        )
        logger.warning(f"[{uid}] Tidak ada kredensial di config.")
        await _delete_wait_message()
        # TIDAK hapus command di mode auto
        return

    username = creds.get("username", "")
    password = creds.get("password", "")
    birthday = normalize_birthday(creds.get("birthday", ""))
    account_key = (username or "").lower().strip()

    driver = setup_driver()
    try:
        logger.info(f"[{uid}] 🔑 Login EPS untuk user={username}")
        if not login_with(driver, username, password):
            await context.bot.send_message(
                uid, "❌ Gagal login ke EPS (cek username/password)."
            )
            logger.warning(f"[{uid}] Login gagal.")
            await _delete_wait_message()
            # TIDAK hapus command di mode auto
            return

        if not verifikasi_tanggal_lahir(driver, birthday):
            await context.bot.send_message(
                uid, "❌ Verifikasi tanggal lahir gagal. Format YYMMDD/ YYYYMMDD."
            )
            logger.warning(f"[{uid}] Verifikasi tanggal lahir gagal.")
            await _delete_wait_message()
            # TIDAK hapus command di mode auto
            return

        logger.info(f"[{uid}] 📦 Mengambil data progres EPS...")
        data = akses_progress(driver, prefer_row2=True)
        logger.info(f"[{uid}] ✅ Data progres berhasil diambil.")

        # TENTUKAN STATUS
        cache = _load_cache(CACHE_AUTO_FILE)
        last = _get_last_snapshot_for_account(cache, uid, account_key)
        if last and _data_equal(last.get("data", {}), data):
            status = "(BELUM ADA PROGRES)"
            logger.info(f"[{uid}] 🔁 Tidak ada perubahan dari cache terakhir.")
        else:
            status = "(NEW PROGRESS)" if last else ""
            logger.info(f"[{uid}] 🆕 Data baru terdeteksi.")

        # SIMPAN SNAPSHOT
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

        # Hapus pesan "mohon tunggu" sebelum kirim hasil
        await _delete_wait_message()

        # KIRIM PESAN —> JANGAN tambahkan spasi manual
        msg = format_data(data, status=status)
        msg += f"\n\n<i>⏱️ Dicek pada: {_get_display_time()}</i>"
        await _send_long_html(context, uid, msg)

        logger.info(f"[{uid}] 📤 Hasil dikirim ke Telegram.")
        logger.info(
            f"[{uid}] ✅ NAMA: {data.get('nama','-')} | REF: {data.get('aktif_ref_id','-')} | STATUS: {status or 'FIRST SNAPSHOT'}"
        )

    except Exception as e:
        logger.exception(f"[{uid}] EPS auto error: {e}")
        await context.bot.send_message(uid, f"❌ Terjadi kesalahan: {e}")
        await _delete_wait_message()
        # TIDAK hapus command di mode auto bahkan jika error
    finally:
        driver.quit()
        logger.info(f"[{uid}] 🧹 Selenium driver ditutup.")
