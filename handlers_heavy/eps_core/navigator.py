# handlers/eps_core/navigator.py

import re
import asyncio
import logging
from typing import Optional
from playwright.async_api import Page, Error, TimeoutError

from .constants import SEL

logger = logging.getLogger(__name__)


async def _try_select_row2(page: Page) -> Optional[str]:
    """
    Coba select row 2 secara otomatis dengan Playwright

    Args:
        page: Playwright page object

    Returns:
        ref_id jika berhasil, None jika gagal
    """
    try:
        logger.debug("[NAVIGATOR] Mencoba select row 2...")

        # Tunggu tabel purple muncul
        await page.wait_for_selector(SEL["tables_purple"], timeout=8000)

        # Cari anchor dengan text "2"
        row_anchor = await page.query_selector(f"{SEL['row_anchor']}:has-text('2')")

        if not row_anchor:
            logger.debug("[NAVIGATOR] Anchor dengan text '2' tidak ditemukan")
            return None

        # Dapatkan href dan extract ref_id
        href = await row_anchor.get_attribute("href") or ""
        logger.debug(f"[NAVIGATOR] Found href: {href}")

        m = re.search(r"fncDetailRow\('([^']+)'", href)
        if not m:
            logger.debug("[NAVIGATOR] Tidak bisa extract ref_id dari href")
            return None

        ref_id = m.group(1)
        logger.debug(f"[NAVIGATOR] Extracted ref_id: {ref_id}")

        # Simpan content sebelum click untuk comparison
        content_before = await page.content()

        # Coba execute JavaScript function
        try:
            await page.evaluate(f"fncDetailRow('{ref_id}', '')")
            logger.debug("[NAVIGATOR] JavaScript function executed")
        except Error as e:
            logger.warning(f"[NAVIGATOR] JavaScript execution failed: {e}")
            # Fallback: click anchor langsung
            await row_anchor.click()
            logger.debug("[NAVIGATOR] Fallback: anchor clicked directly")

        # Tunggu perubahan halaman
        try:
            # Tunggu sampai tabel stale atau update
            await page.wait_for_function(
                """
                () => {
                    const currentTables = document.querySelectorAll('table.tbl_typeA.purple.mt30');
                    return currentTables.length > 0;
                }
                """,
                timeout=6000,
            )

            # Additional wait untuk memastikan content berubah
            await asyncio.sleep(0.3)

            logger.debug("[NAVIGATOR] Page updated after row selection")
            return ref_id

        except TimeoutError:
            logger.warning(
                "[NAVIGATOR] Timeout waiting for page update after row selection"
            )
            # Cek jika content berubah meskipun timeout
            content_after = await page.content()
            if content_before != content_after:
                logger.debug("[NAVIGATOR] Content changed despite timeout")
                return ref_id
            return None

    except Exception as e:
        logger.error(f"[NAVIGATOR] Error selecting row 2: {e}")
        return None


async def _switch_to_ref(page: Page, ref_id: str) -> bool:
    """
    Switch ke roster tertentu berdasarkan ref_id dengan Playwright

    Args:
        page: Playwright page object
        ref_id: Reference ID roster

    Returns:
        True jika berhasil, False jika gagal
    """
    if not ref_id:
        logger.warning("[NAVIGATOR] ref_id kosong, skip switching")
        return False

    try:
        logger.debug(f"[NAVIGATOR] Switching to ref: {ref_id}")

        # Simpan content sebelum switch
        content_before = await page.content()

        # Coba execute JavaScript function
        try:
            await page.evaluate(f"fncDetailRow('{ref_id}', '')")
            logger.debug(
                f"[NAVIGATOR] JavaScript function executed untuk ref: {ref_id}"
            )
        except Error as e:
            logger.warning(
                f"[NAVIGATOR] JavaScript execution failed untuk ref {ref_id}: {e}"
            )
            # Fallback: cari dan click anchor manual
            await _click_anchor_by_ref_id(page, ref_id)

        # Tunggu perubahan halaman
        try:
            # Tunggu sampai ada update pada tabel
            await page.wait_for_function(
                """
                () => {
                    const tables = document.querySelectorAll('table.tbl_typeA.purple.mt30');
                    return tables.length >= 2;
                }
                """,
                timeout=6000,
            )

            # Additional wait untuk memastikan update complete
            await asyncio.sleep(0.3)

            logger.debug(f"[NAVIGATOR] Successfully switched to ref: {ref_id}")
            return True

        except TimeoutError:
            logger.warning(f"[NAVIGATOR] Timeout waiting for switch to ref: {ref_id}")
            # Cek jika content berubah meskipun timeout
            content_after = await page.content()
            if content_before != content_after:
                logger.debug(
                    f"[NAVIGATOR] Content changed for ref {ref_id} despite timeout"
                )
                return True
            return False

    except Exception as e:
        logger.error(f"[NAVIGATOR] Error switching to ref {ref_id}: {e}")
        return False


