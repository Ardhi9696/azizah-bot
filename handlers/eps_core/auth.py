# handlers/eps_core/auth.py

import re
import asyncio
import logging
from typing import Optional, Dict, Any  # <-- TAMBAH INI
from playwright.async_api import Page, Error, TimeoutError

from .constants import LOGIN_URL

logger = logging.getLogger(__name__)


def normalize_birthday(value: str) -> str:
    """Normalize birthday input dengan improved logic"""
    try:
        digits = re.sub(r"\D", "", value or "")
        if len(digits) == 6:  # DDMMYY
            return digits
        elif len(digits) == 8:  # DDMMYYYY
            return digits
        else:
            logger.warning(f"Birthday format mungkin salah: {value}")
            return value
    except Exception as e:
        logger.error(f"Birthday normalization error: {e}")
        return value


# handlers/eps_core/auth.py - PERBAIKI login_with

# handlers/eps_core/auth.py - TAMBAH fungsi fast

async def login_with_fast(page: Page, username: str, password: str) -> bool:
    """Fast login function dengan timeout lebih ketat"""
    try:
        logger.info(f"[AUTH] Fast login for user: {username}")

        # Navigasi cepat
        await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=15000)

        # Tunggu sangat singkat untuk form
        try:
            await page.wait_for_selector("#sKorTestNo", timeout=5000)
        except:
            logger.warning("[AUTH] Login form not found quickly, but continuing")

        # Isi form dengan approach langsung
        try:
            await page.fill("#sKorTestNo", username)
            await page.fill("#sFnrwRecvNo", password)
            await page.click(".btn_login", timeout=3000)
        except Exception as e:
            logger.warning(f"[AUTH] Fast form fill warning: {e}")
            # Fallback ke fungsi normal
            return await login_with(page, username, password)

        # Tunggu hasil login dengan timeout pendek
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
                timeout=10000
            )
            logger.info("[AUTH] ✅ Fast login successful")
            return True
        except Exception:
            # Fallback check
            current_url = page.url
            if "langMain.eo" in current_url or "main" in current_url:
                logger.info("[AUTH] ✅ Fast login successful (fallback check)")
                return True
            return False

    except Exception as e:
        logger.error(f"[AUTH] ❌ Fast login error: {e}")
        return False


async def verifikasi_tanggal_lahir_fast(page: Page, birthday_str: str) -> bool:
    """Fast birthday verification"""
    try:
        logger.info("[AUTH] Fast birthday verification")

        normalized_bday = normalize_birthday(birthday_str)

        # Cepat cek apakah sudah perlu verification
        page_content = await page.content()
        if "birthChk" not in page_content and "chkBirtDt" not in page_content:
            logger.debug("[AUTH] No birthday verification needed")
            return True

        # Isi form dengan timeout pendek
        try:
            await page.fill("#chkBirtDt", normalized_bday, timeout=3000)
            await page.click("span.buttonE > button", timeout=3000)
        except Exception as e:
            logger.warning(f"[AUTH] Fast birthday form warning: {e}")

        # Tunggu hasil dengan timeout pendek
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
                timeout=8000
            )
            logger.info("[AUTH] Fast birthday verification successful")
            return True
        except Exception:
            # Fallback check
            current_url = page.url
            if "langMain.eo" in current_url or "main" in current_url:
                logger.info("[AUTH] Fast birthday verification successful (fallback)")
                return True
            return False

    except Exception as e:
        logger.error(f"[AUTH] Fast birthday verification error: {e}")
        return False


# handlers/eps_core/auth.py - FIX AUTH FUNDAMENTALLY


