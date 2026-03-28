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

from .vision import VisionClient, HCAPTCHA_DRAG_PROMPT, HCAPTCHA_GRID_PROMPT, ARKOSE_PROMPT

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

    def __init__(self, page: Page, vision: VisionClient, max_retries: int = 5):
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

            # Programmatic type detection first (more reliable than Vision)
            challenge_type = await self._detect_challenge_type(frame)
            logger.info("Detected challenge type: %s", challenge_type)

            if challenge_type == "unknown":
                await asyncio.sleep(2)
                continue

            solution = await self._analyze_challenge(challenge_type)
            drag_info = "None"
            if solution.drag_start and solution.drag_end:
                drag_info = (
                    f"({solution.drag_start[0]:.0f},{solution.drag_start[1]:.0f}) "
                    f"-> ({solution.drag_end[0]:.0f},{solution.drag_end[1]:.0f})"
                )
            logger.info(
                "Vision response: type=%s, cells=%s, drag=%s",
                solution.challenge_type, solution.cells_to_click, drag_info,
            )

            if challenge_type == "grid_select":
                await self._solve_grid(frame, solution)
                await asyncio.sleep(1)
                await self._click_verify(frame)
            elif challenge_type == "drag_drop":
                if solution.drag_start and solution.drag_end:
                    await self._solve_drag(solution, frame)
                else:
                    logger.warning("Drag coordinates missing from Vision")
                # drag-drop auto-verifies, no verify button needed

            await asyncio.sleep(3)
            if not self._is_captcha_present():
                logger.info("hCaptcha solved on attempt %d", attempt)
                return True

        logger.error("hCaptcha not solved after %d attempts", self.max_retries)
        return False

    async def _detect_challenge_type(self, frame: Frame) -> str:
        """Detect challenge type programmatically from DOM structure.

        This is more reliable than Vision-based classification.
        - drag_drop: has a canvas element and/or "Move" label
        - grid_select: has task-image elements (9 images in a grid)
        """
        try:
            # Check for canvas element (used by drag-drop challenges)
            canvas = await frame.query_selector("canvas")
            if canvas:
                # Also check for drag-specific elements
                prompt_text = await frame.query_selector(".prompt-text")
                if prompt_text:
                    text = await prompt_text.inner_text()
                    if "drag" in text.lower() or "move" in text.lower():
                        return "drag_drop"
                # Canvas without grid images = drag_drop
                task_images = await frame.query_selector_all(".task-image")
                if len(task_images) == 0:
                    return "drag_drop"
                return "grid_select"

            # No canvas but has task images = grid_select
            task_images = await frame.query_selector_all(".task-image")
            if len(task_images) >= 9:
                return "grid_select"

            # Check for other grid selectors
            for sel in [".image-wrapper", "[class*=\"task\"]", ".challenge-image"]:
                elements = await frame.query_selector_all(sel)
                if len(elements) >= 9:
                    return "grid_select"

        except Exception as e:
            logger.debug("Challenge type detection error: %s", e)

        return "unknown"

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

    async def _analyze_challenge(self, challenge_type: str) -> CaptchaSolution:
        """Screenshot the challenge and send to Vision API for analysis.

        Uses the pre-detected challenge_type to select the right prompt.
        For drag_drop: crops to canvas and extracts coordinates.
        For grid_select: uses full-page screenshot to identify grid cells.
        """
        frame = await self._detect_challenge_frame()
        if not frame:
            return CaptchaSolution(challenge_type=challenge_type)

        await self.page.screenshot(path="/tmp/hcaptcha_challenge.png")

        if challenge_type == "drag_drop":
            return await self._analyze_drag(frame)
        elif challenge_type == "grid_select":
            return await self._analyze_grid(frame)

        return CaptchaSolution(challenge_type=challenge_type)

    async def _analyze_drag(self, frame: Frame) -> CaptchaSolution:
        """Analyze drag-drop challenge: crop canvas, get coordinates from Vision.

        Returns Vision coordinates in canvas-relative CSS space (0-500, 0-470).
        The _solve_drag method handles conversion to iframe viewport coords.
        """
        canvas_box = None
        try:
            canvas = await frame.query_selector("canvas")
            if canvas:
                canvas_box = await canvas.bounding_box()
        except Exception:
            pass

        if not canvas_box:
            logger.warning("No canvas element found for drag analysis")
            return CaptchaSolution(challenge_type="drag_drop")

        # Crop to canvas area
        from PIL import Image
        img = Image.open("/tmp/hcaptcha_challenge.png")
        x, y = int(canvas_box["x"]), int(canvas_box["y"])
        w, h = int(canvas_box["width"]), int(canvas_box["height"])
        cropped = img.crop((x, y, x + w, y + h))
        cropped_path = "/tmp/hcaptcha_cropped.png"
        cropped.save(cropped_path)
        logger.info("Canvas at (%d,%d) %dx%d, cropped for drag analysis", x, y, w, h)

        with open(cropped_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        raw = await self.vision.analyze_image(img_b64, HCAPTCHA_DRAG_PROMPT)
        logger.info("Vision drag raw: %s", raw)

        drag_start = raw.get("drag_start")
        drag_end = raw.get("drag_end")

        # Return raw Vision coordinates (canvas-relative CSS space)
        start = (drag_start["x"], drag_start["y"]) if drag_start else None
        end = (drag_end["x"], drag_end["y"]) if drag_end else None

        if start:
            logger.info("Vision drag_start: canvas CSS (%.0f, %.0f)", *start)
        if end:
            logger.info("Vision drag_end: canvas CSS (%.0f, %.0f)", *end)

        return CaptchaSolution(
            challenge_type="drag_drop",
            instruction=raw.get("instruction", ""),
            drag_start=start,
            drag_end=end,
            has_verify=raw.get("has_verify", False),
        )

    async def _analyze_grid(self, frame: Frame) -> CaptchaSolution:
        """Analyze grid_select challenge: identify cells to click via Vision."""
        with open("/tmp/hcaptcha_challenge.png", "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        raw = await self.vision.analyze_image(img_b64, HCAPTCHA_GRID_PROMPT)
        logger.info("Vision grid raw: %s", raw)

        return CaptchaSolution(
            challenge_type="grid_select",
            instruction=raw.get("instruction", ""),
            cells_to_click=raw.get("cells_to_click", []),
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

    async def _solve_drag(self, solution: CaptchaSolution, frame: Frame):
        """Solve drag-drop using page.mouse for trusted events.

        Vision returns canvas-relative CSS coordinates (0-500, 0-470).
        We convert to page viewport coordinates: canvas_page_pos + vision_coords.
        page.mouse dispatches CDP-level events (isTrusted=true) that propagate
        to cross-origin iframes.
        """
        if not solution.drag_start or not solution.drag_end:
            logger.warning("Drag solution missing coordinates")
            return

        # Get canvas page position
        canvas = await frame.query_selector("canvas")
        if not canvas:
            logger.warning("No canvas element")
            return
        canvas_box = await canvas.bounding_box()
        if not canvas_box:
            logger.warning("Could not get canvas bounding box")
            return

        # Vision coords are in canvas CSS space (0-500, 0-470)
        # Page viewport coords = canvas_page_pos + vision_coords
        vis_sx, vis_sy = solution.drag_start
        vis_ex, vis_ey = solution.drag_end

        page_sx = canvas_box["x"] + vis_sx
        page_sy = canvas_box["y"] + vis_sy
        page_ex = canvas_box["x"] + vis_ex
        page_ey = canvas_box["y"] + vis_ey

        logger.info(
            "Drag: vision(%.0f,%.0f)->(%.0f,%.0f) page(%.0f,%.0f)->(%.0f,%.0f)",
            vis_sx, vis_sy, vis_ex, vis_ey,
            page_sx, page_sy, page_ex, page_ey,
        )

        # Approach with slight offset (human-like)
        await self.page.mouse.move(
            page_sx + random.uniform(-3, 3),
            page_sy + random.uniform(-3, 3),
        )
        await asyncio.sleep(random.uniform(0.2, 0.4))
        await self.page.mouse.move(page_sx, page_sy)
        await asyncio.sleep(random.uniform(0.1, 0.2))
        await self.page.mouse.down()
        await asyncio.sleep(random.uniform(0.2, 0.4))

        # Smooth drag trajectory
        steps = 25
        trajectory = generate_bezier_trajectory(
            (page_sx, page_sy), (page_ex, page_ey), steps=steps,
        )
        delays = generate_dynamic_delays(steps, base_delay=25.0)

        for (x, y), delay in zip(trajectory, delays):
            await self.page.mouse.move(x, y)
            await asyncio.sleep(delay / 1000.0)

        # Small overshoot and settle
        await self.page.mouse.move(
            page_ex + random.uniform(-3, 3),
            page_ey + random.uniform(-3, 3),
        )
        await asyncio.sleep(random.uniform(0.1, 0.2))
        await self.page.mouse.move(page_ex, page_ey)
        await asyncio.sleep(random.uniform(0.15, 0.3))
        await self.page.mouse.up()

        logger.info("Drag completed: (%.0f,%.0f) -> (%.0f,%.0f)",
                     page_sx, page_sy, page_ex, page_ey)

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
