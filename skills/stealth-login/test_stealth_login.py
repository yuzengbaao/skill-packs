"""stealth-login unit and integration tests."""
import asyncio
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, "/root/.openclaw/workspace/skills/stealth-login")

import pytest
import pytest_asyncio

os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test_token")
os.environ.setdefault("ANTHROPIC_BASE_URL", "https://test.example.com/anthropic")

from stealth_login import (
    ArkoseSolver,
    CaptchaSolution,
    Credentials,
    DiscordLogin,
    HcaptchaSolver,
    LoginResult,
    SessionManager,
    StealthBrowser,
    StealthLoginConfig,
    TwitterLogin,
    VisionClient,
    extract_json,
    generate_bezier_trajectory,
    generate_dynamic_delays,
)


# ============ Unit Tests ============

class TestCredentials:
    def test_complete_basic(self):
        c = Credentials(email="a@b.com", password="pass")
        assert c.is_complete() is True
        assert c.is_complete(need_username=True) is False

    def test_incomplete_no_email(self):
        c = Credentials(password="pass")
        assert c.is_complete() is False

    def test_complete_with_username(self):
        c = Credentials(email="a@b.com", password="pass", username="user")
        assert c.is_complete(need_username=True) is True

    def test_incomplete_no_password(self):
        c = Credentials(email="a@b.com")
        assert c.is_complete() is False


class TestStealthLoginConfig:
    def test_from_env_discord(self):
        os.environ["DISCORD_EMAIL"] = "test@test.com"
        os.environ["DISCORD_PASSWORD"] = "secret"
        config = StealthLoginConfig.from_env()
        assert config.discord is not None
        assert config.discord.email == "test@test.com"
        del os.environ["DISCORD_EMAIL"]
        del os.environ["DISCORD_PASSWORD"]

    def test_from_env_twitter(self):
        os.environ["TWITTER_USERNAME"] = "testuser"
        os.environ["TWITTER_PASSWORD"] = "secret"
        config = StealthLoginConfig.from_env()
        assert config.twitter is not None
        assert config.twitter.username == "testuser"
        del os.environ["TWITTER_USERNAME"]
        del os.environ["TWITTER_PASSWORD"]

    def test_load_from_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cred_path = Path(tmpdir) / "credentials.json"
            cred_path.write_text(json.dumps({
                "discord": {"email": "d@t.com", "password": "dp"},
                "twitter": {"username": "tu", "password": "tp"},
            }))

            config = StealthLoginConfig.load(auth_dir=Path(tmpdir))
            assert config.discord is not None
            assert config.discord.email == "d@t.com"
            assert config.twitter is not None
            assert config.twitter.username == "tu"


class TestLoginResult:
    def test_success(self):
        r = LoginResult(success=True, service="discord", state_saved=True)
        assert r.success is True
        assert r.requires_mfa is False
        assert r.error is None

    def test_mfa_required(self):
        r = LoginResult(success=False, service="discord", requires_mfa=True)
        assert r.requires_mfa is True

    def test_failure(self):
        r = LoginResult(success=False, service="twitter", error="timeout")
        assert r.error == "timeout"


class TestExtractJson:
    def test_code_block_json(self):
        text = '```json\n{"type": "grid", "cells": [1, 2]}\n```'
        result = extract_json(text)
        assert result["type"] == "grid"
        assert result["cells"] == [1, 2]

    def test_raw_json(self):
        text = 'Some text {"key": "value"} more text'
        result = extract_json(text)
        assert result["key"] == "value"

    def test_invalid_returns_empty(self):
        result = extract_json("no json here")
        assert result == {}

    def test_nested_json(self):
        text = '{"outer": {"inner": 42}}'
        result = extract_json(text)
        assert result["outer"]["inner"] == 42


class TestCaptchaSolution:
    def test_grid_solution(self):
        s = CaptchaSolution(
            challenge_type="grid_select",
            cells_to_click=[1, 3, 5],
            has_verify=True,
        )
        assert s.challenge_type == "grid_select"
        assert len(s.cells_to_click) == 3

    def test_drag_solution(self):
        s = CaptchaSolution(
            challenge_type="drag_drop",
            drag_start=(100, 200),
            drag_end=(300, 400),
        )
        assert s.drag_start == (100, 200)
        assert s.drag_end == (300, 400)

    def test_default_unknown(self):
        s = CaptchaSolution()
        assert s.challenge_type == "unknown"
        assert s.cells_to_click == []