async def login_with(page: Page, username: str, password: str) -> bool:
    """Fixed login function dengan comprehensive element finding"""
    try:
        logger.info(f"[AUTH] Attempting login for user: {username}")

        # Validasi page
        if page.is_closed():
            logger.error("[AUTH] Page is closed, cannot login")
            return False

        # Navigate dengan wait until load
        await page.goto(LOGIN_URL, wait_until="load", timeout=30000)
        logger.debug("[AUTH] Navigation completed")

        # Tunggu lebih lama untuk pastikan page fully loaded
        await asyncio.sleep(3)

        # DEBUG: Screenshot untuk troubleshooting
        try:
            await page.screenshot(path="debug_login_page.png")
            logger.debug("[AUTH] Screenshot saved: debug_login_page.png")
        except:
            pass

        # Cari form login dengan multiple strategies
        login_form_selectors = [
            "form",
            "form[action*='login']",
            "form[method='post']",
            ".login-form",
            "#loginForm",
        ]

        form_found = False
        for form_selector in login_form_selectors:
            try:
                form = await page.query_selector(form_selector)
                if form:
                    form_found = True
                    logger.info(f"[AUTH] Login form found: {form_selector}")
                    break
            except:
                continue

        if not form_found:
            logger.warning("[AUTH] No login form found, trying direct input search")

        # STRATEGY 1: Cari fields by specific EPS selectors
        username_filled = False
        eps_selectors = [
            "#sKorTestNo",
            "input[name='sKorTestNo']",
            "input[name='username']",
            "#username",
        ]

        for selector in eps_selectors:
            try:
                logger.debug(f"[AUTH] Trying EPS selector: {selector}")
                element = await page.wait_for_selector(
                    selector, timeout=5000, state="visible"
                )
                if element:
                    await element.fill(username)
                    username_filled = True
                    logger.info(f"[AUTH] Username filled with EPS selector: {selector}")
                    break
            except Exception as e:
                logger.debug(f"[AUTH] EPS selector {selector} failed: {e}")
                continue

        # STRATEGY 2: Cari by input type dan attributes
        if not username_filled:
            generic_selectors = [
                "input[type='text']",
                "input[placeholder*='test']",
                "input[placeholder*='number']",
                "input[placeholder*='ID']",
                "input:first-of-type",
            ]

            for selector in generic_selectors:
                try:
                    logger.debug(f"[AUTH] Trying generic selector: {selector}")
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        try:
                            # Cek jika element visible dan enabled
                            is_visible = await element.is_visible()
                            is_enabled = await element.is_enabled()
                            if is_visible and is_enabled:
                                await element.fill(username)
                                username_filled = True
                                logger.info(
                                    f"[AUTH] Username filled with generic selector: {selector}"
                                )
                                break
                        except:
                            continue
                    if username_filled:
                        break
                except Exception as e:
                    logger.debug(f"[AUTH] Generic selector {selector} failed: {e}")
                    continue

        # STRATEGY 3: Fallback - cari semua input fields
        if not username_filled:
            try:
                all_inputs = await page.query_selector_all("input")
                logger.debug(f"[AUTH] Found {len(all_inputs)} input fields")

                for i, input_elem in enumerate(all_inputs):
                    try:
                        input_type = await input_elem.get_attribute("type")
                        if input_type in ["text", "email", "number", None]:
                            is_visible = await input_elem.is_visible()
                            is_enabled = await input_elem.is_enabled()
                            if is_visible and is_enabled:
                                await input_elem.fill(username)
                                username_filled = True
                                logger.info(
                                    f"[AUTH] Username filled with fallback (input #{i})"
                                )
                                break
                    except:
                        continue
            except Exception as e:
                logger.debug(f"[AUTH] Fallback strategy failed: {e}")

        if not username_filled:
            logger.error("[AUTH] ❌ Cannot find username field after all strategies")
            # DEBUG: Log page HTML untuk troubleshooting
            try:
                content = await page.content()
                with open("debug_page_content.html", "w", encoding="utf-8") as f:
                    f.write(content)
                logger.debug("[AUTH] Page content saved: debug_page_content.html")
            except:
                pass
            return False

        # Password field - similar comprehensive approach
        password_filled = await _fill_password_field(page, password)

        if not password_filled:
            logger.error("[AUTH] ❌ Cannot find password field")
            return False

        # Login button
        login_clicked = await _click_login_button(page)

        if not login_clicked:
            logger.error("[AUTH] ❌ Cannot find login button")
            return False

        # Wait for login result
        return await _wait_for_login_result(page)

    except Exception as e:
        logger.error(f"[AUTH] ❌ Login error: {e}")
        return False


async def _fill_password_field(page: Page, password: str) -> bool:
    """Comprehensive password field filling"""
    password_selectors = [
        "#sFnrwRecvNo",
        "input[name='sFnrwRecvNo']",
        "input[type='password']",
        "input[name='password']",
        "#password",
    ]

    for selector in password_selectors:
        try:
            element = await page.wait_for_selector(
                selector, timeout=3000, state="visible"
            )
            if element:
                await element.fill(password)
                logger.info(f"[AUTH] Password filled with selector: {selector}")
                return True
        except:
            continue

    # Fallback: cari password field
    try:
        password_fields = await page.query_selector_all("input[type='password']")
        for field in password_fields:
            if await field.is_visible():
                await field.fill(password)
                logger.info("[AUTH] Password filled with fallback")
                return True
    except:
        pass

    return False


