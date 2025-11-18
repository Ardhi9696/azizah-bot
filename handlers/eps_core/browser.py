# handlers/eps_core/browser.py

from __future__ import annotations

import os
import logging
import platform
import asyncio
from typing import Optional, Tuple
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)


class BrowserConfig:
    """Configuration class untuk Playwright browser settings"""

    # Default environment values
    HEADLESS_DEFAULT = True
    PROFILE_PER_USER_DEFAULT = False  # Nonaktifkan sementara, Playwright handle berbeda

    # Platform-specific configurations
    PLATFORM_CONFIGS = {
        "windows": {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "viewport": {"width": 1366, "height": 768},
            "launch_args": [
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
                "--lang=ko-KR",
                # Log suppression
                "--log-level=3",
                "--disable-logging",
                "--silent",
                "--disable-default-apps",
                "--disable-translate",
                "--disable-notifications",
            ],
            "timeouts": {
                "navigation": 30000,
                "default": 30000,
            },
        },
        "darwin": {  # macOS
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "viewport": {"width": 1366, "height": 768},
            "launch_args": [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-gpu-sandbox",
                "--disable-extensions",
                "--disable-plugins",
                "--disable-blink-features=AutomationControlled",
                "--lang=ko-KR",
                # Log suppression
                "--log-level=3",
                "--disable-logging",
                "--silent",
                "--disable-default-apps",
                "--disable-translate",
            ],
            "timeouts": {
                "navigation": 25000,
                "default": 25000,
            },
        },
        "linux": {
            "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "viewport": {"width": 1366, "height": 768},
            "launch_args": [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-zygote",
                "--disable-extensions",
                "--disable-plugins",
                "--lang=ko-KR",
                # Log suppression
                "--log-level=3",
                "--disable-logging",
                "--silent",
                "--disable-default-apps",
            ],
            "timeouts": {
                "navigation": 25000,
                "default": 25000,
            },
        },
    }

    # Resources to block for performance
    BLOCKED_RESOURCE_TYPES = [
        "image",
        "stylesheet",
        "font",
        "media",
    ]

    # Domains to block (analytics, ads, etc.)
    BLOCKED_DOMAINS = [
        "*google-analytics.com*",
        "*googlesyndication.com*",
        "*doubleclick.net*",
        "*facebook.com*",
        "*twitter.com*",
    ]


