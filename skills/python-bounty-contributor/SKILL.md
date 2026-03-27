---
name: python-bounty-contributor
description: "Python 赏金贡献技能包。用于为开源项目（尤其是 RustChain 生态）生成 Python 代码。覆盖：脚本工具、API 客户端、数据处理、自动化脚本、测试。当赏金要求 Python 代码或需要编写辅助工具时使用。"
metadata:
  {
    "openclaw":
      {
        "emoji": "🐍",
        "requires": { "bins": ["curl", "python3"], "env": ["GH_TOKEN"] },
      },
  }
---

# Python 赏金贡献者

**核心原则**: 生成的 Python 代码必须可运行、有错误处理、符合 PEP 8、包含类型提示。

---

## 代码风格标准

```python
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
```

---

## GitHub API 工具集

### 文件操作

```python
import base64
import requests


class GitHubAPI:
    """GitHub API 封装"""

    def __init__(self, token: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        self.base_url = "https://api.github.com"

    def get_file(self, repo: str, path: str, branch: str = "main") -> dict:
        """获取文件内容和 SHA"""
        url = f"{self.base_url}/repos/{repo}/contents/{path}"
        resp = self.session.get(url, params={"ref": branch})
        resp.raise_for_status()
        return resp.json()

    def create_file(
        self,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str,
    ) -> dict:
        """创建新文件"""
        url = f"{self.base_url}/repos/{repo}/contents/{path}"
        encoded = base64.b64encode(content.encode()).decode()
        payload = {
            "message": message,
            "content": encoded,
            "branch": branch,
        }
        resp = self.session.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    def update_file(
        self,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str,
        sha: str,
    ) -> dict:
        """更新已有文件"""
        url = f"{self.base_url}/repos/{repo}/contents/{path}"
        encoded = base64.b64encode(content.encode()).decode()
        payload = {
            "message": message,
            "content": encoded,
            "branch": branch,
            "sha": sha,
        }
        resp = self.session.put(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    def create_branch(self, repo: str, branch: str, from_sha: str) -> dict:
        """创建新分支"""
        url = f"{self.base_url}/repos/{repo}/git/refs"
        payload = {"sha": from_sha, "ref": f"refs/heads/{branch}"}
        resp = self.session.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    def create_pr(
        self,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str = "main",
    ) -> dict:
        """创建 Pull Request"""
        url = f"{self.base_url}/repos/{repo}/pulls"
        payload = {
            "title": title,
            "body": body,
            "head": head,
            "base": base,
        }
        resp = self.session.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    def comment_on_issue(self, repo: str, issue_number: int, body: str) -> dict:
        """在 issue 上评论"""
        url = f"{self.base_url}/repos/{repo}/issues/{issue_number}/comments"
        resp = self.session.post(url, json={"body": body})
        resp.raise_for_status()
        return resp.json()

    def fork_repo(self, repo: str) -> dict:
        """Fork 仓库"""
        url = f"{self.base_url}/repos/{repo}/forks"
        resp = self.session.post(url)
        resp.raise_for_status()
        return resp.json()
```

---

## 常见赏金任务模板

### 健康检查脚本

```python
#!/usr/bin/env python3
"""RustChain Node Health Check"""

import json
import sys
from datetime import datetime, timezone

import requests


def check_node_status(rpc_url: str) -> dict:
    """检查节点状态"""
    try:
        # 检查区块高度
        resp = requests.post(
            rpc_url,
            json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1},
            timeout=10,
        )
        resp.raise_for_status()
        block_number = int(resp.json()["result"], 16)

        # 检查同步状态
        resp = requests.post(
            rpc_url,
            json={"jsonrpc": "2.0", "method": "eth_syncing", "params": [], "id": 2},
            timeout=10,
        )
        resp.raise_for_status()
        syncing = resp.json()["result"]

        return {
            "status": "healthy" if not syncing else "syncing",
            "block_height": block_number,
            "syncing": syncing,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    except requests.RequestException as e:
        return {"status": "unhealthy", "error": str(e)}


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8545"
    result = check_node_status(url)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "healthy" else 1)
```

