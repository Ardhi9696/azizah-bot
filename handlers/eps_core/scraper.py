# handlers/eps_core/scraper.py

import asyncio
import logging
from bs4 import BeautifulSoup
from playwright.async_api import Page
from typing import Dict, Optional

from .constants import PROGRESS_URL, SEL
from .parsers import (
    parse_pengiriman_table,
    parse_riwayat_table,
    extract_mediasi_from_riwayat,
    pick_latest,
)
from .link_extractor import extract_job_links
from .navigator import _try_select_row2, _switch_to_ref

logger = logging.getLogger(__name__)


async def akses_progress(page: Page, prefer_row2: bool = True) -> dict:
    """
    Akses halaman progress EPS dengan Playwright

    Args:
        page: Playwright page object
        prefer_row2: Whether to automatically select row 2

    Returns:
        Dictionary dengan data yang di-scrape
    """
    try:
        logger.info("[SCRAPER] Mengakses halaman progress...")

        # Navigate ke halaman progress
        await page.goto(PROGRESS_URL, wait_until="domcontentloaded", timeout=30000)

        # Tunggu sampai tabel nama ready
        await page.wait_for_selector(SEL["nama_ready"], timeout=15000)
        logger.debug("[SCRAPER] Halaman progress loaded")

        aktif_ref_id = None
        if prefer_row2:
            try:
                logger.debug("[SCRAPER] Mencoba select row 2...")
                aktif_ref_id = await _try_select_row2(page)
                if aktif_ref_id:
                    logger.info(
                        f"[SCRAPER] Berhasil select row 2 dengan ref_id: {aktif_ref_id}"
                    )
                else:
                    logger.warning(
                        "[SCRAPER] Gagal select row 2, melanjutkan tanpa selection"
                    )
            except Exception as e:
                logger.warning(f"[SCRAPER] Error saat select row 2: {e}")
                aktif_ref_id = None

        # Ambil konten halaman untuk parsing
        page_content = await page.content()
        soup = BeautifulSoup(page_content, "lxml")
        logger.debug("[SCRAPER] Page content diambil untuk parsing")

        # Parse data nama
        nama_el = soup.select_one(SEL["nama_value"])
        nama = nama_el.get_text(strip=True) if nama_el else "-"
        logger.info(f"[SCRAPER] Nama ditemukan: {nama}")

        # Parse tabel-tabel purple
        purple_tables = soup.select(SEL["tables_purple"])
        logger.debug(f"[SCRAPER] Jumlah tabel purple ditemukan: {len(purple_tables)}")

        pengiriman_list = []
        riwayat = []
        job_links = {}

        if purple_tables:
            # Parse tabel pengiriman (biasanya tabel pertama)
            pengiriman_list = parse_pengiriman_table(purple_tables[0])
            logger.debug(f"[SCRAPER] Jumlah entri pengiriman: {len(pengiriman_list)}")

            # Parse riwayat progres (biasanya tabel kedua)
            if len(purple_tables) >= 2:
                riwayat = parse_riwayat_table(purple_tables[1])
                job_links = extract_job_links(purple_tables[1])
                logger.debug(f"[SCRAPER] Jumlah riwayat: {len(riwayat)}")
                logger.debug(f"[SCRAPER] Job links: {len(job_links)}")

        # Cari pengiriman terbaru
        pengiriman_latest = pick_latest(pengiriman_list)

        # Jika tidak ada aktif_ref_id dari row2, gunakan dari pengiriman terbaru
        if not aktif_ref_id and pengiriman_latest:
            aktif_ref_id = pengiriman_latest.get("ref_id")
            logger.debug(
                f"[SCRAPER] Menggunakan ref_id dari pengiriman terbaru: {aktif_ref_id}"
            )

        # Process mediasi untuk setiap roster
        await _process_mediasi_data(page, pengiriman_list, aktif_ref_id, riwayat)

        # Format pengiriman header
        pengiriman_header = _format_pengiriman_header(pengiriman_latest)

        result = {
            "nama": nama,
            "aktif_ref_id": aktif_ref_id,
            "pengiriman": pengiriman_header,
            "pengiriman_list": pengiriman_list,
            "riwayat": riwayat,
            "tautan_pekerjaan": job_links,
        }

        logger.info("[SCRAPER] Scraping completed successfully")
        return result

    except Exception as e:
        logger.error(f"[SCRAPER] Error saat akses progress: {e}")
        # Return empty structure dengan error indicator
        return {
            "nama": "-",
            "aktif_ref_id": None,
            "pengiriman": {
                "no": "-",
                "ref_id": None,
                "tanggal_kirim": "-",
                "tanggal_terima": "-",
            },
            "pengiriman_list": [],
            "riwayat": [],
            "tautan_pekerjaan": {},
            "error": str(e),
        }


