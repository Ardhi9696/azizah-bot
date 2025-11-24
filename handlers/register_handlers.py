# register_handlers.py
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from handlers.command_wrapper import with_cooldown
from handlers.get_info import get_info
from handlers.get_prelim import get_prelim
from handlers.responder import simple_responder
from handlers.get_link import link_command
from handlers.get_kurs import kurs_default, kurs_idr, kurs_won
from handlers.get_kurs import kurs_usd, kurs_idr_usd
from handlers.rules import show_rules
from handlers.welcome import welcome_new_member
from handlers.get_reg import get_reg
from handlers.get_jadwal import get_jadwal
from handlers.get_pass1 import get_pass1
from handlers.get_pass2 import get_pass2
from handlers.cek_id import cek_id
from handlers.help import help_command
from handlers.thread_guard import auto_delete_non_admin_in_threads
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
    cmd_tambahkata,
)
from handlers.auto_reply import (
    handle_autoreply_message,
    handle_autoreply_off,
    handle_autoreply_on,
    handle_autoreply_reload,
)


def register_handlers(app: Application):
    # === Guard & thread cleanup ===
    app.add_handler(
        MessageHandler(
            filters.ChatType.SUPERGROUP
            & ~filters.StatusUpdate.ALL
            & ~filters.COMMAND,  # ⬅️ penting: jangan tangkap perintah lain
            auto_delete_non_admin_in_threads,
        ),
        group=0,
    )

    # === Command Handlers (umum & admin) ===
    app.add_handler(CommandHandler("help", with_cooldown(help_command)))
    app.add_handler(CommandHandler("cekid", with_cooldown(cek_id)))
    app.add_handler(CommandHandler("get", with_cooldown(get_info)))
    app.add_handler(CommandHandler("prelim", with_cooldown(get_prelim)))
    app.add_handler(CommandHandler("reg", with_cooldown(get_reg)))
    app.add_handler(CommandHandler("jadwal", with_cooldown(get_jadwal)))
    app.add_handler(CommandHandler("pass1", with_cooldown(get_pass1)))
    app.add_handler(CommandHandler("pass2", with_cooldown(get_pass2)))
    app.add_handler(CommandHandler("link", with_cooldown(link_command)))
    app.add_handler(CommandHandler("kurs", with_cooldown(kurs_default)))
    app.add_handler(CommandHandler("kursidr", with_cooldown(kurs_idr)))
    app.add_handler(CommandHandler("kurswon", with_cooldown(kurs_won)))
    app.add_handler(CommandHandler("kursusd", with_cooldown(kurs_usd)))
    app.add_handler(CommandHandler("kursidrusd", with_cooldown(kurs_idr_usd)))
    app.add_handler(CommandHandler("rules", with_cooldown(show_rules)))
    app.add_handler(CommandHandler("ban", with_cooldown(cmd_ban)))
    app.add_handler(CommandHandler("unban", with_cooldown(cmd_unban)))
    app.add_handler(CommandHandler("mute", with_cooldown(cmd_mute)))
    app.add_handler(CommandHandler("unmute", with_cooldown(cmd_unmute)))
    app.add_handler(CommandHandler("restrike", with_cooldown(cmd_restrike)))
    app.add_handler(CommandHandler("adminlist", with_cooldown(lihat_admin)))
    app.add_handler(CommandHandler("tambahkata", cmd_tambahkata))
    app.add_handler(CommandHandler("cekstrike", cmd_cekstrike))
    app.add_handler(CommandHandler("resetstrikeall", cmd_resetstrikeall))
    app.add_handler(CommandHandler("resetbanall", cmd_resetbanall))
    app.add_handler(CommandHandler("autoreply_on", handle_autoreply_on))
    app.add_handler(CommandHandler("autoreply_off", handle_autoreply_off))
    app.add_handler(CommandHandler("autoreply_reload", handle_autoreply_reload))

    # === Message Handlers ===
    app.add_handler(
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member)
    )
    # Moderasi hanya di supergroup, juga exclude command (prioritas lebih tinggi)
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.SUPERGROUP, moderasi
        ),
        group=1,
    )
    # Autoreply untuk teks biasa (non-command) di supergroup & DM (jalan setelah moderasi)
    app.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND
            & (filters.ChatType.SUPERGROUP | filters.ChatType.PRIVATE),
            handle_autoreply_message,
        ),
        group=2,
    )
    # Responder hanya untuk teks biasa/mention/reply, TIDAK untuk command (paling akhir)
    app.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND
            & (filters.REPLY | filters.Entity("mention")),
            simple_responder,
        ),
        group=3,
    )
