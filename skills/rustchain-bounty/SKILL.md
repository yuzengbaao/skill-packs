---
name: rustchain-bounty
description: "RustChain 赏金猎人专业技能包。用于分析 RustChain bounties 仓库的 issue、理解赏金要求、认领任务、生成符合规范的提交。当需要：扫描开放赏金、分析赏金需求、认领 issue、检查赏金状态时使用。"
metadata:
  {
    "openclaw":
      {
        "emoji": "⛓️",
        "requires": { "bins": ["curl", "python3"], "env": ["GH_TOKEN"] },
      },
  }
---

# RustChain 赏金猎人

## 生态系统概览

**RustChain**: Proof-of-Antiquity 区块链，老旧硬件获得更高挖矿奖励。
**赏金仓库**: Scottcjn/rustchain-bounties
**代币**: RTC (1 RTC ≈ $0.10 USD)
**已发放**: 23,300+ RTC，218 位贡献者，716 笔交易

---

## 赏金分类与价值

| 类别 | 标签 | 奖励范围 | 代码需求 |
|------|------|----------|----------|
| 社区 | `community` | 0.25 - 150 RTC | 无代码（star、关注、截图） |
| 代码 | `code` | 20 - 200 RTC | Rust/Python/JS/合约 |
| 内容 | `content` | 5 - 50 RTC | 文章/教程/翻译 |
| 安全 | `red-team`, `security` | 100 - 200 RTC | 审计/渗透测试 |
| 创意/游戏 | `creative`, `gaming` | 1 - 150 RTC | 混合 |
| 传播 | `propagation` | 1 - 25 RTC | 社媒发帖 |

## 难度标签

`easy` → `easy-medium` → `standard` → `medium` → `hard` → `major` → `critical` → `extreme`

优先策略：先 `easy` + `community` 积累信用记录，再挑战 `code` 赏金。

---

## API 操作

### 扫描开放赏金

```bash
curl -s -H "Authorization: Bearer $GH_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/Scottcjn/rustchain-bounties/issues?state=open&labels=bounty&per_page=30&sort=created&direction=desc"
```

### 按难度筛选

```bash
# Easy bounties（快速完成）
curl -s -H "Authorization: Bearer $GH_TOKEN" \
  "https://api.github.com/repos/Scottcjn/rustchain-bounties/issues?state=open&labels=bounty,easy&per_page=10"

# Code bounties（高价值）
curl -s -H "Authorization: Bearer $GH_TOKEN" \
  "https://api.github.com/repos/Scottcjn/rustchain-bounties/issues?state=open&labels=bounty,code&per_page=10"
```

### 按奖励金额筛选

奖励标签格式：`1-4-rtc`, `5-rtc`, `10-rtc`, `25-rtc`, `50-rtc`, `100-rtc`, `200-rtc`

```bash
# 25+ RTC 的高价值赏金
curl -s -H "Authorization: Bearer $GH_TOKEN" \
  "https://api.github.com/repos/Scottcjn/rustchain-bounties/issues?state=open&labels=bounty,25-rtc&per_page=10"
curl -s -H "Authorization: Bearer $GH_TOKEN" \
  "https://api.github.com/repos/Scottcjn/rustchain-bounties/issues?state=open&labels=bounty,50-rtc&per_page=10"
```

### 获取单个 issue 详情

```bash
curl -s -H "Authorization: Bearer $GH_TOKEN" \
  "https://api.github.com/repos/Scottcjn/rustchain-bounties/issues/{issue_number}"
```

### 获取 issue 评论

```bash
curl -s -H "Authorization: Bearer $GH_TOKEN" \
  "https://api.github.com/repos/Scottcjn/rustchain-bounties/issues/{issue_number}/comments"
```

---

## 认领流程

### 1. 分析 issue

必须检查：
- 是否已被认领（查看评论中是否有 "I would like to work on this"）
- 是否有 `resolved` / `invalid` / `duplicate` 标签
- 奖励金额是否值得投入
- 所需技术栈是否匹配
- 是否有 `needs strong contributor` 标签（新手避开）

### 2. 认领 issue

```bash
curl -s -X POST -H "Authorization: Bearer $GH_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/Scottcjn/rustchain-bounties/issues/{issue_number}/comments" \
  -d '{
    "body": "I would like to work on this.\n\n**Approach:** [简述实现方案]\n**ETA:** [预计完成时间]\n**Wallet:** [RTC 钱包地址]"
  }'
```

### 3. 执行任务

根据赏金类型执行：
- **社区任务**: 直接按说明完成（star、截图、发帖）
- **代码任务**: Fork 仓库 → 编写代码 → 创建 PR
- **内容任务**: 按要求创建内容并提供链接

### 4. 提交 PR（代码任务）

```bash
# Fork 仓库
curl -s -X POST -H "Authorization: Bearer $GH_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/Scottcjn/rustchain-bounties/forks"

# 在 fork 中创建分支并提交代码后，创建 PR
curl -s -X POST -H "Authorization: Bearer $GH_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/Scottcjn/rustchain-bounties/pulls" \
  -d '{
    "title": "feat(scope): description (Closes #{issue_number})",
    "body": "## What does this PR do?\n[描述]\n\n## Why?\n[原因]\n\n## How to test?\n[测试步骤]\n\n## Related Issues\nCloses #{issue_number}\n\n**Wallet:** [RTC 钱包地址]",
    "head": "your-fork:branch-name",
    "base": "main"
  }'
```

### 5. 回报完成

在 issue 中评论提交链接：

```bash
curl -s -X POST -H "Authorization: Bearer $GH_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/Scottcjn/rustchain-bounties/issues/{issue_number}/comments" \
  -d '{
    "body": "Completed! PR: {pull_request_url}\n\n**Summary:** [完成摘要]\n**Wallet:** [RTC 钱包地址]"
  }'
```

---

## Issue 格式模板

每个赏金 issue 遵循此格式：

```markdown
## Bounty: {X} RTC

### Description
[任务描述]

### Requirements
- [要求 1]
- [要求 2]

### Bonus ({Y} RTC)
- [可选额外奖励]

### Wallet
在 PR 描述中包含 RTC 钱包地址。
```

---

## 关键仓库列表

RustChain 生态相关仓库（赏金可能指向这些）：

| 仓库 | 用途 | 语言 |
|------|------|------|
| Scottcjn/rustchain-bounties | 赏金管理 | Python |
| rustchain-xyz/rustchain | 核心区块链 | Rust |
| rustchain-xyz/rustchain-sdk | SDK | Rust |
| rustchain-xyz/rustchain-explorer | 区块浏览器 | JS/TS |

---

## 避坑指南

1. **不要重复认领**: 先检查评论，已被认领的 issue 不要再抢
2. **不要发模板评论**: 这是当前 0 收益的根本原因，必须提交真实代码/工作
3. **钱包地址必填**: 每次认领和提交都必须包含 RTC 钱包地址
4. **遵循 Conventional Commits**: `feat(scope): ...`, `fix(scope): ...`, `docs(scope): ...`
5. **先 easy 后 hard**: 建立信用记录后再挑战高价值赏金
6. **关注 `multi-claim` 标签**: 部分赏金允许多人完成
7. **PR 必须通过 CI**: 不通过的 PR 不会被合并，也就不会获得奖励

---

## 钱包地址

当前使用的 RTC 钱包地址需要在每次提交时包含。
