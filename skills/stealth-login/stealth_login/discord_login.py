"""Discord login with hCaptcha solving and session persistence."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

from playwright.async_api import BrowserContext

from .captcha_solver import HcaptchaSolver
from .config import Credentials, StealthLoginConfig
from .session import SessionManager
from .stealth import StealthBrowser
from .vision import VisionClient

logger = logging.getLogger(__name__)

DISCORD_LOGIN_URL = "https://discord.com/login"


@dataclass
class LoginResult:
    success: bool
    service: str = ""
    requires_mfa: bool = False
    requires_phone: bool = False
    error: Optional[str] = None
    state_saved: bool = False


class DiscordLogin:
    """Automated Discord login with anti-detection and CAPTCHA solving."""

    def __init__(self, config: StealthLoginConfig):
        self.config = config
        self.stealth = StealthBrowser(headless=config.headless)
        self.vision = VisionClient()
        self.session = SessionManager(config.auth_dir, config.session_max_age_hours)

    async def login(self) -> LoginResult:
        creds = self.config.discord
        if not creds or not creds.is_complete():
            return LoginResult(
                success=False, service="discord",
                error="Discord credentials not configured",
            )

        stealth_result = await self.stealth.launch()
        browser, context, page = (
            stealth_result.browser,
            stealth_result.context,
            stealth_result.page,
        )

        try:
            # Try existing session first (launch separate browser for it)
            if self.session.is_state_valid("discord"):
                existing_state = await self.session.load_state("discord")
                if existing_state and existing_state.get("cookies"):
                    try:
                        session_stealth = StealthBrowser(headless=self.config.headless)
                        session_result = await session_stealth.launch(
                            storage_state=existing_state,
                        )
                        session_page = session_result.page
                        await session_page.goto(DISCORD_LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
                        await asyncio.sleep(3)
                        if "login" not in session_page.url:
                            logger.info("Discord: session still valid")
                            await session_stealth.close()
                            return LoginResult(
                                success=True, service="discord", state_saved=True,
                            )
                        logger.info("Discord: session expired, re-login required")
                        await session_stealth.close()
                    except Exception as e:
                        logger.warning("Session restore failed: %s, proceeding with login", e)

            await page.goto(DISCORD_LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_selector(
                'input[type="text"], input[type="email"]', timeout=15000,
            )
            await asyncio.sleep(1)

            # Fill email
            email_input = await page.query_selector('input[type="email"], input[type="text"]')
            await email_input.click()
            await asyncio.sleep(0.3)
            await email_input.fill(creds.email)
            await asyncio.sleep(0.5)

            # Tab to password and type
            await page.keyboard.press("Tab")
            await asyncio.sleep(0.3)
            await page.keyboard.type(creds.password, delay=30)
            await asyncio.sleep(0.5)

            # Submit
            await page.keyboard.press("Enter")
            await asyncio.sleep(6)

            # Check result
            url = page.url

            # Success: no longer on login page
            if "login" not in url:
                saved = await self.session.save_state(context, "discord")
                return LoginResult(
                    success=True, service="discord", state_saved=saved,
                )

            # MFA required
            if "mfa" in url:
                return LoginResult(
                    success=False, service="discord", requires_mfa=True,
                    error="MFA required",
                )

            # hCaptcha detected
            if any("hcaptcha" in f.url for f in page.frames):
                logger.info("hCaptcha detected, solving...")
                solver = HcaptchaSolver(
                    page, self.vision, max_retries=self.config.max_captcha_retries,
                )
                solved = await solver.solve()
                if solved:
                    await asyncio.sleep(3)
                    if "login" not in page.url:
                        saved = await self.session.save_state(context, "discord")
                        return LoginResult(
                            success=True, service="discord", state_saved=saved,
                        )
                return LoginResult(
                    success=False, service="discord",
                    error="hCaptcha not solved",
                )

            return LoginResult(
                success=False, service="discord",
                error=f"Unexpected state: {url}",
            )

        except Exception as e:
            logger.error("Discord login error: %s", e)
            return LoginResult(
                success=False, service="discord", error=str(e),
            )
        finally:
            await self.stealth.close()
