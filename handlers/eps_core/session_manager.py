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
)
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from .driver import setup_driver
from .auth import login_with, verifikasi_tanggal_lahir
from .constants import LOGIN_URL, PROGRESS_URL

logger = logging.getLogger(__name__)

# ===== Konfigurasi =====
DEFAULT_TTL_SEC = 55 * 60  # 55 menit
WAIT_SHORT = 3
WAIT_MED = 8
WAIT_LONG = 12


@dataclass
class _Session:
    driver: "selenium.webdriver.Chrome"
    created_monotonic: float
    last_used_monotonic: float
    last_login_monotonic: float


_SESS: Dict[str, _Session] = {}


def _accept_login_alert_if_any(driver, timeout: int = 2) -> bool:
    """Handle alert dengan improved logic"""
    try:
        WebDriverWait(driver, timeout).until(EC.alert_is_present())
        try:
            alert = driver.switch_to.alert
            alert_text = alert.text or ""
            alert.accept()
            logger.debug(f"Alert accepted: {alert_text}")
            return True
        except NoAlertPresentException:
            return False
    except Exception as e:
        logger.debug(f"No alert present: {e}")
        return False


def _safe_page_source(driver) -> str:
    """Get page source dengan error handling"""
    try:
        return driver.page_source or ""
    except UnexpectedAlertPresentException:
        _accept_login_alert_if_any(driver, timeout=1)
        time.sleep(0.5)
        try:
            return driver.page_source or ""
        except Exception:
            return ""
    except Exception as e:
        logger.debug(f"Error getting page source: {e}")
        return ""


def _create_driver_for(profile_name: Optional[str] = None):
    """Create driver dengan error handling"""
    try:
        drv = setup_driver(profile_name=profile_name or "default")
        logger.info(f"[DRIVER] Chrome WebDriver started for profile: {profile_name or 'default'}")
        return drv
    except Exception as e:
        logger.error(f"[DRIVER] Failed to create driver: {e}")
        raise


def _close_driver(user_key: str):
    """Close driver dengan cleanup"""
    sess = _SESS.pop(user_key, None)
    if not sess:
        return
    try:
        sess.driver.quit()
        logger.debug(f"[SESSION] Driver closed for {user_key}")
    except Exception as e:
        logger.debug(f"[SESSION] Error closing driver: {e}")


def _is_progress_ready(driver) -> bool:
    """Check if progress page is ready"""
    try:
        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.tbl_typeA.center"))
        )
        return True
    except Exception:
        return False


def _goto_progress_and_wait(driver) -> bool:
    """Navigate to progress page dengan timeout handling"""
    try:
        if _is_progress_ready(driver):
            return True
            
        driver.get(PROGRESS_URL)
        _accept_login_alert_if_any(driver, timeout=2)
        
        WebDriverWait(driver, WAIT_LONG).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.tbl_typeA.center"))
        )
        return True
    except Exception as e:
        logger.warning(f"[SESSION] Failed to navigate to progress: {e}")
        return False