async def _process_mediasi_data(
    page: Page, pengiriman_list: list, aktif_ref_id: Optional[str], riwayat: list
) -> None:
    """
    Process data mediasi untuk semua roster

    Args:
        page: Playwright page object
        pengiriman_list: List data pengiriman
        aktif_ref_id: ID roster aktif
        riwayat: Data riwayat untuk roster aktif
    """
    try:
        # Mediasi untuk roster aktif
        mediasi_aktif = extract_mediasi_from_riwayat(riwayat)
        logger.debug(f"[SCRAPER] Mediasi aktif: {mediasi_aktif}")

        # Set mediasi untuk setiap item
        for item in pengiriman_list:
            item["mediasi"] = "-"
            if item.get("ref_id") and item["ref_id"] == aktif_ref_id:
                item["mediasi"] = mediasi_aktif
                logger.debug(
                    f"[SCRAPER] Set mediasi aktif untuk roster {item.get('no')}: {mediasi_aktif}"
                )

        # Mediasi untuk roster lain (butuh navigasi)
        for item in pengiriman_list:
            ref = item.get("ref_id")
            if not ref or item.get("mediasi") != "-":
                continue

            logger.debug(
                f"[SCRAPER] Processing mediasi untuk roster {item.get('no')} dengan ref: {ref}"
            )
            if await _switch_to_ref(page, ref):
                # Tunggu sebentar untuk update halaman
                await asyncio.sleep(1)

                # Ambil konten halaman yang updated
                page_content = await page.content()
                soup = BeautifulSoup(page_content, "lxml")
                tables = soup.select(SEL["tables_purple"])

                riwayat2 = parse_riwayat_table(tables[1]) if len(tables) >= 2 else []
                item["mediasi"] = extract_mediasi_from_riwayat(riwayat2)

                logger.debug(
                    f"[SCRAPER] Mediasi untuk roster {item.get('no')}: {item['mediasi']}"
                )
            else:
                logger.warning(
                    f"[SCRAPER] Gagal switch ke ref {ref} untuk roster {item.get('no')}"
                )

    except Exception as e:
        logger.error(f"[SCRAPER] Error processing mediasi data: {e}")


def _format_pengiriman_header(pengiriman_latest: Optional[dict]) -> dict:
    """
    Format pengiriman header data

    Args:
        pengiriman_latest: Data pengiriman terbaru

    Returns:
        Dictionary formatted pengiriman header
    """
    if pengiriman_latest:
        masa_berlaku_text = ""
        if pengiriman_latest.get("masa_berlaku"):
            masa_berlaku_text = f"  Masa Berlaku: {pengiriman_latest['masa_berlaku']}"

        return {
            "no": pengiriman_latest.get("no", "-"),
            "ref_id": pengiriman_latest.get("ref_id"),
            "tanggal_kirim": pengiriman_latest.get("tanggal_kirim", "-"),
            "tanggal_terima": f"{pengiriman_latest.get('tanggal_terima', '-') or '-'}{masa_berlaku_text}",
        }
    else:
        return {
            "no": "-",
            "ref_id": None,
            "tanggal_kirim": "-",
            "tanggal_terima": "-",
        }


