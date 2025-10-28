import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import UnexpectedAlertPresentException
from .constants import LOGIN_URL


def normalize_birthday(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    return digits if len(digits) in (6, 8) else value


def login_with(driver, username: str, password: str) -> bool:
    driver.get(LOGIN_URL)
    try:
        WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.ID, "sKorTestNo"))
        )
        driver.find_element(By.ID, "sKorTestNo").send_keys(username)
        driver.find_element(By.ID, "sFnrwRecvNo").send_keys(password)
        driver.find_element(By.CLASS_NAME, "btn_login").click()
        WebDriverWait(driver, 6).until(
            lambda d: ("langMain.eo" in d.current_url)
            or ("birthChk" in (d.page_source or ""))
        )
        return True
    except UnexpectedAlertPresentException:
        try:
            driver.switch_to.alert.accept()
        except Exception:
            pass
        return False
    except Exception:
        return False


def verifikasi_tanggal_lahir(driver, birthday_str: str) -> bool:
    try:
        WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.ID, "chkBirtDt"))
        )
        el = driver.find_element(By.ID, "chkBirtDt")
        el.clear()
        el.send_keys(birthday_str)
        driver.find_element(By.CSS_SELECTOR, "span.buttonE > button").click()
        WebDriverWait(driver, 8).until(EC.url_contains("langMain.eo"))
        return True
    except Exception:
        return False