class TestBezierTrajectory:
    def test_start_equals_end(self):
        pts = generate_bezier_trajectory((100, 100), (100, 100), 10)
        assert len(pts) == 11
        assert pts[0] == (100, 100)
        assert pts[-1] == (100, 100)

    def test_horizontal_line(self):
        pts = generate_bezier_trajectory((0, 0), (200, 0), 20)
        assert len(pts) == 21
        assert pts[0] == (0, 0)
        # End point should match exactly
        assert abs(pts[-1][0] - 200) < 1
        assert abs(pts[-1][1]) < 50  # Bezier curve adds slight Y deviation

    def test_points_count(self):
        for steps in [5, 10, 20, 50]:
            pts = generate_bezier_trajectory((0, 0), (100, 100), steps)
            assert len(pts) == steps + 1

    def test_curve_deviation(self):
        pts = generate_bezier_trajectory((0, 0), (200, 200), 20)
        # Midpoint should deviate from straight line
        mid = pts[len(pts) // 2]
        # Straight line at midpoint would be (100, 100)
        # Bezier curve should differ
        assert mid != (100.0, 100.0)


class TestDynamicDelays:
    def test_delays_count(self):
        delays = generate_dynamic_delays(10, base_delay=30.0)
        assert len(delays) == 11

    def test_delays_positive(self):
        delays = generate_dynamic_delays(20, base_delay=30.0)
        assert all(d > 0 for d in delays)

    def test_ends_slower_than_middle(self):
        delays = generate_dynamic_delays(20, base_delay=30.0)
        # First and last delays should be higher than middle
        assert delays[0] > delays[10]
        assert delays[-1] > delays[10]


class TestSessionManager:
    def test_state_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sm = SessionManager(Path(tmpdir))
            path = sm.get_state_path("discord")
            assert path.name == "discord_state.json"
            assert path.parent == Path(tmpdir)

    def test_is_state_valid_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sm = SessionManager(Path(tmpdir))
            assert sm.is_state_valid("discord") is False

    def test_is_state_valid_recent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sm = SessionManager(Path(tmpdir))
            path = sm.get_state_path("test")
            path.write_text('{"cookies": []}')
            assert sm.is_state_valid("test") is True

    def test_is_state_valid_expired(self):
        import time
        with tempfile.TemporaryDirectory() as tmpdir:
            sm = SessionManager(Path(tmpdir), max_age_hours=0)
            path = sm.get_state_path("test")
            path.write_text('{"cookies": []}')
            time.sleep(0.01)
            assert sm.is_state_valid("test") is False


# ============ Integration Tests (require Playwright) ============

class TestStealthBrowser:
    @pytest_asyncio.fixture
    async def browser(self):
        sb = StealthBrowser(headless=True)
        result = await sb.launch()
        yield result
        await sb.close()

    @pytest.mark.asyncio
    async def test_launch_and_close(self, browser):
        assert browser.page is not None
        assert browser.context is not None

    @pytest.mark.asyncio
    async def test_navigate_after_stealth(self, browser):
        await browser.page.goto("https://example.com", wait_until="domcontentloaded", timeout=15000)
        title = await browser.page.title()
        assert "Example Domain" in title

    @pytest.mark.asyncio
    async def test_webdriver_not_detected(self, browser):
        await browser.page.goto("https://example.com", wait_until="domcontentloaded", timeout=15000)
        webdriver = await browser.page.evaluate("navigator.webdriver")
        assert webdriver is None or webdriver is False


# ============ Mock Tests ============

class TestVisionClientMock:
    @pytest.mark.asyncio
    async def test_analyze_image_format(self):
        vc = VisionClient(base_url="https://test.example.com", api_key="test_key")
        fake_response = {
            "content": [{"text": '{"type": "checkbox", "has_verify": true}'}],
        }
        # httpx Response.json() is synchronous, so use MagicMock (not AsyncMock)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = fake_response

        with patch("stealth_login.vision.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            result = await vc.analyze_image("fake_b64_data", "test prompt")
            assert result["type"] == "checkbox"


class TestArkoseSolverDetect:
    @pytest.mark.asyncio
    async def test_detect_no_arkose(self):
        page = AsyncMock()
        page.frames = []
        solver = ArkoseSolver(page, VisionClient())
        assert solver.detect() is False

    @pytest.mark.asyncio
    async def test_detect_arkose_present(self):
        frame = MagicMock()
        frame.url = "https://api.arkoselabs.com/fc/challenge"
        page = AsyncMock()
        page.frames = [frame]
        solver = ArkoseSolver(page, VisionClient())
        assert solver.detect() is True


# ============ Live Tests (skip without real API key) ============

class TestVisionClientLive:
    @pytest.mark.asyncio
    async def test_real_vision_call(self):
        token = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
        if not token or token == "test_token":
            pytest.skip("No real API key")

        vc = VisionClient()
        # Minimal 1x1 white PNG
        import base64
        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
            "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        result = await vc.analyze_image(base64.b64encode(png).decode(), "Describe this image")
        assert isinstance(result, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
