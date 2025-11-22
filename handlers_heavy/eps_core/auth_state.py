"""Authentication state flow and navigation helpers."""

import asyncio
import logging
from typing import Any, Dict

from playwright.async_api import Page, Error, TimeoutError

from .auth_core import normalize_birthday, login_with
from .auth_fast import verifikasi_tanggal_lahir_fast
from .constants import LOGIN_URL

logger = logging.getLogger(__name__)


async def verifikasi_tanggal_lahir(page: Page, birthday_str: str) -> bool:
    """Optimized birthday verification dengan Playwright."""
    try:
        logger.info("[AUTH] Starting birthday verification")

        normalized_bday = normalize_birthday(birthday_str)

        birthday_selectors = [
            "#chkBirtDt",
            "input[name='birthday']",
            "input[name='chkBirtDt']",
            "input[placeholder*='birth']",
            "input[placeholder*='Birth']",
            "input[placeholder*='생년월일']",
        ]

        birthday_filled = False
        for selector in birthday_selectors:
            try:
                await page.wait_for_selector(selector, timeout=8000)
                await page.fill(selector, normalized_bday)
                birthday_filled = True
                logger.debug(f"[AUTH] Birthday filled dengan selector: {selector}")
                break
            except (Error, TimeoutError):
                continue

        if not birthday_filled:
            current_url = page.url
            page_content = await page.content()

            if "langMain.eo" in current_url or "main" in current_url:
                logger.info("[AUTH] Already past birthday verification")
                return True
            else:
                logger.error("[AUTH] Birthday field not found")
                return False

        submit_selectors = [
            "span.buttonE > button",
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Submit')",
            "button:has-text('확인')",
            "button:has-text('인증')",
            "input[value='Submit']",
            "input[value='확인']",
        ]

        submit_clicked = False
        for selector in submit_selectors:
            try:
                await page.click(selector, timeout=5000)
                submit_clicked = True
                logger.debug(
                    f"[AUTH] Birthday submit clicked dengan selector: {selector}"
                )
                break
            except (Error, TimeoutError):
                continue

        if not submit_clicked:
            logger.error("[AUTH] Cannot find birthday submit button")
            return False

        try:
            await page.wait_for_function(
                """
                () => {
                    const url = window.location.href;
                    return (
                        url.includes('langMain.eo') ||
                        url.includes('main') ||
                        url.includes('progress') ||
                        document.querySelector('table.tbl_typeA')
                    );
                }
                """,
                timeout=10000,
            )
            logger.info("[AUTH] Birthday verification successful")
            return True

        except TimeoutError:
            current_url = page.url
            if "langMain.eo" in current_url or "main" in current_url:
                logger.info(
                    "[AUTH] Birthday verification successful (alternative check)"
                )
                return True
            else:
                logger.error("[AUTH] Birthday verification timeout")
                page_content = await page.content()
                if "error" in page_content.lower() or "invalid" in page_content.lower():
                    logger.error("[AUTH] Birthday verification error detected")
                return False

    except Error as e:
        logger.error(f"[AUTH] Playwright error during birthday verification: {e}")
        return False
    except Exception as e:
        logger.error(f"[AUTH] Unexpected error during birthday verification: {e}")
        return False


async def quick_auth_check(page: Page) -> bool:
    """Quick check if already authenticated dengan Playwright."""
    try:
        current_url = page.url
        page_content = await page.content()

        logged_in_indicators = [
            "langMain.eo" in current_url,
            "main" in current_url,
            "progress" in current_url,
            "tbl_typeA" in page_content,
            "logout" in page_content.lower(),
            "selamat" in page_content.lower(),
            "welcome" in page_content.lower(),
        ]

        need_login_indicators = [
            "login" in current_url,
            "Please Login" in page_content,
            "birthChk" in page_content,
            "sKorTestNo" in page_content,
        ]

        if any(logged_in_indicators) and not any(need_login_indicators):
            logger.debug("[AUTH] Quick check: Already authenticated")
            return True
        else:
            logger.debug("[AUTH] Quick check: Needs authentication")
            return False

    except Exception as e:
        logger.debug(f"[AUTH] Quick check error: {e}")
        return False


