import requests
import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


def get_rate(base: str, target: str):
    try:
        logger.info(
            f"[🔄 FETCH] Mengambil kurs dari {base.upper()} ke {target.upper()}"
        )
        url = f"https://www.floatrates.com/daily/{base.lower()}.json"
        resp = requests.get(url, timeout=5)
        data = resp.json()
        rate = data[target.lower()]["rate"]
        logger.info(f"[✅ RATE] 1 {base.upper()} = {rate:.4f} {target.upper()}")
        return rate
    except Exception as e:
        logger.error(
            f"[❌ ERROR] Gagal mengambil kurs {base.upper()} → {target.upper()}",
            exc_info=True,
        )
        return None


async def kurs_default(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(
        f"[📥 /kurs] {user.full_name} ({user.id}) meminta kurs default KRW → IDR"
    )

    waiting_msg = await update.message.reply_text("🔄 Mohon tunggu, mengambil kurs...")

    rate = get_rate("krw", "idr")
    if rate:
        await waiting_msg.delete()
        logger.info(f"[✅ RESP] Berhasil mengirim kurs ke {user.id}")
        await update.message.reply_text(
            f"*💱 KURS SEKARANG*\n\n🇰🇷 1 KRW = 🇮🇩 {rate:,.2f} IDR",
            parse_mode="Markdown",
        )
    else:
        await waiting_msg.edit_text("❌ Gagal mengambil kurs.")


async def kurs_idr(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    args = text.split()

    if len(args) < 2 or not args[1].isdigit():
        await update.message.reply_text("Gunakan: /kursidr <nominal_KRW>")
        return

    amt = float(args[1])
    logger.info(
        f"[📥 /kursidr] {user.full_name} ({user.id}) meminta konversi {amt} KRW → IDR"
    )

    waiting_msg = await update.message.reply_text("🔄 Mohon tunggu, menghitung...")

    rate = get_rate("krw", "idr")
    if rate:
        hasil = amt * rate
        await waiting_msg.delete()
        logger.info(f"[✅ RESP] {amt:.0f} KRW = {hasil:,.2f} IDR dikirim ke {user.id}")
        await update.message.reply_text(
            f"*💱 KURS SEKARANG*\n\n🇰🇷 {amt:.0f} KRW = 🇮🇩 {hasil:,.2f} IDR",
            parse_mode="Markdown",
        )
    else:
        await waiting_msg.edit_text("❌ Gagal mengambil kurs.")


async def kurs_won(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    args = text.split()

    if len(args) < 2 or not args[1].isdigit():
        await update.message.reply_text("Gunakan: /kurswon <nominal_IDR>")
        return

    amt = float(args[1])
    logger.info(
        f"[📥 /kurswon] {user.full_name} ({user.id}) meminta konversi {amt} IDR → KRW"
    )

    waiting_msg = await update.message.reply_text("🔄 Mohon tunggu, menghitung...")

    rate = get_rate("idr", "krw")
    if rate:
        hasil = amt * rate
        await waiting_msg.delete()
        logger.info(f"[✅ RESP] {amt:.0f} IDR = {hasil:,.2f} KRW dikirim ke {user.id}")
        await update.message.reply_text(
            f"*💱 KURS SEKARANG*\n\n🇮🇩 {amt:.0f} IDR = 🇰🇷 {hasil:,.2f} KRW",
            parse_mode="Markdown",
        )
    else:
        await waiting_msg.edit_text("❌ Gagal mengambil kurs.")
