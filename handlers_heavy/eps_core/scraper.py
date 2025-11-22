# handlers/eps_core/scraper.py

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


# TAMBAHKAN FUNGSI INI DI AWAL FILE
def _create_error_result(error_msg: str) -> dict:
    """Create error result structure"""
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
        "error": error_msg,
    }


# TAMBAHKAN FUNGSI wait_for_selectors JIKA BELUM ADA
async def wait_for_selectors(page: Page, selectors: list, timeout: int = 10000) -> bool:
    """
    Wait for multiple selectors (coba satu per satu)
    """
    for selector in selectors:
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            continue
    return False


async def akses_progress(page: Page, prefer_row2: bool = True) -> dict:
    """Akses halaman progress EPS dengan approach yang lebih reliable"""
    try:
        logger.info("[SCRAPER] Starting progress page access...")

        # Validasi dasar page state
        if page.is_closed():
            logger.error("[SCRAPER] Page is closed, cannot scrape")
            return _create_error_result("Page closed")

        # Navigasi ke halaman progress
        await _navigate_to_progress_page(page)

        # Tunggu halaman siap dengan timeout yang reasonable
        if not await _wait_for_page_ready(page):
            logger.error("[SCRAPER] Progress page not ready after navigation")
            return _create_error_result("Progress page not ready")

        # EKSEKUSI SEQUENTIAL - hindari race conditions
        # 1. Ambil content dasar terlebih dahulu
        page_content = await page.content()
        soup = BeautifulSoup(page_content, "lxml")

        # 2. Parse data dasar sebelum manipulasi apapun
        parsed_data = await _parse_initial_page_content(soup)

        # 3. Select row 2 JIKA prefer_row2=True dan row 2 ada
        aktif_ref_id = None
        if prefer_row2 and await _is_row2_available(page):
            try:
                logger.debug("[SCRAPER] Attempting to select row 2...")
                aktif_ref_id = await _try_select_row2(page)
                if aktif_ref_id:
                    logger.info(
                        f"[SCRAPER] Successfully selected row 2: {aktif_ref_id}"
                    )
                    # Setelah select row 2, ambil content baru
                    await asyncio.sleep(1)  # Tunggu update (dipersingkat)
                    page_content = await page.content()
                    soup = BeautifulSoup(page_content, "lxml")
                    # Parse ulang data dengan content yang updated
                    parsed_data = await _parse_initial_page_content(soup)
            except Exception as e:
                logger.warning(f"[SCRAPER] Row selection error: {e}")

        # 4. Process mediasi data dengan approach yang lebih reliable
        await _process_mediasi_data_reliable(
            page, parsed_data["pengiriman_list"], aktif_ref_id
        )

        # Siapkan result final
        pengiriman_latest = pick_latest(parsed_data["pengiriman_list"])
        default_ref_id = pengiriman_latest.get("ref_id") if pengiriman_latest else None

        result = {
            "nama": parsed_data["nama"],
            "aktif_ref_id": aktif_ref_id or default_ref_id,
            "pengiriman": _format_pengiriman_header(pengiriman_latest),
            "pengiriman_list": parsed_data["pengiriman_list"],
            "riwayat": parsed_data["riwayat"],
            "tautan_pekerjaan": parsed_data["job_links"],
        }

        logger.info("[SCRAPER] Scraping completed successfully")
        return result

    except Exception as e:
        logger.error(f"[SCRAPER] Error during progress access: {e}")
        return _create_error_result(str(e))


async def _is_row2_available(page: Page) -> bool:
    """Cek apakah row 2 tersedia untuk di-select"""
    try:
        row_anchor = await page.query_selector(f"{SEL['row_anchor']}:has-text('2')")
        return row_anchor is not None
    except Exception:
        return False


async def _parse_initial_page_content(soup: BeautifulSoup) -> dict:
    """Parse semua data dari HTML content tanpa manipulasi state"""

    # Parse nama
    nama = _extract_nama(soup)

    # Parse tabel
    purple_tables = _find_purple_tables(soup)
    logger.debug(f"[SCRAPER] Found {len(purple_tables)} purple tables")

    # Parse data dari tabel
    pengiriman_list = _parse_pengiriman_table(purple_tables)
    riwayat, job_links = _parse_riwayat_table(purple_tables)

    return {
        "nama": nama,
        "pengiriman_list": pengiriman_list,
        "riwayat": riwayat,
        "job_links": job_links,
    }


