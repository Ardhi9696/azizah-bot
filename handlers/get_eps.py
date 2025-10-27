import os
import json
import logging
import re

# ====== Tambahkan di bagian import paling atas ======
import time
from typing import List, Dict, Tuple, Optional

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ContextTypes
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import UnexpectedAlertPresentException
from utils.constants import EPS_PROGRESS
from bs4 import BeautifulSoup

# ====== Konstanta selector & pola tanggal (tambahkan sekali saja) ======
SEL = {
    "nama_ready": "table.tbl_typeA.center",
    "nama_value": "table.tbl_typeA.center td:nth-child(2)",
    "tables_purple": "table.tbl_typeA.purple.mt30",
    "row2_anchor": 'table.tbl_typeA.purple.mt30 a[href^="javascript:fncDetailRow("]',
}

DATE_YYYYMMDD = r"\d{4}-\d{2}-\d{2}"
DATE_RANGE = r"(\d{4}-\d{2}-\d{2}~\d{4}-\d{2}-\d{2})"


load_dotenv()
USERNAME = os.getenv("EPS_USERNAME")
PASSWORD = os.getenv("EPS_PASSWORD")
BIRTHDAY = os.getenv("EPS_BIRTHDAY")
OWNER_ID = int(os.getenv("MY_TELEGRAM_ID"))  # <- tambahkan di .env misal: 7088612068

LOGIN_URL = "https://www.eps.go.kr/eo/langMain.eo?langCD=in"
PROGRESS_URL = (
    "https://www.eps.go.kr/eo/EntProgCk.eo?pgID=P_000000015&langCD=in&menuID=10008"
)


def setup_driver():
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--headless=new")
    return webdriver.Chrome(options=options)


def login(driver):
    driver.get(LOGIN_URL)
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "sKorTestNo"))
        )
        driver.find_element(By.ID, "sKorTestNo").send_keys(USERNAME)
        driver.find_element(By.ID, "sFnrwRecvNo").send_keys(PASSWORD)
        driver.find_element(By.CLASS_NAME, "btn_login").click()
        WebDriverWait(driver, 10).until(
            lambda d: "langMain.eo" in d.current_url or "birthChk" in d.page_source
        )
        return True
    except UnexpectedAlertPresentException:
        alert = driver.switch_to.alert
        alert.accept()
        return False
    except Exception:
        return False


def verifikasi_tanggal_lahir(driver, birthday):
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "chkBirtDt"))
        )
        input_birth = driver.find_element(By.ID, "chkBirtDt")
        input_birth.clear()
        input_birth.send_keys(birthday)
        tombol = driver.find_element(By.CSS_SELECTOR, "span.buttonE > button")
        tombol.click()
        WebDriverWait(driver, 10).until(EC.url_contains("langMain.eo"))
        return True
    except:
        return False


# ====== Helper kecil untuk parsing ======
def _extract_first_date(text: str) -> str:
    if not text:
        return "-"
    m = re.search(DATE_YYYYMMDD, text)
    return m.group(0) if m else "-"


def _extract_date_range(text: str) -> Optional[str]:
    if not text:
        return None
    m = re.search(DATE_RANGE, text)
    return m.group(1) if m else None


def _parse_pengiriman_table(t1_soup) -> List[Dict]:
    """Parse tabel pengiriman/penerimaan (purple pertama)."""
    rows = []
    for tr in t1_soup.select("tbody tr"):
        tds = tr.select("td")
        if len(tds) < 3:
            continue

        no_text = tds[0].get_text(strip=True)

        ref_id = None
        a_tag = tds[0].select_one('a[href^="javascript:fncDetailRow("]')
        if a_tag:
            href = a_tag.get("href") or ""
            m = re.search(r"fncDetailRow\('([^']+)'", href)
            if m:
                ref_id = m.group(1)

        tanggal_kirim = tds[1].get_text(" ", strip=True)
        penerimaan_raw = tds[2].get_text("\n", strip=True)

        rows.append(
            {
                "no": no_text,
                "ref_id": ref_id,
                "tanggal_kirim": tanggal_kirim,
                "tanggal_terima": _extract_first_date(penerimaan_raw),
                "masa_berlaku": _extract_date_range(penerimaan_raw),
                "raw": penerimaan_raw,
            }
        )
    return rows


def _parse_riwayat_table(t2_soup) -> List[Tuple[str, str, str]]:
    riwayat = []
    for row in t2_soup.select("tbody tr"):
        cols = row.select("td")
        if len(cols) >= 3:
            prosedur = cols[0].get_text(strip=True)
            status = cols[1].get_text(" ", strip=True)
            tanggal = cols[2].get_text(" ", strip=True)
            riwayat.append((prosedur, status, tanggal))
    return riwayat


def _pick_latest(pengiriman_list: List[Dict]) -> Optional[Dict]:
    if not pengiriman_list:
        return None
    try:
        return max(
            pengiriman_list,
            key=lambda r: int(re.sub(r"\D", "", r.get("no", "") or "0") or 0),
        )
    except Exception:
        return pengiriman_list[-1]