class BrowserFactory:
    """Factory class untuk membuat Playwright browser instances"""

    def __init__(self, config: Optional[BrowserConfig] = None):
        self.config = config or BrowserConfig()
        self.system = platform.system().lower()
        self.platform_config = self._get_platform_config()
        self._playwright = None

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

    async def _setup_playwright(self):
        """Setup playwright instance"""
        if not self._playwright:
            self._playwright = await async_playwright().start()
        return self._playwright

    async def _create_browser(self, profile_name: Optional[str] = None) -> Browser:
        """Create browser instance"""
        playwright = await self._setup_playwright()

        # Launch options - Playwright tidak butuh user_data_dir di sini
        launch_options = {
            "headless": self._get_bool_env("HEADLESS", self.config.HEADLESS_DEFAULT),
            "args": self.platform_config["launch_args"],
        }

        # Launch browser
        browser = await playwright.chromium.launch(**launch_options)
        logger.info(f"Browser launched")

        return browser

    async def _create_context(
        self, browser: Browser, profile_name: Optional[str] = None
    ) -> BrowserContext:
        """Create browser context dengan optimized settings"""

        context_options = {
            "viewport": self.platform_config["viewport"],
            "user_agent": self.platform_config["user_agent"],
            "locale": "ko-KR",
            "ignore_https_errors": True,
            "bypass_csp": True,
        }

        # NOTE: Playwright handle persistence secara berbeda dari Selenium
        # Untuk session persistence, kita akan rely on session_manager

        context = await browser.new_context(**context_options)

        # Setup resource blocking
        await self._setup_resource_blocking(context)

        # Setup other context optimizations
        await self._setup_context_optimizations(context)

        logger.debug("Browser context created dengan optimizations")
        return context

    async def _setup_resource_blocking(self, context: BrowserContext):
        """Block unnecessary resources untuk performance"""

        async def route_handler(route):
            # Block by resource type
            if route.request.resource_type in self.config.BLOCKED_RESOURCE_TYPES:
                await route.abort()
                return

            # Block by domain
            request_url = route.request.url
            for blocked_domain in self.config.BLOCKED_DOMAINS:
                if blocked_domain in request_url:
                    await route.abort()
                    return

            # Continue request untuk resources penting
            await route.continue_()

        await context.route("**/*", route_handler)

    async def _setup_context_optimizations(self, context: BrowserContext):
        """Setup additional context optimizations"""

        # Grant permissions untuk situs EPS
        await context.grant_permissions(
            [
                "geolocation",
                "notifications",
            ],
            origin="https://www.eps.go.kr",
        )

        # Setup extra HTTP headers
        await context.set_extra_http_headers(
            {
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            }
        )

    async def _create_page(self, context: BrowserContext) -> Page:
        """Create page dengan optimized settings"""
        page = await context.new_page()

        # Set timeouts
        page.set_default_timeout(self.platform_config["timeouts"]["default"])
        page.set_default_navigation_timeout(
            self.platform_config["timeouts"]["navigation"]
        )

        # Stealth modifications untuk menghindari detection
        await self._apply_stealth_modifications(page)

        logger.debug("Page created dengan optimized settings")
        return page

    async def _apply_stealth_modifications(self, page: Page):
        """Apply stealth modifications untuk menghindari bot detection"""

        # Remove webdriver property
        await page.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // Override permissions API
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Mock chrome runtime
            window.chrome = {
                runtime: {},
            };
        """
        )

    async def create_browser_stack(
        self, profile_name: Optional[str] = None
    ) -> Tuple[Browser, BrowserContext, Page]:
        """
        Create complete browser stack (browser, context, page)

        Args:
            profile_name: Optional profile name (untuk logging saja, tidak untuk persistence)

        Returns:
            Tuple of (browser, context, page)
        """
        max_retries = 2

        for attempt in range(max_retries):
            try:
                logger.info(f"🔄 Browser creation attempt {attempt + 1}/{max_retries}")

                # Create browser
                browser = await self._create_browser(profile_name)

                # Create context
                context = await self._create_context(browser, profile_name)

                # Create page
                page = await self._create_page(context)

                logger.info(f"[BROWSER] Playwright stack ready on {self.system}")

                return browser, context, page

            except Exception as e:
                logger.warning(f"❌ Browser attempt {attempt + 1} failed: {e}")

                if attempt < max_retries - 1:
                    # Cleanup sebelum retry
                    await self._cleanup_browser_processes()
                    await asyncio.sleep(3)
                    continue
                else:
                    logger.error(f"💥 All browser creation attempts failed")
                    raise

    async def _cleanup_browser_processes(self):
        """Cleanup browser processes sebelum retry"""
        try:
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
            logger.debug("Browser processes cleanup completed")
        except Exception as e:
            logger.debug(f"Browser processes cleanup failed: {e}")

    async def close(self):
        """Cleanup resources"""
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None


# ===== LEGACY FUNCTIONS UNTUK BACKWARD COMPATIBILITY =====


# handlers/eps_core/browser.py - PERBAIKI setup_browser


async def setup_browser(
    profile_name: Optional[str] = None,
) -> Tuple[Browser, BrowserContext, Page]:
    """Stable browser setup"""
    factory = BrowserFactory()

    try:
        browser, context, page = await factory.create_browser_stack(profile_name)

        # Additional stability checks
        if not browser.is_connected():
            raise Exception("Browser not connected after creation")

        if page.is_closed():
            raise Exception("Page closed after creation")

        return browser, context, page

    except Exception as e:
        logger.error(f"Browser setup failed: {e}")
        # Cleanup dan raise
        await factory.close()
        raise


async def setup_simple_browser() -> Tuple[Browser, BrowserContext, Page]:
    """
    Simple browser setup untuk testing
    """
    playwright = await async_playwright().start()

    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--window-size=1366,768",
            "--lang=ko-KR",
        ],
    )

    context = await browser.new_context(
        viewport={"width": 1366, "height": 768},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        locale="ko-KR",
    )

    # Block images dan fonts
    await context.route(
        "**/*",
        lambda route: (
            route.abort()
            if route.request.resource_type in ["image", "font", "stylesheet"]
            else route.continue_()
        ),
    )

    page = await context.new_page()
    page.set_default_timeout(20000)
    page.set_default_navigation_timeout(20000)

    logger.info("[BROWSER] Simple browser stack started")
    return browser, context, page


async def setup_fast_browser() -> Tuple[Browser, BrowserContext, Page]:
    """
    Fast browser setup untuk emergency use cases
    """
    playwright = await async_playwright().start()

    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--window-size=1200,800",
            "--disable-extensions",
            "--lang=ko-KR",
        ],
    )

    context = await browser.new_context(
        viewport={"width": 1200, "height": 800},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        locale="ko-KR",
    )

    page = await context.new_page()

    # Fast timeouts
    page.set_default_timeout(15000)
    page.set_default_navigation_timeout(15000)

    logger.info("⚡ Fast browser stack started")
    return browser, context, page


# ===== UTILITY FUNCTIONS =====


async def close_browser_stack(browser: Browser):
    """Close browser dan semua resources terkait"""
    try:
        await browser.close()
        logger.debug("Browser stack closed")
    except Exception as e:
        logger.debug(f"Error closing browser: {e}")


# handlers/eps_core/browser.py - PERBAIKI safe_goto

async def safe_goto(page: Page, url: str, timeout: int = 30000) -> bool:
    """
    Safe navigation dengan improved error handling
    """
    try:
        # Gunakan approach yang lebih tolerant
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        
        # Tunggu dengan timeout yang lebih pendek untuk ready state
        try:
            await page.wait_for_function(
                "document.readyState === 'complete'", 
                timeout=5000
            )
        except:
            logger.debug("[BROWSER] Ready state timeout, continuing anyway")
            
        return True
    except Exception as e:
        logger.warning(f"[BROWSER] Navigation to {url} had issues: {e}")
        # Return true anyway untuk kasus timeout partial
        return "timeout" in str(e).lower()


async def wait_for_selectors(page: Page, selectors: list, timeout: int = 10000) -> bool:
    """
    Wait for multiple selectors (coba satu per satu)

    Args:
        page: Page object
        selectors: List of CSS selectors
        timeout: Timeout dalam milliseconds

    Returns:
        True jika salah satu selector ditemukan, False jika tidak
    """
    for selector in selectors:
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            continue
    return False


# Suppress Playwright logging noise
import warnings

warnings.filterwarnings("ignore")

# Setup logging levels untuk dependencies
logging.getLogger("playwright").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)
