import os, json, re, logging
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

logger = logging.getLogger(__name__)
CACHE_FILE = EPS_DATA


# ------- cache utils -------
def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    return {}


def save_cache(cache: dict):
    os.makedirs(os.path.dirname(CACHE_FILE) or ".", exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# ------- tanggal utils -------
BULAN_ID = [
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


def format_tanggal_korea(tanggal_str: str) -> str:
    try:
        dt = datetime.strptime(tanggal_str, "%Y%m%d")
        return f"{dt.day} {BULAN_ID[dt.month]} {dt.year}"
    except Exception:
        return tanggal_str


def format_rentang_masa(masa_str: str) -> str:
    try:
        awal, akhir = masa_str.split("~")
        return f"{format_tanggal_korea(awal.strip())} ~ {format_tanggal_korea(akhir.strip())}"
    except Exception:
        return masa_str


def sisa_masa_berlaku(masa_str: str) -> str:
    try:
        _, akhir = masa_str.split("~")
        akhir_dt = datetime.strptime(akhir.strip(), "%Y%m%d")
        now = datetime.now()
        if akhir_dt < now:
            return "⛔ Sudah kedaluwarsa"
        delta = relativedelta(akhir_dt, now)
        return f"{delta.years} tahun {delta.months} bulan {delta.days} hari"
    except Exception:
        return "-"


# ------- penilaian -------
def hitung_status_lulus(total, minimal) -> str:
    try:
        return "✅ Ya" if float(total) >= float(minimal) else "❌ Tidak"
    except Exception:
        return "-"


def tentukan_tipe_ujian(masa_str: str) -> str:
    masa = (masa_str or "").strip()
    return "Special" if masa and masa not in ["-", "~"] else "General"


def tampilkan_hasil(data: dict, sumber: str = "") -> str:
    tipe = tentukan_tipe_ujian(data.get("masa", ""))
    lulus = hitung_status_lulus(data.get("total"), data.get("lulus_min"))
    header = f"📋 *Hasil Ujian EPS-TOPIK {tipe}*"
    if sumber:
        header += f" ({sumber})"

    out = f"""{header}

👱‍♂️ *Nama:* {data.get('nama','-')}
🌍 *Negara:* {data.get('negara','-')}
🏭 *Sektor:* {data.get('bidang','-')}
📅 *Tanggal Ujian:* {format_tanggal_korea(data.get('tanggal','-'))}

📖 *Reading:* {data.get('bacaan','-')}
🎧 *Listening:* {data.get('mendengar','-')}
📊 *Total Nilai:* {data.get('total','-')}
🎯 *KKM:* {data.get('lulus_min','-')}
🏅 *Lulus:* {lulus}
"""
    if lulus == "✅ Ya":
        out += f"""📆 *Masa Berlaku:* {format_rentang_masa(data.get('masa','-'))}
⏳ *Sisa Masa Berlaku:* {sisa_masa_berlaku(data.get('masa','-'))}"""
    else:
        out += "📆 *Masa Berlaku:* -\n⏳ *Sisa Masa Berlaku:* -"
    return out


# ------- handler utama -------
async def cek_ujian(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Thread ID sekarang: %s", update.effective_message.message_thread_id)
    logger.info(
        f"[CHECK] /cek invoked in chat={update.effective_chat.id} thread={getattr(update.effective_message,'message_thread_id',None)} by uid={update.effective_user.id}"
    )

    if not await handle_thread_guard("cek", update, context):
        return

    if not context.args:
        await update.message.reply_text(
            "Masukkan nomor ujian setelah /cek. Contoh: /cek 0122025C50525051"
        )
        return

    nomor_ujian = context.args[0].strip().upper()  # <- normalize ke uppercase
    if not re.fullmatch(r"[A-Z0-9]{16}", nomor_ujian):
        logger.warning("Nomor ujian tidak valid: %s", nomor_ujian)
        await update.message.reply_text(
            "❌ Format salah. Nomor ujian harus 16 karakter.\nContoh: 0122024C50450997"
        )
        return

    # Kirim pesan "Mengecek hasil ujian..." dan simpan message_id-nya
    wait_message = await update.message.reply_text("🔍 Mengecek hasil ujian...")
    wait_message_id = wait_message.message_id

    async def _delete_wait_message():
        """Hapus pesan 'Mengecek hasil ujian...'"""
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id, message_id=wait_message_id
            )
            logger.info("Pesan 'Mengecek hasil ujian...' dihapus.")
        except Exception:
            pass

    # cek cache dulu
    cache = load_cache()
    if nomor_ujian in cache:
        data = cache[nomor_ujian]
        logger.info("Cache hit untuk %s", nomor_ujian)

        # Hapus pesan "Mengecek hasil ujian..." sebelum kirim hasil
        await _delete_wait_message()

        await update.message.reply_text(
            tampilkan_hasil(data, "Tersimpan"), parse_mode="Markdown"
        )
        return

    logger.info("Scraping hasil untuk: %s", nomor_ujian)
    driver = None
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")

        driver = webdriver.Chrome(options=chrome_options)
        driver.get("https://www.eps.go.kr/eo/VisaFndRM.eo?langType=in")

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "sKorTestNo"))
        )
        box = driver.find_element(By.ID, "sKorTestNo")
        box.clear()
        box.send_keys(nomor_ujian)

        driver.find_element(By.XPATH, "//button[contains(text(),'View')]").click()

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "tbl_typeA"))
        )
        soup = BeautifulSoup(driver.page_source, "html.parser")

        table = soup.select_one(".tbl_typeA")
        if not table:
            # Hapus pesan "Mengecek hasil ujian..." sebelum kirim error
            await _delete_wait_message()
            await update.message.reply_text(
                "❌ Data tidak ditemukan atau situs berubah."
            )
            return

        rows = table.find_all("tr")
        cells = [td.get_text(strip=True) for tr in rows for td in tr.find_all("td")]

        # Struktur sangat tergantung HTML; pertahankan offset kamu:
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
            cache[nomor_ujian] = data
            save_cache(cache)
            logger.info("%s disimpan ke cache", nomor_ujian)

            # Hapus pesan "Mengecek hasil ujian..." sebelum kirim hasil
            await _delete_wait_message()

            await update.message.reply_text(
                tampilkan_hasil(data), parse_mode="Markdown"
            )
        else:
            # Hapus pesan "Mengecek hasil ujian..." sebelum kirim error
            await _delete_wait_message()
            await update.message.reply_text(
                "❌ Data tidak ditemukan atau belum diumumkan."
            )
    except Exception as e:
        logger.error("Gagal scraping EPS: %s", e, exc_info=True)

        # Hapus pesan "Mengecek hasil ujian..." sebelum kirim error
        await _delete_wait_message()

        await update.message.reply_text("❌ Terjadi kesalahan saat mengambil hasil.")
    finally:
        if driver:
            driver.quit()
