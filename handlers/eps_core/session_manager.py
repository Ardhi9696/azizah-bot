# handlers/eps_core/session_manager.py

from __future__ import annotations

import time
import asyncio
import logging
from dataclasses import dataclass
from typing import Callable, Optional, Dict, Any, Tuple

from playwright.async_api import Page, Browser, BrowserContext, Error
from .browser import setup_browser, close_browser_stack, safe_goto, wait_for_selectors
from .auth import login_with, verifikasi_tanggal_lahir, normalize_birthday
from .constants import LOGIN_URL, PROGRESS_URL

logger = logging.getLogger(__name__)

# ===== OPTIMIZED CONFIGURATION =====
DEFAULT_TTL_SEC = 30 * 60  # 30 menit
WAIT_SHORT = 2  # Reduced from 5
WAIT_MED = 5  # Reduced from 10
WAIT_LONG = 10  # Reduced from 20
MAX_RETRIES = 2  # Reduced from 3


@dataclass
class _Session:
    page: Page
    context: BrowserContext
    browser: Browser
    created_monotonic: float
    last_used_monotonic: float
    last_login_monotonic: float
    is_authenticated: bool = False


_SESS: Dict[str, _Session] = {}


async def _quick_alert_check(page: Page) -> bool:
    """Quick alert check dengan Playwright"""
    try:
        # Playwright handle alerts secara otomatis, tapi kita cek jika ada
        page.on("dialog", lambda dialog: dialog.accept())
        return True
    except Exception:
        return False


async def _fast_page_check(page: Page) -> str:
    """Fast page content check"""
    try:
        return await page.content()
    except Exception:
        return ""


async def _is_page_ready_fast(page: Page) -> bool:
    """Fast page readiness check dengan Playwright"""
    try:
        await page.wait_for_function("document.readyState === 'complete'", timeout=3000)
        return True
    except Exception:
        return False


async def _fast_navigation(page: Page, url: str) -> bool:
    """Fast navigation dengan timeout pendek"""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=10000)

        # Quick page ready check
        await _is_page_ready_fast(page)

        return True

    except Error as e:
        logger.warning(f"Navigation timeout/warning to {url}: {e}")
        return True  # Continue anyway
    except Exception as e:
        logger.warning(f"Navigation error: {e}")
        return False


async def _quick_login_flow(
    page: Page, username: str, password: str, birthday: str
) -> bool:
    """Fast login flow dengan Playwright"""
    try:
        logger.info(f"[SESSION] Quick login for {username}")

        # Step 1: Navigate to login (fast)
        if not await _fast_navigation(page, LOGIN_URL):
            return False

        await asyncio.sleep(WAIT_SHORT)

        # Step 2: Login
        if not await login_with(page, username, password):
            return False

        await asyncio.sleep(WAIT_SHORT)

        # Step 3: Birthday verification
        if not await verifikasi_tanggal_lahir(page, birthday):
            return False

        logger.info("[SESSION] Quick login completed")
        return True

    except Exception as e:
        logger.error(f"[SESSION] Quick login error: {e}")
        return False


async def _quick_session_check(
    page: Page, username: str, password: str, birthday: str
) -> bool:
    """Quick session validation dengan Playwright"""
    try:
        # Coba navigasi cepat ke progress
        if not await _fast_navigation(page, PROGRESS_URL):
            return False

        # Cek cepat apakah perlu login
        page_content = await _fast_page_check(page)
        need_login = "Please Login" in page_content or "birthChk" in page_content

        if not need_login:
            return True

        # Quick login jika diperlukan
        return await _quick_login_flow(page, username, password, birthday)

    except Exception as e:
        logger.warning(f"[SESSION] Quick check warning: {e}")
        return False


# handlers/eps_core/session_manager.py - PERBAIKI ensure_session_fast


# handlers/eps_core/session_manager.py - TAMBAH DEBUG LOGGING


