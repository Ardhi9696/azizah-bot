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
                "navigation": 15000,
                "default": 15000,
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
                "navigation": 15000,
                "default": 15000,
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
                "navigation": 15000,
                "default": 15000,
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
        # persistent browser instance to avoid repeated costly launches
        self._browser: Optional[Browser] = None
        # lock to serialize browser creation
        self._browser_lock = asyncio.Lock()
        # context pool for faster context acquisition
        self._context_pool: Optional[asyncio.Queue] = None
        # allow disabling pool if sering bermasalah
        self._pool_disabled = self._get_bool_env("DISABLE_CONTEXT_POOL", True)
        # configurable pool size via environment
        try:
            self._pool_size = int(os.getenv("BROWSER_CONTEXT_POOL_SIZE", "2"))
        except Exception:
            self._pool_size = 2

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
        # Reuse existing browser if available and connected
        async with self._browser_lock:
            if self._browser and self._browser.is_connected():
                return self._browser

            # Launch options - Playwright tidak butuh user_data_dir di sini
            launch_options = {
                "headless": self._get_bool_env(
                    "HEADLESS", self.config.HEADLESS_DEFAULT
                ),
                "args": self.platform_config["launch_args"],
            }

            # Launch browser and keep it for reuse
            self._browser = await playwright.chromium.launch(**launch_options)
            logger.info(f"Browser launched (new persistent instance)")

            return self._browser

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

    async def _ensure_context_pool(self, browser: Browser):
        """Initialize the context pool (lazy) and warm contexts."""
        if self._pool_disabled:
            return
        if self._context_pool is not None:
            return

        # Create an asyncio Queue for contexts
        self._context_pool = asyncio.Queue(maxsize=self._pool_size)

        # Warm the pool with contexts to reduce first-use latency
        created = 0
        for _ in range(self._pool_size):
            try:
                ctx = await self._create_context(browser)
                await self._context_pool.put(ctx)
                created += 1
            except Exception as e:
                logger.debug(f"Failed to warm context pool: {e}")
                break

        logger.info(f"Context pool initialized (size={created})")

    async def acquire_context(
        self, browser: Browser, profile_name: Optional[str] = None
    ) -> BrowserContext:
        """Acquire a BrowserContext from the pool or create a new one if empty."""
        # Jika pool dimatikan, selalu buat context baru agar bersih
        if self._pool_disabled:
            return await self._create_context(browser, profile_name)

        # Ensure pool exists
        try:
            await self._ensure_context_pool(browser)
        except Exception:
            # Fallback to creating a single context if pool init fails
            return await self._create_context(browser, profile_name)

        # Try to get a pooled context without waiting
        try:
            ctx = self._context_pool.get_nowait()
            logger.debug("[POOL] Acquired context from pool")

            # Sanity check: if context is somehow closed, discard and create new
            try:
                _ = ctx.browser
            except Exception:
                logger.debug("[POOL] Discarded context (invalid browser ref)")
                try:
                    await ctx.close()
                except Exception:
                    pass
                return await self._create_context(browser, profile_name)

            # Ensure context has no leftover pages (clean slate)
            try:
                pages = ctx.pages
                if pages:
                    logger.debug(
                        f"[POOL] Found {len(pages)} leftover pages in context, closing them"
                    )
                    for p in list(pages):
                        try:
                            if not p.is_closed():
                                await p.close()
                        except Exception:
                            pass
            except Exception:
                # If we can't inspect pages, bail and create fresh context
                logger.debug("[POOL] Unable to inspect pages, creating fresh context")
                try:
                    await ctx.close()
                except Exception:
                    pass
                return await self._create_context(browser, profile_name)

            return ctx
        except asyncio.QueueEmpty:
            # Pool exhausted; create one-off context (caller should release it)
            logger.debug("[POOL] Pool exhausted, creating new context on-demand")
            return await self._create_context(browser, profile_name)

    async def release_context(self, context: BrowserContext):
        """Release a BrowserContext back to the pool or close it if pool is full/unavailable."""
        if not context:
            return

        if self._pool_disabled or self._context_pool is None:
            try:
                await context.close()
            except Exception:
                pass
            return

        try:
            # Ensure context is in a clean state: close any leftover pages
            try:
                pages = context.pages
                if pages:
                    for p in list(pages):
                        try:
                            if not p.is_closed():
                                await p.close()
                        except Exception:
                            pass
            except Exception:
                # If introspection fails, prefer closing and not returning to pool
                logger.debug(
                    "[POOL] Could not inspect pages during release; closing context"
                )
                await context.close()
                return

            if self._context_pool.full():
                logger.debug("[POOL] Pool full on release, closing context")
                await context.close()
            else:
                await self._context_pool.put(context)
                logger.debug("[POOL] Context returned to pool")
        except Exception:
            try:
                await context.close()
            except Exception:
                pass

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
            # Close persistent browser if exists
            try:
                if self._browser:
                    # Before closing browser, also drain/close any pooled contexts
                    if self._context_pool:
                        while not self._context_pool.empty():
                            try:
                                ctx = self._context_pool.get_nowait()
                                await ctx.close()
                            except Exception:
                                pass
                        self._context_pool = None

                    await self._browser.close()
                    self._browser = None
            except Exception:
                pass

            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
            logger.debug("Browser processes cleanup completed")
        except Exception as e:
            logger.debug(f"Browser processes cleanup failed: {e}")

    async def close(self):
        """Cleanup resources"""
        try:
            # Close pooled contexts first
            if self._context_pool:
                while not self._context_pool.empty():
                    try:
                        ctx = self._context_pool.get_nowait()
                        await ctx.close()
                    except Exception:
                        pass
                self._context_pool = None

            if self._browser:
                await self._browser.close()
                self._browser = None
        except Exception:
            pass

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None


