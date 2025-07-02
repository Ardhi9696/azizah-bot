# callback_handler.py
from telegram import Update
from telegram.ext import ContextTypes
from .approval_manager import approve_user


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    approve_user(user_id)
    await query.answer("Terima kasih! Kamu sudah menyetujui aturan.")
    await query.edit_message_text(
        "✅ Kamu telah menyetujui peraturan grup. Selamat bergabung!"
    )
