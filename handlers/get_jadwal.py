import logging
import subprocess
import json
import os
import html
from telegram import Update
from telegram.ext import ContextTypes
from bs4 import BeautifulSoup
from utils.constants import JADWAL_EPS
from utils.topic_guard import handle_thread_guard

logger = logging.getLogger(__name__)

URL_JADWAL = (
    "https://epstopik.hrdkorea.or.kr/epstopik/abot/exam/sechduleGuideList.do?lang=en"
)
CACHE_FILE = JADWAL_EPS


def ambil_data_jadwal():
    try:
        result = subprocess.run(
            ["curl", "-s", "-A", "Mozilla/5.0", URL_JADWAL],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )

        if result.returncode != 0:
            logger.error(f"Curl error: {result.stderr.decode()}")
            return []

        html_text = result.stdout.decode("utf-8")

        soup = BeautifulSoup(html_text, "html.parser")
        rows = soup.select("table.tableType tr[id^='tr_']")

        if not rows:
            logger.warning("⚠️ Tidak ada baris data ditemukan.")
            return []

        data = []
        for row in rows[:10]:
            kolom = row.find_all("td")
            if len(kolom) < 4:
                continue
            data.append(
                {
                    "nation": kolom[0].get_text(strip=True),
                    "title": kolom[1].get_text(strip=True),
                    "type": kolom[2].get_text(strip=True),
                    "announcement_date": kolom[3].get_text(strip=True),
                }
            )

        return data
    except Exception as e:
        logger.error("Gagal mengambil data jadwal", exc_info=True)
        return []


def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("jadwal", [])
    return []


def simpan_cache(data):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump({"jadwal": data}, f, indent=2, ensure_ascii=False)


def is_data_baru(data_baru, data_lama):
    judul_baru = [d["title"] for d in data_baru]
    judul_lama = [d["title"] for d in data_lama]
    return judul_baru != judul_lama


async def get_jadwal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await handle_thread_guard("get_jadwal", update, context):
        return
    try:
        jumlah = 1
        if context.args:
            try:
                jumlah = int(context.args[0])
                if not (1 <= jumlah <= 10):
                    await update.message.reply_text("❗ Masukkan angka antara 1–10.")
                    return
            except ValueError:
                await update.message.reply_text("❗ Format salah. Contoh: /jadwal 3")
                return

        data_lama = load_cache()
        data_baru = ambil_data_jadwal()

        if data_baru:
            if is_data_baru(data_baru, data_lama):
                simpan_cache(data_baru)
                data = data_baru
            else:
                data = data_lama
        else:
            data = data_lama

        if not data:
            await update.message.reply_text("⚠️ Tidak ada data jadwal ditemukan.")
            return

        pesan = ""
        for idx, item in enumerate(data[:jumlah], start=1):
            pesan += (
                f"<b>{idx}. 📅 Jadwal Ujian EPS-TOPIK</b>\n\n"
                f"<b>📌 Judul:</b> {html.escape(item.get('title', '-'))}\n"
                f"<b>🧪 Jenis Ujian:</b> {html.escape(item.get('type', '-'))}\n"
                f"<b>🌍 Negara:</b> {html.escape(item.get('nation', '-'))}\n"
                f"<b>📢 Tanggal Pengumuman Jadwal:</b> {html.escape(item.get('announcement_date', '-'))}\n"
                f'<a href="{URL_JADWAL}">🔗 Selengkapnya (klik di sini)</a>\n\n'
            )

        await update.message.reply_text(
            pesan.strip(), parse_mode="HTML", disable_web_page_preview=True
        )

    except Exception as e:
        logger.error("❌ Gagal ambil data jadwal", exc_info=True)
        await update.message.reply_text(
            "❌ Terjadi kesalahan saat mengambil data jadwal."
        )
