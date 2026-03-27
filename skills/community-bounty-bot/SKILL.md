---
name: community-bounty-bot
description: "社区赏金自动化技能包。用于自动化完成 RustChain 社区任务：star 仓库、关注账号、社交媒体互动、截图证明。这是低门槛、稳定收益的自动化路径。当需要：批量完成社区任务、追踪 star 进度、生成任务证明时使用。"
metadata:
  {
    "openclaw":
      {
        "emoji": "🤖",
        "requires": { "bins": ["curl", "python3"], "env": ["GH_TOKEN"] },
      },
  }
---

# 社区赏金自动化

**核心原则**: 自动化完成零代码的社区任务，稳定积累 RTC。每个任务必须提供可验证的证明。

---

## 社区任务类型

| 任务 | 操作 | 难度 | 典型奖励 |
|------|------|------|----------|
| Star 仓库 | GitHub star | 自动 | 0.25 - 2 RTC |
| Follow 账号 | GitHub follow | 自动 | 0.25 - 1 RTC |
| Fork 仓库 | GitHub fork | 自动 | 0.25 - 1 RTC |
| 截图证明 | 提供截图 | 需要人工 | 1 - 5 RTC |
| 社媒发帖 | X/Twitter/Telegram | 需要人工 | 1 - 25 RTC |
| 博客文章 | 写教程/文章 | 半自动 | 5 - 50 RTC |

---

## 自动化 Star 任务

### 扫描 Star 赏金

```python
#!/usr/bin/env python3
"""扫描需要 star 的赏金 issue"""

import re
import requests

GH_TOKEN = "YOUR_GH_TOKEN"
REPO = "Scottcjn/rustchain-bounties"


def scan_star_bounties() -> list[dict]:
    """找出所有 star 类赏金"""
    url = f"https://api.github.com/repos/{REPO}/issues"
    headers = {
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    params = {"state": "open", "labels": "bounty", "per_page": 100}

    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()

    star_bounties = []
    for issue in resp.json():
        body = issue.get("body", "") or ""
        title = issue.get("title", "")

        # 检测 star 相关任务
        star_keywords = ["star", "star the repo", "give us a star"]
        if any(kw in body.lower() or kw in title.lower() for kw in star_keywords):
            # 提取需要 star 的仓库
            repos_to_star = extract_repos(body)
            star_bounties.append({
                "issue": issue["number"],
                "title": title,
                "repos": repos_to_star,
                "url": issue["html_url"],
            })

    return star_bounties


def extract_repos(text: str) -> list[str]:
    """从 issue 描述中提取 GitHub 仓库地址"""
    pattern = r"github\.com/([\w-]+/[\w.-]+)"
    matches = re.findall(pattern, text)
    # 去重并过滤掉赏金仓库本身
    return list(set(m for m in matches if m != REPO))
```

### 执行 Star

```python
def star_repo(owner: str, repo: str, token: str) -> bool:
    """Star 一个 GitHub 仓库"""
    url = f"https://api.github.com/user/starred/{owner}/{repo}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    resp = requests.put(url, headers=headers, timeout=10)
    return resp.status_code in (204, 200)  # 204 = already starred, 200 = starred


def check_starred(owner: str, repo: str, token: str) -> bool:
    """检查是否已 star"""
    url = f"https://api.github.com/user/starred/{owner}/{repo}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.star+json",
    }
    resp = requests.get(url, headers=headers, timeout=10)
    return resp.status_code == 204


def batch_star(repos: list[str], token: str) -> dict:
    """批量 star 仓库"""
    results = {}
    for repo_full in repos:
        parts = repo_full.split("/")
        if len(parts) != 2:
            results[repo_full] = "invalid format"
            continue

        owner, name = parts
        already = check_starred(owner, name, token)
        if already:
            results[repo_full] = "already starred"
            continue

        success = star_repo(owner, name, token)
        results[repo_full] = "starred" if success else "failed"

    return results
```

### 提交 Star 证明

```python
def claim_star_bounty(
    repo: str,
    issue_number: int,
    starred_repos: list[str],
    wallet_address: str,
    token: str,
) -> dict:
    """在 issue 上评论 star 证明"""
    repo_lines = "\n".join(f"- ⭐ {r}" for r in starred_repos)

    body = f"""Completed all star requirements!

{repo_lines}

Verification: Check my GitHub profile for starred repos.

**Wallet:** {wallet_address}
"""

    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    resp = requests.post(url, headers=headers, json={"body": body}, timeout=10)
    resp.raise_for_status()
    return resp.json()
```