# ===== LEGACY FUNCTIONS UNTUK BACKWARD COMPATIBILITY =====


# handlers/eps_core/browser.py - PERBAIKI setup_browser


async def setup_browser(
    profile_name: Optional[str] = None,
) -> Tuple[Browser, BrowserContext, Page]:
    """Stable browser setup"""
    # Use a shared factory so we don't recreate Playwright/browser every call
    global _DEFAULT_BROWSER_FACTORY
    try:
        _DEFAULT_BROWSER_FACTORY
    except NameError:
        _DEFAULT_BROWSER_FACTORY = BrowserFactory()

    factory = _DEFAULT_BROWSER_FACTORY

    # At most 2 attempts with cleanup in between to recover from TargetClosedError
    for attempt in range(2):
        try:
            # Acquire (or create) persistent browser
            browser = await factory._create_browser(profile_name)

            # Acquire context from pool (or create one)
            context = await factory.acquire_context(browser, profile_name)

            # Create page for this context
            try:
                page = await factory._create_page(context)
            except Exception as e:
                logger.warning(
                    f"[BROWSER] Gagal membuat page dari context (akan coba ulang): {e}"
                )
                try:
                    await factory.release_context(context)
                except Exception:
                    pass

                # fresh browser/context on retry
                browser = await factory._create_browser(profile_name)
                context = await factory.acquire_context(browser, profile_name)
                page = await factory._create_page(context)

            # If the page was closed immediately for some reason, try a couple of fallbacks
            if page.is_closed():
                logger.warning(
                    "[BROWSER] Page closed immediately after creation, trying a fresh page"
                )
                try:
                    page = await context.new_page()
                    await factory._apply_stealth_modifications(page)
                except Exception:
                    # Try acquiring a fresh context from the pool (or create one)
                    try:
                        logger.warning(
                            "[BROWSER] Creating fresh context due to closed page"
                        )
                        # attempt to acquire another context
                        context = await factory.acquire_context(browser, profile_name)
                        page = await factory._create_page(context)
                    except Exception as inner_e:
                        logger.error(
                            f"[BROWSER] Fresh context/page attempt failed: {inner_e}"
                        )
                        raise Exception("Page closed after creation")

            # Additional stability checks
            if not browser.is_connected():
                raise Exception("Browser not connected after creation")

            return browser, context, page

        except Exception as e:
            logger.error(f"Browser setup failed: {e}")
            # Cleanup local resources (do not close the shared factory/browser - that
            # can cause other sessions to lose their pages). Close only context/page
            # created in this iteration, if any.
            try:
                if "page" in locals() and page and not page.is_closed():
                    try:
                        await page.close()
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                if "context" in locals() and context:
                    try:
                        await context.close()
                    except Exception:
                        pass
            except Exception:
                pass

            # Jika masih gagal dan ini attempt pertama, bersihkan browser & pool lalu coba lagi
            if attempt == 0:
                try:
                    await factory._cleanup_browser_processes()
                except Exception:
                    pass
                # reset pooled contexts flag
                try:
                    factory._context_pool = None
                except Exception:
                    pass
                continue

            # Do NOT call factory.close() here; re-raise after last attempt
            raise


async def release_pooled_context(context: Optional[BrowserContext]):
    """Release a context back to the factory pool (no-op if factory missing)."""
    if not context:
        return

    global _DEFAULT_BROWSER_FACTORY
    try:
        _DEFAULT_BROWSER_FACTORY
    except NameError:
        # No factory - close directly
        try:
            await context.close()
        except Exception:
            pass
        return

    factory = _DEFAULT_BROWSER_FACTORY
    try:
        await factory.release_context(context)
    except Exception:
        try:
            await context.close()
        except Exception:
            pass


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
                "document.readyState === 'complete'", timeout=5000
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
