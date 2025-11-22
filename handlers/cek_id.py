from telegram import Update
from telegram.ext import ContextTypes
import logging


async def cek_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menampilkan ID user, ID chat (termasuk grup), dan thread/topik jika ada."""
    user = update.effective_user
    chat = update.effective_chat
    logger = logging.getLogger(__name__)

    uid = user.id
    uname = user.username or "(tanpa username)"
    ctype = chat.type
    chat_id = chat.id
    thread_id = getattr(update.message, "message_thread_id", None)

    logger.info(
        f"User {uid} memanggil /cek_id (username={uname}, chat_type={ctype}, chat_id={chat_id}, thread_id={thread_id})"
    )

    msg = (
        f"<b>🆔 ID User:</b> <code>{uid}</code>\n"
        f"<b>💬 ID Chat:</b> <code>{chat_id}</code>\n"
    )

    if thread_id is not None:
        msg += f"<b>🧵 Thread/Topic ID:</b> <code>{thread_id}</code>\n"

    msg += (
        f"<b>👤 Nama:</b> {user.full_name}\n"
        f"<b>🏷️ Username:</b> @{uname}\n"
        f"<b>📦 Jenis Chat:</b> {ctype}\n\n"
        "Gunakan ID ini untuk whitelist/admin atau pembatasan thread."
    )

    await update.message.reply_text(msg, parse_mode="HTML")