async def _process_mediasi_data_reliable(
    page: Page, pengiriman_list: list, aktif_ref_id: Optional[str]
) -> None:
    """Process data mediasi dengan approach yang lebih reliable - FIXED VERSION"""
    try:
        logger.info("[SCRAPER] Processing mediasi data reliably...")

        # Jika tidak ada pengiriman list, skip
        if not pengiriman_list:
            return

        # Reset semua mediasi ke "-" terlebih dahulu
        for item in pengiriman_list:
            item["mediasi"] = "-"

        # Untuk roster aktif (jika ada), gunakan data dari halaman saat ini
        if aktif_ref_id:
            current_riwayat = await _get_current_riwayat(page)
            mediasi_aktif = extract_mediasi_from_riwayat(current_riwayat)
            logger.info(
                f"[SCRAPER] Mediasi aktif: {mediasi_aktif} untuk ref: {aktif_ref_id}"
            )

            for item in pengiriman_list:
                if item.get("ref_id") == aktif_ref_id:
                    item["mediasi"] = mediasi_aktif
                    logger.info(
                        f"[SCRAPER] Set mediasi {mediasi_aktif} untuk roster aktif {item.get('no')}"
                    )

        # Untuk roster lain, kita perlu switch dan ambil data
        for item in pengiriman_list:
            ref_id = item.get("ref_id")
            # Skip jika sudah di-set atau tidak ada ref_id
            if not ref_id or item["mediasi"] != "-":
                continue

            # Skip jika ini adalah roster aktif (sudah di-handle di atas)
            if ref_id == aktif_ref_id:
                continue

            logger.info(
                f"[SCRAPER] Processing mediasi untuk roster {item.get('no')} dengan ref: {ref_id}"
            )

            # Simpan state current URL sebelum switch
            current_url = page.url

            # Switch ke roster
            if await _switch_to_ref(page, ref_id):
                # Tunggu singkat untuk memastikan halaman update
                await asyncio.sleep(0.5)

                # Ambil data riwayat yang baru
                current_riwayat = await _get_current_riwayat(page)
                item["mediasi"] = extract_mediasi_from_riwayat(current_riwayat)
                logger.info(
                    f"[SCRAPER] Mediasi untuk roster {item.get('no')}: {item['mediasi']}"
                )

                # KEMBALI ke halaman asal (sangat penting!)
                await page.goto(
                    current_url, wait_until="domcontentloaded", timeout=15000
                )
                await asyncio.sleep(0.5)  # Tunggu navigasi kembali
            else:
                logger.warning(f"[SCRAPER] Gagal switch ke ref {ref_id}")

    except Exception as e:
        logger.error(f"[SCRAPER] Error processing mediasi data: {e}")


async def _get_current_riwayat(page: Page) -> list:
    """Ambil data riwayat dari halaman saat ini"""
    try:
        page_content = await page.content()
        soup = BeautifulSoup(page_content, "lxml")
        purple_tables = _find_purple_tables(soup)

        if len(purple_tables) >= 2:
            return parse_riwayat_table(purple_tables[1])
        return []
    except Exception as e:
        logger.error(f"[SCRAPER] Error getting current riwayat: {e}")
        return []


# Fungsi-fungsi helper lainnya tetap sama seperti sebelumnya...
def _extract_nama(soup: BeautifulSoup) -> str:
    """Extract nama dari berbagai possible selector"""
    nama_selectors = [
        SEL["nama_value"],
        "table.tbl_typeA.center td:nth-child(2)",
        "table.tbl_typeA td:nth-child(2)",
    ]

    for selector in nama_selectors:
        try:
            nama_el = soup.select_one(selector)
            if nama_el:
                nama_text = nama_el.get_text(strip=True)
                if nama_text and nama_text != "-":
                    logger.info(f"[SCRAPER] Nama ditemukan: {nama_text}")
                    return nama_text
        except Exception as e:
            logger.debug(f"[SCRAPER] Nama selector {selector} failed: {e}")
            continue

    return "-"


def _find_purple_tables(soup: BeautifulSoup) -> list:
    """Cari purple tables dengan berbagai fallback"""
    tables = soup.select(SEL["tables_purple"])
    if not tables:
        tables = soup.select("table.purple")
    if not tables:
        tables = soup.select("table")
    return tables


def _parse_pengiriman_table(purple_tables: list) -> list:
    """Parse tabel pengiriman dari purple tables"""
    if not purple_tables or len(purple_tables) < 1:
        return []

    pengiriman_list = parse_pengiriman_table(purple_tables[0])
    logger.debug(f"[SCRAPER] Pengiriman entries: {len(pengiriman_list)}")
    return pengiriman_list


def _parse_riwayat_table(purple_tables: list) -> tuple:
    """Parse tabel riwayat dan job links dari purple tables"""
    if not purple_tables or len(purple_tables) < 2:
        return [], {}

    riwayat = parse_riwayat_table(purple_tables[1])
    job_links = extract_job_links(purple_tables[1])
    logger.debug(
        f"[SCRAPER] Riwayat entries: {len(riwayat)}, Job links: {len(job_links)}"
    )
    return riwayat, job_links


async def _navigate_to_progress_page(page: Page) -> None:
    """Handle navigation ke halaman progress"""
    current_url = page.url

    if PROGRESS_URL in current_url:
        # Jika sudah di progress dan tabel sudah ada, skip reload
        try:
            if await page.query_selector(SEL["tables_purple"]):
                logger.debug("[SCRAPER] Already on progress page with tables, skip reload")
                return
        except Exception:
            pass
        logger.debug("[SCRAPER] On progress page but tables missing, reload...")
        await page.reload(wait_until="domcontentloaded", timeout=15000)
    else:
        logger.debug("[SCRAPER] Navigating to progress page...")
        await page.goto(PROGRESS_URL, wait_until="domcontentloaded", timeout=20000)


async def _wait_for_page_ready(page: Page) -> bool:
    """Tunggu sampai halaman progress ready dengan timeout reasonable"""
    selectors_to_check = [
        SEL["tables_purple"],
        "table.tbl_typeA.purple",
        "table.tbl_typeA",
        "table",
    ]

    for selector in selectors_to_check:
        try:
            await page.wait_for_selector(selector, timeout=4000)
            logger.debug(f"[SCRAPER] Page ready - found: {selector}")
            return True
        except Exception:
            continue

    # Fallback: cek ada tabel apapun
    try:
        tables = await page.query_selector_all("table")
        if tables:
            logger.debug(f"[SCRAPER] Found {len(tables)} tables as fallback")
            return True
    except Exception as e:
        logger.debug(f"[SCRAPER] Fallback table check failed: {e}")

    return False


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
