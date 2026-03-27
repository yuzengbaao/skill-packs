"""RustChain 赏金智能扫描器

直接查询 Scottcjn/rustchain-bounties 仓库的开放 issues，
按标签分类（community/code/其他），用 state.json 去重，
将新赏金写入 bounty_queue.log 供收割器处理。
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("GH_TOKEN", "")
BOUNTY_REPO = "Scottcjn/rustchain-bounties"
QUEUE_FILE = Path("/root/.openclaw/workspace/bounty_queue.log")
STATE_FILE = Path("/root/.openclaw/workspace/bounty_state.json")

SESSION = requests.Session()
SESSION.headers.update({
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
})


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"claimed_issues": [], "starred_repos": [], "followed_users": [], "forked_repos": [], "last_scan": ""}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def categorize_bounty(labels: list[dict]) -> str:
    """根据标签分类赏金类型"""
    label_names = {l["name"] for l in labels}
    if "community" in label_names or "propagation" in label_names:
        return "community"
    if "code" in label_names or "red-team" in label_names or "security" in label_names:
        return "code"
    if "content" in label_names:
        return "content"
    if "gaming" in label_names or "creative" in label_names:
        return "gaming"
    return "other"


def parse_reward_rtc(labels: list[dict]) -> int:
    """从标签解析 RTC 奖励金额"""
    for label in labels:
        name = label.get("name", "")
        if "rtc" in name.lower():
            parts = name.replace("-rtc", "").split("-")
            try:
                return max(int(p) for p in parts if p.isdigit())
            except ValueError:
                continue
    return 0


def get_existing_queue_urls() -> set[str]:
    """获取队列中已有的 URL（去重用）"""
    if not QUEUE_FILE.exists():
        return set()
    return {line.strip().split(" | ")[-1] for line in QUEUE_FILE.read_text().splitlines() if " | " in line}


def scan_bounties() -> dict:
    """扫描开放赏金，返回分类统计"""
    state = load_state()
    existing_urls = get_existing_queue_urls()

    url = f"https://api.github.com/repos/{BOUNTY_REPO}/issues"
    params = {"state": "open", "labels": "bounty", "per_page": 100}

    try:
        resp = SESSION.get(url, params=params, timeout=30)
        resp.raise_for_status()
        issues = resp.json()
    except requests.RequestException as e:
        logger.error(f"扫描赏金失败: {e}")
        return {}

    stats = {"total": len(issues), "new": 0, "skipped": 0, "by_type": {}}
    new_entries = []

    for issue in issues:
        issue_num = issue["number"]
        html_url = issue["html_url"]

        # 去重：已在 state 或队列中的跳过
        if issue_num in state["claimed_issues"] or html_url in existing_urls:
            stats["skipped"] += 1
            continue

        labels = issue.get("labels", [])
        category = categorize_bounty(labels)
        reward = parse_reward_rtc(labels)
        title = issue.get("title", "")

        entry = f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}] BOUNTY FOUND | {title} ({reward} RTC) [{category}] | {html_url}\n"
        new_entries.append(entry)

        stats["new"] += 1
        stats["by_type"][category] = stats["by_type"].get(category, 0) + 1
        logger.info(f"  新赏金 #{issue_num}: {title} ({reward} RTC) [{category}]")

    if new_entries:
        with open(QUEUE_FILE, "a") as f:
            f.writelines(new_entries)

    state["last_scan"] = datetime.now(timezone.utc).isoformat()
    save_state(state)

    logger.info(f"扫描完成: {stats['total']} 总计, {stats['new']} 新增, {stats['skipped']} 跳过")
    for cat, count in stats["by_type"].items():
        logger.info(f"  {cat}: {count}")

    return stats


if __name__ == "__main__":
    scan_bounties()