def _do_login_flow(driver, username: str, password: str, birthday: str) -> bool:
    """Execute complete login flow dengan improved error handling"""
    try:
        logger.info(f"[SESSION] Starting login flow for {username}")
        
        # Step 1: Navigate to login page
        driver.get(LOGIN_URL)
        time.sleep(WAIT_SHORT)
        
        # Step 2: Login
        if not login_with(driver, username, password):
            logger.error("[SESSION] Login failed")
            return False
        
        # Step 3: Birthday verification
        if not verifikasi_tanggal_lahir(driver, birthday):
            logger.error("[SESSION] Birthday verification failed")
            return False
            
        logger.info("[SESSION] Login flow completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"[SESSION] Login flow error: {e}")
        return False


def ensure_session(
    driver,
    username: str,
    password: str,
    birthday: str,
    relogin_if_needed: bool = True,
    logger_: Optional[logging.Logger] = None,
) -> bool:
    """Ensure valid session dengan simplified logic"""
    log = logger_ or logger
    max_retries = 2
    
    for attempt in range(max_retries):
        try:
            log.info(f"[SESSION] ensure_session attempt {attempt + 1}")
            
            # Navigate to progress page first
            if not _goto_progress_and_wait(driver):
                log.warning("[SESSION] Failed to navigate to progress page")
                if not relogin_if_needed:
                    return False
                continue
            
            # Check if login is required
            page = _safe_page_source(driver)
            need_login = ("Please Login" in page) or ("birthChk" in page)
            
            if not need_login:
                log.info("[SESSION] Session is valid")
                return True
                
            if not relogin_if_needed:
                log.warning("[SESSION] Login needed but relogin disabled")
                return False
            
            # Perform login
            log.info("[SESSION] Session expired, performing login...")
            if _do_login_flow(driver, username, password, birthday):
                # Verify login success
                if _goto_progress_and_wait(driver):
                    page_after = _safe_page_source(driver)
                    if "Please Login" not in page_after:
                        log.info("[SESSION] Login successful")
                        return True
            
            log.warning(f"[SESSION] Login attempt {attempt + 1} failed")
            if attempt < max_retries - 1:
                time.sleep(WAIT_MED)
                
        except Exception as e:
            log.error(f"[SESSION] ensure_session error: {e}")
            if attempt < max_retries - 1:
                time.sleep(WAIT_MED)
    
    return False


def with_session(
    user_key: str,
    username: str,
    password: str,
    birthday: str,
    fn: Callable[[Any], Any],
    ttl_sec: Optional[int] = None,
    auto_cleanup: bool = False,
    logger_: Optional[logging.Logger] = None,
):
    """Main session handler dengan simplified logic"""
    ttl = ttl_sec or DEFAULT_TTL_SEC
    now = time.monotonic()
    log = logger_ or logger
    
    if auto_cleanup:
        cleanup_idle(ttl_sec=ttl, logger_=logger_)

    # Get or create session
    sess = _SESS.get(user_key)
    if not sess:
        try:
            driver = _create_driver_for(profile_name=user_key)
            sess = _Session(
                driver=driver,
                created_monotonic=now,
                last_used_monotonic=now,
                last_login_monotonic=0.0,
            )
            _SESS[user_key] = sess
            log.info(f"[SESSION] New session created for {user_key}")
        except Exception as e:
            log.error(f"[SESSION] Failed to create session: {e}")
            raise RuntimeError(f"Gagal membuat session: {e}")

    driver = sess.driver
    
    # Check TTL and ensure session
    try:
        ttl_expired = (now - sess.last_login_monotonic) > ttl if sess.last_login_monotonic else True
        
        if ttl_expired:
            log.info(f"[SESSION] TTL expired, ensuring session...")
            if ensure_session(driver, username, password, birthday, True, log):
                # Update login time only on successful login
                _SESS[user_key].last_login_monotonic = time.monotonic()
                log.info("[SESSION] Session renewed successfully")
            else:
                log.error("[SESSION] Failed to ensure session after TTL")
                raise RuntimeError("Gagal memperbarui session setelah TTL")
        else:
            # Quick check without forced login
            if not ensure_session(driver, username, password, birthday, False, log):
                log.warning("[SESSION] Quick check failed, trying with login...")
                if ensure_session(driver, username, password, birthday, True, log):
                    _SESS[user_key].last_login_monotonic = time.monotonic()
                else:
                    raise RuntimeError("Gagal memastikan session")
        
        # Execute the function
        result = fn(driver)
        _SESS[user_key].last_used_monotonic = time.monotonic()
        
        return result
        
    except Exception as e:
        log.error(f"[SESSION] Error in with_session: {e}")
        # Cleanup on error
        _close_driver(user_key)
        raise


def cleanup_idle(ttl_sec: int = DEFAULT_TTL_SEC, logger_: Optional[logging.Logger] = None) -> int:
    """Cleanup idle sessions"""
    now = time.monotonic()
    to_close = [k for k, s in _SESS.items() if (now - s.last_used_monotonic) > ttl_sec]
    
    for k in to_close:
        _close_driver(k)
        
    if to_close:
        (logger_ or logger).info(f"[SESSION] Cleaned up {len(to_close)} idle sessions")
    
    return len(to_close)


def close_all():
    """Close all sessions"""
    for k in list(_SESS.keys()):
        _close_driver(k)
    logger.info("[SESSION] All sessions closed")