"""Anti-detection browser using playwright-stealth."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

logger = logging.getLogger(__name__)

# Memory-optimized launch args for low-memory servers (2GB RAM + 6GB swap)
BROWSER_ARGS = [
    "--no-sandbox",
    "--disable-gpu",
    "--disable-dev-shm-usage",
    "--disable-extensions",
    "--single-process",
    "--disable-software-rasterizer",
    "--no-zygote",
    "--js-flags=--max-old-space-size=256",
    "--disable-blink-features=AutomationControlled",
]

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

DEFAULT_VIEWPORT = {"width": 1280, "height": 720}


@dataclass
class StealthBrowserResult:
    browser: Browser
    context: BrowserContext
    page: Page


class StealthBrowser:
    """Launches Playwright browser with comprehensive anti-detection."""

    def __init__(self, headless: bool = True, user_agent: Optional[str] = None):
        self.headless = headless
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self._playwright = None
        self._browser = None

    async def launch(
        self, storage_state: Optional[dict] = None
    ) -> StealthBrowserResult:
        self._playwright = await async_playwright().start()

        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=BROWSER_ARGS,
        )

        context = await self._browser.new_context(
            viewport=DEFAULT_VIEWPORT,
            user_agent=self.user_agent,
            locale="en-US",
            storage_state=storage_state,
        )

        # Apply playwright-stealth evasions
        await self._apply_stealth(context)

        page = await context.new_page()
        return StealthBrowserResult(
            browser=self._browser, context=context, page=page
        )

    async def _apply_stealth(self, context: BrowserContext):
        """Apply anti-detection scripts to all new pages."""
        from playwright_stealth import Stealth

        stealth = Stealth()
        await stealth.apply_stealth_async(context)

    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
