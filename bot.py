import os
import logging
import asyncio
from telegram import Update
from logging.handlers import TimedRotatingFileHandler
from colorlog import ColoredFormatter
from dotenv import load_dotenv
from utils.constants import MONITOR_INFO, MONITOR_PRELIM
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from handlers import help, cek_eps, welcome, moderasi
from handlers.command_wrapper import with_cooldown
from handlers.get_info import get_info
from handlers.get_prelim import get_prelim
from handlers.responder import simple_responder
from handlers.get_eps import cek_kolom
from handlers.tanya_meta import tanya_meta
from handlers.get_link import link_command
from handlers.get_kurs import kurs_default, kurs_idr, kurs_won
from handlers.rules import show_rules
from handlers.welcome import welcome_new_member

# from handlers.rules import agree_button
from handlers.moderasi import cmd_tambahkata
from handlers.moderasi import (
    lihat_admin,
    moderasi,
    cmd_ban,
    cmd_unban,
    cmd_restrike,
    cmd_mute,
    cmd_unmute,
    cmd_cekstrike,
    cmd_resetstrikeall,
    cmd_resetbanall,
)
from utils.monitor_utils import (
    check_api_multi,
    is_waktu_aktif,
    is_jam_delapan,
    format_pesan,
)

# from handlers.approval_manager import (
#     # add_new_user,
#     # is_approved,
#     remove_user,
#     get_unapproved_users,
#     # save_user_status,
# )
from handlers.get_reg import get_reg
from handlers.get_jadwal import get_jadwal
from handlers.get_pass1 import get_pass1
from handlers.get_pass2 import get_pass2

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Formatter
color_formatter = ColoredFormatter(
    "%(log_color)s%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    log_colors={
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold_red",
    },
)

file_formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S"
)

# Hapus handler lama
if logger.hasHandlers():
    logger.handlers.clear()

# === Buat folder logs/ jika belum ada ===
try:
    os.makedirs("logs", exist_ok=True)
except Exception as e:
    print(f"[Logger] ⚠️ Gagal membuat folder logs/: {e}")
    # Fallback ke folder saat ini
    LOG_PATH = "log.txt"
    ERROR_LOG_PATH = "error.log"
else:
    LOG_PATH = "logs/log.txt"
    ERROR_LOG_PATH = "logs/error.log"

# Log ke file harian
file_handler = TimedRotatingFileHandler(
    "logs/log.txt", when="midnight", backupCount=7, encoding="utf-8"
)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Log error khusus
error_handler = logging.FileHandler("logs/error.log", mode="a", encoding="utf-8")
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(file_formatter)
logger.addHandler(error_handler)

# Log ke terminal
console_handler = logging.StreamHandler()
console_handler.setFormatter(color_formatter)
logger.addHandler(console_handler)

# Matikan log verbose dari lib lain
for name in [
    "httpx",
    "telegram.vendor.ptb_urllib3.urllib3",
    "telegram.ext._application",
]:
    logging.getLogger(name).setLevel(logging.WARNING)


def mask_token(token: str) -> str:
    if not token or len(token) < 10:
        return "[TOKEN INVALID]"
    return token[:5] + "****" + token[-3:]


# ===== Load .env =====
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
THREAD_ID = int(os.getenv("THREAD_ID", 0))


