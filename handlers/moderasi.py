import re
import os
import time
import json
import random
import logging
from collections import defaultdict
from telegram import Update, ChatPermissions, User
from telegram.ext import ContextTypes
from dotenv import load_dotenv
from datetime import datetime, timedelta
from utils.constants import MODERATION_FILE, BANNED_FILE, RESPON_FILE, STRIKE_LOG
from utils.anti_phishing import handle_phishing


# Waktu reset per strike
STRIKE_RESET_RULES = {
    1: timedelta(days=1),
    2: timedelta(days=2),
}

# Untuk mencatat waktu strike
user_strike_timestamps = defaultdict(list)

os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)


# === Logging ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="logs/moderasi.log",
    filemode="a",
)


def load_keywords():
    try:
        with open(MODERATION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return (
                data.get("BAN_KEYWORDS", []),
                data.get("BAD_WORDS", []),
                data.get("SENSITIF", []),
            )
    except Exception as e:
        logging.warning(f"Gagal memuat moderation_keywords.json: {e}")
        return [], [], []


def save_keywords(ban, bad, sensitif):
    try:
        with open(MODERATION_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {"BAN_KEYWORDS": ban, "BAD_WORDS": bad, "SENSITIF": sensitif},
                f,
                indent=2,
                ensure_ascii=False,
            )
    except Exception as e:
        logging.warning(f"Gagal menyimpan keyword ke JSON: {e}")


def is_reply_to_bot(update: Update) -> bool:
    """Cek apakah balasan ditujukan ke bot itu sendiri"""
    return (
        update.message
        and update.message.reply_to_message
        and update.message.reply_to_message.from_user.is_bot
    )


# === Load .env dan Admin Whitelist ===
load_dotenv()
ADMIN_IDS = list(map(int, os.getenv("ADMIN_LIST", "").split(",")))
OWNER_ID = int(os.getenv("MY_TELEGRAM_ID", "0"))

# === Konfigurasi ===
STRIKE_LIMIT = 3
MUTE_DURATION = 60 * 5  # 5 menit


BAN_KEYWORDS, BAD_WORDS, SENSITIF = load_keywords()

# === Data Tracking ===
user_strikes = defaultdict(int)
last_global_command = 0

# === Load respon.json ===
try:
    with open(RESPON_FILE, "r", encoding="utf-8") as f:
        RESPON_DATA = json.load(f)
except:
    RESPON_DATA = []

# === Banned User Storage ===
try:
    with open(BANNED_FILE, "r") as f:
        BANNED_USERS = set(json.load(f))
except:
    BANNED_USERS = set()


def save_banned():
    with open(BANNED_FILE, "w") as f:
        json.dump(list(BANNED_USERS), f)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def get_target_user(update: Update) -> User | None:
    if update.message and update.message.reply_to_message:
        return update.message.reply_to_message.from_user
    return None


def clean_text(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text.lower())


async def cmd_tambahkata(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text(
            "⛔ Hanya admin yang bisa menambahkan kata."
        )

    if not ctx.args or len(ctx.args) < 2:
        return await update.message.reply_text(
            "❗ Format: /tambahkata <kategori> <kata>"
        )

    kategori = ctx.args[0].upper()
    kata_baru = ctx.args[1].lower()

    global BAN_KEYWORDS, BAD_WORDS, SENSITIF

    added = False
    label = ""

    if kategori == "BAN":
        if kata_baru not in BAN_KEYWORDS:
            BAN_KEYWORDS.append(kata_baru)
            label = "kata terlarang"
            added = True
    elif kategori == "BAD":
        if kata_baru not in BAD_WORDS:
            BAD_WORDS.append(kata_baru)
            label = "kata buruk"
            added = True
    elif kategori == "SENSITIF":
        if kata_baru not in SENSITIF:
            SENSITIF.append(kata_baru)
            label = "kata sensitif"
            added = True
    else:
        return await update.message.reply_text(
            "❗Kategori tidak dikenal. Gunakan: BAN, BAD, atau SENSITIF."
        )

    if added:
        save_keywords(BAN_KEYWORDS, BAD_WORDS, SENSITIF)

        try:
            await update.message.delete()
        except:
            pass  # gagal hapus tidak masalah

        await ctx.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"✅ {label.capitalize()} berhasil ditambahkan.",
        )
    else:
        await update.message.reply_text("⚠️ Kata sudah ada di daftar.")


# === Mute & Ban ===
async def mute_user(chat_id, user_id, ctx, duration=MUTE_DURATION):
    until = int(time.time() + duration)
    await ctx.bot.restrict_chat_member(
        chat_id, user_id, ChatPermissions(can_send_messages=False), until_date=until
    )
    logging.info(f"🔇 Mute {user_id} di {chat_id} selama {duration}s")


async def ban_user(chat_id, user_id, ctx):
    await ctx.bot.ban_chat_member(chat_id, user_id)
    BANNED_USERS.add(user_id)
    save_banned()
    logging.warning(f"🚫 Ban {user_id} dari {chat_id}")


# === Command Handler: admin only ===
async def cmd_unmute(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text(
            "⛔ Hanya admin yang bisa menggunakan perintah ini."
        )

    if is_reply_to_bot(update):
        return await update.message.reply_text(
            "🤖 Kamu sedang membalas pesan bot. Bot tidak bisa di-unmute 😅"
        )

    target = get_target_user(update)
    if not target:
        return await update.message.reply_text(
            "ℹ️ Balas pesan pengguna yang ingin di-unmute."
        )

    try:
        await ctx.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            permissions=ChatPermissions(can_send_messages=True),
        )
        await update.message.reply_text(
            f"🔓 {target.mention_html()} telah di-unmute.", parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text("❌ Gagal unmute user.")
        logging.exception("Gagal unmute:", exc_info=True)


async def cmd_mute(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text(
            "⛔ Hanya admin yang bisa menggunakan perintah ini."
        )

    if is_reply_to_bot(update):
        return await update.message.reply_text(
            "🤖 Kamu sedang membalas pesan bot. Bot tidak bisa dimute 😅"
        )

    target = get_target_user(update)
    if not target:
        return await update.message.reply_text(
            "ℹ️ Balas pesan pengguna yang ingin dimute."
        )

    await mute_user(update.effective_chat.id, target.id, ctx)
    await update.message.reply_text(
        f"🔇 {target.mention_html()} telah dimute sementara.", parse_mode="HTML"
    )


async def cmd_ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text(
            "⛔ Hanya admin yang bisa menggunakan perintah ini."
        )

    if is_reply_to_bot(update):
        return await update.message.reply_text(
            "🤖 Kamu sedang membalas pesan bot. Bot tidak bisa diban 😅"
        )

    target = get_target_user(update)
    if not target:
        return await update.message.reply_text(
            "ℹ️ Balas pesan pengguna yang ingin diban."
        )

    await ban_user(update.effective_chat.id, target.id, ctx)
    await update.message.reply_text(
        f"🚫 {target.mention_html()} telah dibanned.", parse_mode="HTML"
    )


async def cmd_unban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text(
            "⛔ Hanya admin yang bisa menggunakan perintah ini."
        )

    if is_reply_to_bot(update):
        return await update.message.reply_text(
            "🤖 Kamu sedang membalas pesan bot. Bot tidak bisa di-unban 😅"
        )

    target = get_target_user(update)
    if not target:
        return await update.message.reply_text(
            "ℹ️ Balas pesan pengguna yang ingin di-unban."
        )

    await ctx.bot.unban_chat_member(update.effective_chat.id, target.id)
    BANNED_USERS.discard(target.id)
    save_banned()
    await update.message.reply_text(
        f"✅ {target.mention_html()} telah di-unban.", parse_mode="HTML"
    )


async def cmd_restrike(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text(
            "⛔ Hanya admin yang bisa menggunakan perintah ini."
        )

    if is_reply_to_bot(update):
        return await update.message.reply_text(
            "🤖 Kamu sedang membalas pesan bot. Tidak ada strike untuk bot 😅"
        )

    target = get_target_user(update)
    if not target:
        return await update.message.reply_text(
            "ℹ️ Balas pesan pengguna yang ingin direset strikenya."
        )

    user_strikes[target.id] = 0
    await update.message.reply_text(
        f"✅ Strike {target.mention_html()} telah direset.", parse_mode="HTML"
    )


async def cmd_cekstrike(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    caller = update.effective_user
    target = get_target_user(update)

    # Jika tidak membalas siapa pun → default target adalah caller
    if not target:
        if caller.id == OWNER_ID:
            return await update.message.reply_text(
                "👑 Owner tidak bisa dicek strikenya 😎"
            )
        target = caller

    uid = target.id
    count = user_strikes.get(uid, 0)
    await update.message.reply_text(
        f"📊 Strike {target.mention_html()}: {count}/{STRIKE_LIMIT}",
        parse_mode="HTML",
    )


async def cmd_resetstrikeall(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text(
            "🚫 Perintah ini hanya untuk pemilik bot."
        )

    user_strikes.clear()
    user_strike_timestamps.clear()

    with open(STRIKE_LOG, "a") as f:
        f.write(f"{datetime.utcnow().isoformat()} - Semua strike direset oleh OWNER\n")

    await update.message.reply_text("✅ Semua strike berhasil direset.")


async def cmd_resetbanall(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text(
            "🚫 Perintah ini hanya untuk pemilik bot."
        )

    # Untuk jaga-jaga, reset file JSON dan data set
    BANNED_USERS.clear()
    save_banned()

    await update.message.reply_text(
        "✅ Semua user yang dibanned telah dihapus dari daftar ban."
    )


# === Admin List ===
async def lihat_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat.type.endswith("group"):
        return await update.message.reply_text("❗Hanya bisa digunakan di grup.")
    admins = await ctx.bot.get_chat_administrators(update.effective_chat.id)
    msg = "*Daftar Admin:*\n\n" + "\n".join(
        f"• {a.user.full_name} (`{a.user.id}`)" for a in admins
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


# === Handler Utama ===
async def moderasi(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # 1. 🔍 Deteksi phishing dulu
    if await handle_phishing(update, ctx):
        return
    global last_global_command

    msg = update.message
    if not msg or not msg.text:
        return

    text = msg.text
    user_id = msg.from_user.id
    chat_id = msg.chat_id
    is_bot = msg.from_user.is_bot

    if user_id in BANNED_USERS:
        try:
            await msg.delete()
        except:
            pass
        return

    # Auto reset strike jika waktunya sudah lewat
    timestamps = user_strike_timestamps.get(user_id, [])
    if timestamps:
        now = datetime.utcnow()
        retained = []
        for i, t in enumerate(timestamps):
            try:
                ts = datetime.fromisoformat(t)
                reset_time = STRIKE_RESET_RULES.get(i + 1)
                if reset_time and now - ts < reset_time:
                    retained.append(t)
            except:
                continue
        user_strike_timestamps[user_id] = retained
        user_strikes[user_id] = len(retained)

    # Deteksi kata kasar, topik sensitif, link
    clean = clean_text(text)

    # Link + kata terlarang → ban
    if any(link in clean for link in ["http", ".com", "t.me/"]):
        if any(bad in clean for bad in BAN_KEYWORDS):
            await msg.delete()
            await ban_user(chat_id, user_id, ctx)
            return

    # Kata kasar → strike / mute / ban
    if any(bad in clean for bad in BAD_WORDS):
        await msg.delete()
        now = datetime.utcnow()
        user_strikes[user_id] += 1
        strikes = user_strikes[user_id]
        user_strike_timestamps[user_id].append(now.isoformat())

        with open(STRIKE_LOG, "a") as f:
            f.write(
                f"{now.isoformat()} - User {user_id} dapat strike ke-{strikes}: {text}\n"
            )

        if strikes >= STRIKE_LIMIT:
            await ban_user(chat_id, user_id, ctx)
            await ctx.bot.send_message(
                chat_id,
                f"🚫 {msg.from_user.mention_html()} dibanned karena terlalu banyak pelanggaran.",
                parse_mode="HTML",
            )
        else:
            await mute_user(chat_id, user_id, ctx)
            await ctx.bot.send_message(
                chat_id,
                f"⚠️ {msg.from_user.mention_html()} strike {strikes}/{STRIKE_LIMIT}. Dimute sementara.",
                parse_mode="HTML",
            )
        return

    # Topik sensitif
    if any(topik in clean for topik in SENSITIF):
        await mute_user(chat_id, user_id, ctx)
        await ctx.bot.send_message(
            chat_id,
            f"⚠️ {msg.from_user.first_name}, topik sensitif (politik/agama/ras) dilarang.",
            parse_mode="HTML",
        )
        return

    # Balasan ke bot → random response
    if msg.reply_to_message and msg.reply_to_message.from_user.is_bot and RESPON_DATA:
        await msg.reply_text(random.choice(RESPON_DATA))
