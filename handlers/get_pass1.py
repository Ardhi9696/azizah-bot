import os
import json
import subprocess
import logging
from html import escape
from telegram import Update
from telegram.ext import ContextTypes
from bs4 import BeautifulSoup
from utils.constants import EPS_TAHAP1
from utils.topic_guard import handle_thread_guard

logger = logging.getLogger(__name__)

URL_TAHAP1 = "https://epstopik.hrdkorea.or.kr/epstopik/pass/candidate/functionalLevelCandidateList.do?lang=en"
CACHE_FILE = EPS_TAHAP1


def ambil_html(url: str, fallback_filename: str) -> str:
    try:
        result = subprocess.run(
            ["curl", "-sLk", "-A", "Mozilla/5.0", url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout.decode("utf-8", errors="replace")
        logger.error(f"Curl error ({url}): {result.stderr.decode(errors='replace')}")
    except Exception:
        logger.exception("curl exception")

    for local_path in (fallback_filename, os.path.join("data", fallback_filename)):
        if os.path.exists(local_path):
            try:
                with open(local_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                logger.exception("Gagal baca fallback %s", local_path)
    return ""


def ambil_data_tahap1():
    try:
        html_text = ambil_html(URL_TAHAP1, "pass1.html")
        if not html_text:
            return []

        soup = BeautifulSoup(html_text, "html.parser")
        rows = soup.select("table.tableType tr[id^='tr_']")
        if not rows:
            table = soup.find("table", class_="tableType") or soup.find("table")
            if table:
                rows = [tr for tr in table.find_all("tr") if tr.find_all("td")]

        if not rows:
            logger.warning("⚠️ Tidak ada baris data tahap1 ditemukan (selector kosong).")
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
                    "date": kolom[3].get_text(strip=True),
                }
            )

        return data
    except Exception as e:
        logger.error("Gagal ambil data tahap 1", exc_info=True)
        return []


def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("tahap1", [])
    return []


def simpan_cache(data):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump({"tahap1": data}, f, indent=2, ensure_ascii=False)


def is_data_baru(data_baru, data_lama):
    key = lambda d: (
        d.get("title", ""),
        d.get("type", ""),
        d.get("date", ""),
        d.get("nation", ""),
    )
    baru = [key(d) for d in data_baru]
    lama = [key(d) for d in data_lama]
    return baru != lama


def format_tahap1_html(data: list, jumlah: int = 1) -> str:
    output = []
    jumlah = max(1, min(jumlah, 10))

    for i, item in enumerate(data[:jumlah], 1):
        bagian = (
            f"<b>{i}. 🧾 Hasil Tahap 1 EPS-TOPIK</b>\n\n"
            f"<b>📌 Judul:</b> {escape(item.get('title', '-'))}\n"
            f"<b>🧪 Jenis Ujian:</b> {escape(item.get('type', '-'))}\n"
            f"<b>🌍 Negara:</b> {escape(item.get('nation', '-'))}\n"
            f"<b>📅 Diumumkan:</b> {escape(item.get('date', '-'))}\n"
            f'<a href="{URL_TAHAP1}">🔗 Selengkapnya (klik di sini)</a>\n\n'
        )
        output.append(bagian)

    return "".join(output)


async def get_pass1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await handle_thread_guard("get_pass1", update, context):
        return

    try:
        jumlah = 1
        if context.args and context.args[0].isdigit():
            jumlah = int(context.args[0])

        data_lama = load_cache()
        data_baru = ambil_data_tahap1()

        data = data_lama
        if data_baru:
            if is_data_baru(data_baru, data_lama) or not data_lama:
                simpan_cache(data_baru)
                data = data_baru
            else:
                data = data_lama

        if not data:
            await update.message.reply_text("⚠️ Tidak ada data tahap 1 ditemukan.")
            return

        pesan = format_tahap1_html(data, jumlah)
        await update.message.reply_text(
            pesan.strip(), parse_mode="HTML", disable_web_page_preview=True
        )

    except Exception as e:
        logger.error("❌ Gagal ambil data tahap 1", exc_info=True)
        await update.message.reply_text(
            "❌ Terjadi kesalahan saat mengambil data tahap 1."
        )