async def akses_progress_with_retry(
    page: Page, prefer_row2: bool = True, max_retries: int = 2, retry_delay: int = 3
) -> dict:
    """
    Akses progress dengan retry mechanism

    Args:
        page: Playwright page object
        prefer_row2: Whether to auto-select row 2
        max_retries: Maximum retry attempts
        retry_delay: Delay between retries in seconds

    Returns:
        Dictionary dengan data yang di-scrape
    """
    for attempt in range(max_retries):
        try:
            logger.info(f"[SCRAPER] Attempt {attempt + 1}/{max_retries}")

            result = await akses_progress(page, prefer_row2)

            # Check if result looks valid
            if result.get("nama") and result.get("nama") != "-":
                logger.info(f"[SCRAPER] Attempt {attempt + 1} successful")
                return result
            else:
                logger.warning(f"[SCRAPER] Attempt {attempt + 1} returned invalid data")

        except Exception as e:
            logger.error(f"[SCRAPER] Attempt {attempt + 1} failed: {e}")

        if attempt < max_retries - 1:
            logger.info(f"[SCRAPER] Retrying in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)

    # Jika semua retry gagal, return empty result
    logger.error("[SCRAPER] All scraping attempts failed")
    return {
        "nama": "-",
        "aktif_ref_id": None,
        "pengiriman": {
            "no": "-",
            "ref_id": None,
            "tanggal_kirim": "-",
            "tanggal_terima": "-",
        },
        "pengiriman_list": [],
        "riwayat": [],
        "tautan_pekerjaan": {},
        "error": "All scraping attempts failed",
    }


async def quick_progress_check(page: Page) -> Dict[str, bool]:
    """
    Quick check untuk memverifikasi halaman progress loaded dengan benar

    Args:
        page: Playwright page object

    Returns:
        Dictionary dengan status berbagai element
    """
    try:
        check_results = {}

        # Check if we're on progress page
        current_url = page.url
        check_results["on_progress_page"] = "progress" in current_url.lower()

        # Check for essential elements
        essential_selectors = {
            "nama_table": SEL["nama_ready"],
            "purple_tables": SEL["tables_purple"],
            "nama_value": SEL["nama_value"],
        }

        for key, selector in essential_selectors.items():
            try:
                element = await page.query_selector(selector)
                check_results[key] = element is not None
            except Exception:
                check_results[key] = False

        # Quick content check
        content = await page.content()
        check_results["has_progress_data"] = any(
            [
                "tbl_typeA" in content,
                "pengiriman" in content.lower(),
                "riwayat" in content.lower(),
            ]
        )

        logger.debug(f"[SCRAPER] Quick check results: {check_results}")
        return check_results

    except Exception as e:
        logger.error(f"[SCRAPER] Quick check error: {e}")
        return {"error": str(e)}


async def get_page_snapshot(page: Page) -> Dict[str, any]:
    """
    Ambil snapshot lengkap dari halaman untuk debugging

    Args:
        page: Playwright page object

    Returns:
        Dictionary dengan berbagai page metrics
    """
    try:
        current_url = page.url
        page_title = await page.title()
        content = await page.content()

        # Count elements
        element_counts = {}
        selectors_to_count = [
            SEL["tables_purple"],
            SEL["nama_ready"],
            SEL["row_anchor"],
            "table",
            "tr",
            "td",
        ]

        for selector in selectors_to_count:
            try:
                elements = await page.query_selector_all(selector)
                element_counts[selector] = len(elements)
            except Exception:
                element_counts[selector] = 0

        snapshot = {
            "url": current_url,
            "title": page_title,
            "content_length": len(content),
            "element_counts": element_counts,
            "has_purple_tables": element_counts[SEL["tables_purple"]] > 0,
            "has_nama_table": element_counts[SEL["nama_ready"]] > 0,
            "timestamp": asyncio.get_event_loop().time(),
        }

        return snapshot

    except Exception as e:
        logger.error(f"[SCRAPER] Page snapshot error: {e}")
        return {"error": str(e)}


async def safe_scrape_progress(
    page: Page,
    username: str,
    password: str,
    birthday: str,
    prefer_row2: bool = True,
    max_retries: int = 2,
) -> dict:
    """
    Safe scraping dengan automatic authentication handling

    Args:
        page: Playwright page object
        username: Login username
        password: Login password
        birthday: Birthday untuk verification
        prefer_row2: Whether to auto-select row 2
        max_retries: Maximum retry attempts

    Returns:
        Dictionary dengan data yang di-scrape
    """
    from .auth import safe_navigation_and_auth

    for attempt in range(max_retries):
        try:
            logger.info(f"[SCRAPER] Safe scrape attempt {attempt + 1}/{max_retries}")

            # Navigate dan auth otomatis
            auth_success = await safe_navigation_and_auth(
                page, PROGRESS_URL, username, password, birthday
            )

            if not auth_success:
                logger.warning(
                    f"[SCRAPER] Authentication failed on attempt {attempt + 1}"
                )
                continue

            # Quick check untuk memastikan halaman ready
            quick_check = await quick_progress_check(page)
            if not quick_check.get("has_progress_data", False):
                logger.warning(
                    f"[SCRAPER] Progress data not found on attempt {attempt + 1}"
                )
                continue

            # Lakukan scraping
            result = await akses_progress(page, prefer_row2)

            # Validate result
            if result.get("nama") and result.get("nama") != "-":
                logger.info(f"[SCRAPER] Safe scrape attempt {attempt + 1} successful")
                return result
            else:
                logger.warning(
                    f"[SCRAPER] Safe scrape attempt {attempt + 1} returned invalid data"
                )

        except Exception as e:
            logger.error(f"[SCRAPER] Safe scrape attempt {attempt + 1} failed: {e}")

        if attempt < max_retries - 1:
            await asyncio.sleep(3)  # Delay sebelum retry

    logger.error("[SCRAPER] All safe scrape attempts failed")
    return {
        "nama": "-",
        "aktif_ref_id": None,
        "pengiriman": {
            "no": "-",
            "ref_id": None,
            "tanggal_kirim": "-",
            "tanggal_terima": "-",
        },
        "pengiriman_list": [],
        "riwayat": [],
        "tautan_pekerjaan": {},
        "error": "All safe scrape attempts failed",
    }


# Export functions
__all__ = [
    "akses_progress",
    "akses_progress_with_retry",
    "quick_progress_check",
    "get_page_snapshot",
    "safe_scrape_progress",
]
