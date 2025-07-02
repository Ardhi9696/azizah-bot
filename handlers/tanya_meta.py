from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from meta_ai_api import MetaAI


async def tanya_meta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type = update.effective_chat.type
    user = update.effective_user
    user_mention = user.mention_html()

    if len(context.args) == 0:
        await update.message.reply_html(
            f"💬 Halo {user_mention}, silakan gunakan perintah seperti ini:\n"
            f"<code>/tanya Siapa presiden Indonesia sekarang?</code>"
        )
        return

    message = " ".join(context.args)

    # Kirim pesan tunggu
    waiting_msg = await update.message.reply_text(
        "⏳ Mohon tunggu, sedang memproses pertanyaanmu..."
    )

    try:
        ai = MetaAI()
        result = ai.prompt(message=message)

        msg = (
            result.get("message", "❌ Tidak ada jawaban yang tersedia.")
            .replace("\\n", "\n")
            .strip()
        )

        # Respons dengan mention (terlihat di grup)
        response = (
            f"🤖 <b>Jawaban dari Meta AI</b>\n\n"
            f"👤 Ditanyakan oleh: {user_mention}\n\n"
            f"{msg}"
        )
        await update.message.reply_html(response, disable_web_page_preview=True)

    except Exception as e:
        await update.message.reply_text(
            "❌ Terjadi kesalahan saat memproses pertanyaan."
        )
    finally:
        await waiting_msg.delete()


def register_handler(app):
    app.add_handler(CommandHandler("tanya", tanya_meta))