### 数据处理 / 统计脚本

```python
#!/usr/bin/env python3
"""RustChain Contributor Statistics"""

import csv
from collections import Counter
from pathlib import Path


def analyze_contributors(ledger_path: str) -> list[dict]:
    """分析贡献者统计数据"""
    counter = Counter()

    with open(ledger_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            wallet = row.get("wallet", "unknown")
            amount = int(row.get("amount", 0))
            counter[wallet] += amount

    return [
        {"wallet": wallet, "total_rtc": total}
        for wallet, total in counter.most_common()
    ]


def export_report(data: list[dict], output_path: str) -> None:
    """导出报告为 CSV"""
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["wallet", "total_rtc"])
        writer.writeheader()
        writer.writerows(data)
```

### Star 追踪器（社区任务）

```python
#!/usr/bin/env python3
"""RustChain Star Tracker - 追踪仓库 star 数量变化"""

import json
import time
from pathlib import Path

import requests


STAR_LOG = Path("star_history.json")


def get_stars(repo: str) -> int:
    """获取仓库 star 数量"""
    resp = requests.get(
        f"https://api.github.com/repos/{repo}",
        headers={"Accept": "application/vnd.github+json"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["stargazers_count"]


def record_stars(repos: list[str]) -> dict:
    """记录当前 star 数量"""
    snapshot = {}
    for repo in repos:
        try:
            stars = get_stars(repo)
            snapshot[repo] = {"stars": stars, "timestamp": time.time()}
        except requests.RequestException as e:
            snapshot[repo] = {"error": str(e), "timestamp": time.time()}

    # 追加到历史记录
    history = []
    if STAR_LOG.exists():
        history = json.loads(STAR_LOG.read_text())
    history.append(snapshot)
    STAR_LOG.write_text(json.dumps(history, indent=2))

    return snapshot
```

---

## 错误处理规范

```python
"""正确的错误处理模式"""

# 1. 使用自定义异常
class BountyError(Exception):
    """赏金操作基础异常"""
    pass


class ClaimConflictError(BountyError):
    """赏金已被认领"""
    pass


class InsufficientFundsError(BountyError):
    """余额不足"""
    pass


# 2. 使用 result 模式（不抛异常）
from dataclasses import dataclass
from typing import TypeVar, Union

T = TypeVar("T")

@dataclass
class Result:
    success: bool
    data: T | None = None
    error: str | None = None


def safe_claim_bounty(issue: int) -> Result:
    try:
        # ... 操作逻辑
        return Result(success=True, data={"issue": issue})
    except requests.Timeout:
        return Result(success=False, error="API timeout")
    except requests.HTTPError as e:
        if e.response.status_code == 409:
            return Result(success=False, error="Already claimed")
        return Result(success=False, error=f"HTTP {e.response.status_code}")
```

---

## 测试模板

```python
"""测试模板"""
import json
from unittest.mock import patch, MagicMock

import pytest
import requests


class TestFetchBounties:
    """赏金获取测试"""

    @patch("requests.get")
    def test_returns_sorted_bounties(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {
                "number": 1,
                "title": "Easy task",
                "labels": [{"name": "bounty"}, {"name": "5-rtc"}],
                "html_url": "https://github.com/test/repo/issues/1",
            },
            {
                "number": 2,
                "title": "Hard task",
                "labels": [{"name": "bounty"}, {"name": "50-rtc"}],
                "html_url": "https://github.com/test/repo/issues/2",
            },
        ]
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        bounties = fetch_bounties("test/repo", "fake_token")
        assert len(bounties) == 2
        assert bounties[0].reward_rtc == 50  # 高奖励排前面

    def test_parse_reward_from_labels(self):
        assert _parse_reward_from_labels([{"name": "25-rtc"}]) == 25
        assert _parse_reward_from_labels([{"name": "1-4-rtc"}]) == 4
        assert _parse_reward_from_labels([{"name": "other"}]) == 0
```
