from telegram import Update
from telegram.ext import ContextTypes
import logging


async def cek_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menampilkan ID user, ID chat (termasuk grup), dan thread/topik jika ada."""
    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message
    logger = logging.getLogger(__name__)

    uid = user.id
    uname = user.username or "(tanpa username)"
    ctype = chat.type
    chat_id = chat.id
    thread_id = getattr(message, "message_thread_id", None)

    logger.info(
        f"User {uid} memanggil /cek_id (username={uname}, chat_type={ctype}, chat_id={chat_id}, thread_id={thread_id})"
    )

    thread_label = (
        f"<code>{thread_id}</code>" if thread_id is not None else "Tidak ada (bukan topik)"
    )

    msg = (
        f"<b>🆔 ID User:</b> <code>{uid}</code>\n"
        f"<b>💬 ID Chat:</b> <code>{chat_id}</code>\n"
        f"<b>🧵 Thread/Topic ID:</b> {thread_label}\n"
        f"<b>👤 Nama:</b> {user.full_name}\n"
        f"<b>🏷️ Username:</b> @{uname}\n"
        f"<b>📦 Jenis Chat:</b> {ctype}\n\n"
        "Gunakan ID ini untuk whitelist/admin atau pembatasan thread."
    )

    await update.message.reply_text(msg, parse_mode="HTML")
