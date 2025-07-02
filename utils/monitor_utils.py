# monitor_utils.py
import requests
import html
import json
import os
import logging
from bs4 import BeautifulSoup
from datetime import datetime, time
from urllib.parse import urlparse, unquote

logger = logging.getLogger(__name__)


def mask_api_url(url):
    parsed = urlparse(url)
    return unquote(
        f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    )  # Hapus query param


# === WAKTU MONITORING ===
def is_waktu_aktif():
    now = datetime.now()
    print("⏱️ Sekarang (WIB):", now.strftime("%Y-%m-%d %H:%M:%S"))
    return True  # Ganti ke logika aktif jam kerja jika perlu


def is_jam_delapan():
    return datetime.now().strftime("%H:%M") == "08:00"


# === PARSE JUDUL & LINK ===
def parse_judul_link(html_string):
    raw_html = html.unescape(html_string)
    soup = BeautifulSoup(raw_html, "html.parser")
    a = soup.find("a")
    if not a:
        logger.warning("⚠️ Tidak ditemukan tag <a> saat parsing judul.")
        return "Judul tidak ditemukan", "-"

    teks = a.get_text(strip=True)
    href = a.get("href", "").strip().replace("\\/", "/")

    if href.startswith("/"):
        href = f"https://bp2mi.go.id{href}"

    logger.info(f"📌 Judul hasil parsing: {teks}")
    logger.info(f"🔗 Link hasil parsing: {href or '-'}")
    return teks, href if href else "-"


# === FORMAT PESAN UNTUK TELEGRAM ===
def format_pesan(item, tipe="pengumuman"):
    from html import escape

    judul = item.get("judul", "Judul tidak ditemukan")
    link = item.get("link", "#")
    kategori = item.get("kategori", "-")
    creator = item.get("creator", "-")
    tanggal = item.get("tanggal", "-")
    view = item.get("view", "-")
    id_ = item.get("id", "-")

    return (
        f"🆕 <b>{judul}</b>\n\n"
        f"🆔 ID: <code>{id_}</code>\n"
        f"✍️ Creator: {creator}\n"
        f"📅 Tanggal: {tanggal}\n"
        f"👁️ View: {view}\n"
        f"🏷️ Kategori: {kategori}\n"
        f'🔗 Link: <a href="{escape(link)}">Klik di sini</a>'
    )


# === CACHE UTILITAS ===
def load_last_ids(cache_file, n=10):
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f).get("last_ids", [])[:n]
    return []


def save_last_ids(cache_file, ids, n=10):
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump({"last_ids": ids[:n]}, f, indent=2)


# === CEK API ===


def check_api_multi(api_url, cache_file, tipe="pengumuman"):
    try:
        logger.info(
            f"🚀 Memulai pengecekan {tipe.upper()} dari API: {mask_api_url(api_url)}"
        )

        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json().get("data", [])[:10]

        logger.debug(
            f"📥 Data {tipe} dari API: {json.dumps(data, indent=2, ensure_ascii=False)}"
        )

        if not data:
            logger.warning(f"🔍 Tidak ada data {tipe} dari API.")
            return []

        cached_ids = load_last_ids(cache_file)
        logger.info("🗂️  Cached IDs saat ini: %s", cached_ids)

        baru = []

        for item in data:
            id_baru = item.get("id")
            if id_baru not in cached_ids:
                logger.info(f"🆕 ID baru ditemukan: {id_baru}")
                judul_html = item.get("judul", "")
                judul, link = parse_judul_link(judul_html)

                baru.append(
                    {
                        "id": id_baru,
                        "judul": judul,
                        "link": link,
                        "tanggal": item.get("tanggal", "-"),
                        "creator": item.get("creator", "-"),
                        "view": item.get("view", "-"),
                        "kategori": item.get("kategori", "-"),
                    }
                )
            else:
                logger.debug(f"🔁 ID lama (sudah ada): {id_baru}")

        total_data = len(data)
        total_baru = len(baru)
        total_lama = total_data - total_baru

        logger.info(f"📊 Statistik: total {tipe} dari API: {total_data}")
        logger.info(f"🆕 ID baru ditemukan: {total_baru}, Lama: {total_lama}")

        if baru:
            logger.info(f"📢 Ditemukan {total_baru} {tipe} baru.")
            all_ids = [item.get("id") for item in data]
            logger.info(f"💾 Cache diperbarui. ID terakhir disimpan: {all_ids}")
            save_last_ids(cache_file, all_ids)
        else:
            logger.info(f"✅ Tidak ditemukan {tipe} baru. Cache tetap.")

        return list(reversed(baru))

    except Exception as e:
        logger.exception(f"❌ Gagal mengambil data {tipe}.")
        return []
