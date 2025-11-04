from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from typing import Callable, Optional, Dict, Any

import selenium
from selenium.common.exceptions import (
    UnexpectedAlertPresentException,
    NoAlertPresentException,
    WebDriverException,
    TimeoutException,
)
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from .driver import setup_driver
from .auth import login_with, verifikasi_tanggal_lahir
from .constants import LOGIN_URL, PROGRESS_URL

logger = logging.getLogger(__name__)

# ===== OPTIMIZED CONFIGURATION =====
DEFAULT_TTL_SEC = 30 * 60  # 30 menit saja
WAIT_SHORT = 2  # Reduced from 5
WAIT_MED = 5  # Reduced from 10
WAIT_LONG = 10  # Reduced from 20
MAX_RETRIES = 2  # Reduced from 3


# Tambahkan function untuk force cleanup
def cleanup_old_sessions(age_seconds: int = 3600, logger_=None) -> int:
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
        _close_driver_fast(key)

    if to_close:
        log.info(
            f"[SESSION] Cleaned up {len(to_close)} old sessions (> {age_seconds}s)"
        )

    return len(to_close)


@dataclass
class _Session:
    driver: "selenium.webdriver.Chrome"
    created_monotonic: float
    last_used_monotonic: float
    last_login_monotonic: float
    is_authenticated: bool = False  # Track auth status


_SESS: Dict[str, _Session] = {}


def _quick_alert_check(driver) -> bool:
    """Quick alert check tanpa wait panjang"""
    try:
        alert = driver.switch_to.alert
        alert_text = alert.text
        alert.accept()
        logger.debug(f"Quick alert accepted: {alert_text}")
        return True
    except NoAlertPresentException:
        return False
    except Exception:
        return False


def _fast_page_check(driver) -> str:
    """Fast page source check"""
    try:
        return driver.page_source or ""
    except Exception:
        return ""


def _create_driver_fast(profile_name: Optional[str] = None):
    """Fast driver creation"""
    try:
        drv = setup_driver(profile_name=profile_name or "default")
        # Set timeouts lebih pendek
        drv.set_page_load_timeout(15)
        drv.implicitly_wait(5)
        logger.info(f"[DRIVER] Fast driver created for: {profile_name or 'default'}")
        return drv
    except Exception as e:
        logger.error(f"[DRIVER] Fast creation failed: {e}")
        raise


def _is_page_ready_fast(driver) -> bool:
    """Fast page readiness check"""
    try:
        # Cuma tunggu 3 detik maksimal
        WebDriverWait(driver, 3).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        return True
    except Exception:
        return False


def _fast_navigation(driver, url: str) -> bool:
    """Fast navigation dengan timeout pendek"""
    try:
        driver.set_page_load_timeout(10)  # Timeout pendek
        driver.get(url)

        # Quick alert check
        _quick_alert_check(driver)

        # Fast page ready check
        return _is_page_ready_fast(driver)

    except TimeoutException:
        logger.warning(f"Navigation timeout to {url}, but continuing...")
        return True  # Continue anyway
    except Exception as e:
        logger.warning(f"Navigation warning: {e}")
        return False


def _quick_login_flow(driver, username: str, password: str, birthday: str) -> bool:
    """Fast login flow"""
    try:
        logger.info(f"[SESSION] Quick login for {username}")

        # Step 1: Navigate to login (fast)
        if not _fast_navigation(driver, LOGIN_URL):
            return False

        time.sleep(WAIT_SHORT)

        # Step 2: Login
        if not login_with(driver, username, password):
            return False

        time.sleep(WAIT_SHORT)

        # Step 3: Birthday verification
        if not verifikasi_tanggal_lahir(driver, birthday):
            return False

        logger.info("[SESSION] Quick login completed")
        return True

    except Exception as e:
        logger.error(f"[SESSION] Quick login error: {e}")
        return False


def _quick_session_check(driver, username: str, password: str, birthday: str) -> bool:
    """Quick session validation tanpa proses panjang"""
    try:
        # Coba navigasi cepat ke progress
        if not _fast_navigation(driver, PROGRESS_URL):
            return False

        # Cek cepat apakah perlu login
        page = _fast_page_check(driver)
        need_login = "Please Login" in page or "birthChk" in page

        if not need_login:
            return True

        # Quick login jika diperlukan
        return _quick_login_flow(driver, username, password, birthday)

    except Exception as e:
        logger.warning(f"[SESSION] Quick check warning: {e}")
        return False


def ensure_session_fast(
    driver,
    username: str,
    password: str,
    birthday: str,
    force_login: bool = False,
    logger_=None,
) -> bool:
    """Fast session ensure dengan minimal waiting"""
    log = logger_ or logger

    for attempt in range(MAX_RETRIES):
        try:
            log.info(f"[SESSION] Fast ensure attempt {attempt + 1}")

            # Quick navigation first
            if not _fast_navigation(driver, PROGRESS_URL):
                if force_login:
                    return _quick_login_flow(driver, username, password, birthday)
                return False

            # Quick page check
            page = _fast_page_check(driver)
            need_login = force_login or "Please Login" in page or "birthChk" in page

            if not need_login:
                log.info("[SESSION] Session valid (fast check)")
                return True

            # Quick login
            if _quick_login_flow(driver, username, password, birthday):
                log.info("[SESSION] Quick login successful")
                return True

            log.warning(f"[SESSION] Fast attempt {attempt + 1} failed")

        except Exception as e:
            log.error(f"[SESSION] Fast ensure error: {e}")

        if attempt < MAX_RETRIES - 1:
            time.sleep(WAIT_SHORT)

    return False


