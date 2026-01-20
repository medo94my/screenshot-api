"""
Screenshot rendering using Playwright.

This module handles all browser automation for capturing website screenshots:
- Browser lifecycle management (launch, reuse, close)
- Page creation and cleanup per request
- Screenshot capture with various options
- Error handling and timeout management
- SSRF protection via request interception
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from playwright.async_api import (
    async_playwright,
    Browser as PlaywrightBrowser,
    BrowserContext,
    Page,
)
from playwright.async_api import Error as PlaywrightError

from app.config import Config
from app.security import validate_url, is_internal_url
from app.utils import clamp


class ScreenshotError(Exception):
    """Exception raised for screenshot capture failures."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ScreenshotRenderer:
    """
    Manages Playwright browser instances for screenshot capture.

    This class implements browser reuse for efficiency:
    - A single Chromium browser is launched at startup
    - Each request creates a new browser context and page
    - Contexts and pages are closed after each screenshot
    - Request interception blocks access to internal/private addresses
    """

    def __init__(self):
        self.config = Config
        self._playwright: Optional[async_playwright] = None
        self._browser: Optional[PlaywrightBrowser] = None
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Initialize Playwright and launch the browser."""
        async with self._lock:
            if self._browser is not None:
                return  # Already started

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True, args=self.config.CHROMIUM_ARGS
            )
            self._semaphore = asyncio.Semaphore(self.config.MAX_CONCURRENCY)

    async def ensure_started(self) -> None:
        """Ensure the browser is started. Thread-safe lazy initialization."""
        if self._semaphore is None:
            await self.start()

    async def close(self) -> None:
        """Close the browser and stop Playwright."""
        async with self._lock:
            if self._browser:
                await self._browser.close()
                self._browser = None

            if self._playwright:
                await self._playwright.stop()
                self._playwright = None

            self._semaphore = None

    def _should_block_request(self, url: str) -> bool:
        """Check if a request should be blocked based on SSRF protection."""
        from urllib.parse import urlparse

        # Block empty or invalid URLs
        if not url or url.strip() == "":
            return True

        # Block dangerous URL schemes
        lowered = url.lower()
        if any(
            lowered.startswith(scheme)
            for scheme in ["file://", "data://", "javascript://", "vbscript://"]
        ):
            return True

        # Use the security module's internal URL check
        return is_internal_url(url)

    async def capture(
        self,
        url: str,
        width: int = 1280,
        height: int = 720,
        full_page: bool = False,
        delay: int = 0,
        format: str = "png",
        quality: int = 85,
    ) -> bytes:
        """Capture a screenshot of the given URL with SSRF protection."""
        # Ensure browser is started
        await self.ensure_started()

        async with self._semaphore:
            # Validate and clamp parameters
            width = clamp(width, 320, 1920)
            height = clamp(height, 240, 1080)
            delay = clamp(delay, 0, 10000)

            # Validate URL before navigation (SSRF protection)
            validation = validate_url(url)
            if not validation.is_valid:
                raise ScreenshotError(validation.error_message or "Invalid URL", 400)

            # Route handler for this request - blocks all internal requests
            async def handle_route(route, request):
                url_to_check = request.url
                if not self._should_block_request(url_to_check):
                    await route.continue_()
                else:
                    await route.abort("blockedbyclient")

            try:
                async with self._create_context(handle_route) as context:
                    async with self._create_page(context) as page:
                        # Set viewport size for the page
                        await page.set_viewport_size({"width": width, "height": height})

                        # Navigate to the page - all requests will be intercepted
                        try:
                            await page.goto(
                                url,
                                wait_until="domcontentloaded",
                                timeout=self.config.NAV_TIMEOUT_MS,
                            )
                        except PlaywrightError as e:
                            error_msg = str(e).lower()
                            if "timeout" in error_msg:
                                raise ScreenshotError(
                                    "Page navigation timed out", status_code=504
                                )
                            elif "net::err" in error_msg or "dns" in error_msg:
                                raise ScreenshotError(
                                    f"Failed to load page: {str(e)[:100]}",
                                    status_code=400,
                                )
                            elif "aborted" in error_msg or "blocked" in error_msg:
                                raise ScreenshotError(
                                    "Request blocked by security policy",
                                    status_code=403,
                                )
                            else:
                                raise ScreenshotError(
                                    f"Navigation error: {str(e)[:100]}", status_code=500
                                )

                        # Apply delay if specified
                        if delay > 0:
                            await page.wait_for_timeout(delay)

                        # Build screenshot options
                        screenshot_opts: dict = {
                            "type": "jpeg" if format == "jpeg" else "png",
                            "full_page": full_page,
                            "animations": "disabled",
                        }

                        if format == "jpeg":
                            screenshot_opts["quality"] = min(100, max(1, quality))

                        # For full page, clamp height to prevent memory issues
                        if full_page:
                            max_height = self.config.MAX_FULLPAGE_HEIGHT
                            page_height = await page.evaluate(
                                "() => document.body.scrollHeight"
                            )
                            if page_height > max_height:
                                screenshot_opts["clip"] = {
                                    "x": 0,
                                    "y": 0,
                                    "width": width,
                                    "height": max_height,
                                }

                        image_bytes = await page.screenshot(**screenshot_opts)

                        # Check size limit
                        if len(image_bytes) > self.config.MAX_RESPONSE_SIZE_BYTES:
                            raise ScreenshotError(
                                "Screenshot response too large", status_code=413
                            )

                        return image_bytes

            except ScreenshotError:
                raise
            except PlaywrightError as e:
                raise ScreenshotError(
                    f"Playwright error: {str(e)[:100]}", status_code=500
                )
            except Exception as e:
                raise ScreenshotError(
                    f"Unexpected error: {str(e)[:100]}", status_code=500
                )

    @asynccontextmanager
    async def _create_context(self, route_handler):
        """Create a browser context with request interception."""
        if not self._browser:
            raise ScreenshotError("Browser not initialized", 500)

        context = await self._browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (compatible; ScreenshotAPI/1.0; +self)",
            ignore_https_errors=True,
            java_script_enabled=True,
            has_touch=False,
            is_mobile=False,
        )

        await context.route("**/*", route_handler)

        try:
            yield context
        finally:
            await context.unroute("**/*", route_handler)
            await context.close()

    @asynccontextmanager
    async def _create_page(self, context: BrowserContext):
        """Create a page within the context."""
        page = await context.new_page()
        try:
            yield page
        finally:
            await page.close()


# Global renderer instance
_renderer: Optional[ScreenshotRenderer] = None
_renderer_lock = asyncio.Lock()


async def get_renderer() -> ScreenshotRenderer:
    """Get the global renderer instance with lazy initialization."""
    global _renderer
    if _renderer is None:
        async with _renderer_lock:
            if _renderer is None:
                _renderer = ScreenshotRenderer()
                await _renderer.start()
    return _renderer


async def close_renderer() -> None:
    """Close the global renderer."""
    global _renderer
    if _renderer:
        await _renderer.close()
        _renderer = None