async def _click_login_button(page: Page) -> bool:
    """Comprehensive login button clicking"""
    button_selectors = [
        ".btn_login",
        "input[type='submit']",
        "button[type='submit']",
        "input[value='Login']",
        "button:has-text('Login')",
        "input[value='로그인']",
        "button:has-text('로그인')",
    ]

    for selector in button_selectors:
        try:
            await page.click(selector, timeout=3000)
            logger.info(f"[AUTH] Login clicked with selector: {selector}")
            return True
        except:
            continue

    return False


async def _wait_for_login_result(page: Page) -> bool:
    """Wait for login result dengan comprehensive checking"""
    try:
        await page.wait_for_function(
            """
            () => {
                const url = window.location.href;
                const body = document.body.innerHTML;
                return (
                    url.includes('langMain.eo') ||
                    url.includes('main') ||
                    url.includes('progress') ||
                    body.includes('birthChk') ||
                    document.querySelector('#chkBirtDt') ||
                    document.querySelector('table.tbl_typeA') ||
                    document.querySelector('.welcome') ||
                    document.querySelector('.logout')
                );
            }
            """,
            timeout=15000,
        )
        logger.info("[AUTH] ✅ Login successful")
        return True
    except Exception:
        # Fallback checks
        current_url = page.url
        page_content = await page.content()

        success_indicators = [
            "langMain.eo" in current_url,
            "main" in current_url,
            "progress" in current_url,
            "tbl_typeA" in page_content,
            "birthChk" in page_content,
            "welcome" in page_content.lower(),
            "selamat" in page_content.lower(),
        ]

        if any(success_indicators):
            logger.info("[AUTH] ✅ Login successful (fallback check)")
            return True

        logger.error("[AUTH] ❌ Login failed - no success indicators found")
        return False


async def verifikasi_tanggal_lahir(page: Page, birthday_str: str) -> bool:
    """Optimized birthday verification dengan Playwright"""
    try:
        logger.info("[AUTH] Starting birthday verification")

        normalized_bday = normalize_birthday(birthday_str)

        # Tunggu untuk birthday field dengan multiple strategies
        birthday_filled = False
        birthday_selectors = [
            "#chkBirtDt",
            "input[name='birthday']",
            "input[name='chkBirtDt']",
            "input[placeholder*='birth']",
            "input[placeholder*='Birth']",
            "input[placeholder*='생년월일']",
        ]

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
            # Check if we're already past birthday verification
            current_url = page.url
            page_content = await page.content()

            if "langMain.eo" in current_url or "main" in current_url:
                logger.info("[AUTH] Already past birthday verification")
                return True
            else:
                logger.error("[AUTH] Birthday field not found")
                return False

        # Cari dan klik submit button dengan multiple strategies
        submit_clicked = False
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

        # Tunggu hasil verifikasi
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
            # Alternative success check
            current_url = page.url
            if "langMain.eo" in current_url or "main" in current_url:
                logger.info(
                    "[AUTH] Birthday verification successful (alternative check)"
                )
                return True
            else:
                logger.error("[AUTH] Birthday verification timeout")
                # Cek jika ada error message
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
    """Quick check if already authenticated dengan Playwright"""
    try:
        current_url = page.url
        page_content = await page.content()

        # Check various indicators of being logged in
        logged_in_indicators = [
            "langMain.eo" in current_url,
            "main" in current_url,
            "progress" in current_url,
            "tbl_typeA" in page_content,
            "logout" in page_content.lower(),
            "selamat" in page_content.lower(),
            "welcome" in page_content.lower(),
        ]

        # Check indicators of needing login
        need_login_indicators = [
            "login" in current_url,
            "Please Login" in page_content,
            "birthChk" in page_content,
            "sKorTestNo" in page_content,  # Login form
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
    """
    Complete authentication flow (login + birthday verification) dalam satu function

    Returns:
        bool: True jika berhasil, False jika gagal
    """
    try:
        logger.info("[AUTH] Starting full authentication flow")

        # Step 1: Quick check dulu
        if await quick_auth_check(page):
            logger.info("[AUTH] Already authenticated, skipping auth flow")
            return True

        # Step 2: Navigate to login page
        await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=15000)
        await asyncio.sleep(2)

        # Step 3: Login
        if not await login_with(page, username, password):
            logger.error("[AUTH] Login failed in full auth flow")
            return False

        await asyncio.sleep(2)

        # Step 4: Birthday verification (jika diperlukan)
        page_content = await page.content()
        if "birthChk" in page_content or "chkBirtDt" in page_content:
            if not await verifikasi_tanggal_lahir(page, birthday):
                logger.error("[AUTH] Birthday verification failed in full auth flow")
                return False
            await asyncio.sleep(2)

        # Step 5: Final verification
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
    """
    Comprehensive auth state check

    Returns:
        Dict dengan informasi detail tentang state authentication
    """
    try:
        current_url = page.url
        page_content = await page.content()

        state_info = {
            "current_url": current_url,
            "is_logged_in": False,
            "needs_birthday_verification": False,
            "needs_login": False,
            "auth_stage": "unknown",
            "page_indicators": [],
        }

        # Collect indicators
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

        # Determine auth stage
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
    """
    Safe navigation dengan automatic authentication jika diperlukan

    Args:
        page: Playwright page object
        url: Target URL
        username: Login username
        password: Login password
        birthday: Birthday untuk verification
        timeout: Navigation timeout

    Returns:
        bool: True jika berhasil navigate (dan auth jika diperlukan)
    """
    try:
        # Navigate ke target URL
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout)

        # Check auth state
        auth_state = await check_auth_state(page)

        # Jika perlu authentication, lakukan full auth flow
        if auth_state["needs_login"] or auth_state["needs_birthday_verification"]:
            logger.info(
                "[AUTH] Authentication required after navigation, starting auth flow"
            )
            return await full_auth_flow(page, username, password, birthday)

        # Jika sudah authenticated, langsung return success
        if auth_state["is_logged_in"]:
            logger.debug("[AUTH] Already authenticated after navigation")
            return True

        # Unknown state - coba auth flow untuk amannya
        logger.warning(
            "[AUTH] Unknown auth state after navigation, attempting auth flow"
        )
        return await full_auth_flow(page, username, password, birthday)

    except Exception as e:
        logger.error(f"[AUTH] Safe navigation and auth error: {e}")
        return False


