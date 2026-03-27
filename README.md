# Skill Pack Verification

Automated CI verification for OpenClaw/Automaton skill packs.

## Skills

| Skill | Description |
|-------|-------------|
| rustchain-bounty | RustChain 赏金猎人 — 赏金扫描、认领、提交流程 |
| pr-craftsman | PR 工匠 — 高质量 PR 创建工作流 |
| rust-developer | Rust 开发 — 区块链数据结构、签名、CLI |
| python-bounty-contributor | Python 贡献 — GitHub API 封装、工具脚本 |
| community-bounty-bot | 社区自动化 — star/follow 批量执行 |

## CI

- Python tests: pytest with real data validation
- Rust compile: cargo build + cargo test
- SKILL.md format: YAML frontmatter validation