---

## 自动化 Follow 任务

```python
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
```

---

## 完整自动化流程

```python
#!/usr/bin/env python3
"""RustChain 社区赏金自动化 bot"""

import json
import logging
import time
from pathlib import Path
from datetime import datetime

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

CONFIG = {
    "gh_token": "YOUR_GH_TOKEN",
    "bounty_repo": "Scottcjn/rustchain-bounties",
    "wallet": "YOUR_RTC_WALLET",
    "state_file": Path("community_bounty_state.json"),
}


def load_state() -> dict:
    """加载已完成的任务状态"""
    if CONFIG["state_file"].exists():
        return json.loads(CONFIG["state_file"].read_text())
    return {"claimed": [], "starred": [], "followed": []}


def save_state(state: dict) -> None:
    """保存任务状态"""
    CONFIG["state_file"].write_text(json.dumps(state, indent=2))


def run_community_bot() -> None:
    """主执行循环"""
    state = load_state()
    headers = {
        "Authorization": f"Bearer {CONFIG['gh_token']}",
        "Accept": "application/vnd.github+json",
    }

    # 1. 扫描开放社区赏金
    url = f"https://api.github.com/repos/{CONFIG['bounty_repo']}/issues"
    resp = requests.get(url, headers=headers, params={
        "state": "open", "labels": "bounty", "per_page": 100,
    }, timeout=30)
    resp.raise_for_status()

    for issue in resp.json():
        issue_num = issue["number"]
        if issue_num in state["claimed"]:
            continue

        body = (issue.get("body", "") or "").lower()

        # 检测社区任务
        is_community = any(
            label["name"] in ("community", "propagation")
            for label in issue.get("labels", [])
        )

        if not is_community:
            continue

        # 尝试自动完成
        completed_actions = []

        # Star 任务
        if "star" in body:
            repos = extract_repos(issue.get("body", ""))
            for repo in repos:
                if repo not in state["starred"]:
                    parts = repo.split("/")
                    if len(parts) == 2:
                        if star_repo(parts[0], parts[1], CONFIG["gh_token"]):
                            state["starred"].append(repo)
                            completed_actions.append(f"⭐ Starred {repo}")
                            logger.info(f"Starred {repo}")
                        time.sleep(1)  # 避免 rate limit

        # Follow 任务
        if "follow" in body:
            # 提取用户名
            usernames = extract_usernames(issue.get("body", ""))
            for username in usernames:
                if username not in state["followed"]:
                    if follow_user(username, CONFIG["gh_token"]):
                        state["followed"].append(username)
                        completed_actions.append(f"👤 Followed @{username}")
                        logger.info(f"Followed @{username}")
                    time.sleep(1)

        # 如果完成了任何操作，提交证明
        if completed_actions:
            claim_text = "\n".join(completed_actions)
            claim_body = f"""Completed the following:

{claim_text}

Timestamp: {datetime.utcnow().isoformat()}

**Wallet:** {CONFIG['wallet']}
"""
            comment_url = f"{url}/{issue_num}/comments"
            requests.post(comment_url, headers=headers,
                        json={"body": claim_body}, timeout=10)
            state["claimed"].append(issue_num)
            save_state(state)
            logger.info(f"Claimed bounty #{issue_num}")

    logger.info("Community bot cycle complete")


if __name__ == "__main__":
    run_community_bot()
```

---

## Rate Limit 管理

GitHub API 限制：认证用户 5000 req/hour

```python
import time

class RateLimiter:
    """GitHub API 速率限制器"""

    def __init__(self, max_per_hour: int = 4500):
        self.max_per_hour = max_per_hour
        self.requests = []

    def wait_if_needed(self) -> None:
        """如果接近限制则等待"""
        now = time.time()
        # 清理超过 1 小时的记录
        self.requests = [t for t in self.requests if now - t < 3600]

        if len(self.requests) >= self.max_per_hour - 100:
            oldest = self.requests[0]
            wait_time = 3600 - (now - oldest) + 10
            logger.warning(f"Rate limit approaching, waiting {wait_time:.0f}s")
            time.sleep(wait_time)

        self.requests.append(now)
```

---

## 日志记录

```python
def log_action(action: str, target: str, result: str, rtc_earned: float = 0) -> None:
    """记录每次操作"""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        "target": target,
        "result": result,
        "rtc_earned": rtc_earned,
    }

    log_file = Path("bounty_actions.log")
    with open(log_file, "a") as f:
        f.write(json.dumps(log_entry) + "\n")
```
