from telegram import Update
from telegram.ext import ContextTypes

WELCOME_MESSAGE = """👋 Selamat datang {mention}!

📌 Ini adalah grup diskusi seputar EPS-TOPIK. Harap perhatikan aturan dasar berikut:

1. ❌ *Dilarang kirim spam, promosi, atau link judi/bokep*  
2. 💬 Sopan dalam bertanya, jangan nyepam command / fitur bot  
3. 🧼 Hindari kata kasar, hujatan, atau provokasi  
4. ⚠️ Topik sensitif seperti *politik, agama, ras* tidak diperbolehkan  
5. 👀 Silent reader gapapa, tapi aktif lebih baik~  
6. 🤖 Abuse bot = auto mute/ban  
7. 🙋 Kalau bingung, gunakan perintah /help

💌 Nikmati suasana belajar bareng, kita semua di sini berproses~  
"""


async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue  # Jangan sambut bot

        try:
            await update.message.reply_text(
                WELCOME_MESSAGE.format(mention=member.mention_html()),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception as e:
            print(f"Gagal mengirim pesan sambutan: {e}")