async def ensure_session_fast(
    page: Page,
    username: str,
    password: str,
    birthday: str,
    force_login: bool = False,
    logger_=None,
) -> bool:
    """Fast session ensure dengan comprehensive debugging"""
    log = logger_ or logger

    for attempt in range(MAX_RETRIES):
        try:
            log.info(f"[SESSION] Fast ensure attempt {attempt + 1}")

            # DEBUG: Log page state sebelum navigation
            log.debug(f"[SESSION] Page state - closed: {page.is_closed()}")

            # Quick navigation first
            nav_success = await _fast_navigation(page, PROGRESS_URL)
            log.debug(f"[SESSION] Navigation success: {nav_success}")

            if not nav_success:
                if force_login:
                    login_result = await _quick_login_flow(
                        page, username, password, birthday
                    )
                    log.debug(f"[SESSION] Login result: {login_result}")
                    return login_result
                return False

            # Quick page check
            try:
                page_content = await page.content()
                need_login = (
                    force_login
                    or "Please Login" in page_content
                    or "birthChk" in page_content
                )
                log.debug(f"[SESSION] Need login: {need_login}")

                if not need_login:
                    log.info("[SESSION] Session valid (fast check)")
                    return True
            except Exception as e:
                log.warning(f"[SESSION] Page content check failed: {e}")
                need_login = True

            # Quick login
            login_result = await _quick_login_flow(page, username, password, birthday)
            log.debug(f"[SESSION] Quick login result: {login_result}")

            if login_result:
                log.info("[SESSION] Quick login successful")
                return True

            log.warning(f"[SESSION] Fast attempt {attempt + 1} failed")

        except Exception as e:
            log.error(f"[SESSION] Fast ensure error: {e}")
            log.debug(f"[SESSION] Page closed after error: {page.is_closed()}")

        if attempt < MAX_RETRIES - 1:
            log.debug(f"[SESSION] Waiting {WAIT_SHORT}s before retry...")
            await asyncio.sleep(WAIT_SHORT)

    return False


# Di session_manager.py - pastikan cleanup logic bekerja dengan baik


async def cleanup_old_sessions(age_seconds: int = 3600, logger_=None) -> int:
    """Cleanup sessions yang lebih tua dari age_seconds"""
    log = logger_ or logger
    now = time.monotonic()
    to_close = []

    for key, sess in _SESS.items():
        session_age = now - sess.created_monotonic
        if session_age > age_seconds:
            to_close.append(key)
            log.info(
                f"[SESSION] Session {key} age {session_age:.1f}s > {age_seconds}s, scheduling cleanup"
            )

    for key in to_close:
        await _close_browser_fast(key)

    if to_close:
        log.info(
            f"[SESSION] Cleaned up {len(to_close)} old sessions (> {age_seconds}s)"
        )

    return len(to_close)


async def cleanup_idle_fast(ttl_sec: int = DEFAULT_TTL_SEC, logger_=None) -> int:
    """Fast cleanup sessions yang idle"""
    log = logger_ or logger
    now = time.monotonic()
    to_close = [k for k, s in _SESS.items() if (now - s.last_used_monotonic) > ttl_sec]

    for k in to_close:
        await _close_browser_fast(k)

    if to_close:
        log.info(f"[SESSION] Fast cleaned {len(to_close)} idle sessions")

    return len(to_close)


async def _close_browser_fast(user_key: str):
    """Fast browser close dengan Playwright"""
    sess = _SESS.pop(user_key, None)
    if not sess:
        return

    try:
        await close_browser_stack(sess.browser)
        logger.info(f"[SESSION] Closed browser for {user_key}")
    except Exception as e:
        logger.debug(f"[SESSION] Error closing browser: {e}")


# handlers/eps_core/session_manager.py - PERBAIKI with_session_fast


