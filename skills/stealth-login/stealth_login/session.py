"""Session persistence and cookie management."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional

from playwright.async_api import Browser, BrowserContext

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages browser session persistence (cookies + localStorage)."""

    def __init__(self, auth_dir: Path, max_age_hours: int = 24):
        self.auth_dir = auth_dir
        self.auth_dir.mkdir(parents=True, exist_ok=True)
        self.max_age_hours = max_age_hours

    def get_state_path(self, service: str) -> Path:
        return self.auth_dir / f"{service}_state.json"

    def is_state_valid(self, service: str) -> bool:
        path = self.get_state_path(service)
        if not path.exists():
            return False
        try:
            stat = path.stat()
            age_hours = (time.time() - stat.st_mtime) / 3600
            return age_hours < self.max_age_hours
        except OSError:
            return False

    async def load_state(self, service: str) -> Optional[dict]:
        path = self.get_state_path(service)
        if not self.is_state_valid(service):
            logger.info("Session state for %s is missing or expired", service)
            return None
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load state for %s: %s", service, e)
            return None

    async def save_state(self, context: BrowserContext, service: str) -> bool:
        path = self.get_state_path(service)
        try:
            state = await context.storage_state()
            with open(path, "w") as f:
                json.dump(state, f, indent=2)
            logger.info("Saved session state for %s to %s", service, path)
            return True
        except Exception as e:
            logger.error("Failed to save state for %s: %s", service, e)
            return False

    async def create_context(
        self, browser: Browser, service: str, **kwargs
    ) -> BrowserContext:
        state = await self.load_state(service)
        if state:
            logger.info("Reusing existing session for %s", service)
            return await browser.new_context(storage_state=state, **kwargs)
        return await browser.new_context(**kwargs)
