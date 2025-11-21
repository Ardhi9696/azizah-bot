"""Core auth helpers: normalize birthday, login_with, and low-level helpers."""

import asyncio
import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional

from playwright.async_api import Error, Page, TimeoutError

from .constants import LOGIN_URL

logger = logging.getLogger(__name__)


def normalize_birthday(value: str) -> str:
    """Normalize birthday input."""
    try:
        digits = re.sub(r"\D", "", value or "")
        if len(digits) in (6, 8):  # DDMMYY / DDMMYYYY
            return digits
        logger.warning(f"Birthday format mungkin salah: {value}")
        return value
    except Exception as e:
        logger.error(f"Birthday normalization error: {e}")
        return value


async def _dump_debug(page: Page, label: str):
    """Simpan HTML & screenshot untuk investigasi."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    html_path = f"debug_page_content_{label}_{ts}.html"
    shot_path = f"debug_login_page_{label}_{ts}.png"
    try:
        content = await page.content()
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.debug(f"[AUTH] Page content saved: {html_path}")
    except Exception as e:
        logger.debug(f"[AUTH] Failed saving HTML {html_path}: {e}")
    try:
        await page.screenshot(path=shot_path)
        logger.debug(f"[AUTH] Screenshot saved: {shot_path}")
    except Exception as e:
        logger.debug(f"[AUTH] Failed saving screenshot {shot_path}: {e}")


async def login_with(page: Page, username: str, password: str) -> bool:
    """Fixed login function dengan comprehensive element finding."""
    try:
        logger.info(f"[AUTH] Attempting login for user: {username}")

        async def _find_selector_anywhere(selector: str, timeout: int = 3000):
            # Coba tunggu visible dulu
            try:
                el = await page.wait_for_selector(
                    selector, timeout=timeout, state="visible"
                )
                if el:
                    return el
            except Exception:
                # Fallback: cari tanpa syarat visible
                try:
                    el = await page.query_selector(selector)
                    if el:
                        return el
                except Exception:
                    pass

            # Try frames
            try:
                for f in page.frames:
                    try:
                        el = await f.wait_for_selector(
                            selector, timeout=timeout, state="visible"
                        )
                        if el:
                            return el
                    except Exception:
                        # Fallback: cari tanpa syarat visible di frame
                        try:
                            el = await f.query_selector(selector)
                            if el:
                                return el
                        except Exception:
                            continue
            except Exception:
                pass

            return None

        async def _fill_username_once() -> bool:
            eps_selectors = [
                "#sKorTestNo",
                "input[name='sKorTestNo']",
                "input[name='username']",
                "#username",
            ]

            for selector in eps_selectors:
                try:
                    logger.debug(f"[AUTH] Trying EPS selector: {selector}")
                    element = await _find_selector_anywhere(selector, timeout=7000)
                    if element:
                        await element.fill(username)
                        logger.info(
                            f"[AUTH] Username filled with EPS selector: {selector}"
                        )
                        return True
                except Exception as e:
                    logger.debug(f"[AUTH] EPS selector {selector} failed: {e}")
                    continue

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
                            is_visible = await element.is_visible()
                            is_enabled = await element.is_enabled()
                            if is_visible and is_enabled:
                                await element.fill(username)
                                logger.info(
                                    f"[AUTH] Username filled with generic selector: {selector}"
                                )
                                return True
                        except:
                            continue
                except Exception as e:
                    logger.debug(f"[AUTH] Generic selector {selector} failed: {e}")
                    continue

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
                                logger.info(
                                    f"[AUTH] Username filled with fallback (input #{i})"
                                )
                                return True
                    except:
                        continue
            except Exception as e:
                logger.debug(f"[AUTH] Fallback strategy failed: {e}")

            # STRATEGY 4: JS fill langsung (main frame + frames)
            script = """
            (value) => {
                const selectors = [
                    '#sKorTestNo',
                    'input[name="sKorTestNo"]',
                    'input[name="username"]',
                    '#username',
                    'input[type="text"]',
                    'input[type="number"]'
                ];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el && !el.disabled) {
                        el.value = value;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        return true;
                    }
                }
                return false;
            }
            """
            try:
                filled = await page.evaluate(script, username)
                if filled:
                    logger.info("[AUTH] Username filled via JS on main frame")
                    return True
            except Exception as e:
                logger.debug(f"[AUTH] JS fill main frame failed: {e}")

            for f in page.frames:
                try:
                    filled = await f.evaluate(script, username)
                    if filled:
                        logger.info("[AUTH] Username filled via JS on frame")
                        return True
                except Exception:
                    continue

            return False

        # Navigate
        await page.goto(LOGIN_URL, wait_until="load", timeout=30000)
        logger.debug("[AUTH] Navigation completed")
        await asyncio.sleep(1)

        # Cari form
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
            try:
                await page.reload(wait_until="domcontentloaded", timeout=10000)
                await asyncio.sleep(0.3)
                for form_selector in login_form_selectors:
                    try:
                        form = await page.query_selector(form_selector)
                        if form:
                            form_found = True
                            logger.info(
                                f"[AUTH] Login form found after reload: {form_selector}"
                            )
                            break
                    except:
                        continue
            except Exception as e:
                logger.debug(f"[AUTH] Reload-on-miss warning: {e}")

        username_filled = False
        for attempt in range(3):
            username_filled = await _fill_username_once()
            if username_filled:
                break
            if attempt == 0:
                logger.warning(
                    "[AUTH] Username field not found, reloading page and retrying once"
                )
                try:
                    await page.reload(wait_until="domcontentloaded", timeout=12000)
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.debug(f"[AUTH] Reload warning: {e}")
            elif attempt == 1:
                logger.warning(
                    "[AUTH] Username field still not found, navigating fresh to login page"
                )
                try:
                    await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=15000)
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.debug(f"[AUTH] Navigation retry warning: {e}")

        if not username_filled:
            logger.error("[AUTH] ❌ Cannot find username field after all strategies")
            await _dump_debug(page, "nouser")
            return False

        password_filled = await _fill_password_field(page, password)
        if not password_filled:
            logger.error("[AUTH] ❌ Cannot find password field")
            await _dump_debug(page, "nopass")
            return False

        login_clicked = await _click_login_button(page)
        if not login_clicked:
            logger.error("[AUTH] ❌ Cannot find login button")
            await _dump_debug(page, "nobutton")
            return False

        return await _wait_for_login_result(page)

    except Exception as e:
        logger.error(f"[AUTH] ❌ Login error: {e}")
        await _dump_debug(page, "error")
        return False


async def _fill_password_field(page: Page, password: str) -> bool:
    """Comprehensive password field filling."""
    password_selectors = [
        "#sFnrwRecvNo",
        "input[name='sFnrwRecvNo']",
        "input[type='password']",
        "input[name='password']",
        "#password",
    ]

    for selector in password_selectors:
        try:
            element = None
            try:
                element = await page.wait_for_selector(
                    selector, timeout=2000, state="visible"
                )
            except Exception:
                try:
                    for f in page.frames:
                        try:
                            element = await f.wait_for_selector(
                                selector, timeout=2000, state="visible"
                            )
                            if element:
                                break
                        except Exception:
                            continue
                except Exception:
                    element = None
            if element:
                await element.fill(password)
                logger.info(f"[AUTH] Password filled with selector: {selector}")
                return True
        except:
            continue

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
    """Comprehensive login button clicking."""
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

    try:
        el = await page.query_selector("[onclick*='fncLogin']")
    except Exception:
        el = None

    if el:
        try:
            await el.click()
            logger.info("[AUTH] Login clicked via onclick element")
            return True
        except Exception:
            try:
                await page.evaluate(
                    "() => { if (typeof fncLogin === 'function') fncLogin(); }"
                )
                logger.info("[AUTH] Login triggered via fncLogin() evaluate")
                return True
            except Exception:
                pass

    try:
        await page.evaluate(
            "() => { if (typeof fncLogin === 'function') fncLogin(); }"
        )
        logger.info("[AUTH] Login triggered via fncLogin() evaluate (last resort)")
        return True
    except Exception:
        pass

    return False


async def _wait_for_login_result(page: Page) -> bool:
    """Wait for login result dengan comprehensive checking."""
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


__all__ = [
    "normalize_birthday",
    "login_with",
    "_fill_password_field",
    "_click_login_button",
    "_wait_for_login_result",
]
