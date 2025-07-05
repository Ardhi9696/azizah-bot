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


# from telegram import Update
# from telegram.ext import ContextTypes
# from .approval_manager import add_new_user, is_approved, remove_user
# from telegram.constants import ParseMode

# async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     for member in update.message.new_chat_members:
#         name = member.mention_html()

#         # 1. Sapa & instruksi ke user di grup
#         await update.message.reply_html(
#             f"✨ Hai, {name}! Selamat datang di grup EPS-TOPIK!\n"
#             f"📜 Untuk bisa tetap di grup, kamu wajib menyetujui aturan dalam 5 menit.\n\n"
#             f"👉 Klik <a href='https://t.me/{context.bot.username}'>bot ini</a> dan kirim <code>/start</code>.",
#             disable_web_page_preview=True
#         )

#         # 2. Tambahkan ke sistem approval
#         add_new_user(member.id)

#         # ✅ Simpan ID grup agar bisa digunakan saat user kirim /start
#         context.bot_data["group_id"] = update.effective_chat.id

#         # 3. Jadwalkan kick
#         context.job_queue.run_once(
#             callback=kick_unapproved,
#             when=300,
#             data={"user_id": member.id, "chat_id": update.effective_chat.id},
#             name=f"kick_{member.id}",
#         )

# # Fungsi kick tetap sama seperti sebelumnya
# async def kick_unapproved(context: ContextTypes.DEFAULT_TYPE):
#     data = context.job.data
#     user_id = data["user_id"]
#     chat_id = data["chat_id"]

#     if not is_approved(user_id):
#         try:
#             await context.bot.ban_chat_member(chat_id, user_id)
#             await context.bot.unban_chat_member(chat_id, user_id)
#             remove_user(user_id)
#             await context.bot.send_message(
#                 chat_id,
#                 f"🚫 <a href='tg://user?id={user_id}'>Pengguna</a> dikeluarkan karena tidak menyetujui aturan dalam 5 menit.",
#                 parse_mode=ParseMode.HTML,
#             )
#         except Exception as e:
#             print(f"[KickError] Gagal mengeluarkan user {user_id}: {e}")
