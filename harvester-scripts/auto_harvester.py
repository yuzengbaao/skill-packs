"""RustChain 智能收割器

从 bounty_queue.log 读取待处理赏金，按类型分流：
- community 标签或含 star/follow 关键词 → 调用 community_executor 自动执行
- code 标签 → 生成实质性认领评论（分析需求 + 方案）
- 其他 → 生成通用认领评论

严格去重，绝不重复处理同一 issue。
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

from community_executor import (
    execute_community_bounty,
    load_state,
    save_state,
    extract_repos,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("GH_TOKEN", "")
WALLET = os.environ.get("RTC_WALLET", "RTC0816b68b604630945c94cde35da4641a926aa4fd")
BOUNTY_REPO = "Scottcjn/rustchain-bounties"
QUEUE_FILE = Path("/root/.openclaw/workspace/bounty_queue.log")

SESSION = requests.Session()
SESSION.headers.update({
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
})


def get_issue_body(issue_number: int) -> dict:
    """获取 issue 完整内容"""
    url = f"https://api.github.com/repos/{BOUNTY_REPO}/issues/{issue_number}"
    resp = SESSION.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_issue_comments(issue_number: int) -> list[dict]:
    """获取 issue 评论列表"""
    url = f"https://api.github.com/repos/{BOUNTY_REPO}/issues/{issue_number}/comments"
    resp = SESSION.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()


def is_already_claimed(comments: list[dict]) -> bool:
    """检查是否已被他人认领"""
    for comment in comments:
        author = comment.get("user", {}).get("login", "")
        body = (comment.get("body", "") or "").lower()
        if author != "yuzengbaao" and "i would like to work on this" in body:
            return True
    return False


def post_comment(issue_number: int, body: str) -> bool:
    """发布评论"""
    url = f"https://api.github.com/repos/{BOUNTY_REPO}/issues/{issue_number}/comments"
    resp = SESSION.post(url, json={"body": body}, timeout=10)
    return resp.status_code == 201


def extract_requirements(body: str) -> list[str]:
    """从 issue body 提取 Requirements 列表"""
    requirements = []
    in_requirements = False
    for line in body.split("\n"):
        stripped = line.strip()
        if "### requirements" in stripped.lower() or "requirements:" in stripped.lower():
            in_requirements = True
            continue
        if in_requirements and stripped.startswith("###"):
            break
        if in_requirements and (stripped.startswith("- ") or stripped.startswith("* ")):
            requirements.append(stripped[2:])
        elif in_requirements and re.match(r"^\d+\.", stripped):
            requirements.append(re.sub(r"^\d+\.\s*", "", stripped))
    return requirements[:10]  # 最多 10 条


def extract_reward(body: str, title: str) -> str:
    """提取奖励金额"""
    combined = title + " " + body
    match = re.search(r"(\d[\d,]*\.?\d*)\s*RTC", combined)
    if match:
        return match.group(1).replace(",", "") + " RTC"
    return "Unknown"


def generate_code_claim(issue_number: int, title: str, body: str, labels: list[str]) -> str:
    """为代码类赏金生成实质性认领评论"""
    requirements = extract_requirements(body)
    reward = extract_reward(body, title)
    label_str = ", ".join(f"`{l}`" for l in labels if l != "bounty")

    req_section = ""
    if requirements:
        req_items = "\n".join(f"  - {r}" for r in requirements)
        req_section = f"\n**Requirements understood:**\n{req_items}"

    approach_section = ""
    if "sdk" in body.lower() or "sdk" in title.lower():
        approach_section = "\n**Approach:** Create a Python SDK with typed functions for core RPC endpoints (balance, epoch, attestation), full error handling, and pytest test suite."
    elif "cli" in body.lower() or "command" in title.lower():
        approach_section = "\n**Approach:** Implement using `clap` (Rust) or `argparse` (Python) with subcommands, proper error messages, and man-page generation."
    elif "test" in body.lower() or "testing" in title.lower():
        approach_section = "\n**Approach:** Write comprehensive tests covering edge cases, use mocking for external dependencies, ensure CI integration."
    elif "api" in body.lower() or "endpoint" in title.lower():
        approach_section = "\n**Approach:** Implement REST API endpoints with proper input validation, error responses, and OpenAPI documentation."
    else:
        approach_section = "\n**Approach:** Will analyze the codebase structure, follow existing patterns, implement the required changes with proper error handling and tests."

    return f"""I would like to work on this.

