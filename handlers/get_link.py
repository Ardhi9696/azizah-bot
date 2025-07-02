import json
from telegram import Update
from telegram.ext import ContextTypes
from utils.constants import LINK

LINK_FILE = LINK


async def link_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open(LINK_FILE, "r", encoding="utf-8") as f:
            links = json.load(f)

        pesan = "🔗 <b>KUMPULAN LINK G to G Korea</b> 🇰🇷\n\n"
        for item in links:
            emoji = item.get("emoji", "🔗")
            judul = item.get("judul", "Tanpa Judul")
            url = item.get("link", "#")
            pesan += f'{emoji} <a href="{url}">{judul}</a>\n\n'
        await update.message.reply_text(
            pesan.strip(), parse_mode="HTML", disable_web_page_preview=True
        )

    except Exception as e:
        await update.message.reply_text("❌ Gagal memuat daftar link.")
        print(f"[ERROR] link_command: {e}")
