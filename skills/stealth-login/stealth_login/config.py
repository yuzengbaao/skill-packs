"""Credential and configuration management for stealth-login."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_AUTH_DIR = Path("/root/.openclaw/workspace/auth")
DEFAULT_CREDENTIALS_FILE = DEFAULT_AUTH_DIR / "credentials.json"


@dataclass
class Credentials:
    email: str = ""
    password: str = ""
    username: str = ""
    phone: str = ""

    def is_complete(self, need_username: bool = False) -> bool:
        if not self.email or not self.password:
            return False
        if need_username and not self.username:
            return False
        return True


@dataclass
class StealthLoginConfig:
    discord: Optional[Credentials] = None
    twitter: Optional[Credentials] = None
    auth_dir: Path = field(default_factory=lambda: DEFAULT_AUTH_DIR)
    headless: bool = True
    max_captcha_retries: int = 3
    captcha_timeout: int = 120
    session_max_age_hours: int = 24

    @classmethod
    def from_env(cls) -> StealthLoginConfig:
        config = cls()

        discord_email = os.environ.get("DISCORD_EMAIL", "")
        discord_password = os.environ.get("DISCORD_PASSWORD", "")
        if discord_email and discord_password:
            config.discord = Credentials(email=discord_email, password=discord_password)

        twitter_username = os.environ.get("TWITTER_USERNAME", "")
        twitter_password = os.environ.get("TWITTER_PASSWORD", "")
        twitter_email = os.environ.get("TWITTER_EMAIL", "")
        twitter_phone = os.environ.get("TWITTER_PHONE", "")
        if twitter_username and twitter_password:
            config.twitter = Credentials(
                email=twitter_email or twitter_username,
                password=twitter_password,
                username=twitter_username,
                phone=twitter_phone,
            )

        return config

    @classmethod
    def load(cls, auth_dir: Optional[Path] = None) -> StealthLoginConfig:
        config = cls.from_env()
        if config.discord and config.twitter:
            return config

        cred_path = Path(auth_dir or DEFAULT_AUTH_DIR) / "credentials.json"
        if not cred_path.exists():
            return config

        try:
            with open(cred_path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read credentials file: %s", e)
            return config

        if not config.discord and "discord" in data:
            d = data["discord"]
            config.discord = Credentials(
                email=d.get("email", ""),
                password=d.get("password", ""),
            )

        if not config.twitter and "twitter" in data:
            t = data["twitter"]
            config.twitter = Credentials(
                email=t.get("email", ""),
                password=t.get("password", ""),
                username=t.get("username", ""),
                phone=t.get("phone", ""),
            )

        return config
