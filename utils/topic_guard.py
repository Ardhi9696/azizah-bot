import json
import os
import logging
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from utils.constants import TOPIK_ID
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()
OWNER_ID = int(os.getenv("MY_TELEGRAM_ID", "0"))

# Load ID topik dari file JSON
with open(TOPIK_ID, "r", encoding="utf-8") as f:
    TOPIK_COMMAND_ID = json.load(f)


async def handle_thread_guard(
    command_key: str, update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """Validasi command agar hanya bisa dijalankan di tempat yang tepat:
    - DM: hanya owner yang boleh
    - Grup: harus supergroup, dan harus di thread yang sesuai
    - Jika salah thread atau topik general, balasan dialihkan ke thread yang benar
    """
    chat = update.effective_chat
    msg = update.effective_message
    user = update.effective_user

    # DM check
    if chat.type == "private":
        if user.id != OWNER_ID:
            logger.error(
                f"[❌ DM BLOCKED] User {user.id} mencoba '{command_key}' di DM."
            )
            await msg.reply_text("❌ Perintah ini hanya bisa digunakan di dalam grup.")
            return False
        logger.info(
            f"[✅ DM ALLOWED] Owner {user.id} menjalankan '{command_key}' di DM."
        )
        return True

    # Non-supergroup check
    if chat.type != "supergroup":
        logger.error(f"[❌ NON-SUPERGROUP] Command dari {user.id} di chat {chat.type}")
        await msg.reply_text("❌ Perintah ini hanya tersedia di supergroup.")
        return False

    # Ambil thread ID yang benar
    expected_thread_id = TOPIK_COMMAND_ID.get(command_key)
    if expected_thread_id is None:
        logger.error(
            f"[❌ UNKNOWN COMMAND] Command '{command_key}' tidak terdaftar di TOPIK_COMMAND_ID."
        )
        await msg.reply_text("❌ Command ini belum dikonfigurasi topiknya.")
        return False

    current_thread_id = msg.message_thread_id

    # Jika thread cocok → izinkan
    if expected_thread_id and current_thread_id == expected_thread_id:
        logger.info(
            f"[✅ THREAD OK] {user.id} jalankan '{command_key}' di thread yang benar."
        )
        return True

    # Jika dikirim di topik general (threadless) → beri peringatan + teruskan
    if expected_thread_id and current_thread_id is None:
        logger.warning(
            f"[⚠️ GENERAL THREAD] {user.full_name} ({user.id}) jalankan '{command_key}' di thread {current_thread_id} ≠ {expected_thread_id}."
        )

        await msg.reply_text(
            "⚠️ Perintah ini tidak boleh dikirim di topik utama.\nSilakan gunakan thread  *📁 Cek Info Manual*.",
            parse_mode=ParseMode.MARKDOWN,
        )

    else:
        logger.warning(
            f"[⚠️ WRONG THREAD] {user.full_name} ({user.id}) jalankan '{command_key}' di thread {current_thread_id} ≠ {expected_thread_id}."
        )

        await msg.reply_text(
            "⚠️ Perintah ini hanya boleh dijalankan di topik *📁 Cek Info Manual*.\nSilakan gunakan thread tersebut.",
            parse_mode=ParseMode.MARKDOWN,
        )

    return False  # Stop handler lokal (command dijalankan di thread lain)
