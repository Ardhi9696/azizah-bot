import os
import json
import logging
import re
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


def akses_progress(driver):
    driver.get(PROGRESS_URL)
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "table.tbl_typeA.center"))
    )
    soup = BeautifulSoup(driver.page_source, "html.parser")

    # 1) Nama: tetap dari tabel center
    nama_el = soup.select_one("table.tbl_typeA.center td:nth-child(2)")
    nama = nama_el.get_text(strip=True) if nama_el else "-"

    # 2) Tabel purple #1: Daftar Pengiriman/Penerimaan (bisa multi-row)
    purple_tables = soup.select("table.tbl_typeA.purple.mt30")
    pengiriman_list = []
    if purple_tables:
        t1 = purple_tables[0]
        for tr in t1.select("tbody tr"):
            tds = tr.select("td")
            if len(tds) < 3:
                continue
            no_text = tds[0].get_text(strip=True)
            # Ekstrak id (jika ada) dari onclick link a[href^="javascript:fncDetailRow("]
            a_tag = tds[0].select_one('a[href^="javascript:fncDetailRow("]')
            ref_id = None
            if a_tag and "fncDetailRow" in (a_tag.get("href") or ""):
                # contoh: javascript:fncDetailRow('ID02024005432', '');
                m = re.search(r"fncDetailRow\('([^']+)'", a_tag["href"])
                if m:
                    ref_id = m.group(1)

            tanggal_kirim = tds[1].get_text(" ", strip=True)

            # Kolom penerimaan berpotensi mengandung 'Masa Berlaku' di baris baru
            penerimaan_raw = tds[2].get_text("\n", strip=True)
            # Pecah jadi tanggal penerimaan + masa berlaku (jika ada rentang)
            tanggal_terima = "-"
            masa_berlaku = None

            # Ambil tanggal penerimaan (YYYY-MM-DD pertama pada kolom)
            m_date = re.search(r"\d{4}-\d{2}-\d{2}", penerimaan_raw)
            if m_date:
                tanggal_terima = m_date.group(0)

            # Ambil rentang masa berlaku
            m_masa = re.search(r"(\d{4}-\d{2}-\d{2}~\d{4}-\d{2}-\d{2})", penerimaan_raw)
            if m_masa:
                masa_berlaku = m_masa.group(1)

            pengiriman_list.append(
                {
                    "no": no_text,
                    "ref_id": ref_id,
                    "tanggal_kirim": tanggal_kirim,
                    "tanggal_terima": tanggal_terima,
                    "masa_berlaku": masa_berlaku,
                    "raw": penerimaan_raw,  # simpan mentah untuk debugging/perbandingan cache
                }
            )

    # Tentukan latest (NO terbesar jika numerik, else gunakan baris terakhir)
    pengiriman_latest = None
    if pengiriman_list:
        try:
            pengiriman_latest = max(
                pengiriman_list,
                key=lambda r: int(re.sub(r"\D", "", r.get("no", "") or "0") or 0),
            )
        except Exception:
            pengiriman_latest = pengiriman_list[-1]

    # 3) Tabel purple #2: Prosedur/Perkembangan/Tanggal (riwayat)
    riwayat = []
    if len(purple_tables) >= 2:
        t2 = purple_tables[1]
        for row in t2.select("tbody tr"):
            cols = row.select("td")
            if len(cols) >= 3:
                prosedur = cols[0].get_text(strip=True)
                status = cols[1].get_text(" ", strip=True)
                tanggal = cols[2].get_text(" ", strip=True)
                riwayat.append((prosedur, status, tanggal))

    return {
        "nama": nama,
        # kompatibilitas lama: sediakan field lama bila dibutuhkan di tempat lain
        "pengiriman": (  # keep old shape; gunakan pengiriman_latest
            {
                "no": pengiriman_latest.get("no") if pengiriman_latest else "-",
                "tanggal_kirim": (pengiriman_latest or {}).get("tanggal_kirim", "-"),
                "tanggal_terima": (
                    # isi tanggal + label masa berlaku bila ada, mirip format lama
                    ((pengiriman_latest or {}).get("tanggal_terima", "-") or "-")
                    + (
                        f"  Masa Berlaku: {(pengiriman_latest or {}).get('masa_berlaku')}"
                        if (pengiriman_latest or {}).get("masa_berlaku")
                        else ""
                    )
                ),
            }
            if pengiriman_latest
            else {"no": "-", "tanggal_kirim": "-", "tanggal_terima": "-"}
        ),
        # bentuk baru yang lengkap
        "pengiriman_list": pengiriman_list,
        "riwayat": riwayat,
    }


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

    lines = []
    lines.append("<b>📋 Hasil Kemajuan EPS</b>\n")

    # Header umum
    lines.append(f"<b>👤 Nama:</b> {data.get('nama', '-')}")
    pengiriman_latest = data.get("pengiriman", {})
    t_kirim = pengiriman_latest.get("tanggal_kirim", "-")
    t_terima_raw = pengiriman_latest.get("tanggal_terima", "-")

    # Ambil masa berlaku dari raw/teks penerimaan
    masa = None
    m = re.findall(r"(\d{4}-\d{2}-\d{2}~\d{4}-\d{2}-\d{2})", t_terima_raw)
    if m:
        masa = m[0]

    # Ambil tanggal_terima (YYYY-MM-DD pertama) untuk tampilan ringkas
    t_terima = "-"
    m2 = re.search(r"\d{4}-\d{2}-\d{2}", t_terima_raw or "")
    if m2:
        t_terima = m2.group(0)

    lines.append(f"<b>📮 Pengiriman (terbaru):</b> {t_kirim}")
    lines.append(f"<b>✅ Penerimaan (terbaru):</b> {t_terima}")

    if masa:
        lines.append(f"<b>📆 Masa Aktif :</b> {masa}")

    # Riwayat pengiriman/penerimaan (jika ada multi-row)
    pengiriman_list = data.get("pengiriman_list") or []
    if pengiriman_list:
        lines.append("\n<b>🗂️ Riwayat Pengiriman/Penerimaan:</b>")
        for r in pengiriman_list:
            no = r.get("no", "-")
            kirim = r.get("tanggal_kirim", "-")
            terima = r.get("tanggal_terima", "-")
            masa_r = r.get("masa_berlaku")
            masa_txt = f"  |  Masa: {masa_r}" if masa_r else ""
            lines.append(
                f"• <b>#{no}</b> Kirim: {kirim}  |  Terima: {terima}{masa_txt}"
            )

    # Riwayat prosedur
    lines.append("\n<b>🧾 Progres Kemajuan Imigrasi:</b>")
    for idx, (prosedur, status, tanggal) in enumerate(data.get("riwayat", []), 1):
        prosedur = prosedur.strip()
        emoji = emoji_map.get(prosedur.strip(), "🔹")

        # Hapus teks seperti URL, IMG, ROAD VIEW
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