async def error_handler_function(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error("🚨 Terjadi error saat memproses update:", exc_info=context.error)


# ===== Perintah /id untuk cek chat ID =====
async def get_chat_id(update, context):
    chat_id = update.effective_chat.id
    thread_id = update.message.message_thread_id
    await update.message.reply_text(
        f"📌 Chat ID: `{chat_id}`\n🧵 Thread ID: `{thread_id}`", parse_mode="Markdown"
    )


# ====== kick_unaprove =======
# async def kick_unapproved(context: ContextTypes.DEFAULT_TYPE):
#     for user_id in get_unapproved_users():
#         try:
#             await context.bot.ban_chat_member(chat_id=context.job.data, user_id=user_id)
#             await context.bot.unban_chat_member(
#                 chat_id=context.job.data, user_id=user_id
#             )
#             remove_user(user_id)
#             logging.info(
#                 f"🚫 User {user_id} dikeluarkan karena tidak menyetujui aturan."
#             )
#         except Exception as e:
#             logging.warning(f"Gagal mengeluarkan user {user_id}: {e}")


# ===== JOB Monitoring =====
async def monitor_job(context: ContextTypes.DEFAULT_TYPE):
    if not is_waktu_aktif():
        if is_jam_delapan():
            logger.info("🔔 Waktu monitoring aktif dimulai (08:00 WIB)")
        logger.info(
            "⏹️ Lewat jam aktif, monitoring pengumuman & training dihentikan sementara."
        )
        return

    if is_jam_delapan():
        try:
            await context.bot.send_message(
                chat_id=CHAT_ID,
                message_thread_id=THREAD_ID,
                text="🕗 Selamat pagi! Monitoring pengumuman EPS-TOPIK & Training sudah aktif.\nAku akan kasih tahu kalau ada info baru ya! 😉",
                parse_mode="Markdown",
            )
            logger.info("📢 Pesan pengingat jam 08:00 berhasil dikirim.")
        except Exception as e:
            logger.error(f"❌ Gagal kirim pesan jam 08:00: {e}")

    # === Monitoring Pengumuman ===
    pengumuman_baru = check_api_multi(
        "https://bp2mi.go.id/gtog-data/korea/Pengumuman?start=0&length=10",
        MONITOR_INFO,
        "pengumuman",
    )
    for item in pengumuman_baru:
        try:
            pesan = format_pesan(item, tipe="pengumuman")
            await context.bot.send_message(
                chat_id=CHAT_ID,
                message_thread_id=THREAD_ID,
                text=pesan,
                parse_mode="HTML",
            )
            logger.info("✅ Pengumuman baru berhasil dikirim.")
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"❌ Gagal kirim pengumuman: {e}")

    # === Monitoring Preliminary Training ===
    training_baru = check_api_multi(
        "https://bp2mi.go.id/gtog-data/korea/Preliminary%20Training%20dan%20Info?start=0&length=10",
        MONITOR_PRELIM,
        "training",
    )
    for item in training_baru:
        try:
            pesan = format_pesan(item, tipe="training")
            await context.bot.send_message(
                chat_id=CHAT_ID,
                message_thread_id=THREAD_ID,
                text=pesan,
                parse_mode="HTML",
            )
            logger.info("✅ Info training baru berhasil dikirim.")
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"❌ Gagal kirim info training: {e}")