# Update with_session_fast untuk auto cleanup yang lebih aggressive
def with_session_fast(
    user_key: str,
    username: str,
    password: str,
    birthday: str,
    fn: Callable[[Any], Any],
    ttl_sec: Optional[int] = None,
    auto_cleanup: bool = True,  # Default True sekarang
    logger_=None,
):
    """Optimized session handler dengan auto cleanup"""
    ttl = ttl_sec or DEFAULT_TTL_SEC
    now = time.monotonic()
    log = logger_ or logger

    # 🚀 SELALU cleanup sessions yang idle > 1 jam
    cleanup_idle_fast(ttl_sec=3600, logger_=logger_)

    # Juga cleanup sessions yang terlalu tua
    cleanup_old_sessions(age_seconds=3600, logger_=logger_)

    # Get or create session
    sess = _SESS.get(user_key)
    if not sess:
        try:
            from .driver import setup_driver

            driver = setup_driver(profile_name=user_key)
            sess = _Session(
                driver=driver,
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

    driver = sess.driver

    # 🚀 FORCE LOGIN JIKA SESSION SUDAH > 45 MENIT (lebih aggressive)
    session_age = now - sess.created_monotonic
    ttl_expired = (
        (now - sess.last_login_monotonic) > ttl if sess.last_login_monotonic else True
    )
    force_login = (
        ttl_expired or session_age > 2700 or not sess.is_authenticated
    )  # 45 menit

    log.info(
        f"[SESSION] TTL check: expired={ttl_expired}, session_age={session_age:.0f}s, authenticated={sess.is_authenticated}"
    )

    try:
        # Ensure session dengan force login jika perlu
        if ensure_session_fast(driver, username, password, birthday, force_login, log):
            _SESS[user_key].last_login_monotonic = time.monotonic()
            _SESS[user_key].is_authenticated = True
            _SESS[user_key].last_used_monotonic = time.monotonic()
            log.info("[SESSION] Session ensured")
        else:
            log.error("[SESSION] Ensure failed")
            # 🚀 CLEANUP FAILED SESSION
            _close_driver_fast(user_key)
            raise RuntimeError("Gagal memastikan session")

        # Execute function
        result = fn(driver)
        _SESS[user_key].last_used_monotonic = time.monotonic()

        return result

    except Exception as e:
        log.error(f"[SESSION] Session error: {e}")
        # 🚀 CLEANUP ON ERROR
        _close_driver_fast(user_key)
        raise


def cleanup_idle_fast(ttl_sec: int = DEFAULT_TTL_SEC, logger_=None) -> int:
    """Fast cleanup"""
    now = time.monotonic()
    to_close = [k for k, s in _SESS.items() if (now - s.last_used_monotonic) > ttl_sec]

    for k in to_close:
        _close_driver_fast(k)

    if to_close:
        (logger_ or logger).info(f"[SESSION] Fast cleaned {len(to_close)} sessions")

    return len(to_close)


def _close_driver_fast(user_key: str):
    """Fast driver close"""
    sess = _SESS.pop(user_key, None)
    if not sess:
        return

    try:
        sess.driver.quit()
    except:
        pass


# ===== COMPATIBILITY =====
# Keep original functions for backward compatibility
def with_session(
    user_key: str,
    username: str,
    password: str,
    birthday: str,
    fn: Callable[[Any], Any],
    ttl_sec: Optional[int] = None,
    auto_cleanup: bool = False,
    logger_=None,
):
    """Alias untuk fast version dengan parameter lengkap"""
    return with_session_fast(
        user_key=user_key,
        username=username,
        password=password,
        birthday=birthday,
        fn=fn,
        ttl_sec=ttl_sec,
        auto_cleanup=auto_cleanup,  # Pass the parameter
        logger_=logger_,
    )


def ensure_session(
    driver, username, password, birthday, relogin_if_needed=True, logger_=None
):
    """Alias untuk fast version"""
    return ensure_session_fast(
        driver, username, password, birthday, relogin_if_needed, logger_
    )


def cleanup_idle(ttl_sec: int = DEFAULT_TTL_SEC, logger_=None) -> int:
    """Alias untuk fast version"""
    return cleanup_idle_fast(ttl_sec, logger_)


def close_all():
    """Close all sessions"""
    count = len(_SESS)
    for k in list(_SESS.keys()):
        _close_driver_fast(k)
    logger.info(f"[SESSION] All {count} sessions closed")


def get_session_stats() -> Dict[str, Any]:
    """Get session statistics untuk monitoring"""
    now = time.monotonic()
    stats = {"total_sessions": len(_SESS), "sessions": {}}

    for key, sess in _SESS.items():
        stats["sessions"][key] = {
            "age_seconds": now - sess.created_monotonic,
            "idle_seconds": now - sess.last_used_monotonic,
            "since_login_seconds": (
                now - sess.last_login_monotonic if sess.last_login_monotonic else None
            ),
            "authenticated": sess.is_authenticated,
        }

    return stats
