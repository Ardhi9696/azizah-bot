# handlers/start.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from .approval_manager import add_new_user, is_approved
from .welcome import kick_unapproved


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    if is_approved(user_id):
        await update.message.reply_text("✅ Kamu sudah menyetujui aturan sebelumnya.")
        return

    # Tambahkan ke sistem approval jika belum
    add_new_user(user_id)

    # Kirim ulang aturan
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("✅ Saya Setuju", callback_data="setuju_rules")]]
    )
    await update.message.reply_text(
        text=(
            "👋 Hai! Terima kasih sudah bergabung di grup *EPS-TOPIK Indonesia*.\n\n"
            "📜 Berikut beberapa peraturan penting:\n"
            "1. ❌ Dilarang spam, judi, promosi, atau link berbahaya.\n"
            "2. ❌ Hindari kata kasar, topik sensitif, atau provokasi.\n"
            "3. ✅ Gunakan fitur bot dengan bijak, jangan abuse.\n"
            "4. 💬 Saling bantu, saling respek. Admin juga manusia 😄\n\n"
            "Klik tombol di bawah ini jika kamu setuju ya 👇"
        ),
        reply_markup=keyboard,
        parse_mode="Markdown",
    )

    # Jalankan kick timer (jika belum dijadwalkan sebelumnya)
    context.job_queue.run_once(
        callback=kick_unapproved,
        when=300,
        data={"user_id": user_id, "chat_id": context.bot_data.get("group_id")},
        name=f"kick_{user_id}",
    )
