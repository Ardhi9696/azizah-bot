from __future__ import annotations

import os
import logging
import platform
import time
from typing import Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

logger = logging.getLogger(__name__)


class DriverConfig:
    """Configuration class untuk ChromeDriver settings"""
    
    # Default environment values
    HEADLESS_DEFAULT = True
    PROFILE_PER_USER_DEFAULT = True
    CHROME_USER_DIR_DEFAULT = os.path.join(os.getcwd(), "chrome_profiles")
    
    # Platform-specific configurations
    PLATFORM_CONFIGS = {
        "windows": {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "stability_args": [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-extensions",
                "--disable-plugins",
                "--disable-blink-features=AutomationControlled",
                "--disable-features=VizDisplayCompositor",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--memory-pressure-off",
                "--window-size=1366,768",
                "--lang=ko-KR",
                # === LOG SUPPRESSION ARGS ===
                "--log-level=3",  # FATAL only
                "--disable-logging",
                "--silent",
                "--disable-default-apps",
                "--disable-translate",
                "--disable-notifications",
                "--disable-ipc-flooding-protection",
            ],
            "page_load_timeout": 30,
            "implicit_wait": 10,
        },
        "darwin": {  # macOS
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "stability_args": [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-gpu-sandbox",
                "--disable-extensions",
                "--disable-plugins",
                "--disable-blink-features=AutomationControlled",
                "--window-size=1366,768",
                "--lang=ko-KR",
                # === LOG SUPPRESSION ARGS ===
                "--log-level=3",
                "--disable-logging", 
                "--silent",
                "--disable-default-apps",
                "--disable-translate",
            ],
            "page_load_timeout": 25,
            "implicit_wait": 8,
        },
        "linux": {
            "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "stability_args": [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-zygote",
                "--disable-extensions",
                "--disable-plugins",
                "--window-size=1366,768",
                "--lang=ko-KR",
                # === LOG SUPPRESSION ARGS ===
                "--log-level=3",
                "--disable-logging",
                "--silent",
                "--disable-default-apps",
            ],
            "page_load_timeout": 25,
            "implicit_wait": 8,
        }
    }
    
    # Resources to block for performance
    BLOCKED_RESOURCES = [
        "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp",
        "*.css", "*.woff", "*.woff2", "*.ttf", "*.otf",
        "*/analytics/*", "*doubleclick.net/*",
        "*google-analytics.com/*", "*googlesyndication.com/*",
    ]


