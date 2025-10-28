from typing import Dict
from bs4 import BeautifulSoup
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from .constants import SEL, PROGRESS_URL
from .navigator import _try_select_row2, _switch_to_ref
from .parsers import (
    parse_pengiriman_table,
    parse_riwayat_table,
    extract_mediasi_from_riwayat,
)
from .utils import pick_latest
from .link_extractor import extract_job_links


def akses_progress(driver, prefer_row2: bool = True) -> dict:
    driver.get(PROGRESS_URL)
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, SEL["nama_ready"]))
    )

    aktif_ref_id = None
    if prefer_row2:
        try:
            aktif_ref_id = _try_select_row2(driver)
        except Exception:
            aktif_ref_id = None

    # snapshot pertama
    WebDriverWait(driver, 8).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, SEL["nama_ready"]))
    )
    soup = BeautifulSoup(driver.page_source, "lxml")

    nama_el = soup.select_one(SEL["nama_value"])
    nama = nama_el.get_text(strip=True) if nama_el else "-"

    purple_tables = soup.select(SEL["tables_purple"])
    pengiriman_list = parse_pengiriman_table(purple_tables[0]) if purple_tables else []
    riwayat = parse_riwayat_table(purple_tables[1]) if len(purple_tables) >= 2 else []
    job_links = (
        extract_job_links(purple_tables[1]) if len(purple_tables) >= 2 else {}
    )  # ⬅️ tambahkan ini

    pengiriman_latest = pick_latest(pengiriman_list)
    if not aktif_ref_id and pengiriman_latest:
        aktif_ref_id = pengiriman_latest.get("ref_id")

    mediasi_aktif = extract_mediasi_from_riwayat(riwayat)
    for item in pengiriman_list:
        item["mediasi"] = "-"
        if item.get("ref_id") and item["ref_id"] == aktif_ref_id:
            item["mediasi"] = mediasi_aktif

    # cek roster lain
    for item in pengiriman_list:
        item_ref = item.get("ref_id")
        if not item_ref or item.get("mediasi") != "-":
            continue
        if not _switch_to_ref(driver, item_ref):
            continue
        soup2 = BeautifulSoup(driver.page_source, "lxml")
        tables2 = soup2.select(SEL["tables_purple"])
        riwayat2 = parse_riwayat_table(tables2[1]) if len(tables2) >= 2 else []
        item["mediasi"] = extract_mediasi_from_riwayat(riwayat2)

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
        "tautan_pekerjaan": job_links,  # ⬅️ ini penting!
    }
