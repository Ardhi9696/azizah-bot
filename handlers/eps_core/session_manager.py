# handlers/eps_core/session_manager.py
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
from selenium.webdriver.support import expected_conditions as EC  # type: ignore
from selenium.webdriver.common.by import By  # type: ignore
from selenium.webdriver.support.ui import WebDriverWait  # type: ignore

from .driver import setup_driver
from .auth import login_with, verifikasi_tanggal_lahir
from .constants import LOGIN_URL, PROGRESS_URL

logger = logging.getLogger(__name__)

# ===== Konfigurasi =====
DEFAULT_TTL_SEC = 70 * 60  # ~55 menit (cookie EPS biasanya ~1 jam)
WAIT_SHORT = 2
WAIT_MED = 6
WAIT_LONG = 8


@dataclass
class _Session:
    driver: "selenium.webdriver.Chrome"
    created_monotonic: float
    last_used_monotonic: float
    last_login_monotonic: float  # DISET HANYA setelah login flow sukses


# registry sesi in-memory: user_key -> _Session
_SESS: Dict[str, _Session] = {}


# ===== Util: Alert & Page Source aman =====
def _accept_login_alert_if_any(driver, timeout: int = 2) -> bool:
    try:
        WebDriverWait(driver, timeout).until(EC.alert_is_present())
        try:
            a = driver.switch_to.alert
            _ = (a.text or "").strip()  # bisa dipakai untuk debug kalau mau
            a.accept()
            return True
        except NoAlertPresentException:
            return False
    except Exception:
        return False


def _safe_page_source(driver) -> str:
    try:
        return driver.page_source or ""
    except UnexpectedAlertPresentException:
        _accept_login_alert_if_any(driver, timeout=1)
        time.sleep(0.15)  # cooldown kecil agar driver stabil
        try:
            return driver.page_source or ""
        except Exception:
            return ""
    except Exception:
        return ""


# ===== Util: Driver =====
def _create_driver_for(profile_name: Optional[str] = None):
    drv = setup_driver(profile_name=profile_name or "default")
    logger.info(
        "[DRIVER] Chrome WebDriver started for profile: %s", profile_name or "default"
    )
    return drv


def _close_driver(user_key: str):
    sess = _SESS.pop(user_key, None)
    if not sess:
        return
    try:
        sess.driver.quit()
    except Exception:
        pass


# ===== Util: Deteksi “siap di halaman progress” cepat =====
def _is_progress_ready(driver) -> bool:
    try:
        WebDriverWait(driver, 1).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.tbl_typeA.center"))
        )
        return True
    except Exception:
        return False


def _goto_progress_and_wait(driver) -> None:
    if _is_progress_ready(driver):
        return
    driver.get(PROGRESS_URL)
    _accept_login_alert_if_any(driver, timeout=1)
    try:
        WebDriverWait(driver, WAIT_LONG).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.tbl_typeA.center"))
        )
    except Exception:
        # best-effort
        pass


# ===== Login flow =====
def _do_login_flow(driver, username: str, password: str, birthday: str) -> bool:
    driver.get(LOGIN_URL)
    if not login_with(driver, username, password):
        return False
    if not verifikasi_tanggal_lahir(driver, birthday):
        return False
    return True


# ===== Inti: memastikan sesi valid =====
def ensure_session(
    driver,
    username: str,
    password: str,
    birthday: str,
    relogin_if_needed: bool = True,
    logger_: Optional[logging.Logger] = None,
) -> bool:
    log = logger_.info if logger_ else logger.info

    # --- FAST PATH: kalau sudah di progress & login masih valid, jangan navigate ---
    try:
        cur = driver.current_url or ""
    except Exception:
        cur = ""
    if PROGRESS_URL in cur:
        page0 = _safe_page_source(driver)
        if page0 and ("Please Login" not in page0) and ("birthChk" not in page0):
            return True  # sudah oke, langsung pakai

    # Cek halaman progress sekali
    driver.get(PROGRESS_URL)
    had_alert = _accept_login_alert_if_any(driver, timeout=1)
    page = _safe_page_source(driver)
    need_login = had_alert or ("Please Login" in page) or ("birthChk" in page)

    if not need_login:
        # sudah siap
        return True

    if not relogin_if_needed:
        log("[SESSION] Perlu login tapi relogin_if_needed=False → gagal.")
        return False

    log("[SESSION] Need login → performing login flow...")
    if not _do_login_flow(driver, username, password, birthday):
        log("[SESSION] Login/verifikasi gagal.")
        return False

    _goto_progress_and_wait(driver)
    ps = _safe_page_source(driver)
    if not ps or ("Please Login" in ps):
        log("[SESSION] Masih terlempar ke login → sesi tidak siap.")
        return False

    return True