async def with_session_fast(
    user_key: str,
    username: str,
    password: str,
    birthday: str,
    fn: Callable[[Page], Any],
    ttl_sec: Optional[int] = None,
    auto_cleanup: bool = True,
    logger_=None,
):
    """Optimized session handler dengan Playwright - FIXED"""
    ttl = ttl_sec or DEFAULT_TTL_SEC
    now = time.monotonic()
    log = logger_ or logger

    # Cleanup sessions
    await cleanup_idle_fast(ttl_sec=3600, logger_=logger_)
    await cleanup_old_sessions(age_seconds=3600, logger_=logger_)

    # Get or create session - DENGAN VALIDATION
    sess = _SESS.get(user_key)

    # Validasi session sebelum digunakan
    if sess and await _is_session_valid(sess):
        log.info(f"[SESSION] Using existing session for {user_key}")
    else:
        # Session tidak valid, buat baru
        if sess:
            log.warning(
                f"[SESSION] Existing session invalid, creating new one for {user_key}"
            )
            await _close_browser_fast(user_key)

        try:
            from .browser import setup_browser

            browser, context, page = await setup_browser(profile_name=user_key)
            sess = _Session(
                page=page,
                context=context,
                browser=browser,
                created_monotonic=now,
                last_used_monotonic=now,
                last_login_monotonic=0.0,
                is_authenticated=False,
            )
            _SESS[user_key] = sess
            log.info(f"[SESSION] New session created for {user_key}")
        except Exception as e:
            log.error(f"[SESSION] Creation failed: {e}")
            raise RuntimeError(f"Gagal membuat session: {e}")

    # Force login logic
    session_age = now - sess.created_monotonic
    ttl_expired = (
        (now - sess.last_login_monotonic) > ttl if sess.last_login_monotonic else True
    )
    force_login = ttl_expired or session_age > 2700 or not sess.is_authenticated

    log.info(
        f"[SESSION] TTL check: expired={ttl_expired}, session_age={session_age:.0f}s, authenticated={sess.is_authenticated}"
    )

    try:
        # Validasi session lagi sebelum ensure
        if not await _is_session_valid(sess):
            log.error("[SESSION] Session became invalid before ensure")
            await _close_browser_fast(user_key)
            raise RuntimeError("Session invalid")

        # Ensure session dengan force login jika perlu
        if await ensure_session_fast(
            sess.page, username, password, birthday, force_login, log
        ):
            _SESS[user_key].last_login_monotonic = time.monotonic()
            _SESS[user_key].is_authenticated = True
            _SESS[user_key].last_used_monotonic = time.monotonic()
            log.info("[SESSION] Session ensured")
        else:
            log.error("[SESSION] Ensure failed")
            await _close_browser_fast(user_key)
            raise RuntimeError("Gagal memastikan session")

        # Validasi session sebelum execute function
        if not await _is_session_valid(sess):
            log.error("[SESSION] Session became invalid before function execution")
            await _close_browser_fast(user_key)
            raise RuntimeError("Session invalid")

        # Execute function
        result = await fn(sess.page)
        _SESS[user_key].last_used_monotonic = time.monotonic()

        return result

    except Exception as e:
        log.error(f"[SESSION] Session error: {e}")
        await _close_browser_fast(user_key)
        raise


async def _is_session_valid(sess: _Session) -> bool:
    """Check if session is still valid"""
    try:
        if not sess or not sess.page or not sess.browser:
            return False

        # Check if browser is connected
        if not sess.browser.is_connected():
            return False

        # Check if page is not closed
        if sess.page.is_closed():
            return False

        return True

    except Exception:
        return False


async def with_session_async(
    user_key: str,
    username: str,
    password: str,
    birthday: str,
    fn: Callable[[Page], Any],
    ttl_sec: Optional[int] = None,
    auto_cleanup: bool = True,
    logger_=None,
):
    """Alias untuk with_session_fast dengan naming yang lebih jelas untuk async"""
    return await with_session_fast(
        user_key=user_key,
        username=username,
        password=password,
        birthday=birthday,
        fn=fn,
        ttl_sec=ttl_sec,
        auto_cleanup=auto_cleanup,
        logger_=logger_,
    )


# ===== COMPATIBILITY WRAPPERS =====
# Untuk memudahkan transisi dari sync ke async


def with_session_sync_wrapper(
    user_key: str,
    username: str,
    password: str,
    birthday: str,
    fn: Callable[[Page], Any],
    ttl_sec: Optional[int] = None,
    auto_cleanup: bool = True,
    logger_=None,
):
    """
    Sync wrapper untuk async function - HANYA untuk transitional period
    WARNING: Tidak disarankan untuk production use
    """
    import asyncio

    async def async_fn(page: Page):
        return fn(page)

    return asyncio.run(
        with_session_fast(
            user_key=user_key,
            username=username,
            password=password,
            birthday=birthday,
            fn=async_fn,
            ttl_sec=ttl_sec,
            auto_cleanup=auto_cleanup,
            logger_=logger_,
        )
    )


# ===== SESSION MANAGEMENT UTILITIES =====


async def close_all_sessions():
    """Close all sessions"""
    count = len(_SESS)
    for k in list(_SESS.keys()):
        await _close_browser_fast(k)
    logger.info(f"[SESSION] All {count} sessions closed")


