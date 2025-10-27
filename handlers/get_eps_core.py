import os
import re
import time
import logging
from typing import List, Dict, Tuple, Optional

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import UnexpectedAlertPresentException

# ================== KONSTANTA ==================
LOGIN_URL = "https://www.eps.go.kr/eo/langMain.eo?langCD=in"
PROGRESS_URL = (
    "https://www.eps.go.kr/eo/EntProgCk.eo?pgID=P_000000015&langCD=in&menuID=10008"
)

SEL = {
    "nama_ready": "table.tbl_typeA.center",
    "nama_value": "table.tbl_typeA.center td:nth-child(2)",
    "tables_purple": "table.tbl_typeA.purple.mt30",
    "row_anchor": 'a[href^="javascript:fncDetailRow("]',  # anchor nomor
}

DATE_YYYYMMDD = r"\d{4}-\d{2}-\d{2}"
DATE_RANGE = r"(\d{4}-\d{2}-\d{2}~\d{4}-\d{2}-\d{2})"


# ================== DRIVER & LOGIN ==================
def setup_driver() -> webdriver.Chrome:
    options = Options()
    # headless default; set HEADLESS=0 di .env utk non-headless
    headless = os.getenv("HEADLESS", "1") != "0"
    if headless:
        options.add_argument("--headless=new")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--lang=id-ID,id;q=0.9")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    # kadang membantu
    options.add_argument("--disable-blink-features=AutomationControlled")

    return webdriver.Chrome(options=options)


def login_with(driver: webdriver.Chrome, username: str, password: str) -> bool:
    driver.get(LOGIN_URL)
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "sKorTestNo"))
        )
        driver.find_element(By.ID, "sKorTestNo").send_keys(username)
        driver.find_element(By.ID, "sFnrwRecvNo").send_keys(password)
        driver.find_element(By.CLASS_NAME, "btn_login").click()
        WebDriverWait(driver, 10).until(
            lambda d: "langMain.eo" in d.current_url or "birthChk" in d.page_source
        )
        return True
    except UnexpectedAlertPresentException:
        try:
            driver.switch_to.alert.accept()
        except Exception:
            pass
        return False
    except Exception:
        return False


def verifikasi_tanggal_lahir(driver: webdriver.Chrome, birthday_str: str) -> bool:
    """birthday_str bisa 6 digit (YYMMDD) atau 8 digit (YYYYMMDD)."""
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "chkBirtDt"))
        )
        el = driver.find_element(By.ID, "chkBirtDt")
        el.clear()
        el.send_keys(birthday_str)
        driver.find_element(By.CSS_SELECTOR, "span.buttonE > button").click()
        WebDriverWait(driver, 10).until(EC.url_contains("langMain.eo"))
        return True
    except Exception:
        return False


def normalize_birthday(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    return digits if len(digits) in (6, 8) else value


# ================== PARSER & SCRAPER ==================
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
    rows = []
    for tr in t1_soup.select("tbody tr"):
        tds = tr.select("td")
        if len(tds) < 3:
            continue

        no_text = tds[0].get_text(strip=True)

        ref_id = None
        a_tag = tds[0].select_one(SEL["row_anchor"])
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


def _try_select_row2(driver: webdriver.Chrome) -> Optional[str]:
    """Jika ada baris '2' di tabel pengiriman, jalankan JS fncDetailRow agar detail reload."""
    try:
        old_tables = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, SEL["tables_purple"]))
        )
        old_detail_el = old_tables[1] if len(old_tables) >= 2 else None
    except Exception:
        old_detail_el = None

    try:
        t1 = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, SEL["tables_purple"]))
        )
    except Exception:
        return None

    anchors = t1.find_elements(By.CSS_SELECTOR, SEL["row_anchor"])
    chosen, ref_id = None, None
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

    try:
        driver.execute_script(f"return fncDetailRow('{ref_id}', '');")
    except Exception:
        chosen.click()

    html_before = driver.page_source
    try:
        if old_detail_el:
            WebDriverWait(driver, 10).until(EC.staleness_of(old_detail_el))
        WebDriverWait(driver, 15).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, SEL["tables_purple"]))
        )
        WebDriverWait(driver, 5).until(lambda d: d.page_source != html_before)
    except Exception:
        time.sleep(0.8)

    return ref_id


