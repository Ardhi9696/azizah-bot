# command_wrapper.py

import time
import asyncio
from typing import Callable, Dict
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes

COOLDOWN_COMMAND = 10  # detik (per-user)
# Simpan timestamp terakhir per user_id
_last_command_time: Dict[int, float] = {}


def with_cooldown(callback: Callable):
    @wraps(callback)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Pastikan ada message dan pengirim
        if not update.message or not update.message.from_user:
            return await callback(update, context)

        user_id = update.message.from_user.id
        now = time.monotonic()
        last = _last_command_time.get(user_id, 0)

        if now - last < COOLDOWN_COMMAND:
            # Kirim notifikasi singkat, lalu schedule penghapusan tanpa blocking
            try:
                notice = await update.message.reply_text(
                    "⏳ Tunggu sebentar sebelum menggunakan perintah lagi."
                )
            except Exception:
                notice = None

            # Hapus pesan pengguna (coba, tapi jangan block jika gagal)
            try:
                asyncio.create_task(update.message.delete())
            except Exception:
                pass

            # Hapus pesan notifikasi setelah cooldown secara non-blocking
            async def _delayed_delete(msg):
                await asyncio.sleep(COOLDOWN_COMMAND)
                if not msg:
                    return
                try:
                    await msg.delete()
                except Exception:
                    pass

            if notice:
                try:
                    asyncio.create_task(_delayed_delete(notice))
                except Exception:
                    pass

            return

        # Update last time dan jalankan callback
        _last_command_time[user_id] = now
        await callback(update, context)

    return wrapper
