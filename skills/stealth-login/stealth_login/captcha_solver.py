"""CAPTCHA solving logic with Bezier curve mouse movement."""
from __future__ import annotations

import asyncio
import base64
import logging
import math
import random
from dataclasses import dataclass, field
from typing import Optional

from playwright.async_api import Frame, Page

from .vision import VisionClient, HCAPTCHA_PROMPT, ARKOSE_PROMPT

logger = logging.getLogger(__name__)


@dataclass
class CaptchaSolution:
    challenge_type: str = "unknown"
    instruction: str = ""
    cells_to_click: list[int] = field(default_factory=list)
    drag_start: Optional[tuple[float, float]] = None
    drag_end: Optional[tuple[float, float]] = None
    rotation_angle: float = 0.0
    has_verify: bool = False
    confidence: float = 0.0


def generate_bezier_trajectory(
    start: tuple[float, float],
    end: tuple[float, float],
    steps: int = 20,
) -> list[tuple[float, float]]:
    """Quadratic Bezier curve trajectory for natural mouse movement.

    Extracted from hcaptcha_challenger/agent/challenger.py L52-83.
    """
    distance = math.sqrt((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2)
    offset_factor = min(0.3, max(0.1, distance / 1000))

    mid_x = (start[0] + end[0]) / 2
    mid_y = (start[1] + end[1]) / 2
    control_x = mid_x + random.uniform(-1, 1) * distance * offset_factor
    control_y = mid_y + random.uniform(-1, 1) * distance * offset_factor

    points = []
    for i in range(steps + 1):
        t = i / steps
        x = (1 - t) ** 2 * start[0] + 2 * (1 - t) * t * control_x + t**2 * end[0]
        y = (1 - t) ** 2 * start[1] + 2 * (1 - t) * t * control_y + t**2 * end[1]
        points.append((x, y))
    return points


def generate_dynamic_delays(steps: int, base_delay: float = 30.0) -> list[float]:
    """Dynamic delays with acceleration/deceleration for human-like timing.

    Extracted from hcaptcha_challenger/agent/challenger.py L86-111.
    """
    delays = []
    for i in range(steps + 1):
        progress = i / steps
        if progress < 0.5:
            factor = 2 * progress * progress
        else:
            p = progress - 1
            factor = 1 - (-2 * p * p)
        delay_factor = 1.5 - 0.9 * factor
        random_factor = random.uniform(0.9, 1.1)
        delays.append(base_delay * delay_factor * random_factor)
    return delays


class HcaptchaSolver:
    """Solves hCaptcha challenges using GLM-5 Vision API."""

    def __init__(self, page: Page, vision: VisionClient, max_retries: int = 3):
        self.page = page
        self.vision = vision
        self.max_retries = max_retries

    async def solve(self) -> bool:
        """Attempt to solve hCaptcha. Returns True if solved."""
        for attempt in range(1, self.max_retries + 1):
            logger.info("hCaptcha solve attempt %d/%d", attempt, self.max_retries)

            if await self._click_checkbox():
                return True

            frame = await self._detect_challenge_frame()
            if not frame:
                logger.warning("No challenge frame detected")
                await asyncio.sleep(2)
                continue

            solution = await self._analyze_challenge()
            if solution.challenge_type == "unknown":
                logger.warning("Could not determine challenge type")
                await asyncio.sleep(2)
                continue

            if solution.challenge_type == "grid_select":
                await self._solve_grid(frame, solution)
            elif solution.challenge_type == "drag_drop":
                await self._solve_drag(solution)

            await asyncio.sleep(1)
            await self._click_verify(frame)

            await asyncio.sleep(3)
            if not self._is_captcha_present():
                logger.info("hCaptcha solved on attempt %d", attempt)
                return True

        logger.error("hCaptcha not solved after %d attempts", self.max_retries)
        return False

    async def _click_checkbox(self) -> bool:
        """Click hCaptcha checkbox. Returns True if login proceeded without challenge."""
        for frame in self.page.frames:
            if "hcaptcha" in frame.url and "checkbox" in frame.url:
                try:
                    cb = frame.locator("#checkbox")
                    if await cb.count() > 0:
                        await cb.click()
                        logger.info("Clicked hCaptcha checkbox")
                        await asyncio.sleep(4)
                        return not self._is_captcha_present()
                except Exception as e:
                    logger.debug("Checkbox click error: %s", e)
                break
        return False

    def _is_captcha_present(self) -> bool:
        """Check if hCaptcha iframe is still on the page."""
        return any("hcaptcha" in f.url for f in self.page.frames)

    async def _detect_challenge_frame(self) -> Optional[Frame]:
        for frame in self.page.frames:
            if "hcaptcha" in frame.url and "challenge" in frame.url:
                return frame
        return None

    async def _analyze_challenge(self) -> CaptchaSolution:
        screenshot_path = "/tmp/hcaptcha_challenge.png"
        await self.page.screenshot(path=screenshot_path)

        with open(screenshot_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        raw = await self.vision.analyze_image(img_b64, HCAPTCHA_PROMPT)
        return CaptchaSolution(
            challenge_type=raw.get("type", "unknown"),
            instruction=raw.get("instruction", ""),
            cells_to_click=raw.get("cells_to_click", []),
            drag_start=tuple(raw["drag_start"].values()) if raw.get("drag_start") else None,
            drag_end=tuple(raw["drag_end"].values()) if raw.get("drag_end") else None,
            has_verify=raw.get("has_verify", False),
        )

    async def _solve_grid(self, frame: Frame, solution: CaptchaSolution):
        selectors = [".task-image", ".image-wrapper", "[class*=\"task\"]", ".challenge-image"]
        tasks = []
        for sel in selectors:
            tasks = await frame.query_selector_all(sel)
            if len(tasks) >= len(solution.cells_to_click):
                break

        logger.info(
            "Grid: found %d elements, clicking %d cells",
            len(tasks), len(solution.cells_to_click),
        )
        for idx in solution.cells_to_click:
            if idx - 1 < len(tasks):
                try:
                    await tasks[idx - 1].click()
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.warning("Grid click error for cell %d: %s", idx, e)

    async def _solve_drag(self, solution: CaptchaSolution):
        if not solution.drag_start or not solution.drag_end:
            logger.warning("Drag solution missing coordinates")
            return

        sx, sy = solution.drag_start
        ex, ey = solution.drag_end
        trajectory = generate_bezier_trajectory((sx, sy), (ex, ey), steps=20)
        delays = generate_dynamic_delays(20, base_delay=30.0)

        await self.page.mouse.move(sx, sy)
        await asyncio.sleep(0.3)
        await self.page.mouse.down()
        await asyncio.sleep(0.5)

        for (x, y), delay in zip(trajectory, delays):
            await self.page.mouse.move(x, y)
            await asyncio.sleep(delay / 1000.0)

        await asyncio.sleep(0.3)
        await self.page.mouse.up()
        logger.info("Drag completed: (%.0f,%.0f) -> (%.0f,%.0f)", sx, sy, ex, ey)

    async def _click_verify(self, frame: Frame):
        for sel in ["button[type=\"submit\"]", ".verify-button", "[aria-label=\"Verify\"]"]:
            verify = await frame.query_selector(sel)
            if verify:
                await verify.click()
                logger.info("Clicked verify button")
                return


class ArkoseSolver:
    """Attempts to solve Arkose Labs FunCaptcha using GLM-5 Vision."""

    def __init__(self, page: Page, vision: VisionClient):
        self.page = page
        self.vision = vision

    def detect(self) -> bool:
        """Check if Arkose FunCaptcha iframe is present."""
        return any("arkoselabs" in f.url for f in self.page.frames)

    async def solve(self) -> bool:
        """Attempt to solve Arkose FunCaptcha."""
        if not self.detect():
            return False

        logger.info("Arkose FunCaptcha detected, attempting to solve")
        screenshot_path = "/tmp/arkose_challenge.png"
        await self.page.screenshot(path=screenshot_path)

        with open(screenshot_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        raw = await self.vision.analyze_image(img_b64, ARKOSE_PROMPT)
        challenge_type = raw.get("type", "unknown")

        if challenge_type == "image_grid":
            cells = raw.get("cells_to_click", [])
            frame = self._detect_frame()
            if frame and cells:
                selectors = [".task-image", ".image-wrapper", "[class*=\"task\"]"]
                tasks = []
                for sel in selectors:
                    tasks = await frame.query_selector_all(sel)
                    if len(tasks) >= len(cells):
                        break
                for idx in cells:
                    if idx - 1 < len(tasks):
                        try:
                            await tasks[idx - 1].click()
                            await asyncio.sleep(0.5)
                        except Exception as e:
                            logger.warning("Arkose grid click error: %s", e)

        elif challenge_type == "puzzle_rotation":
            angle = raw.get("rotation_angle", 0)
            frame = self._detect_frame()
            if frame:
                try:
                    slider = frame.locator("[class*=\"rotate\"], [class*=\"slider\"]")
                    if await slider.count() > 0:
                        await slider.drag_to(
                            slider,
                            target_position={"x": int(angle * 2), "y": 0},
                        )
                except Exception as e:
                    logger.warning("Arkose rotation error: %s", e)

        await asyncio.sleep(3)
        return not self.detect()

    def _detect_frame(self) -> Optional[Frame]:
        for frame in self.page.frames:
            if "arkoselabs" in frame.url and "challenge" in frame.url:
                return frame
        return None
