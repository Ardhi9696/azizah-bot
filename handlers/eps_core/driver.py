# handlers/eps_core/driver.py
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def setup_driver() -> webdriver.Chrome:
    options = Options()
    options.page_load_strategy = "eager"
    if os.getenv("HEADLESS", "1") != "0":
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1366,768")
    options.add_argument("--disable-gpu")
    options.add_argument("--lang=id-ID,id;q=0.9")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--blink-settings=imagesEnabled=false")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=options)
    try:
        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_cdp_cmd(
            "Network.setBlockedURLs",
            {
                "urls": [
                    "*.png",
                    "*.jpg",
                    "*.jpeg",
                    "*.gif",
                    "*.webp",
                    "*.css",
                    "*.woff",
                    "*.woff2",
                    "*.ttf",
                    "*.otf",
                    "*/analytics/*",
                    "*doubleclick.net/*",
                ]
            },
        )
    except Exception:
        pass
    return driver