async def _click_anchor_by_ref_id(page: Page, ref_id: str) -> bool:
    """
    Fallback: click anchor manually berdasarkan ref_id

    Args:
        page: Playwright page object
        ref_id: Reference ID untuk dicari

    Returns:
        True jika berhasil click, False jika gagal
    """
    try:
        logger.debug(f"[NAVIGATOR] Mencari anchor manually untuk ref: {ref_id}")

        # Dapatkan semua anchor
        anchors = await page.query_selector_all(SEL["row_anchor"])
        logger.debug(f"[NAVIGATOR] Found {len(anchors)} anchors")

        for anchor in anchors:
            href = await anchor.get_attribute("href") or ""
            if ref_id in href:
                logger.debug(f"[NAVIGATOR] Found matching anchor untuk ref: {ref_id}")
                await anchor.click()
                return True

        logger.warning(f"[NAVIGATOR] Tidak ditemukan anchor untuk ref: {ref_id}")
        return False

    except Exception as e:
        logger.error(f"[NAVIGATOR] Error clicking anchor for ref {ref_id}: {e}")
        return False


async def navigate_to_roster(page: Page, roster_number: int) -> Optional[str]:
    """
    Navigate ke roster tertentu berdasarkan nomor

    Args:
        page: Playwright page object
        roster_number: Nomor roster (1, 2, 3, etc.)

    Returns:
        ref_id jika berhasil, None jika gagal
    """
    try:
        logger.info(f"[NAVIGATOR] Navigating to roster {roster_number}...")

        # Tunggu tabel muncul
        await page.wait_for_selector(SEL["tables_purple"], timeout=10000)

        # Cari anchor dengan nomor yang sesuai
        roster_anchor = await page.query_selector(
            f"{SEL['row_anchor']}:has-text('{roster_number}')"
        )

        if not roster_anchor:
            logger.warning(f"[NAVIGATOR] Roster {roster_number} tidak ditemukan")
            return None

        # Extract ref_id dari href
        href = await roster_anchor.get_attribute("href") or ""
        m = re.search(r"fncDetailRow\('([^']+)'", href)

        if not m:
            logger.warning(
                f"[NAVIGATOR] Tidak bisa extract ref_id untuk roster {roster_number}"
            )
            return None

        ref_id = m.group(1)

        # Switch ke roster tersebut
        success = await _switch_to_ref(page, ref_id)

        if success:
            logger.info(f"[NAVIGATOR] Berhasil navigate ke roster {roster_number}")
            return ref_id
        else:
            logger.warning(f"[NAVIGATOR] Gagal switch ke roster {roster_number}")
            return None

    except Exception as e:
        logger.error(f"[NAVIGATOR] Error navigating to roster {roster_number}: {e}")
        return None


async def get_available_rosters(page: Page) -> list:
    """
    Dapatkan list semua roster yang available

    Args:
        page: Playwright page object

    Returns:
        List of dictionaries dengan info roster
    """
    try:
        logger.debug("[NAVIGATOR] Getting available rosters...")

        # Tunggu tabel muncul
        await page.wait_for_selector(SEL["tables_purple"], timeout=10000)

        # Dapatkan semua anchor
        anchors = await page.query_selector_all(SEL["row_anchor"])
        rosters = []

        for anchor in anchors:
            try:
                # Dapatkan text (nomor roster)
                text = await anchor.text_content()
                roster_no = text.strip() if text else "Unknown"

                # Dapatkan href dan extract ref_id
                href = await anchor.get_attribute("href") or ""
                m = re.search(r"fncDetailRow\('([^']+)'", href)
                ref_id = m.group(1) if m else None

                if roster_no and ref_id:
                    rosters.append(
                        {"number": roster_no, "ref_id": ref_id, "href": href}
                    )

            except Exception as e:
                logger.debug(f"[NAVIGATOR] Error processing anchor: {e}")
                continue

        # Sort by roster number
        rosters.sort(key=lambda x: int(x["number"]) if x["number"].isdigit() else 0)

        logger.debug(f"[NAVIGATOR] Found {len(rosters)} available rosters")
        return rosters

    except Exception as e:
        logger.error(f"[NAVIGATOR] Error getting available rosters: {e}")
        return []


