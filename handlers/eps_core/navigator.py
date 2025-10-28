import re, time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .constants import SEL


def _try_select_row2(driver) -> str | None:
    try:
        old_tables = WebDriverWait(driver, 8).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, SEL["tables_purple"]))
        )
        old_detail_el = old_tables[1] if len(old_tables) >= 2 else None
    except Exception:
        old_detail_el = None

    try:
        t1 = WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, SEL["tables_purple"]))
        )
    except Exception:
        return None

    anchors = t1.find_elements(By.CSS_SELECTOR, SEL["row_anchor"])
    ref_id = None
    for a in anchors:
        if (a.text or "").strip() == "2":
            href = a.get_attribute("href") or ""
            m = re.search(r"fncDetailRow\('([^']+)'", href)
            if m:
                ref_id = m.group(1)
            break
    if not ref_id:
        return None

    try:
        driver.execute_script(f"return fncDetailRow('{ref_id}', '');")
    except Exception:
        for a in anchors:
            href = a.get_attribute("href") or ""
            if ref_id in href:
                a.click()
                break

    html_before = driver.page_source
    try:
        if old_detail_el:
            WebDriverWait(driver, 8).until(EC.staleness_of(old_detail_el))
        WebDriverWait(driver, 12).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, SEL["tables_purple"]))
        )
        WebDriverWait(driver, 4).until(lambda d: d.page_source != html_before)
    except Exception:
        time.sleep(0.6)
    return ref_id


def _switch_to_ref(driver, ref_id: str) -> bool:
    try:
        old_tables = WebDriverWait(driver, 8).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, SEL["tables_purple"]))
        )
        old_detail_el = old_tables[1] if len(old_tables) >= 2 else None
    except Exception:
        old_detail_el = None

    try:
        html_before = driver.page_source
        driver.execute_script(f"return fncDetailRow('{ref_id}', '');")
    except Exception:
        try:
            t1 = WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, SEL["tables_purple"]))
            )
            anchors = t1.find_elements(By.CSS_SELECTOR, SEL["row_anchor"])
            clicked = False
            for a in anchors:
                href = a.get_attribute("href") or ""
                if ref_id in href:
                    a.click()
                    clicked = True
                    break
            if not clicked:
                return False
            html_before = driver.page_source
        except Exception:
            return False

    try:
        if old_detail_el:
            WebDriverWait(driver, 8).until(EC.staleness_of(old_detail_el))
        WebDriverWait(driver, 12).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, SEL["tables_purple"]))
        )
        WebDriverWait(driver, 4).until(lambda d: d.page_source != html_before)
    except Exception:
        import time as _t

        _t.sleep(0.6)
    return True
