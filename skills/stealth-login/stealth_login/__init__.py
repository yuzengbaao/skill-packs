"""stealth-login: Anti-detection browser login for Discord and X (Twitter)."""
from .captcha_solver import (
    ArkoseSolver,
    CaptchaSolution,
    HcaptchaSolver,
    generate_bezier_trajectory,
    generate_dynamic_delays,
)
from .config import Credentials, StealthLoginConfig
from .discord_login import DiscordLogin, LoginResult
from .session import SessionManager
from .stealth import StealthBrowser, StealthBrowserResult
from .twitter_login import TwitterLogin
from .vision import VisionClient, extract_json

__all__ = [
    "ArkoseSolver",
    "CaptchaSolution",
    "Credentials",
    "DiscordLogin",
    "HcaptchaSolver",
    "LoginResult",
    "SessionManager",
    "StealthBrowser",
    "StealthBrowserResult",
    "StealthLoginConfig",
    "TwitterLogin",
    "VisionClient",
    "extract_json",
    "generate_bezier_trajectory",
    "generate_dynamic_delays",
]
