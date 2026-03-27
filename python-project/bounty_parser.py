"""模块文档字符串"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class BountyInfo:
    """赏金信息数据类"""
    issue_number: int
    title: str
    reward_rtc: int
    labels: list[str] = field(default_factory=list)
    url: str = ""
    status: str = "open"


def fetch_bounties(repo: str, token: str) -> list[BountyInfo]:
    """获取开放赏金列表"""
    url = f"https://api.github.com/repos/{repo}/issues"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    params = {
        "state": "open",
        "labels": "bounty",
        "per_page": 30,
    }

    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()

    bounties = []
    for issue in resp.json():
        reward = _parse_reward_from_labels(issue.get("labels", []))
        if reward > 0:
            bounties.append(BountyInfo(
                issue_number=issue["number"],
                title=issue["title"],
                reward_rtc=reward,
                labels=[l["name"] for l in issue.get("labels", [])],
                url=issue["html_url"],
            ))

    return sorted(bounties, key=lambda b: b.reward_rtc, reverse=True)


def _parse_reward_from_labels(labels: list[dict]) -> int:
    """从标签解析奖励金额"""
    for label in labels:
        name = label.get("name", "")
        if "rtc" in name.lower():
            # "25-rtc" → 25, "1-4-rtc" → 4 (取上限)
            parts = name.replace("-rtc", "").split("-")
            try:
                return max(int(p) for p in parts if p.isdigit())
            except ValueError:
                continue
    return 0