def _try_select_row2(driver) -> Optional[str]:
    """Kalau ada link baris '2', jalankan fncDetailRow/klik, tunggu tabel detail reload, lalu return ref_id yang dipilih."""
    try:
        old_tables = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, SEL["tables_purple"]))
        )
        old_detail_el = old_tables[1] if len(old_tables) >= 2 else None
    except Exception:
        old_detail_el = None

    # cari anchor yang teksnya '2'
    anchors = driver.find_elements(By.CSS_SELECTOR, SEL["row2_anchor"])
    chosen = None
    ref_id = None
    for a in anchors:
        if (a.text or "").strip() == "2":
            chosen = a
            href = a.get_attribute("href") or ""
            m = re.search(r"fncDetailRow\('([^']+)'", href)
            if m:
                ref_id = m.group(1)
            break

    if not chosen or not ref_id:
        return None

    # eksekusi
    try:
        driver.execute_script(f"return fncDetailRow('{ref_id}', '');")
    except Exception:
        chosen.click()

    # tunggu perubahan
    try:
        if old_detail_el:
            WebDriverWait(driver, 10).until(EC.staleness_of(old_detail_el))
        WebDriverWait(driver, 15).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, SEL["tables_purple"]))
        )
    except Exception:
        time.sleep(1.0)

    return ref_id


# ====== Akses & scrap utama (REFRESHED) ======
def akses_progress(driver, prefer_row2: bool = True):
    driver.get(PROGRESS_URL)

    # Pastikan halaman siap
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, SEL["nama_ready"]))
    )

    # Jika ada 2 row, pilih row #2 dulu agar detail menyesuaikan
    aktif_ref_id = None
    if prefer_row2:
        try:
            aktif_ref_id = _try_select_row2(driver)
        except Exception:
            aktif_ref_id = None  # lanjut scraping tanpa switch

    # Ambil HTML terkini setelah (mungkin) switch
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, SEL["nama_ready"]))
    )
    soup = BeautifulSoup(driver.page_source, "html.parser")

    # Nama
    nama_el = soup.select_one(SEL["nama_value"])
    nama = nama_el.get_text(strip=True) if nama_el else "-"

    # Tabel-tabel ungu
    purple_tables = soup.select(SEL["tables_purple"])

    # Tabel 1: Pengiriman/Penerimaan
    pengiriman_list = _parse_pengiriman_table(purple_tables[0]) if purple_tables else []
    pengiriman_latest = _pick_latest(pengiriman_list)

    # Tabel 2: Riwayat prosedur
    riwayat = _parse_riwayat_table(purple_tables[1]) if len(purple_tables) >= 2 else []

    # ref aktif: jika kita barusan pilih row2 pakai JS, gunakan itu; kalau tidak ada, pakai ref latest
    if not aktif_ref_id and pengiriman_latest:
        aktif_ref_id = pengiriman_latest.get("ref_id")

    # Bentuk hasil kompatibel lama + tambahan
    return {
        "nama": nama,
        "aktif_ref_id": aktif_ref_id,  # bisa ditampilkan di header
        "pengiriman": (
            {
                "no": pengiriman_latest.get("no", "-"),
                "ref_id": pengiriman_latest.get("ref_id"),
                "tanggal_kirim": pengiriman_latest.get("tanggal_kirim", "-"),
                "tanggal_terima": (
                    (pengiriman_latest.get("tanggal_terima", "-") or "-")
                    + (
                        f"  Masa Berlaku: {pengiriman_latest.get('masa_berlaku')}"
                        if pengiriman_latest.get("masa_berlaku")
                        else ""
                    )
                ),
            }
            if pengiriman_latest
            else {
                "no": "-",
                "ref_id": None,
                "tanggal_kirim": "-",
                "tanggal_terima": "-",
            }
        ),
        "pengiriman_list": pengiriman_list,
        "riwayat": riwayat,
    }


