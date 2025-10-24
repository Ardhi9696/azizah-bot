import logging
import os
import json
import requests
from bs4 import BeautifulSoup
from html import unescape
from telegram import Update
from telegram.ext import ContextTypes
from utils.constants import PENGUMUMAN_FILE
from utils.topic_guard import handle_thread_guard


logger = logging.getLogger(__name__)

API_URL = "https://www.kp2mi.go.id/gtog-data/korea/Pengumuman?draw=1&start=0&length=10"
CACHE_FILE = PENGUMUMAN_FILE


# === Parser judul & link ===
def parse_judul_link(html_string):
    if not html_string or not isinstance(html_string, str):
        return "Judul tidak ditemukan", "-"

    raw_html = unescape(html_string)
    soup = BeautifulSoup(raw_html, "html.parser")
    a = soup.find("a")
    if not a or not a.get("href"):

        return "Judul tidak ditemukan", "-"
    teks = a.get_text(strip=True)
    href = a["href"].replace("\\/", "/").strip()
    if href.startswith("/"):
        href = f"https://www.kp2mi.go.id{href}"
    return teks, href


# === Cache ===
def load_cache_info():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_cache_info(api_data):
    cleaned = []
    for item in api_data:
        html_judul = item.get("judul", "")
        judul, link = parse_judul_link(html_judul)

        if judul == "Judul tidak ditemukan" or link == "-":

            continue

        cleaned.append(
            {
                "id": item.get("id"),
                "judul": judul,
                "link": link,
                "creator": item.get("creator", "-"),
                "is_active": item.get("is_active", 1),
                "created_at": item.get("created_at", "-"),
                "updated_at": item.get("updated_at", "-"),
                "view": item.get("view", 0),
                "kategori": item.get("kategori", "-"),
                "tanggal": item.get("tanggal", "-"),
            }
        )

    if cleaned:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cleaned, f, ensure_ascii=False, indent=2)


# === Handler ===
async def get_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await handle_thread_guard("get_info", update, context):
        return
    try:
        jumlah = 1
        if context.args:
            try:
                jumlah = int(context.args[0])
                if not (1 <= jumlah <= 10):
                    await update.message.reply_text("Masukkan angka antara 1–10.")
                    return
            except ValueError:
                await update.message.reply_text("Format salah. Contoh: /get 3")
                return

        response = requests.get(API_URL)
        api_data = response.json().get("data", [])

        if not api_data:
            logger.warning("API tidak mengembalikan data.")
            await update.message.reply_text("⚠️ Tidak ada pengumuman ditemukan.")
            return

        cache_data = load_cache_info()
        id_terakhir_cache = cache_data[0]["id"] if cache_data else None
        id_terbaru_api = api_data[0].get("id")

        if id_terakhir_cache != id_terbaru_api:
            logger.info("📥 Ditemukan pengumuman baru, update cache.")
            save_cache_info(api_data)
            data = load_cache_info()[:jumlah]
        else:
            logger.info("🟡 Tidak ada pengumuman baru — gunakan cache (update view)")
            save_cache_info(api_data)
            logger.info(
                "ℹ️ Cache diperbarui untuk menyinkronkan view atau data lainnya."
            )
            updated_cache = []
            for i, cached_item in enumerate(cache_data):
                if i < len(api_data):
                    cached_item["view"] = api_data[i].get(
                        "view", cached_item.get("view")
                    )
                updated_cache.append(cached_item)
            save_cache_info(updated_cache)
            data = updated_cache[:jumlah]

        pesan = ""
        for idx, item in enumerate(data, start=1):
            judul = item.get("judul", "-")
            link = item.get("link", "-")
            pesan += (
                f"*{idx}. 📢 {judul}*\n\n"
                f"🆔 ID: `{item.get('id', '-')}`\n"
                f"✍️ Creator: `{item.get('creator', '-')}`\n"
                f"📅 Tanggal: `{item.get('tanggal', '-')}`\n"
                f"👁️ View: `{item.get('view', '-')}`\n"
                f"🏷️ Kategori: `{item.get('kategori', '-')}`\n"
            )
            if link and link != "-":
                pesan += f"🔗 [Klik untuk lihat pengumuman]({link})\n"

            if jumlah > 1 and idx < jumlah:
                pesan += "\n==========================\n\n"

        await update.message.reply_text(pesan.strip(), parse_mode="Markdown")

    except Exception as e:
        logger.error("❌ Gagal ambil data pengumuman", exc_info=True)
        await update.message.reply_text(
            "❌ Terjadi kesalahan saat mengambil pengumuman."
        )
