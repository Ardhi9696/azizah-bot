# utils/topic_guard.py
import json
import logging
from pathlib import Path
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from dotenv import load_dotenv
import os

from .constants import TOPIK_ID  # -> Path ke data/topik_ids.json

logger = logging.getLogger(__name__)
load_dotenv()
OWNER_ID = int(os.getenv("MY_TELEGRAM_ID", "0"))

# Sediakan alias command kalau kamu ingin fleksibel
COMMAND_ALIASES = {
    "cek": ["cek", "cek_ujian", "cek-topik", "cek_topik"],
    # tambah kalau perlu
}


def _normalize_key(k: str) -> str:
    return (k or "").strip().lstrip("/").lower()


def _load_topik_mapping() -> dict:
    """
    Selalu load saat dipanggil (biar perubahan JSON kebaca tanpa restart).
    """
    try:
        path = Path(TOPIK_ID)
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.error("topik_ids.json bukan object dict.")
            return {}
        return data
    except FileNotFoundError:
        logger.error("File topik_ids.json tidak ditemukan di: %s", TOPIK_ID)
        return {}
    except Exception as e:
        logger.exception("Gagal load topik_ids.json: %s", e)
        return {}


def _resolve_thread_id(mapping: dict, command_key: str):
    """
    Cari thread id berdasarkan command_key & alias.
    """
    key = _normalize_key(command_key)
    # 1) coba exact
    if key in mapping:
        return mapping[key]
    # 2) coba alias
    for main, aliases in COMMAND_ALIASES.items():
        if key in [_normalize_key(a) for a in aliases]:
            return mapping.get(main)
    return None


async def handle_thread_guard(
    command_key: str, update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    chat = update.effective_chat
    msg = update.effective_message
    user = update.effective_user

    mapping = _load_topik_mapping()
    expected_thread_id = _resolve_thread_id(mapping, command_key)

    # DM
    if chat.type == "private":
        if user.id != OWNER_ID:
            logger.error(
                "[❌ DM BLOCKED] User %s mencoba '%s' di DM.", user.id, command_key
            )
            await msg.reply_text("❌ Perintah ini hanya bisa digunakan di dalam grup.")
            return False
        logger.info(
            "[✅ DM ALLOWED] Owner %s jalankan '%s' di DM.", user.id, command_key
        )
        return True

    # Harus supergroup
    if chat.type != "supergroup":
        logger.error(
            "[❌ NON-SUPERGROUP] Command dari %s di chat %s", user.id, chat.type
        )
        await msg.reply_text("❌ Perintah ini hanya tersedia di supergroup.")
        return False

    # Pastikan sudah dikonfigurasi
    if expected_thread_id is None:
        logger.error(
            "[❌ UNKNOWN COMMAND] '%s' tidak ada di topik_ids.json", command_key
        )
        # bantuin user dengan daftar keys yang ada
        available = ", ".join(sorted(mapping.keys())) or "(kosong)"
        await msg.reply_text(
            "❌ Command ini belum dikonfigurasi topiknya.\n"
            f"Tambahkan di file <code>data/topik_ids.json</code> dengan key <b>{_normalize_key(command_key)}</b>.\n"
            f"Key yang tersedia saat ini: <code>{available}</code>",
            parse_mode=ParseMode.HTML,
        )
        return False

    # Cek thread
    current_thread_id = msg.message_thread_id
    if current_thread_id == expected_thread_id:
        logger.info(
            "[✅ THREAD OK] %s jalankan '%s' di thread benar (%s).",
            user.id,
            command_key,
            expected_thread_id,
        )
        return True

    # Topik general (tanpa thread id)
    if current_thread_id is None:
        logger.warning(
            "[⚠️ GENERAL THREAD] %s jalankan '%s' di main topic, seharusnya %s.",
            user.id,
            command_key,
            expected_thread_id,
        )
        await msg.reply_text(
            "⚠️ Perintah ini tidak boleh di topik utama.\n"
            "Silakan gunakan thread yang benar sesuai konfigurasi.",
        )
        return False

    # Salah thread lain
    logger.warning(
        "[⚠️ WRONG THREAD] %s jalankan '%s' di thread %s ≠ %s.",
        user.id,
        command_key,
        current_thread_id,
        expected_thread_id,
    )
    await msg.reply_text(
        "⚠️ Perintah ini hanya boleh dijalankan di thread yang sudah ditentukan untuk command ini.",
    )
    return False
