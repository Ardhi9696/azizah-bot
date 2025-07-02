import json
import os
import random
import difflib
from telegram import Update
from telegram.ext import ContextTypes
from utils.constants import RESPON_FILE

# === Load file respon.json ===
def load_responses():
    if os.path.exists(RESPON_FILE):
        with open(RESPON_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


responses = load_responses()


# === Normalisasi teks: huruf kecil, hapus spasi berlebih ===
def normalisasi(teks: str):
    return " ".join(teks.lower().strip().split())


# === Cari kategori berdasarkan kemiripan teks dengan kunci ===
def cari_kategori(pesan: str):
    pesan_norm = normalisasi(pesan)

    kandidat = [
        (kunci, kunci.replace("_", " ")) for kunci in responses if kunci != "mood_swing"
    ]
    semua_teks = [item[1] for item in kandidat]

    cocok = difflib.get_close_matches(pesan_norm, semua_teks, n=1, cutoff=0.7)
    if cocok:
        for kunci, teks in kandidat:
            if teks == cocok[0]:
                return kunci

    if "korea" in pesan_norm:
        return "belajar_korea"

    return None


# === Fallback respon mood swing random ===
def mood_swing_respon():
    mood = random.choice(list(responses.get("mood_swing", {"netral": ["..."]})))
    return random.choice(responses["mood_swing"][mood])


# === Responder utama ===
async def simple_responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    pesan_obj = update.message
    text = pesan_obj.text.lower()

    # Cek apakah reply ke bot
    is_reply_to_bot = (
        pesan_obj.reply_to_message
        and pesan_obj.reply_to_message.from_user
        and pesan_obj.reply_to_message.from_user.is_bot
    )

    # Cek mention ke bot
    bot_username = context.bot.username.lower() if context.bot.username else ""
    is_mention_bot = bot_username and bot_username in text

    if not is_reply_to_bot and not is_mention_bot:
        return  # Tidak balas kalau bukan reply atau mention

    # === Respon berdasarkan kata kunci spesifik ===
    if "kata hari ini" in text or "word of the day" in text:
        balasan = random.choice(
            responses.get("kata_hari_ini", ["Hari ini spesial, kayak kamu~ ✨"])
        )
    elif "tebakan" in text:
        balasan = random.choice(
            responses.get("tebakan", ["Aku punya tebakan, tapi rahasia~ 🙊"])
        )
    elif "puji" in text:
        balasan = random.choice(
            responses.get("pujian", ["Kamu keren banget deh hari ini 😍"])
        )
    elif "marah" in text:
        balasan = random.choice(
            responses.get("marah", ["Aku marah lho! Tapi tetep sayang... 😤❤️"])
        )
    elif "semangat" in text or "support dong" in text:
        balasan = random.choice(responses.get("penyemangat", ["Semangattt!! 🚀"]))
    elif "ngambek" in text:
        balasan = random.choice(responses.get("ngambek_parah", ["Aku ngambek! 😤"]))
    elif "motivasi korea" in text:
        balasan = random.choice(
            responses.get(
                "motivasi_korea", ["공부 열심히 해요! (Belajarlah dengan semangat!)"]
            )
        )
    else:
        # === Cari berdasarkan kategori ===
        kategori = cari_kategori(text)
        if kategori and kategori in responses:
            balasan = random.choice(responses[kategori])
        else:
            # === Fallback ke random respon umum / mood swing ===
            pilihan = []
            if "sarkasme_lucu" in responses:
                pilihan += responses["sarkasme_lucu"]
            pilihan += [
                "Hmm aku juga masih belajar... 😅",
                "Kamu nanya kayak gitu ke aku? 😐",
                "Kalau capek, rehat. Tapi jangan nyerah ya 💪",
                mood_swing_respon(),
            ]
            balasan = random.choice(pilihan)

    await pesan_obj.reply_text(balasan)
