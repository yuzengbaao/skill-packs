"""GLM-5 Vision API client for CAPTCHA analysis."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

HCAPTCHA_PROMPT = """Analyze this hCaptcha challenge screenshot carefully.

Determine the challenge type:
1. "grid_select" — a 3x3 grid of images, click those matching the instruction
2. "drag_drop" — a puzzle piece that must be dragged to fit into the image
3. "checkbox" — already solved (no challenge visible)

For grid_select:
- What is the instruction text (e.g. "select all images with a boat")?
- Which grid cells (numbered 1-9, left-to-right top-to-bottom) should be clicked?

For drag_drop:
- Locate the draggable puzzle piece (usually on the right side)
- Locate where it should be placed (the gap/hole in the image)
- Give pixel coordinates of the CENTER of the drag piece (drag_start) and the CENTER of the target hole (drag_end)
- Coordinates must be relative to the image top-left corner

Reply ONLY in JSON:
{"type": "grid_select|drag_drop|checkbox", "instruction": "...", "cells_to_click": [1,2,3], "drag_start": {"x": 0, "y": 0}, "drag_end": {"x": 0, "y": 0}, "has_verify": true}"""

HCAPTCHA_DRAG_PROMPT = """This is a cropped screenshot of an hCaptcha DRAG-DROP puzzle (500x470 pixels or similar).

The puzzle shows geometric shapes on a textured background. There is a gap/hole in the pattern on the LEFT side, and a matching puzzle piece on the RIGHT side (usually in a "Move" area).

Your task: Find the EXACT pixel coordinates of:
1. drag_start: CENTER of the draggable puzzle piece (the piece on the right that needs to be moved)
2. drag_end: CENTER of the target hole/gap (where the piece should be placed on the left)

IMPORTANT:
- Coordinates must be relative to the TOP-LEFT corner of THIS image
- Be as precise as possible (within 5-10 pixels)
- Look carefully at which shape in the pattern has a visible gap/outline
- The matching piece is the one that fills that gap

Reply ONLY in JSON:
{"instruction": "...", "drag_start": {"x": 100, "y": 200}, "drag_end": {"x": 300, "y": 400}, "has_verify": false}"""

HCAPTCHA_GRID_PROMPT = """This is a screenshot of an hCaptcha GRID SELECT challenge.

There is a 3x3 grid of images. An instruction text tells you which images to select.

Your task:
1. Read the instruction text exactly
2. Identify which grid cells (1-9, left-to-right top-to-bottom) match the instruction
3. Only select cells that clearly match — when in doubt, exclude

Reply ONLY in JSON:
{"instruction": "select all images with ...", "cells_to_click": [1, 2, 3], "has_verify": true}"""

ARKOSE_PROMPT = """Analyze this Arkose Labs FunCaptcha challenge screenshot.

Determine:
1. Challenge type: "image_grid", "puzzle_rotation", "audio", or "unknown"
2. For image_grid: What is the instruction? Which cells should be selected?
3. For puzzle_rotation: What approximate rotation angle is needed?
4. Is there a "Verify" button visible?

Reply ONLY in JSON format:
{"type": "image_grid|puzzle_rotation|audio|unknown", "instruction": "...", "cells_to_click": [1,2,3], "rotation_angle": 0, "has_verify": true}"""


def extract_json(text: str) -> dict[str, Any]:
    """Extract JSON from LLM response."""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return {}


@dataclass
class VisionClient:
    base_url: str = field(
        default_factory=lambda: os.environ.get(
            "ANTHROPIC_BASE_URL", "https://open.bigmodel.cn/api/anthropic"
        )
    )
    api_key: str = field(
        default_factory=lambda: os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
    )
    model: str = field(
        default_factory=lambda: os.environ.get(
            "ANTHROPIC_DEFAULT_SONNET_MODEL", "glm-5"
        )
    )
    max_retries: int = 3

    async def analyze_image(
        self, image_b64: str, prompt: str
    ) -> dict[str, Any]:
        """Send image to GLM-5 Vision API, return parsed JSON."""
        url = f"{self.base_url}/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                    if resp.status_code == 200:
                        text = resp.json()["content"][0]["text"]
                        return extract_json(text)
                    last_error = f"HTTP {resp.status_code}"
            except Exception as e:
                last_error = str(e)

            if attempt < self.max_retries:
                wait = 2 ** attempt
                logger.warning(
                    "Vision API attempt %d/%d failed: %s, retrying in %ds",
                    attempt, self.max_retries, last_error, wait,
                )
                await asyncio.sleep(wait)

        logger.error("Vision API failed after %d attempts: %s", self.max_retries, last_error)
        return {}
