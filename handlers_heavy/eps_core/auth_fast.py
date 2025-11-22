"""Fast/ultra-fast auth helpers and retry wrappers."""

import asyncio
import logging
from typing import Any, Dict, Optional

from playwright.async_api import Page

from .constants import LOGIN_URL
from .auth_core import login_with
from .utils import normalize_birthday

logger = logging.getLogger(__name__)


async def login_with_fast(page: Page, username: str, password: str) -> bool:
    """Fast login function dengan timeout lebih ketat."""
    try:
        logger.info(f"[AUTH] Fast login for user: {username}")

        await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=15000)

        try:
            await page.wait_for_selector("#sKorTestNo", timeout=5000)
        except Exception:
            logger.warning("[AUTH] Login form not found quickly, but continuing")

        try:
            await page.fill("#sKorTestNo", username)
            await page.fill("#sFnrwRecvNo", password)
            await page.click(".btn_login", timeout=3000)
        except Exception as e:
            logger.warning(f"[AUTH] Fast form fill warning: {e}")
            return await login_with(page, username, password)

        try:
            await page.wait_for_function(
                """
                () => {
                    const url = window.location.href;
                    return url.includes('langMain.eo') || 
                           url.includes('main') || 
                           url.includes('progress') ||
                           document.querySelector('table.tbl_typeA');
                }
                """,
                timeout=10000,
            )
            logger.info("[AUTH] ✅ Fast login successful")
            return True
        except Exception:
            current_url = page.url
            if "langMain.eo" in current_url or "main" in current_url:
                logger.info("[AUTH] ✅ Fast login successful (fallback check)")
                return True
            return False

    except Exception as e:
        logger.error(f"[AUTH] ❌ Fast login error: {e}")
        return False


async def verifikasi_tanggal_lahir_fast(page: Page, birthday_str: str) -> bool:
    """Fast birthday verification."""
    try:
        logger.info("[AUTH] Fast birthday verification")

        normalized_bday = normalize_birthday(birthday_str)

        page_content = await page.content()
        if "birthChk" not in page_content and "chkBirtDt" not in page_content:
            logger.debug("[AUTH] No birthday verification needed")
            return True

        try:
            await page.fill("#chkBirtDt", normalized_bday, timeout=3000)
            await page.click("span.buttonE > button", timeout=3000)
        except Exception as e:
            logger.warning(f"[AUTH] Fast birthday form warning: {e}")

        try:
            await page.wait_for_function(
                """
                () => {
                    const url = window.location.href;
                    return url.includes('langMain.eo') || 
                           url.includes('main') || 
                           url.includes('progress');
                }
                """,
                timeout=8000,
            )
            logger.info("[AUTH] Fast birthday verification successful")
            return True
        except Exception:
            current_url = page.url
            if "langMain.eo" in current_url or "main" in current_url:
                logger.info(
                    "[AUTH] Fast birthday verification successful (fallback)"
                )
                return True
            return False

    except Exception as e:
        logger.error(f"[AUTH] Fast birthday verification error: {e}")
        return False


async def login_with_ultra_fast(page: Page, username: str, password: str) -> bool:
    """Ultra-fast login dengan timeout sangat ketat."""
    try:
        logger.info(f"[AUTH] Ultra-fast login for user: {username}")

        try:
            await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=10000)
        except Exception as e:
            logger.debug(f"[AUTH] Navigation warning: {e}")

        try:
            await page.fill("#sKorTestNo", username, timeout=2000)
            await page.fill("#sFnrwRecvNo", password, timeout=2000)
            await page.click(".btn_login", timeout=2000)
        except Exception as e:
            logger.warning(f"[AUTH] Ultra-fast form fill warning: {e}")
            return await login_with(page, username, password)

        try:
            await page.wait_for_function(
                """
                () => {
                    const url = window.location.href;
                    return url.includes('langMain.eo') || 
                           url.includes('main') || 
                           url.includes('progress') ||
                           document.querySelector('table.tbl_typeA') ||
                           document.querySelector('#chkBirtDt');
                }
                """,
                timeout=5000,
            )
            logger.info("[AUTH] ✅ Ultra-fast login successful")
            return True
        except Exception:
            current_url = page.url
            page_content = await page.content()

            if (
                "langMain.eo" in current_url
                or "main" in current_url
                or "progress" in current_url
                or "chkBirtDt" in page_content
            ):
                logger.info("[AUTH] ✅ Ultra-fast login successful (fallback check)")
                return True
            return False

    except Exception as e:
        logger.error(f"[AUTH] ❌ Ultra-fast login error: {e}")
        return False


async def login_with_retry(
    page: Page, username: str, password: str, max_retries: int = 2, retry_delay: int = 3
) -> bool:
    """Login dengan retry mechanism."""
    for attempt in range(max_retries):
        logger.info(f"[AUTH] Login attempt {attempt + 1}/{max_retries}")

        if await login_with(page, username, password):
            return True

        if attempt < max_retries - 1:
            logger.info(f"[AUTH] Retrying login in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)

    return False


async def verifikasi_tanggal_lahir_retry(
    page: Page, birthday: str, max_retries: int = 2, retry_delay: int = 3
) -> bool:
    """Birthday verification dengan retry mechanism."""
    for attempt in range(max_retries):
        logger.info(f"[AUTH] Birthday verification attempt {attempt + 1}/{max_retries}")

        from .auth_state import verifikasi_tanggal_lahir  # avoid cycle

        if await verifikasi_tanggal_lahir(page, birthday):
            return True

        if attempt < max_retries - 1:
            logger.info(
                f"[AUTH] Retrying birthday verification in {retry_delay} seconds..."
            )
            await asyncio.sleep(retry_delay)

    return False


__all__ = [
    "login_with_fast",
    "verifikasi_tanggal_lahir_fast",
    "login_with_ultra_fast",
    "login_with_retry",
    "verifikasi_tanggal_lahir_retry",
]