**Issue:** #{issue_number} — {title}
**Reward:** {reward}
**Labels:** {label_str}
{req_section}
{approach_section}

**Wallet:** {WALLET}"""


def generate_generic_claim(issue_number: int, title: str, body: str) -> str:
    """为非代码类赏金生成认领评论"""
    reward = extract_reward(body, title)

    return f"""I would like to work on this.

**Issue:** #{issue_number} — {title}
**Reward:** {reward}

I have read the requirements and will complete this task.

**Wallet:** {WALLET}"""


def harvest() -> None:
    """主收割逻辑"""
    state = load_state()

    if not QUEUE_FILE.exists():
        logger.info("队列为空，无待处理赏金")
        return

    lines = QUEUE_FILE.read_text().splitlines()
    remaining = []
    processed = 0

    for line in lines:
        line = line.strip()
        if not line or "BOUNTY FOUND" not in line:
            remaining.append(line)
            continue

        # 解析 issue 编号
        match = re.search(r"issues/(\d+)", line)
        if not match:
            remaining.append(line)
            continue

        issue_num = int(match.group(1))

        # 严格去重
        if issue_num in state["claimed_issues"]:
            continue

        # 提取标题信息
        parts = line.split(" | ")
        title_info = parts[1] if len(parts) > 1 else "Unknown"

        logger.info(f"处理 Issue #{issue_num}: {title_info}")

        try:
            issue_data = get_issue_body(issue_num)
            comments = get_issue_comments(issue_num)

            # 检查是否已被他人认领
            if is_already_claimed(comments):
                logger.info(f"  Issue #{issue_num} 已被他人认领，跳过")
                state["claimed_issues"].append(issue_num)
                continue

            body_text = issue_data.get("body", "") or ""
            title_text = issue_data.get("title", "")
            labels = [l["name"] for l in issue_data.get("labels", [])]
            body_lower = body_text.lower()

            # 按类型分流
            is_community = "community" in labels or "propagation" in labels
            has_star_follow = "star" in body_lower or "follow" in body_lower
            is_code = "code" in labels

            if is_community or has_star_follow:
                # 社区任务 → 自动执行
                result = execute_community_bounty(issue_num)
                if result.success:
                    logger.info(f"  社区任务完成: {', '.join(result.actions)}")
                else:
                    logger.info(f"  社区任务无自动可执行项")
                state["claimed_issues"].append(issue_num)

            elif is_code:
                # 代码任务 → 实质性认领
                claim = generate_code_claim(issue_num, title_text, body_text, labels)
                if post_comment(issue_num, claim):
                    logger.info(f"  代码认领评论已提交")
                    state["claimed_issues"].append(issue_num)
                else:
                    logger.error(f"  评论提交失败")
                    remaining.append(line)

            else:
                # 其他类型 → 通用认领
                claim = generate_generic_claim(issue_num, title_text, body_text)
                if post_comment(issue_num, claim):
                    logger.info(f"  认领评论已提交")
                    state["claimed_issues"].append(issue_num)
                else:
                    logger.error(f"  评论提交失败")
                    remaining.append(line)

            processed += 1
            time.sleep(2)  # API rate limit

        except requests.RequestException as e:
            logger.error(f"  处理失败: {e}")
            remaining.append(line)

    # 更新队列文件（移除已处理的行）
    QUEUE_FILE.write_text("\n".join(remaining) + "\n" if remaining else "")
    save_state(state)

    logger.info(f"收割完成: 处理 {processed} 个，剩余 {len([l for l in remaining if 'BOUNTY FOUND' in l])} 个")


if __name__ == "__main__":
    harvest()