# ===== Main Program =====
def main():
    application = Application.builder().token(TOKEN).build()
    application.add_error_handler(error_handler_function)

    # === Command Handlers with Cooldown ===
    application.add_handler(CommandHandler("id", with_cooldown(get_chat_id)))
    # application.add_handler(CommandHandler("start", with_cooldown(start.start)))
    application.add_handler(CommandHandler("help", with_cooldown(help.help_command)))
    application.add_handler(CommandHandler("cek", with_cooldown(cek_eps.cek_eps)))
    application.add_handler(CommandHandler("get", with_cooldown(get_info)))
    application.add_handler(CommandHandler("prelim", with_cooldown(get_prelim)))
    application.add_handler(CommandHandler("reg", with_cooldown(get_reg)))
    application.add_handler(CommandHandler("jadwal", with_cooldown(get_jadwal)))
    application.add_handler(CommandHandler("pass1", with_cooldown(get_pass1)))
    application.add_handler(CommandHandler("pass2", with_cooldown(get_pass2)))
    application.add_handler(CommandHandler("link", with_cooldown(link_command)))
    application.add_handler(CommandHandler("cek_eps", with_cooldown(cek_kolom)))
    application.add_handler(CommandHandler("tanya", with_cooldown(tanya_meta)))
    application.add_handler(CommandHandler("kurs", with_cooldown(kurs_default)))
    application.add_handler(CommandHandler("kursidr", with_cooldown(kurs_idr)))
    application.add_handler(CommandHandler("kurswon", with_cooldown(kurs_won)))
    application.add_handler(CommandHandler("mute", with_cooldown(cmd_mute)))
    application.add_handler(CommandHandler("ban", with_cooldown(cmd_ban)))
    application.add_handler(CommandHandler("unban", with_cooldown(cmd_unban)))
    application.add_handler(CommandHandler("restrike", with_cooldown(cmd_restrike)))
    application.add_handler(CommandHandler("unmute", with_cooldown(cmd_unmute)))
    application.add_handler(CommandHandler("adminlist", with_cooldown(lihat_admin)))
    application.add_handler(CommandHandler("rules", with_cooldown(show_rules)))
    application.add_handler(CommandHandler("cekstrike", cmd_cekstrike))
    application.add_handler(CommandHandler("resetstrikeall", cmd_resetstrikeall))
    application.add_handler(CommandHandler("resetbanall", cmd_resetbanall))
    application.add_handler(CommandHandler("tambahkata", cmd_tambahkata))

    application.add_handler(
        MessageHandler(
            filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome.welcome_new_member
        )
    )

    # application.add_handler(CallbackQueryHandler(agree_button, pattern="^agree_rules$"))
    application.add_handler(
        MessageHandler(
            filters.TEXT & (filters.REPLY | filters.Entity("mention")), simple_responder
        )
    )

    application.add_handler(
        MessageHandler(filters.TEXT & filters.ChatType.GROUPS, moderasi)
    )

    # === Pesan saat startup ===
    # async def startup_notify(app):
    #     await app.bot.send_message(
    #         chat_id=CHAT_ID,
    #         text=(
    #             "✅ *안녕하세요, 아자자입니다 (Hi, Azizah di sini!)*\n\n"
    #             "🖥️ Monitoring Pengumuman dan Prelim Status : Aktif 🟢\n\n"
    #             "Aku siap bantu kamu update seputar EPS-TOPIK! ✨\n\n"
    #             "*Fitur yang bisa kamu pakai:*\n\n"
    #             "• 🧾 Pengumuman Hasil Tahap 1 → `/pass1`\n\n"
    #             "• 🏁 Pengumuman Hasil Final → `/pass2`\n\n"
    #             "• 📝 Info Pendaftaran Ujian → `/reg`\n\n"
    #             "• 📅 Jadwal Pelaksanaan Ujian → `/jadwal`\n\n"
    #             "• 📊 Cek Nilai Ujian EPS → `/cek <nomor>`\n\n"
    #             "• 📣 Panggilan Prelim G to G Korea → `/prelim`\n\n"
    #             "• 📑 Info Umum G to G Korea → `/get <jumlah>`\n\n"
    #             "• 💱 Info Nilai Tukar WON to IDR → `/kurs`\n\n"
    #             "• 💱 Info Nilai Tukar WON to IDR Custom → `/kursidr <Nominal>`\n\n"
    #             "• 💱 Info Nilai Tukar IDR to WON Custom → `/kurswon <Nominal>`\n\n"
    #             "• 🤖 Tanya META AI→ `/tanya <isi pertanyaan>`\n\n"
    #             "• 💬 Bantuan & Daftar Perintah → `/help`"
    #         ),
    #         parse_mode="Markdown",
    #     )

    # application.post_init = startup_notify

    # === Jadwal monitoring tiap menit ===
    application.job_queue.run_repeating(monitor_job, interval=60, first=5)

    logger.info("✅ Azizah_Bot aktif dan siap digunakan.")
    application.run_polling()


if __name__ == "__main__":
    main()
