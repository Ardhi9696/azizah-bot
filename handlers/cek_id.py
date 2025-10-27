from telegram import Update
from telegram.ext import ContextTypes
import logging


async def cek_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menampilkan ID Telegram user dan tipe chat."""
    user = update.effective_user
    chat = update.effective_chat
    logger = logging.getLogger(__name__)

    uid = user.id
    uname = user.username or "(tanpa username)"
    ctype = chat.type

    logger.info(f"User {uid} memanggil /cek_id (username={uname}, chat_type={ctype})")

    msg = (
        f"<b>🆔 ID Telegram:</b> <code>{uid}</code>\n"
        f"<b>👤 Nama:</b> {user.full_name}\n"
        f"<b>🏷️ Username:</b> @{uname}\n"
        f"<b>💬 Jenis Chat:</b> {ctype}\n\n"
        "Kirim ID ini ke admin agar bisa di-whitelist di sistem bot."
    )

    await update.message.reply_text(msg, parse_mode="HTML")