# ===== API Publik =====
def with_session(
    user_key: str,
    username: str,
    password: str,
    birthday: str,
    fn: Callable[[Any], Any],  # fn(driver) -> result
    ttl_sec: Optional[int] = None,
    auto_cleanup: bool = False,
    logger_: Optional[logging.Logger] = None,
):
    ttl = int(ttl_sec if ttl_sec is not None else DEFAULT_TTL_SEC)
    now = time.monotonic()
    logi = (logger_ or logger).info
    logw = (logger_ or logger).warning

    if auto_cleanup:
        cleanup_idle(ttl_sec=ttl, logger_=logger_)

    sess = _SESS.get(user_key)

    # 1) buat driver bila belum ada
    if not sess:
        drv = _create_driver_for(profile_name=user_key)
        sess = _Session(
            driver=drv,
            created_monotonic=now,
            last_used_monotonic=now,
            last_login_monotonic=0.0,
        )
        _SESS[user_key] = sess
        logi("[SESSION] New webdriver created for key=%s", user_key)

    drv = sess.driver

    # 2) Force relogin bila TTL lewat (berdasarkan usia LOGIN, bukan pemakaian)
    # 2) TTL check: cukup catat, biar ensure_session() yang tentukan perlu login
    ttl_expired = (
        (now - sess.last_login_monotonic) > ttl if sess.last_login_monotonic else True
    )

    try:
        if ttl_expired:
            logi("[SESSION] TTL lewat → akan soft-check via ensure_session()")
            if not _do_login_flow(drv, username, password, birthday):
                # reset & retry satu kali
                _close_driver(user_key)
                drv = _create_driver_for(profile_name=user_key)
                _SESS[user_key] = _Session(
                    driver=drv,
                    created_monotonic=now,
                    last_used_monotonic=now,
                    last_login_monotonic=0.0,
                )
                if not _do_login_flow(drv, username, password, birthday):
                    raise RuntimeError("Gagal relogin setelah TTL.")
            _goto_progress_and_wait(drv)
            _SESS[user_key].last_login_monotonic = time.monotonic()
        else:
            # jalur cepat: biarkan ensure_session memutuskan apakah perlu login
            ok = ensure_session(
                drv,
                username=username,
                password=password,
                birthday=birthday,
                relogin_if_needed=True,
                logger_=logger_,
            )
            if not ok:
                logw("[SESSION] ensure_session gagal → hard reset driver & retry")
                _close_driver(user_key)
                drv = _create_driver_for(profile_name=user_key)
                _SESS[user_key] = _Session(
                    driver=drv,
                    created_monotonic=now,
                    last_used_monotonic=now,
                    last_login_monotonic=0.0,
                )
                ok2 = ensure_session(
                    drv,
                    username=username,
                    password=password,
                    birthday=birthday,
                    relogin_if_needed=True,
                    logger_=logger_,
                )
                if not ok2:
                    raise RuntimeError("Gagal memastikan sesi EPS (login/verifikasi).")
            else:
                # berhasil TANPA login baru → jangan update last_login_monotonic
                pass

    except WebDriverException as e:
        logw("[SESSION] WebDriverException → hard reset: %s", e)
        _close_driver(user_key)
        drv = _create_driver_for(profile_name=user_key)
        _SESS[user_key] = _Session(
            driver=drv,
            created_monotonic=now,
            last_used_monotonic=now,
            last_login_monotonic=0.0,
        )
        if not ensure_session(
            drv,
            username=username,
            password=password,
            birthday=birthday,
            relogin_if_needed=True,
            logger_=logger_,
        ):
            raise RuntimeError("Gagal memastikan sesi EPS (login/verifikasi).")

    # 3) Jalankan fungsi scraping
    try:
        result = fn(drv)
        _SESS[user_key].last_used_monotonic = time.monotonic()
        return result
    except UnexpectedAlertPresentException:
        _accept_login_alert_if_any(drv, timeout=1)
        if not ensure_session(
            drv,
            username=username,
            password=password,
            birthday=birthday,
            relogin_if_needed=True,
            logger_=logger_,
        ):
            raise RuntimeError("Sesi terputus saat scraping & gagal relogin.")
        result = fn(drv)
        _SESS[user_key].last_used_monotonic = time.monotonic()
        return result


# ===== Opsional: Cleanup =====
def cleanup_idle(
    ttl_sec: int = DEFAULT_TTL_SEC,
    logger_: Optional[logging.Logger] = None,
) -> int:
    now = time.monotonic()
    to_close = [k for k, s in _SESS.items() if (now - s.last_used_monotonic) > ttl_sec]
    for k in to_close:
        try:
            _close_driver(k)
        except Exception:
            pass
    if to_close:
        (logger_ or logger).info(
            "[SESSION] Cleanup: menutup %d sesi idle: %s",
            len(to_close),
            ", ".join(to_close),
        )
    return len(to_close)


def close_all():
    for k in list(_SESS.keys()):
        _close_driver(k)