async def get_current_roster_info(page: Page) -> dict:
    """
    Dapatkan informasi tentang roster yang sedang aktif

    Args:
        page: Playwright page object

    Returns:
        Dictionary dengan informasi roster aktif
    """
    try:
        # Cari anchor yang memiliki class active atau style tertentu
        # (Ini mungkin perlu disesuaikan dengan implementasi spesifik EPS)

        active_selectors = [
            f"{SEL['row_anchor']}.active",
            f"{SEL['row_anchor']}[style*='background']",
            f"{SEL['row_anchor']}[style*='color']",
        ]

        active_anchor = None
        for selector in active_selectors:
            active_anchor = await page.query_selector(selector)
            if active_anchor:
                break

        if active_anchor:
            text = await active_anchor.text_content()
            href = await active_anchor.get_attribute("href") or ""
            m = re.search(r"fncDetailRow\('([^']+)'", href)
            ref_id = m.group(1) if m else None

            return {
                "number": text.strip() if text else "Unknown",
                "ref_id": ref_id,
                "is_active": True,
            }
        else:
            # Jika tidak ditemukan active, ambil roster pertama sebagai default
            all_rosters = await get_available_rosters(page)
            if all_rosters:
                return {
                    "number": all_rosters[0]["number"],
                    "ref_id": all_rosters[0]["ref_id"],
                    "is_active": False,
                    "note": "Assuming first roster as current",
                }

        return {"number": "Unknown", "ref_id": None, "is_active": False}

    except Exception as e:
        logger.error(f"[NAVIGATOR] Error getting current roster info: {e}")
        return {"number": "Unknown", "ref_id": None, "is_active": False}


async def wait_for_page_update(page: Page, timeout: int = 15000) -> bool:
    """
    Tunggu sampai halaman selesai update setelah navigation

    Args:
        page: Playwright page object
        timeout: Timeout dalam milliseconds

    Returns:
        True jika berhasil, False jika timeout
    """
    try:
        # Tunggu sampai tidak ada loading indicator
        await page.wait_for_function(
            """
            () => {
                // Cek beberapa loading indicators dengan cara yang kompatibel (tanpa :contains)
                const loadingSelectors = ['.loading', '.spinner', '[aria-busy="true"]'];
                for (const sel of loadingSelectors) {
                    const el = document.querySelector(sel);
                    if (el && el.offsetParent !== null) return false;
                }

                // Cek elemen yang mengandung teks 'loading' (div/span/p)
                const textElems = Array.from(document.querySelectorAll('div, span, p'));
                for (const el of textElems) {
                    try {
                        if (el && el.offsetParent !== null && /loading/i.test(el.textContent || '')) {
                            return false;
                        }
                    } catch (e) {
                        // ignore elements that throw on access
                        continue;
                    }
                }

                return document.readyState === 'complete';
            }
            """,
            timeout=timeout,
        )

        # Additional wait untuk memastikan
        await asyncio.sleep(0.5)
        return True

    except TimeoutError:
        logger.warning("[NAVIGATOR] Timeout waiting for page update")
        return False
    except Exception as e:
        logger.error(f"[NAVIGATOR] Error waiting for page update: {e}")
        return False


async def safe_navigation(
    page: Page, action_callback, description: str = "navigation"
) -> bool:
    """
    Safe navigation dengan error handling dan retry

    Args:
        page: Playwright page object
        action_callback: Async function yang melakukan navigation
        description: Deskripsi action untuk logging

    Returns:
        True jika berhasil, False jika gagal
    """
    max_retries = 2

    for attempt in range(max_retries):
        try:
            logger.debug(f"[NAVIGATOR] {description} attempt {attempt + 1}")

            # Simpan state sebelum action
            url_before = page.url
            content_before = await page.content()

            # Execute action
            await action_callback()

            # Tunggu update
            update_success = await wait_for_page_update(page)

            if update_success:
                logger.debug(f"[NAVIGATOR] {description} successful")
                return True
            else:
                # Cek jika ada perubahan meskipun timeout
                content_after = await page.content()
                if content_before != content_after:
                    logger.debug(
                        f"[NAVIGATOR] {description} successful (content changed)"
                    )
                    return True

                logger.warning(
                    f"[NAVIGATOR] {description} mungkin gagal - no content change"
                )

        except Exception as e:
            logger.error(f"[NAVIGATOR] {description} attempt {attempt + 1} failed: {e}")

        if attempt < max_retries - 1:
            await asyncio.sleep(1)

    logger.error(f"[NAVIGATOR] All {description} attempts failed")
    return False


async def refresh_page_safe(page: Page) -> bool:
    """
    Safe page refresh dengan error handling

    Args:
        page: Playwright page object

    Returns:
        True jika berhasil, False jika gagal
    """
    try:
        logger.debug("[NAVIGATOR] Refreshing page...")

        await page.reload(wait_until="domcontentloaded")

        # Tunggu sampai page ready
        await page.wait_for_function(
            "document.readyState === 'complete'", timeout=10000
        )

        logger.debug("[NAVIGATOR] Page refreshed successfully")
        return True

    except Exception as e:
        logger.error(f"[NAVIGATOR] Error refreshing page: {e}")
        return False


# Export functions
__all__ = [
    "_try_select_row2",
    "_switch_to_ref",
    "navigate_to_roster",
    "get_available_rosters",
    "get_current_roster_info",
    "wait_for_page_update",
    "safe_navigation",
    "refresh_page_safe",
]
