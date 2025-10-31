# handlers/eps_core/driver.py
from __future__ import annotations

import os
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

logger = logging.getLogger(__name__)


def _bool_env(name: str, default: bool) -> bool:
    raw = (os.getenv(name, "") or "").strip()
    if not raw:
        return default
    return raw not in {"0", "false", "False", "no", "NO"}


def _get_profiles_base_dir() -> str:
    # Boleh override lewat env biar fleksibel
    return os.getenv("CHROME_USER_DIR", os.path.join(os.getcwd(), "chrome_profiles"))


def setup_driver(profile_name: str | None = None) -> webdriver.Chrome:
    """
    Buat Chrome WebDriver dengan opsi:
      - Headless by default (HEADLESS=0 untuk non-headless)
      - page_load_strategy=eager
      - (opsional) user-data-dir per profile_name agar cookie/sesi bisa direuse
        * set PROFILE_PER_USER=0 untuk mematikan pemakaian profile
        * ubah base dir via CHROME_USER_DIR
    """
    headless = _bool_env("HEADLESS", True)
    use_profile = _bool_env("PROFILE_PER_USER", True)

    options = Options()
    options.page_load_strategy = "eager"

    if headless:
        # gunakan headless new agar lebih stabil
        options.add_argument("--headless=new")

    # Stabilitas & performa
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
    options.add_experimental_option(
        "prefs",
        {
            "profile.managed_default_content_settings.images": 2,
            "intl.accept_languages": "ko-KR,ko,en-US,en",  # halaman EPS Korea
        },
    )
    options.add_argument("--disable-extensions")
    options.add_argument("--lang=ko-KR")

    options.add_argument(
        "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    # User profile per akun (agar cookie bertahan antar-run)
    prof_label = "default"
    if use_profile and profile_name:
        base = _get_profiles_base_dir()
        user_data_dir = os.path.join(base, profile_name)
        os.makedirs(user_data_dir, exist_ok=True)
        options.add_argument(f"--user-data-dir={user_data_dir}")
        # Tidak wajib set --profile-directory kalau pakai user-data-dir custom
        prof_label = profile_name

    driver = webdriver.Chrome(options=options)
    logger.info("[DRIVER] Chrome WebDriver started for profile: %s", prof_label)

    # (Opsional) Blokir resource berat via CDP agar makin cepat.
    # Abaikan quietly jika tidak didukung.
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