class DriverFactory:
    """Factory class untuk membuat ChromeDriver instances"""
    
    def __init__(self, config: Optional[DriverConfig] = None):
        self.config = config or DriverConfig()
        self.system = platform.system().lower()
        self.platform_config = self._get_platform_config()
    
    def _get_platform_config(self):
        """Get configuration untuk current platform"""
        if self.system == "darwin":
            return self.config.PLATFORM_CONFIGS["darwin"]
        elif self.system == "windows":
            return self.config.PLATFORM_CONFIGS["windows"]
        else:
            return self.config.PLATFORM_CONFIGS["linux"]
    
    @staticmethod
    def _get_bool_env(name: str, default: bool) -> bool:
        """Parse boolean environment variable"""
        raw = (os.getenv(name, "") or "").strip().lower()
        if not raw:
            return default
        return raw not in {"0", "false", "no", "off"}
    
    @staticmethod
    def _get_str_env(name: str, default: str) -> str:
        """Parse string environment variable"""
        return os.getenv(name, default).strip()
    
    def _setup_chrome_options(self, profile_name: Optional[str] = None) -> Options:
        """Setup Chrome options dengan platform-specific settings dan log suppression"""
        options = Options()
        
        # Page load strategy - gunakan "normal" untuk stability
        options.page_load_strategy = "normal"
        
        # Headless mode
        if self._get_bool_env("HEADLESS", self.config.HEADLESS_DEFAULT):
            options.add_argument("--headless=new")
        
        # Platform-specific stability arguments + log suppression
        for arg in self.platform_config["stability_args"]:
            options.add_argument(arg)
        
        # User agent
        options.add_argument(f"--user-agent={self.platform_config['user_agent']}")
        
        # Experimental options untuk better compatibility dan log suppression
        options.add_experimental_option("excludeSwitches", [
            "enable-automation",
            "enable-logging",  # Suppress logging
            "disable-background-timer-throttling",
            "disable-backgrounding-occluded-windows"
        ])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Content settings dengan log suppression preferences
        options.add_experimental_option(
            "prefs", {
                "profile.managed_default_content_settings.images": 2,
                "intl.accept_languages": "ko-KR,ko,en-US,en",
                "profile.default_content_setting_values.notifications": 2,
                "profile.default_content_settings.popups": 0,
                "profile.default_content_setting_values.geolocation": 2,
                # Suppress Chrome logs
                "download.default_directory": os.path.join(os.getcwd(), 'downloads'),
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
            }
        )
        
        # User profile management
        self._setup_user_profile(options, profile_name)
        
        return options
    
    def _setup_user_profile(self, options: Options, profile_name: Optional[str]) -> None:
        """Setup user data directory untuk session persistence"""
        if not self._get_bool_env("PROFILE_PER_USER", self.config.PROFILE_PER_USER_DEFAULT):
            return
        
        if not profile_name:
            return
            
        base_dir = self._get_str_env("CHROME_USER_DIR", self.config.CHROME_USER_DIR_DEFAULT)
        user_data_dir = os.path.join(base_dir, profile_name)
        
        try:
            os.makedirs(user_data_dir, exist_ok=True)
            options.add_argument(f"--user-data-dir={user_data_dir}")
            logger.info(f"Using profile directory: {user_data_dir}")
        except OSError as e:
            logger.warning(f"Failed to create user data directory: {e}")
    
    def _block_resources(self, driver: webdriver.Chrome) -> None:
        """Block unnecessary resources untuk performance"""
        try:
            driver.execute_cdp_cmd("Network.enable", {})
            driver.execute_cdp_cmd(
                "Network.setBlockedURLs",
                {"urls": self.config.BLOCKED_RESOURCES}
            )
            logger.debug("Resource blocking enabled")
        except Exception as e:
            logger.debug(f"Resource blocking not available: {e}")
    
    def _create_chrome_service(self) -> Service:
        """Create Chrome service dengan platform-specific optimizations dan log suppression"""
        try:
            # Untuk Windows, gunakan CREATE_NO_WINDOW flag untuk stability
            if self.system == "windows":
                service = Service()
                # CREATE_NO_WINDOW flag (0x08000000) untuk background process
                import subprocess
                service.creationflags = subprocess.CREATE_NO_WINDOW
                
                # Suppress service logs
                service.creationflags |= 0x08000000  # Suppress output
                return service
            else:
                service = Service()
                # Untuk Unix systems, redirect output ke /dev/null
                import subprocess
                service.creationflags = subprocess.CREATE_NO_WINDOW
                return service
        except Exception:
            return Service()
    
    def create_driver(self, profile_name: Optional[str] = None) -> webdriver.Chrome:
        """
        Create and configure ChromeDriver instance dengan log suppression.
        
        Args:
            profile_name: Optional profile name untuk session persistence
            
        Returns:
            Configured Chrome WebDriver instance
        """
        max_retries = 2
        
        for attempt in range(max_retries):
            try:
                logger.info(f"🔄 Driver creation attempt {attempt + 1}/{max_retries}")
                
                # Setup Chrome options dengan log suppression
                options = self._setup_chrome_options(profile_name)
                
                # Create driver dengan suppressed logs
                if self.system == "windows":
                    # Untuk Windows, gunakan service dengan stability flags
                    service = self._create_chrome_service()
                    driver = webdriver.Chrome(service=service, options=options)
                else:
                    # Untuk macOS/Linux, langsung tanpa service (lebih sedikit logs)
                    driver = webdriver.Chrome(options=options)
                
                # Set platform-specific timeouts
                driver.set_page_load_timeout(self.platform_config["page_load_timeout"])
                driver.implicitly_wait(self.platform_config["implicit_wait"])
                
                # Block resources
                self._block_resources(driver)
                
                # Remove webdriver properties untuk stealth
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                
                # Log successful creation
                profile_label = profile_name or "default"
                logger.info(f"[DRIVER] ChromeDriver started on {self.system} for profile: {profile_label}")
                
                return driver
                
            except Exception as e:
                logger.warning(f"❌ Driver attempt {attempt + 1} failed: {e}")
                
                if attempt < max_retries - 1:
                    # Cleanup sebelum retry
                    self._cleanup_chrome_processes()
                    time.sleep(3)
                    continue
                else:
                    logger.error(f"💥 All driver creation attempts failed")
                    raise

    def _cleanup_chrome_processes(self):
        """Cleanup Chrome processes sebelum retry"""
        try:
            if self.system == "windows":
                import subprocess
                subprocess.run(["taskkill", "/f", "/im", "chrome.exe"], 
                              capture_output=True, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["taskkill", "/f", "/im", "chromedriver.exe"], 
                              capture_output=True, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                import subprocess
                subprocess.run(["pkill", "-f", "chrome"], capture_output=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["pkill", "-f", "chromedriver"], capture_output=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            time.sleep(2)
            logger.debug("Chrome processes cleanup completed")
        except Exception as e:
            logger.debug(f"Chrome processes cleanup failed: {e}")


# Tambahkan juga environment variable suppression di level yang lebih tinggi
import warnings
warnings.filterwarnings("ignore")
os.environ['WDM_LOG_LEVEL'] = '0'
os.environ['WDM_PRINT_FIRST_LINE'] = 'False'

# Suppress specific loggers
import logging
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('webdriver_manager').setLevel(logging.WARNING)
logging.getLogger('chromedriver').setLevel(logging.ERROR)


# Legacy functions untuk backward compatibility
def setup_driver(profile_name: Optional[str] = None) -> webdriver.Chrome:
    """
    Legacy function - creates Chrome WebDriver dengan optimized settings dan log suppression.
    
    Args:
        profile_name: Optional profile name untuk session persistence
        
    Returns:
        Configured Chrome WebDriver instance
    """
    factory = DriverFactory()
    return factory.create_driver(profile_name)


def setup_simple_driver() -> webdriver.Chrome:
    """
    Simple driver setup tanpa profile management untuk testing dengan log suppression.
    """
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1366,768")
    options.add_argument("--disable-gpu")
    options.add_argument("--lang=ko-KR")
    # Log suppression
    options.add_argument("--log-level=3")
    options.add_argument("--disable-logging")
    
    options.add_experimental_option(
        "prefs", {
            "profile.managed_default_content_settings.images": 2,
            "intl.accept_languages": "ko-KR,ko,en-US,en",
        }
    )

    driver = webdriver.Chrome(options=options)
    
    # Conservative timeouts untuk stability
    driver.set_page_load_timeout(20)
    driver.implicitly_wait(5)
    
    logger.info("[DRIVER] Simple ChromeDriver started")
    return driver


def setup_fast_driver() -> webdriver.Chrome:
    """
    Fast driver setup untuk emergency use cases dengan log suppression.
    """
    system = platform.system().lower()
    
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1200,800")
    options.add_argument("--disable-extensions")
    options.add_argument("--lang=ko-KR")
    # Log suppression
    options.add_argument("--log-level=3")
    options.add_argument("--silent")
    
    # Minimal content settings
    options.add_experimental_option(
        "prefs", {
            "profile.managed_default_content_settings.images": 2,
            "intl.accept_languages": "ko-KR,ko,en-US,en",
        }
    )

    driver = webdriver.Chrome(options=options)
    
    # Fast timeouts
    driver.set_page_load_timeout(15)
    driver.implicitly_wait(3)
    
    logger.info("⚡ Fast ChromeDriver started")
    return driver