def akses_progress(driver: webdriver.Chrome, prefer_row2: bool = True) -> Dict:
    driver.get(PROGRESS_URL)

    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, SEL["nama_ready"]))
    )

    aktif_ref_id = None
    if prefer_row2:
        try:
            aktif_ref_id = _try_select_row2(driver)
        except Exception:
            aktif_ref_id = None

    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, SEL["nama_ready"]))
    )
    soup = BeautifulSoup(driver.page_source, "html.parser")

    # Nama
    nama_el = soup.select_one(SEL["nama_value"])
    nama = nama_el.get_text(strip=True) if nama_el else "-"

    # Tabel ungu
    purple_tables = soup.select(SEL["tables_purple"])
    pengiriman_list = _parse_pengiriman_table(purple_tables[0]) if purple_tables else []
    pengiriman_latest = _pick_latest(pengiriman_list)

    riwayat = _parse_riwayat_table(purple_tables[1]) if len(purple_tables) >= 2 else []

    if not aktif_ref_id and pengiriman_latest:
        aktif_ref_id = pengiriman_latest.get("ref_id")

    return {
        "nama": nama,
        "aktif_ref_id": aktif_ref_id,
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


# ================== FORMATTER ==================
def format_data(data: dict) -> str:
    emoji_map = {
        "Ujian Bahasa Korea": "📝",
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
        # Korea
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

    def _extract_first_date_local(text: str) -> str:
        m = re.search(DATE_YYYYMMDD, text or "")
        return m.group(0) if m else "-"

    def _extract_date_range_local(text: str) -> Optional[str]:
        m = re.search(DATE_RANGE, text or "")
        return m.group(1) if m else None

    lines = ["<b>📋 Hasil Kemajuan EPS</b>\n"]
    lines.append(f"<b>👤 Nama:</b> {data.get('nama', '-')}")

    aktif_ref = data.get("aktif_ref_id")
    if aktif_ref:
        lines.append(f"<b>🆔 ID Nodongbu aktif:</b> <code>{aktif_ref}</code>")

    pengiriman_latest = data.get("pengiriman", {}) or {}
    t_kirim = pengiriman_latest.get("tanggal_kirim", "-")
    t_terima_raw = pengiriman_latest.get("tanggal_terima", "-")
    ref_id_latest = pengiriman_latest.get("ref_id")

    masa = _extract_date_range_local(t_terima_raw or "")
    t_terima = _extract_first_date_local(t_terima_raw or "")

    lines.append(f"<b>📮 Pengiriman (terbaru):</b> {t_kirim}")
    lines.append(f"<b>✅ Penerimaan (terbaru):</b> {t_terima}")
    if ref_id_latest:
        lines.append(f"<b>🆔 ID Nodongbu (terbaru):</b> <code>{ref_id_latest}</code>")
    if masa:
        lines.append(f"<b>📆 Masa Aktif :</b> {masa}")

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

    lines.append("\n<b>🧾 Progres Kemajuan Imigrasi:</b>")
    for idx, (prosedur, status, tanggal) in enumerate(data.get("riwayat", []), 1):
        emoji = emoji_map.get(prosedur.strip(), "🔹")
        status_bersih = re.sub(
            r"\b(URL|IMG2?|ROAD VIEW)\b", "", status or "", flags=re.IGNORECASE
        )
        status_bersih = re.sub(r"\s{2,}", " ", status_bersih).strip()
        tanggal_str = (
            f" ({tanggal})" if (tanggal or "-").strip() not in ["", "-"] else ""
        )
        lines.append(
            f"\n<b>{idx:02d}. {emoji} {prosedur}</b> — {status_bersih}{tanggal_str}"
        )

    return "\n".join(lines)
