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

Determine:
1. Challenge type: "grid_select" (click images matching criteria), "drag_drop" (drag piece to match), or "checkbox" (already solved)
2. For grid_select: What is the instruction? Which grid cells (numbered 1-9 left-to-right, top-to-bottom) should be clicked?
3. For drag_drop: Describe the draggable piece and where it should be placed. Give approximate pixel coordinates of the drag start and drop target relative to the full image.
4. Is there a "Verify" or "Skip" button visible?

Reply ONLY in JSON format:
{"type": "grid_select|drag_drop|checkbox", "instruction": "...", "cells_to_click": [1,2,3], "drag_start": {"x": 0, "y": 0}, "drag_end": {"x": 0, "y": 0}, "has_verify": true}"""

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
