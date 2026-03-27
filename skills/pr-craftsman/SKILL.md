---
name: pr-craftsman
description: "GitHub PR 专业提交技能。用于创建高质量的 Pull Request，包含真实代码、测试、文档更新和规范的提交信息。当需要：创建 PR、编写代码变更、添加测试、撰写 PR 描述时使用。不是模板生成器，是真实代码工程师。"
metadata:
  {
    "openclaw":
      {
        "emoji": "🔧",
        "requires": { "bins": ["curl", "git"], "env": ["GH_TOKEN"] },
      },
  }
---

# PR 工匠 — 专业代码提交

**核心原则**: 每一个 PR 都必须包含真实、可运行、有价值的代码变更。绝不生成模板或占位符。

---

## PR 创建工作流

### Phase 1: 理解需求

在写任何代码之前：
1. 仔细阅读 issue 描述中的每一个 Requirements 项
2. 阅读目标仓库的 README、CONTRIBUTING.md
3. 查看仓库现有代码结构和风格
4. 检查是否有类似的已合并 PR 作为参考

```bash
# 获取仓库结构
curl -s -H "Authorization: Bearer $GH_TOKEN" \
  "https://api.github.com/repos/{owner}/{repo}/contents/"

# 获取 CONTRIBUTING.md
curl -s -H "Authorization: Bearer $GH_TOKEN" \
  "https://api.github.com/repos/{owner}/{repo}/contents/CONTRIBUTING.md"

# 查看已合并 PR 作为参考
curl -s -H "Authorization: Bearer $GH_TOKEN" \
  "https://api.github.com/repos/{owner}/{repo}/pulls?state=closed&per_page=5"
```

### Phase 2: 分析现有代码

```bash
# 获取目标文件内容
curl -s -H "Authorization: Bearer $GH_TOKEN" \
  "https://api.github.com/repos/{owner}/{repo}/contents/{path}"

# 查看 git log 了解提交风格
curl -s -H "Authorization: Bearer $GH_TOKEN" \
  "https://api.github.com/repos/{owner}/{repo}/commits?per_page=10"
```

### Phase 3: 编写代码

**绝对禁止**:
- 占位符代码（`TODO: implement`、`pass`、`// ...`）
- 不理解需求的盲目提交
- 复制粘贴不相关的代码
- 不读源码就写修改

**必须做到**:
- 理解每一行修改的作用
- 保持与现有代码风格一致
- 只修改必要的部分，不做无关变更
- 处理边界情况和错误

### Phase 4: 测试

每个代码 PR 必须包含：
1. 如果仓库有测试框架，添加对应测试
2. 如果没有测试框架，至少确保代码可运行
3. 在 PR 描述中说明如何验证修改

### Phase 5: 提交 PR

---

## API 操作

### Fork 仓库

```bash
curl -s -X POST -H "Authorization: Bearer $GH_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/{owner}/{repo}/forks"
```

### 获取 fork 信息

```bash
curl -s -H "Authorization: Bearer $GH_TOKEN" \
  "https://api.github.com/user/repos?per_page=100" | python3 -c "
import json, sys
repos = json.load(sys.stdin)
for r in repos:
    if r.get('fork'):
        print(f\"{r['full_name']} → parent: {r['parent']['full_name']}\")
"
```

### 获取仓库默认分支

```bash
curl -s -H "Authorization: Bearer $GH_TOKEN" \
  "https://api.github.com/repos/{owner}/{repo}" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data['default_branch'])
"
```

### 创建分支

```bash
# 获取 main 分支最新 SHA
SHA=$(curl -s -H "Authorization: Bearer $GH_TOKEN" \
  "https://api.github.com/repos/{owner}/{repo}/git/ref/heads/{default_branch}" | python3 -c "
import json, sys
print(json.load(sys.stdin)['object']['sha'])
")

# 创建新分支
curl -s -X POST -H "Authorization: Bearer $GH_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/{owner}/{repo}/git/refs" \
  -d "{\"sha\": \"$SHA\", \"ref\": \"refs/heads/{branch_name}\"}"
```

### 创建/更新文件

```bash
# 创建新文件
curl -s -X PUT -H "Authorization: Bearer $GH_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/{owner}/{repo}/contents/{path}" \
  -d '{
    "message": "feat(scope): description",
    "content": "'$(echo -n "file content" | base64)'",
    "branch": "branch-name"
  }'

# 更新已有文件（需要 sha）
curl -s -X PUT -H "Authorization: Bearer $GH_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/{owner}/{repo}/contents/{path}" \
  -d '{
    "message": "fix(scope): description",
    "content": "'$(echo -n "new content" | base64)'",
    "sha": "file_sha",
    "branch": "branch-name"
  }'
```

### 创建 PR

```bash
curl -s -X POST -H "Authorization: Bearer $GH_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/{owner}/{repo}/pulls" \
  -d '{
    "title": "feat(scope): clear description (Closes #123)",
    "body": "## What does this PR do?\n\n[具体描述代码做了什么]\n\n## Why?\n\n[为什么需要这个变更]\n\n## How to test?\n\n1. 步骤一\n2. 步骤二\n3. 预期结果：[描述]\n\n## Related Issues\n\nCloses #123\n\n---\n**Wallet:** [RTC address]",
    "head": "fork-owner:branch-name",
    "base": "main"
  }'
```

### 更新 PR（响应 review）

```bash
# 推送新 commit 到同一分支即可自动更新 PR
# 也可以评论回复
curl -s -X POST -H "Authorization: Bearer $GH_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments" \
  -d '{"body": "Addressed review feedback:\n- [x] Fixed X\n- [x] Updated Y\n- [x] Added test for Z"}'
```

---

## Conventional Commits 规范

```
feat(scope): 新功能
fix(scope): 修复 bug
docs(scope): 文档更新
refactor(scope): 重构
test(scope): 添加测试
chore(scope): 杂项
```

示例：
```
feat(wallet): add RTC balance check command
fix(miner): resolve epoch calculation overflow
docs(readme): add quickstart guide for new contributors
test(sdk): add unit tests for transaction signing
```

---

## PR 描述模板

```markdown
## What does this PR do?

[1-3 句话描述变更内容。必须是具体的技术描述，不是泛泛而谈]

## Why?

[为什么需要这个变更。引用 issue 中的具体需求]

## How to test?

1. [具体测试步骤]
2. [命令或操作]
3. 预期结果：[具体预期]

## Changes

- [ ] 变更 1
- [ ] 变更 2

## Related Issues

Closes #{issue_number}

---
**Wallet:** [RTC wallet address]
```

---

## 代码质量检查清单

提交前自检：

- [ ] 代码可运行，无语法错误
- [ ] 与现有代码风格一致（缩进、命名规范）
- [ ] 没有硬编码的密钥或敏感信息
- [ ] 处理了错误情况
- [ ] 如果修改了 API，更新了相关文档
- [ ] 提交信息遵循 Conventional Commits
- [ ] PR 描述清晰说明了变更内容
- [ ] 包含了钱包地址（RustChain 赏金必需）
