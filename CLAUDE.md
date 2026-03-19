# Reddit Research 项目经验总结

## 项目概述

构建 Agent Team 自动化采集 Reddit 数据，分析 AI Agent 市场机会。最终采集 17,155 条帖子，覆盖 31 个 subreddit，结合 Upwork、自动化模板、Agent 能力边界、生产采用信号共 5 个数据源生成综合分析报告。

## Agent Team 架构经验

### 串行 Pipeline + Review 循环是有效的
- 6 个 Agent 角色（Architect → Arch Reviewer → Coder → Code Reviewer → QA → DA）串行执行
- Review 环节（最多 3 轮打回）确实能拦截问题，Arch Review 和 Code Review 都在第 1 轮通过
- 每个 Agent 通过文件系统传递数据（JSONL、Markdown），简单可靠

### Agent 会自主进化方案
- Scraper Agent 在执行过程中自己发现了 Reddit JSON API（`search.json`），比原始设计的 Playwright HTML 方案快 10 倍
- 从 `old.reddit.com/r/{sub}/search` 切换到 `old.reddit.com/r/{sub}/search.json?limit=100`
- 教训：设计阶段不必追求完美方案，Agent 执行时会根据实际情况优化

### 并行 Agent 是关键提速手段
- 5 个 Scraper Agent 并行跑不同 subreddit 分组，总时间从线性的 10 小时降到 2 小时
- 4 个 Agent prompt 编写任务并行执行（Task 2-5）
- 4 个数据源采集并行执行（Upwork + 模板 + 能力 + 采用信号）
- 关键：每个并行 Agent 操作不同的数据分片，通过 progress.json 避免冲突

## Reddit 数据采集经验

### 技术选型
- **首选 Reddit JSON API**（`search.json`），不要用 Playwright 浏览器
  - JSON API 每页返回 100 条（HTML 只有 25 条）
  - 不需要渲染页面、不需要 JS 提取脚本
  - 用 Python `urllib` 或 `curl` 直接请求
- **Playwright 保留用于**：首次探索页面结构、处理需要登录的场景、JS 交互
- **old.reddit.com 比 new reddit 好**：传统分页、无 SPA、反爬更松

### 反爬策略
- Reddit 429 频繁出现，指数退避（60s → 120s → 240s）有效
- 5 个并行 Agent 会加速触发 429，需要更长的冷却时间
- SSL EOF 错误通常是 IP 被临时封禁，等待 5-10 分钟后恢复
- 先访问首页建立会话再做搜索，可减少被封概率

### 数据量优化
- 降低过滤门槛（upvotes≥1 而非≥5）大幅增加数据量
- 扩展 subreddit（11→36）和关键词（16→44）是最有效的增量手段
- 不进详情页、不采评论可 10x 提速（后续按需补充高价值帖子的详情）
- 断点续抓（progress.json）在长时间采集中必不可少

### 搜索覆盖策略
- 按 subreddit 分组：hiring / ai_discussion / startup / automation / industry
- 按关键词分组：hiring / buying / demand / tools
- 时间筛选：`t=year` + 客户端日期过滤（Reddit 无"半年"选项）
- 排序用 `sort=top` 获取高价值内容

## 数据分析经验

### 需求交叉验证是最有价值的分析
- Reddit 讨论热度 ≠ 付费意愿，两者对比能发现虚火和隐性需求
- 例：Reddit 最热话题（AI 安全、vibe coding）在 Upwork 上零付费需求
- 例：Microsoft Copilot Studio（Upwork 6条）在 Reddit 零讨论
- 多数据源交叉比对的公式：需求强度 × 技术成熟度 × 供给稀缺度 ÷ 竞争强度

### 大规模数据分析策略
- 17K 条帖子不能逐条 LLM 分析（成本和时间不可行）
- 用 Python 脚本做定量统计（分布、趋势、TopN）
- 提取高价值子集（upvotes>50）做 LLM 深度分析
- 分批处理（每批 50 条）管理上下文窗口

## 工具和配置

### 项目结构
```
config/search_config.json          # 搜索配置
agents/*.md                        # Agent prompt 定义
scripts/orchestrator.py            # 编排脚本
data/raw/posts_raw.jsonl           # 原始数据
data/raw/posts_deduped.jsonl       # 去重数据
data/raw/progress.json             # 采集进度
data/reports/*.md                  # 分析报告
docs/architecture.md               # 架构文档
```

### 使用的工具
- Playwright MCP：浏览器自动化（初始探索 + QA 测试）
- Reddit JSON API：批量数据采集
- Python：数据处理、去重、统计
- Claude Code Agent：LLM 分析、报告生成、Agent 编排

### Brainstorming Skill 流程
本项目严格遵循 superpowers:brainstorming 技能流程：
1. 探索项目上下文 → 2. 逐个澄清问题 → 3. 提出 2-3 方案 → 4. 分段呈现设计 → 5. 写设计文档 → 6. Spec Review → 7. 写实施计划 → 8. Subagent-Driven 执行
整个流程确保了设计质量，Review 环节拦截了多个关键问题（Python vs MCP 冲突、上下文溢出、认证策略缺失等）。
