from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler


async def show_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules_text = """📌 *Peraturan Grup EPS-TOPIK*  
1. ❌ *Dilarang kirim spam, promosi, atau link judi/bokep*  
2. 💬 Sopan dalam bertanya, jangan nyepam command / fitur bot  
3. 🧼 Hindari kata kasar, hujatan, atau provokasi  
4. ⚠️ Topik sensitif seperti *politik, agama, ras* tidak diperbolehkan  
5. 👀 Silent reader gapapa, tapi aktif lebih baik~  
6. 🤖 Abuse bot = auto mute/ban  
7. 🙋 Kalau bingung, gunakan perintah /help

💌 Nikmati suasana belajar bareng, kita semua di sini berproses~  
"""
    await update.message.reply_text(
        rules_text, parse_mode="Markdown", disable_web_page_preview=True
    )


async def agree_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "✅ Terima kasih sudah menyetujui peraturan. Selamat belajar di grup EPS-TOPIK! 🇰🇷✨"
    )
