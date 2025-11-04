import re
import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    UnexpectedAlertPresentException, 
    TimeoutException, 
    NoSuchElementException,
    ElementNotInteractableException
)
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


def login_with(driver, username: str, password: str) -> bool:
    """Optimized login function dengan timeout lebih pendek dan better error handling"""
    try:
        logger.info(f"[AUTH] Attempting login for user: {username}")
        
        # Navigate to login page dengan timeout pendek
        driver.set_page_load_timeout(10)
        driver.get(LOGIN_URL)
        
        # Wait for page elements dengan multiple fallbacks
        try:
            # Try primary element first
            username_field = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.ID, "sKorTestNo"))
            )
        except TimeoutException:
            # Fallback to other possible selectors
            try:
                username_field = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.NAME, "username")) |
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='username']")) |
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='text']"))
                )
            except TimeoutException:
                logger.error("[AUTH] Cannot find username field")
                return False
        
        # Clear and enter username
        try:
            username_field.clear()
            username_field.send_keys(username)
            logger.debug("[AUTH] Username entered")
        except ElementNotInteractableException:
            logger.error("[AUTH] Username field not interactable")
            return False
        
        # Find password field dengan fallbacks
        try:
            password_field = driver.find_element(By.ID, "sFnrwRecvNo")
        except NoSuchElementException:
            try:
                password_field = driver.find_element(By.NAME, "password")
            except NoSuchElementException:
                try:
                    password_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
                except NoSuchElementException:
                    logger.error("[AUTH] Cannot find password field")
                    return False
        
        # Enter password
        try:
            password_field.clear()
            password_field.send_keys(password)
            logger.debug("[AUTH] Password entered")
        except ElementNotInteractableException:
            logger.error("[AUTH] Password field not interactable")
            return False
        
        # Find and click login button dengan fallbacks
        try:
            login_btn = driver.find_element(By.CLASS_NAME, "btn_login")
        except NoSuchElementException:
            try:
                login_btn = driver.find_element(By.CSS_SELECTOR, "input[type='submit']")
            except NoSuchElementException:
                try:
                    login_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                except NoSuchElementException:
                    logger.error("[AUTH] Cannot find login button")
                    return False
        
        # Click login button
        try:
            login_btn.click()
            logger.debug("[AUTH] Login button clicked")
        except ElementNotInteractableException:
            logger.error("[AUTH] Login button not clickable")
            return False
        
        # Wait for login result dengan improved conditions
        try:
            WebDriverWait(driver, 8).until(
                lambda d: (
                    "langMain.eo" in d.current_url or
                    "birthChk" in (d.page_source or "") or
                    "main" in (d.current_url or "") or
                    EC.presence_of_element_located((By.ID, "chkBirtDt"))(d) or
                    "progress" in (d.current_url or "")
                )
            )
            logger.info("[AUTH] Login successful")
            return True
            
        except TimeoutException:
            # Check if we're already logged in (alternative success condition)
            current_url = driver.current_url or ""
            page_source = driver.page_source or ""
            
            if "langMain.eo" in current_url or "main" in current_url:
                logger.info("[AUTH] Login successful (alternative check)")
                return True
            elif "birthChk" in page_source:
                logger.info("[AUTH] Login successful, birthday verification needed")
                return True
            else:
                logger.error("[AUTH] Login timeout - unknown state")
                return False
                
    except UnexpectedAlertPresentException:
        try:
            alert = driver.switch_to.alert
            alert_text = alert.text
            alert.accept()
            logger.warning(f"[AUTH] Alert during login: {alert_text}")
            # Cek apakah alert adalah "login successful" dalam bentuk lain
            if "success" in alert_text.lower() or "selamat" in alert_text.lower():
                return True
            return False
        except Exception as alert_e:
            logger.error(f"[AUTH] Alert handling error: {alert_e}")
            return False
            
    except Exception as e:
        logger.error(f"[AUTH] Login unexpected error: {e}")
        return False


def verifikasi_tanggal_lahir(driver, birthday_str: str) -> bool:
    """Optimized birthday verification"""
    try:
        logger.info("[AUTH] Starting birthday verification")
        
        normalized_bday = normalize_birthday(birthday_str)
        
        # Wait for birthday field dengan multiple strategies
        try:
            bday_field = WebDriverWait(driver, 6).until(
                EC.element_to_be_clickable((By.ID, "chkBirtDt"))
            )
        except TimeoutException:
            # Check if we're already past birthday verification
            current_url = driver.current_url or ""
            page_source = driver.page_source or ""
            
            if "langMain.eo" in current_url or "main" in current_url:
                logger.info("[AUTH] Already past birthday verification")
                return True
            else:
                logger.error("[AUTH] Birthday field not found")
                return False
        
        # Enter birthday
        try:
            bday_field.clear()
            bday_field.send_keys(normalized_bday)
            logger.debug("[AUTH] Birthday entered")
        except ElementNotInteractableException:
            logger.error("[AUTH] Birthday field not interactable")
            return False
        
        # Find and click submit button dengan fallbacks
        try:
            submit_btn = driver.find_element(By.CSS_SELECTOR, "span.buttonE > button")
        except NoSuchElementException:
            try:
                submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            except NoSuchElementException:
                try:
                    submit_btn = driver.find_element(By.CSS_SELECTOR, "input[type='submit']")
                except NoSuchElementException:
                    logger.error("[AUTH] Cannot find birthday submit button")
                    return False
        
        # Click submit
        try:
            submit_btn.click()
            logger.debug("[AUTH] Birthday submit clicked")
        except ElementNotInteractableException:
            logger.error("[AUTH] Birthday submit button not clickable")
            return False
        
        # Wait for verification result
        try:
            WebDriverWait(driver, 8).until(
                lambda d: (
                    "langMain.eo" in d.current_url or
                    "main" in d.current_url or
                    "progress" in d.current_url or
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table.tbl_typeA"))(d)
                )
            )
            logger.info("[AUTH] Birthday verification successful")
            return True
            
        except TimeoutException:
            # Alternative success check
            current_url = driver.current_url or ""
            if "langMain.eo" in current_url or "main" in current_url:
                logger.info("[AUTH] Birthday verification successful (alternative check)")
                return True
            else:
                logger.error("[AUTH] Birthday verification timeout")
                return False
                
    except Exception as e:
        logger.error(f"[AUTH] Birthday verification error: {e}")
        return False


def quick_auth_check(driver) -> bool:
    """Quick check if already authenticated"""
    try:
        current_url = driver.current_url or ""
        page_source = driver.page_source or ""
        
        # Check various indicators of being logged in
        logged_in_indicators = [
            "langMain.eo" in current_url,
            "main" in current_url,
            "progress" in current_url,
            "tbl_typeA" in page_source,  # Progress table
            "logout" in page_source.lower(),
            "selamat" in page_source.lower()
        ]
        
        # Check indicators of needing login
        need_login_indicators = [
            "login" in current_url,
            "Please Login" in page_source,
            "birthChk" in page_source,
            "sKorTestNo" in page_source  # Login form
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