async def get_session_stats() -> Dict[str, Any]:
    """Get session statistics untuk monitoring"""
    now = time.monotonic()
    stats = {
        "total_sessions": len(_SESS),
        "sessions": {},
        "summary": {"authenticated": 0, "idle_over_1h": 0, "old_over_2h": 0},
    }

    for key, sess in _SESS.items():
        age_seconds = now - sess.created_monotonic
        idle_seconds = now - sess.last_used_monotonic
        since_login_seconds = (
            now - sess.last_login_monotonic if sess.last_login_monotonic else None
        )

        stats["sessions"][key] = {
            "age_seconds": age_seconds,
            "idle_seconds": idle_seconds,
            "since_login_seconds": since_login_seconds,
            "authenticated": sess.is_authenticated,
        }

        # Update summary
        if sess.is_authenticated:
            stats["summary"]["authenticated"] += 1
        if idle_seconds > 3600:
            stats["summary"]["idle_over_1h"] += 1
        if age_seconds > 7200:
            stats["summary"]["old_over_2h"] += 1

    return stats


async def cleanup_idle_sessions(
    ttl_sec: int = DEFAULT_TTL_SEC, logger_=None
) -> Dict[str, Any]:
    """Cleanup idle sessions dan return report"""
    log = logger_ or logger

    before_stats = await get_session_stats()
    cleaned_count = await cleanup_idle_fast(ttl_sec, logger_)
    after_stats = await get_session_stats()

    report = {
        "cleaned_sessions": cleaned_count,
        "before": before_stats,
        "after": after_stats,
        "timestamp": time.time(),
    }

    log.info(f"[SESSION] Cleanup report: {cleaned_count} sessions cleaned")
    return report


async def force_cleanup_all():
    """Force cleanup semua sessions (emergency use)"""
    logger.warning("[SESSION] Force cleaning up ALL sessions")
    await close_all_sessions()


# ===== HEALTH CHECK FUNCTIONS =====


async def health_check_session(user_key: str) -> Dict[str, Any]:
    """Health check untuk session tertentu"""
    sess = _SESS.get(user_key)
    if not sess:
        return {"status": "not_found", "user_key": user_key}

    now = time.monotonic()

    try:
        # Coba navigasi ke halaman utama untuk test responsiveness
        await safe_goto(sess.page, "https://www.eps.go.kr", timeout=10000)

        health_info = {
            "status": "healthy",
            "user_key": user_key,
            "age_seconds": now - sess.created_monotonic,
            "idle_seconds": now - sess.last_used_monotonic,
            "authenticated": sess.is_authenticated,
            "page_url": sess.page.url,
            "responsive": True,
        }

        if sess.last_login_monotonic:
            health_info["since_login_seconds"] = now - sess.last_login_monotonic

    except Exception as e:
        health_info = {
            "status": "unhealthy",
            "user_key": user_key,
            "error": str(e),
            "responsive": False,
        }

    return health_info


async def health_check_all_sessions() -> Dict[str, Any]:
    """Health check untuk semua active sessions"""
    results = {}

    for user_key in list(_SESS.keys()):
        try:
            results[user_key] = await health_check_session(user_key)
        except Exception as e:
            results[user_key] = {
                "status": "error",
                "user_key": user_key,
                "error": str(e),
            }

    summary = {
        "total": len(results),
        "healthy": sum(1 for r in results.values() if r.get("status") == "healthy"),
        "unhealthy": sum(1 for r in results.values() if r.get("status") == "unhealthy"),
        "errors": sum(1 for r in results.values() if r.get("status") == "error"),
    }

    return {"summary": summary, "details": results, "timestamp": time.time()}


# ===== DEPRECATION NOTICES =====


def with_session(*args, **kwargs):
    """DEPRECATED: Sync version - use with_session_async instead"""
    logger.warning(
        "with_session() is deprecated. Use with_session_async() for async operations "
        "or with_session_sync_wrapper() for transitional period."
    )
    return with_session_sync_wrapper(*args, **kwargs)


def ensure_session(*args, **kwargs):
    """DEPRECATED: Sync version"""
    logger.warning(
        "ensure_session() is deprecated for Playwright. Use ensure_session_fast() instead."
    )
    raise NotImplementedError("Use async ensure_session_fast() with Playwright")


def cleanup_idle(*args, **kwargs):
    """DEPRECATED: Sync version"""
    logger.warning(
        "cleanup_idle() is deprecated for Playwright. Use cleanup_idle_fast() instead."
    )
    raise NotImplementedError("Use async cleanup_idle_fast() with Playwright")


# Export utama untuk public API
__all__ = [
    "with_session_fast",
    "with_session_async",
    "with_session_sync_wrapper",
    "ensure_session_fast",
    "cleanup_idle_fast",
    "cleanup_old_sessions",
    "close_all_sessions",
    "get_session_stats",
    "health_check_session",
    "health_check_all_sessions",
    "cleanup_idle_sessions",
    "force_cleanup_all",
]
