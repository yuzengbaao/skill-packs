"""社区赏金自动化工具 — 从 SKILL.md 提取的独立函数版本"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


def star_repo(owner: str, repo: str, token: str) -> bool:
    """Star 一个 GitHub 仓库"""
    url = f"https://api.github.com/user/starred/{owner}/{repo}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    resp = requests.put(url, headers=headers, timeout=10)
    return resp.status_code in (204, 200)


def check_starred(owner: str, repo: str, token: str) -> bool:
    """检查是否已 star"""
    url = f"https://api.github.com/user/starred/{owner}/{repo}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.star+json",
    }
    resp = requests.get(url, headers=headers, timeout=10)
    return resp.status_code == 204


def follow_user(username: str, token: str) -> bool:
    """关注 GitHub 用户"""
    url = f"https://api.github.com/user/following/{username}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    resp = requests.put(url, headers=headers, timeout=10)
    return resp.status_code in (204, 200)


def check_following(username: str, token: str) -> bool:
    """检查是否已关注"""
    url = f"https://api.github.com/user/following/{username}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    resp = requests.get(url, headers=headers, timeout=10)
    return resp.status_code == 204
