# === IMPORT DAN KONFIGURASI DASAR ===
import os
import logging
import json
import re
from datetime import datetime
from dateutil.relativedelta import relativedelta
from telegram import Update
from telegram.ext import ContextTypes
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from utils.constants import EPS_DATA
from utils.topic_guard import handle_thread_guard

CACHE_FILE = EPS_DATA
logger = logging.getLogger(__name__)


# === UTILITAS CACHE ===


def load_cache():
    """Membaca file cache hasil EPS jika tersedia."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    """Menyimpan hasil terbaru ke dalam file cache."""
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# === FORMAT TANGGAL & MASA BERLAKU ===


def format_tanggal_korea(tanggal_str):
    """Mengubah format YYYYMMDD ke format tanggal Indonesia."""
    bulan_indo = [
        "",
        "Januari",
        "Februari",
        "Maret",
        "April",
        "Mei",
        "Juni",
        "Juli",
        "Agustus",
        "September",
        "Oktober",
        "November",
        "Desember",
    ]
    try:
        dt = datetime.strptime(tanggal_str, "%Y%m%d")
        return f"{dt.day} {bulan_indo[dt.month]} {dt.year}"
    except:
        return tanggal_str


def format_rentang_masa(masa_str):
    """Mengubah rentang masa YYYYMMDD ~ YYYYMMDD ke format human-readable."""
    try:
        awal, akhir = masa_str.split("~")
        return f"{format_tanggal_korea(awal.strip())} ~ {format_tanggal_korea(akhir.strip())}"
    except:
        return masa_str


def sisa_masa_berlaku(masa_str):
    """Menghitung sisa waktu dari masa berlaku hingga hari ini."""
    try:
        _, akhir = masa_str.split("~")
        akhir_dt = datetime.strptime(akhir.strip(), "%Y%m%d")
        now = datetime.now()
        if akhir_dt < now:
            return "⛔ Sudah kedaluwarsa"
        delta = relativedelta(akhir_dt, now)
        return f"{delta.years} tahun {delta.months} bulan {delta.days} hari"
    except:
        return "-"


# === LOGIKA UJIAN DAN HASIL ===


def hitung_status_lulus(nilai_total, nilai_lulus):
    """Menentukan apakah total nilai >= nilai minimum."""
    try:
        return "✅ Ya" if float(nilai_total) >= float(nilai_lulus) else "❌ Tidak"
    except:
        return "-"


def tentukan_tipe_ujian(masa_str):
    """Menentukan apakah hasil ujian tergolong 'Special' berdasarkan validitas masa."""
    masa = masa_str.strip() if masa_str else ""
    return "Special" if masa and masa not in ["-", "~"] else "General"


def tampilkan_hasil(data, sumber=""):
    """Merakit string hasil ujian dari data dan sumber (cache atau live)."""
    tipe_ujian = tentukan_tipe_ujian(data.get("masa", ""))
    status = hitung_status_lulus(data["total"], data["lulus_min"])
    header = f"📋 *Hasil Ujian EPS-TOPIK {tipe_ujian}*"
    if sumber:
        header += f" ({sumber})"

    hasil = f"""{header}

👱‍♂️ *Nama:* {data['nama']}
🌍 *Negara:* {data['negara']}
🏭 *Sektor:* {data['bidang']}
📅 *Tanggal Ujian:* {format_tanggal_korea(data['tanggal'])}

📖 *Reading:* {data['bacaan']}
🎧 *Listening:* {data['mendengar']}
📊 *Total Nilai:* {data['total']}
🎯 *KKM:* {data['lulus_min']}
🏅 *Lulus:* {status}
"""

    if status == "✅ Ya":
        hasil += f"""📆 *Masa Berlaku:* {format_rentang_masa(data['masa'])}
⏳ *Sisa Masa Berlaku:* {sisa_masa_berlaku(data['masa'])}"""
    else:
        hasil += "📆 *Masa Berlaku:* -\n⏳ *Sisa Masa Berlaku:* -"

    return hasil


# === HANDLER TELEGRAM ===
async def cek_eps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await handle_thread_guard("cek_eps", update, context):
        return
    """Handler utama untuk perintah /cek <nomor ujian>"""
    if not context.args:
        await update.message.reply_text(
            "Masukkan nomor ujian setelah /cek. Contoh: /cek 0122025C50525051"
        )
        return

    nomor_ujian = context.args[0].strip()
    if not re.fullmatch(r"[A-Z0-9]{16}", nomor_ujian):
        logger.warning(f"❌ Nomor ujian tidak valid: {nomor_ujian}")
        await update.message.reply_text(
            "❌ Format salah. Nomor ujian harus 16 karakter.\nContoh: 0122024C50450997"
        )
        return

    cache = load_cache()
    if nomor_ujian in cache:
        data = cache[nomor_ujian]
        logger.info(f"✅ Ambil dari cache untuk {nomor_ujian}")
        result = tampilkan_hasil(data, "Tersimpan")
        await update.message.reply_text(result, parse_mode="Markdown")
        return

    # Ambil dari web jika belum ada di cache
    logger.info(f"🔍 Scraping hasil untuk: {nomor_ujian}")
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")

        driver = webdriver.Chrome(options=chrome_options)
        driver.get("https://www.eps.go.kr/eo/VisaFndRM.eo?langType=in")

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "sKorTestNo"))
        )
        input_box = driver.find_element(By.ID, "sKorTestNo")
        input_box.clear()
        input_box.send_keys(nomor_ujian)

        tombol_view = driver.find_element(By.XPATH, "//button[contains(text(),'View')]")
        tombol_view.click()

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "tbl_typeA"))
        )
        soup = BeautifulSoup(driver.page_source, "html.parser")
        driver.quit()
        logger.info(f"✅ {nomor_ujian} Founded!")

        table = soup.select_one(".tbl_typeA")
        rows = table.find_all("tr")
        cells = [
            cell.get_text(strip=True) for row in rows for cell in row.find_all("td")
        ]

        logger.info(f"✅ {nomor_ujian} Proses Menyimpan........")
        if len(cells) >= 12:
            data = {
                "nama": cells[5],
                "negara": cells[1],
                "bidang": cells[2],
                "tanggal": cells[3],
                "mendengar": cells[6],
                "bacaan": cells[7],
                "total": cells[8],
                "lulus_min": cells[9],
                "status": cells[10],
                "masa": cells[11],
            }
            result = tampilkan_hasil(data)
            cache[nomor_ujian] = data
            save_cache(cache)
            logger.info(f"✅ {nomor_ujian} Disimpan di JSON.")
        else:
            result = "❌ Data tidak ditemukan atau belum diumumkan."

        await update.message.reply_text(result, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"❌ Gagal scraping EPS: {e}", exc_info=True)
        await update.message.reply_text("❌ Terjadi kesalahan saat mengambil hasil.")
