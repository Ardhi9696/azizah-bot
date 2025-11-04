from __future__ import annotations

import os
import logging
import platform
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

logger = logging.getLogger(__name__)


def _bool_env(name: str, default: bool) -> bool:
    raw = (os.getenv(name, "") or "").strip()
    if not raw:
        return default
    return raw not in {"0", "false", "False", "no", "NO"}


def _get_profiles_base_dir() -> str:
    return os.getenv("CHROME_USER_DIR", os.path.join(os.getcwd(), "chrome_profiles"))


def _get_user_agent() -> str:
    """Return appropriate user agent based on operating system"""
    system = platform.system().lower()
    
    if system == "windows":
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    elif system == "linux":
        return (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    else:  # macos or others
        return (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )


def setup_driver(profile_name: str | None = None) -> webdriver.Chrome:
    """
    Buat Chrome WebDriver dengan opsi yang dioptimalkan.
    """
    headless = _bool_env("HEADLESS", True)
    use_profile = _bool_env("PROFILE_PER_USER", True)

    options = Options()
    options.page_load_strategy = "eager"

    # Headless mode
    if headless:
        options.add_argument("--headless=new")

    # === STABILITY ARGUMENTS ===
    stability_args = [
        "--no-sandbox",
        "--disable-dev-shm-usage", 
        "--disable-gpu",
        f"--window-size=1366,768",
        "--disable-extensions",
        "--disable-default-apps",
        "--disable-notifications",
        "--disable-blink-features=AutomationControlled",
        "--disable-features=VizDisplayCompositor",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
    ]
    
    for arg in stability_args:
        options.add_argument(arg)

    # === LANGUAGE & CONTENT SETTINGS ===
    # Hanya gunakan satu setting language untuk EPS Korea
    options.add_argument("--lang=ko-KR")
    
    options.add_experimental_option(
        "prefs",
        {
            "profile.managed_default_content_settings.images": 2,
            "intl.accept_languages": "ko-KR,ko,en-US,en",
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_settings.popups": 0,
        },
    )

    # === USER AGENT ===
    user_agent = _get_user_agent()
    options.add_argument(f"--user-agent={user_agent}")
    logger.debug(f"Using User-Agent: {user_agent}")

    # === USER PROFILE MANAGEMENT ===
    prof_label = "default"
    if use_profile and profile_name:
        try:
            base = _get_profiles_base_dir()
            user_data_dir = os.path.join(base, profile_name)
            os.makedirs(user_data_dir, exist_ok=True)
            options.add_argument(f"--user-data-dir={user_data_dir}")
            prof_label = profile_name
            logger.info(f"Using profile directory: {user_data_dir}")
        except Exception as e:
            logger.warning(f"Failed to setup profile directory: {e}")

    # === CREATE DRIVER ===
    try:
        driver = webdriver.Chrome(options=options)
        logger.info(f"[DRIVER] Chrome WebDriver started for profile: {prof_label}")
    except Exception as e:
        logger.error(f"Failed to create ChromeDriver: {e}")
        raise

    # === RESOURCE BLOCKING ===
    try:
        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_cdp_cmd(
            "Network.setBlockedURLs",
            {
                "urls": [
                    "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp",
                    "*.css", "*.woff", "*.woff2", "*.ttf", "*.otf",
                    "*/analytics/*", "*doubleclick.net/*",
                    "*google-analytics.com/*", "*googlesyndication.com/*",
                ]
            },
        )
        logger.debug("Resource blocking enabled")
    except Exception as e:
        logger.debug(f"Resource blocking not available: {e}")

    return driver


# Alternative simple driver for testing
def setup_simple_driver() -> webdriver.Chrome:
    """
    Simple driver setup tanpa profile management untuk testing.
    """
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1366,768")
    options.add_argument("--disable-gpu")
    options.add_argument("--lang=ko-KR")
    
    options.add_experimental_option(
        "prefs", {
            "profile.managed_default_content_settings.images": 2,
            "intl.accept_languages": "ko-KR,ko,en-US,en",
        }
    )

    driver = webdriver.Chrome(options=options)
    logger.info("[DRIVER] Simple ChromeDriver started")
    
    return driver