# command_wrapper.py

import time
import asyncio
from telegram import Update
from telegram.ext import ContextTypes

COOLDOWN_COMMAND = 10  # detik
_last_command_time = 0  # global shared cooldown


def with_cooldown(callback):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        global _last_command_time

        now = time.time()
        if now - _last_command_time < COOLDOWN_COMMAND:
            msg = await update.message.reply_text(
                "⏳ Tunggu sebentar sebelum menggunakan perintah lagi."
            )
            try:
                await update.message.delete()
            except:
                pass
            # Jadwalkan penghapusan pesan ⏳ setelah cooldown selesai
            await asyncio.sleep(COOLDOWN_COMMAND)
            try:
                await msg.delete()
            except:
                pass
            return

        _last_command_time = now
        await callback(update, context)

    return wrapper
