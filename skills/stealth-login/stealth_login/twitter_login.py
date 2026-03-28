"""X (Twitter) login with Arkose FunCaptcha handling and session persistence."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

from .captcha_solver import ArkoseSolver
from .config import Credentials, StealthLoginConfig
from .discord_login import LoginResult
from .session import SessionManager
from .stealth import StealthBrowser
from .vision import VisionClient

logger = logging.getLogger(__name__)

TWITTER_LOGIN_URL = "https://x.com/i/flow/login"


class TwitterLogin:
    """Automated X (Twitter) login with anti-detection and CAPTCHA handling."""

    def __init__(self, config: StealthLoginConfig):
        self.config = config
        self.stealth = StealthBrowser(headless=config.headless)
        self.vision = VisionClient()
        self.session = SessionManager(config.auth_dir, config.session_max_age_hours)

    async def login(self) -> LoginResult:
        creds = self.config.twitter
        if not creds or not creds.is_complete(need_username=True):
            return LoginResult(
                success=False, service="twitter",
                error="Twitter credentials not configured (need username + password)",
            )

        stealth_result = await self.stealth.launch()
        browser, context, page = (
            stealth_result.browser,
            stealth_result.context,
            stealth_result.page,
        )

        try:
            # Try existing session
            if self.session.is_state_valid("twitter"):
                existing_state = await self.session.load_state("twitter")
                await context.close()
                context = await self.stealth._browser.new_context(
                    storage_state=existing_state,
                    user_agent=self.stealth.user_agent,
                    locale="en-US",
                )
                page = await context.new_page()
                await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(3)
                if "login" not in page.url and "i/flow" not in page.url:
                    logger.info("Twitter: session still valid")
                    return LoginResult(
                        success=True, service="twitter", state_saved=True,
                    )
                logger.info("Twitter: session expired, re-login required")

            await page.goto(TWITTER_LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            # Step 1: Username
            username_input = await page.wait_for_selector(
                'input[autocomplete="username"]', timeout=15000,
            )
            await username_input.click()
            await asyncio.sleep(0.3)
            await username_input.fill(creds.username)
            await asyncio.sleep(0.5)
            await page.keyboard.press("Enter")
            await asyncio.sleep(4)

            # Check for unusual activity prompt
            if await self._detect_unusual_activity(page):
                return LoginResult(
                    success=False, service="twitter",
                    requires_phone=True,
                    error="Unusual activity detected, phone verification required",
                )

            # Step 2: Password
            try:
                password_input = await page.wait_for_selector(
                    'input[type="password"]', timeout=10000,
                )
                await password_input.click()
                await asyncio.sleep(0.3)
                await password_input.fill(creds.password)
                await asyncio.sleep(0.5)
                await page.keyboard.press("Enter")
                await asyncio.sleep(5)
            except Exception:
                # Might need email verification step
                logger.warning("Password input not found, checking for email verification")
                email_input = await page.query_selector('input[data-testid="ocfEnterTextTextInput"]')
                if email_input and creds.email:
                    await email_input.fill(creds.email)
                    await page.keyboard.press("Enter")
                    await asyncio.sleep(4)
                    try:
                        password_input = await page.wait_for_selector(
                            'input[type="password"]', timeout=10000,
                        )
                        await password_input.fill(creds.password)
                        await page.keyboard.press("Enter")
                        await asyncio.sleep(5)
                    except Exception:
                        return LoginResult(
                            success=False, service="twitter",
                            error="Email verification flow failed",
                        )

            # Check for Arkose FunCaptcha
            arkose = ArkoseSolver(page, self.vision)
            if arkose.detect():
                logger.info("Arkose FunCaptcha detected, attempting to solve...")
                solved = await arkose.solve()
                if not solved:
                    return LoginResult(
                        success=False, service="twitter",
                        error="Arkose FunCaptcha not solved",
                    )
                await asyncio.sleep(3)

            # Check result
            url = page.url
            if "login" not in url and "i/flow" not in url:
                saved = await self.session.save_state(context, "twitter")
                return LoginResult(
                    success=True, service="twitter", state_saved=saved,
                )

            # Phone verification
            if await self._detect_phone_verification(page):
                return LoginResult(
                    success=False, service="twitter",
                    requires_phone=True,
                    error="Phone verification required",
                )

            return LoginResult(
                success=False, service="twitter",
                error=f"Unexpected state: {url}",
            )

        except Exception as e:
            logger.error("Twitter login error: %s", e)
            return LoginResult(
                success=False, service="twitter", error=str(e),
            )
        finally:
            await self.stealth.close()

    async def _detect_unusual_activity(self, page) -> bool:
        text = await page.inner_text("body") if page else ""
        indicators = ["unusual activity", "verify your phone", "suspicious login"]
        return any(indicator in text.lower() for indicator in indicators)

    async def _detect_phone_verification(self, page) -> bool:
        text = await page.inner_text("body") if page else ""
        indicators = ["phone", "verify", "confirm", "code", "SMS"]
        return any(indicator in text.lower() for indicator in indicators)