async def full_auth_flow(
    page: Page, username: str, password: str, birthday: str
) -> bool:
    """Complete authentication flow (login + birthday verification)."""
    try:
        logger.info("[AUTH] Starting full authentication flow")

        if await quick_auth_check(page):
            logger.info("[AUTH] Already authenticated, skipping auth flow")
            return True

        await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=15000)
        await asyncio.sleep(2)

        if not await login_with(page, username, password):
            logger.error("[AUTH] Login failed in full auth flow")
            return False

        await asyncio.sleep(2)

        page_content = await page.content()
        if "birthChk" in page_content or "chkBirtDt" in page_content:
            if not await verifikasi_tanggal_lahir(page, birthday):
                logger.error("[AUTH] Birthday verification failed in full auth flow")
                return False
            await asyncio.sleep(2)

        if await quick_auth_check(page):
            logger.info("[AUTH] Full authentication flow completed successfully")
            return True
        else:
            logger.error("[AUTH] Full authentication flow failed final check")
            return False

    except Exception as e:
        logger.error(f"[AUTH] Full auth flow error: {e}")
        return False


async def check_auth_state(page: Page) -> Dict[str, Any]:
    """Comprehensive auth state check."""
    try:
        current_url = page.url
        page_content = await page.content()

        state_info: Dict[str, Any] = {
            "current_url": current_url,
            "is_logged_in": False,
            "needs_birthday_verification": False,
            "needs_login": False,
            "auth_stage": "unknown",
            "page_indicators": [],
        }

        indicators = {
            "login_form": "sKorTestNo" in page_content,
            "birthday_form": "birthChk" in page_content or "chkBirtDt" in page_content,
            "main_page": "langMain.eo" in current_url or "main" in current_url,
            "progress_page": "progress" in current_url,
            "welcome_message": any(
                word in page_content.lower() for word in ["selamat", "welcome"]
            ),
            "logout_button": "logout" in page_content.lower(),
            "progress_table": "tbl_typeA" in page_content,
        }

        state_info["page_indicators"] = [k for k, v in indicators.items() if v]

        if indicators["main_page"] or indicators["progress_page"]:
            state_info["is_logged_in"] = True
            state_info["auth_stage"] = "authenticated"
        elif indicators["birthday_form"]:
            state_info["needs_birthday_verification"] = True
            state_info["auth_stage"] = "needs_birthday"
        elif indicators["login_form"]:
            state_info["needs_login"] = True
            state_info["auth_stage"] = "needs_login"
        else:
            state_info["auth_stage"] = "unknown"

        logger.debug(f"[AUTH] Auth state: {state_info['auth_stage']}")
        return state_info

    except Exception as e:
        logger.error(f"[AUTH] Auth state check error: {e}")
        return {
            "current_url": "error",
            "is_logged_in": False,
            "needs_birthday_verification": False,
            "needs_login": False,
            "auth_stage": "error",
            "error": str(e),
        }


async def safe_navigation_and_auth(
    page: Page,
    url: str,
    username: str,
    password: str,
    birthday: str,
    timeout: int = 30000,
) -> bool:
    """Safe navigation dengan automatic authentication jika diperlukan."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        auth_state = await check_auth_state(page)

        if auth_state["needs_login"] or auth_state["needs_birthday_verification"]:
            logger.info(
                "[AUTH] Authentication required after navigation, starting auth flow"
            )
            return await full_auth_flow(page, username, password, birthday)

        if auth_state["is_logged_in"]:
            logger.debug("[AUTH] Already authenticated after navigation")
            return True

        logger.warning(
            "[AUTH] Unknown auth state after navigation, attempting auth flow"
        )
        return await full_auth_flow(page, username, password, birthday)

    except Exception as e:
        logger.error(f"[AUTH] Safe navigation and auth error: {e}")
        return False


__all__ = [
    "verifikasi_tanggal_lahir",
    "quick_auth_check",
    "full_auth_flow",
    "check_auth_state",
    "safe_navigation_and_auth",
]