# ===== COMPATIBILITY FUNCTIONS =====
# Untuk transitional period dari Selenium ke Playwright


async def login_with_retry(
    page: Page, username: str, password: str, max_retries: int = 2, retry_delay: int = 3
) -> bool:
    """Login dengan retry mechanism"""
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
    """Birthday verification dengan retry mechanism"""
    for attempt in range(max_retries):
        logger.info(f"[AUTH] Birthday verification attempt {attempt + 1}/{max_retries}")

        if await verifikasi_tanggal_lahir(page, birthday):
            return True

        if attempt < max_retries - 1:
            logger.info(
                f"[AUTH] Retrying birthday verification in {retry_delay} seconds..."
            )
            await asyncio.sleep(retry_delay)

    return False


# Export functions
__all__ = [
    "normalize_birthday",
    "login_with",
    "verifikasi_tanggal_lahir",
    "quick_auth_check",
    "full_auth_flow",
    "check_auth_state",
    "safe_navigation_and_auth",
    "login_with_retry",
    "verifikasi_tanggal_lahir_retry",
]

# handlers/eps_core/auth.py - TAMBAH di bagian akhir

async def login_with_ultra_fast(page: Page, username: str, password: str) -> bool:
    """Ultra-fast login dengan timeout sangat ketat"""
    try:
        logger.info(f"[AUTH] Ultra-fast login for user: {username}")

        # Navigasi super cepat
        try:
            await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=10000)
        except Exception as e:
            logger.debug(f"[AUTH] Navigation warning: {e}")

        # Isi form dengan approach langsung dan timeout sangat pendek
        try:
            # Langsung coba isi form tanpa waiting panjang
            await page.fill("#sKorTestNo", username, timeout=2000)
            await page.fill("#sFnrwRecvNo", password, timeout=2000)
            await page.click(".btn_login", timeout=2000)
        except Exception as e:
            logger.warning(f"[AUTH] Ultra-fast form fill warning: {e}")
            # Fallback ke approach normal
            return await login_with(page, username, password)

        # Tunggu hasil login dengan timeout sangat pendek
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
                timeout=5000  # Hanya 5 detik!
            )
            logger.info("[AUTH] ✅ Ultra-fast login successful")
            return True
        except Exception:
            # Fallback check yang sangat cepat
            current_url = page.url
            page_content = await page.content()
            
            if ("langMain.eo" in current_url or 
                "main" in current_url or 
                "progress" in current_url or
                "chkBirtDt" in page_content):
                logger.info("[AUTH] ✅ Ultra-fast login successful (fallback check)")
                return True
            return False

    except Exception as e:
        logger.error(f"[AUTH] ❌ Ultra-fast login error: {e}")
        return False