# ====== Formatter (REFRESHED) ======
def format_data(data: dict) -> str:
    emoji_map = {
        "Ujian Bahasa Korea": "📝",
        "Pengiriman": "📮",
        "Penerimaan": "📥",
        "Tanggal Pengiriman Daftar Pencari Kerja": "📮",
        "Tanggal Penerimaan Daftar Pencari Kerja": "📥",
        "Keadaan pencarian pekerjaan": "🏢",
        "Pengeluaran Izin Kerja": "📄",
        "Pengiriman SLC": "📤",
        "Penandatanganan SLC": "✍️",
        "Pengeluaran CCVI": "📑",
        "Tanggal Masuk Sementara": "🛬",
        "Tanggal Masuk Sesungguhnya": "🛬",
        "Penugasan kerja": "📌",
        # versi Korea
        "고용허가제 한국어능력시험": "📝",
        "구직자명부 전송일": "📮",
        "구직자명부 인증일": "📥",
        "구직 진행상태": "🏢",
        "고용허가서 발급": "📄",
        "표준근로계약서 전송": "📤",
        "표준근로계약 체결": "✍️",
        "사증발급인정서 발급": "📑",
        "입국예상일": "🛬",
        "실제입국일": "🛬",
        "사업장 배치": "📌",
    }

    lines = ["<b>📋 Hasil Kemajuan EPS</b>\n"]
    lines.append(f"<b>👤 Nama:</b> {data.get('nama', '-')}")

    aktif_ref = data.get("aktif_ref_id")
    if aktif_ref:
        lines.append(f"<b>🆔 Ref ID aktif:</b> <code>{aktif_ref}</code>")

    pengiriman_latest = data.get("pengiriman", {}) or {}
    t_kirim = pengiriman_latest.get("tanggal_kirim", "-")
    t_terima_raw = pengiriman_latest.get("tanggal_terima", "-")
    ref_id_latest = pengiriman_latest.get("ref_id")

    masa = _extract_date_range(t_terima_raw or "")
    t_terima = _extract_first_date(t_terima_raw or "")

    lines.append(f"<b>📮 Pengiriman (terbaru):</b> {t_kirim}")
    lines.append(f"<b>✅ Penerimaan (terbaru):</b> {t_terima}")
    if ref_id_latest:
        lines.append(f"<b>🆔 Ref ID (terbaru):</b> <code>{ref_id_latest}</code>")
    if masa:
        lines.append(f"<b>📆 Masa Aktif :</b> {masa}")

    # Riwayat pengiriman/penerimaan
    pengiriman_list = data.get("pengiriman_list") or []
    if pengiriman_list:
        lines.append("\n<b>🗂️ Riwayat Pengiriman/Penerimaan:</b>")
        for r in pengiriman_list:
            parts = [f"<b>#{r.get('no', '-')}</b>"]
            if r.get("ref_id"):
                parts.append(f"ID: <code>{r['ref_id']}</code>")
            parts.append(f"Kirim: {r.get('tanggal_kirim', '-')}")
            parts.append(f"Terima: {r.get('tanggal_terima', '-')}")
            if r.get("masa_berlaku"):
                parts.append(f"Masa: {r['masa_berlaku']}")
            lines.append("• " + " | ".join(parts))

    # Riwayat prosedur
    lines.append("\n<b>🧾 Progres Kemajuan Imigrasi:</b>")
    for idx, (prosedur, status, tanggal) in enumerate(data.get("riwayat", []), 1):
        emoji = emoji_map.get(prosedur.strip(), "🔹")
        status_bersih = re.sub(
            r"\b(URL|IMG2?|ROAD VIEW)\b", "", status, flags=re.IGNORECASE
        )
        status_bersih = re.sub(r"\s{2,}", " ", status_bersih).strip()
        tanggal_str = (
            f" ({tanggal})" if (tanggal or "-").strip() not in ["", "-"] else ""
        )
        lines.append(
            f"\n<b>{idx:02d}. {emoji} {prosedur}</b> — {status_bersih}{tanggal_str}"
        )

    return "\n".join(lines)


async def cek_kolom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger = logging.getLogger(__name__)
    logger.info(f"🟢 Handler /cek_kolom dipanggil oleh user {update.effective_user.id}")
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type

    if user_id != OWNER_ID or chat_type != "private":
        return await update.message.reply_text(
            "❌ Perintah ini hanya tersedia untuk pengguna terdaftar di pesan pribadi."
        )

    driver = setup_driver()
    try:
        if not login(driver):
            logger.warning("🔒 Gagal login ke EPS")
            return await context.bot.send_message(
                chat_id=user_id, text="❌ Gagal login ke EPS."
            )

        if not verifikasi_tanggal_lahir(driver, BIRTHDAY):
            logger.warning("📛 Gagal verifikasi tanggal lahir")
            return await context.bot.send_message(
                chat_id=user_id, text="❌ Verifikasi tanggal lahir gagal."
            )

        data = akses_progress(driver)
        logger.info("✅ Data berhasil diambil dari EPS.go.kr")

        if data:
            try:
                with open(EPS_PROGRESS, "r", encoding="utf-8") as f:
                    lama = json.load(f)
            except:
                lama = {}

            def data_sama(d1, d2):
                return json.dumps(d1, sort_keys=True) == json.dumps(d2, sort_keys=True)

            if not lama:
                logger.info("📂 Cache belum ada. Menyimpan data pertama kali.")
                sumber = ""
            elif not data_sama(data, lama):
                logger.info("🆕 Ada perubahan data EPS.")
                sumber = "(NEW PROGRESS)"
            else:
                logger.info("ℹ️ Tidak ada perubahan dari cache EPS.")
                sumber = "(BELUM ADA PROGRES)"

            # Simpan jika pertama kali atau data baru
            if not lama or not data_sama(data, lama):
                with open(EPS_PROGRESS, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                logger.info("💾 Data progres EPS disimpan.")

            msg = format_data(data)
            msg = msg.replace(
                "📋 Hasil Kemajuan EPS", f"📋 Hasil Kemajuan EPS {sumber}"
            )
            await context.bot.send_message(chat_id=user_id, text=msg, parse_mode="HTML")
            logger.info("📤 Data progres EPS dikirim ke user.")

    except Exception as e:
        await context.bot.send_message(
            chat_id=user_id, text="❌ Terjadi kesalahan saat scraping."
        )
        logging.exception("Scraping error:")
    finally:
        driver.quit()
