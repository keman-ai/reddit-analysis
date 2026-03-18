# Reddit AI Agent 需求研究 — 系统设计文档

## 概述

构建一个基于 Claude Code Agent Team 的自动化系统，自动浏览 Reddit，采集近半年内关于 AI Agent 雇佣/购买需求的高价值讨论，并进行分类统计和用户客群分析。

## 核心决策

- **数据采集**：Playwright MCP 工具，Agent 直接操控浏览器
- **LLM 分析**：Claude Code Agent 自身能力，零额外 API 成本
- **流程架构**：6 个 Agent 串行 Pipeline，review 环节最多 3 轮打回
- **输出格式**：Markdown 报告 + CSV 原始数据

---

## 1. 架构总览

```
┌─────────────────────────────────────────────────────┐
│                   主控 Orchestrator                    │
│  (用户在 Claude Code 中启动，按顺序调度各 Agent)        │
└──────┬──────────────────────────────────────────────┘
       │
       ▼
┌──────────────┐    不通过    ┌──────────────────┐
│  Architect   │◄────────────│  Arch Reviewer   │
│  架构师 Agent │────────────►│  架构审核 Agent   │
└──────┬───────┘   提交设计   └──────────────────┘
       │ 通过
       ▼
┌──────────────┐    不通过    ┌──────────────────┐
│    Coder     │◄────────────│  Code Reviewer   │
│  编码 Agent   │────────────►│  代码审核 Agent   │
└──────┬───────┘   提交代码   └──────────────────┘
       │ 通过
       ▼
┌──────────────┐
│      QA      │  运行测试，验证流程跑通
│  测试 Agent   │
└──────┬───────┘
       │ 通过
       ▼
┌──────────────┐
│      DA      │  启动抓取 → 分析数据 → 生成报告
│  分析 Agent   │
└──────────────┘
```

## 2. Agent 角色定义

| Agent | 类型 | 职责 | 输入 | 输出 |
|-------|------|------|------|------|
| Architect | Plan agent | 设计爬取流程、数据模型、模块划分 | 需求描述 | `docs/architecture.md` |
| Arch Reviewer | Review agent | 审核架构合理性、完整性，不通过则打回 | 架构文档 | PASS / REJECT + 反馈 |
| Coder | general-purpose agent | 编写 Python 编排脚本 | 架构文档 | Python 源码 |
| Code Reviewer | code-reviewer agent | 审核代码质量、异常处理、网络容错 | Python 源码 | PASS / REJECT + 反馈 |
| QA | general-purpose agent | 运行代码，验证核心流程跑通 | Python 源码 | 测试结果报告 |
| DA | general-purpose agent | 执行抓取、LLM 分析、生成报告 | 抓取数据 | 分析报告 + CSV |

## 3. 数据采集设计

### 3.1 目标 Subreddits

**需求发布类**：r/forhire, r/slavelabour, r/freelance

**AI 讨论类**：r/artificial, r/ChatGPT, r/LocalLLaMA, r/MachineLearning

**创业/产品类**：r/Entrepreneur, r/SaaS, r/startups, r/AItools

### 3.2 搜索关键词

```python
KEYWORDS = {
    "hiring": [
        "hire AI agent", "looking for AI agent", "need AI developer",
        "AI automation developer", "build me an AI agent"
    ],
    "buying": [
        "best AI agent tool", "AI agent service", "buy AI agent",
        "AI agent platform", "pay for AI automation"
    ],
    "demand": [
        "need automation", "AI agent for", "automate my",
        "AI workflow", "AI agent use case", "who uses AI agents"
    ]
}
```

### 3.3 Playwright 操作流程

1. 使用 `browser_navigate` 打开 Reddit 搜索页
2. 对每个 subreddit × keyword 组合：
   a. 构造搜索 URL（限定时间范围：近6个月）
   b. 使用 `browser_snapshot` 获取页面内容
   c. 使用 `browser_click` / `browser_press_key` 翻页加载更多
   d. LLM 直接从 snapshot 中识别和提取帖子信息
   e. 按 upvotes ≥ 5 或 comments ≥ 3 过滤高价值帖子
   f. 进入高价值帖子页面，抓取正文 + Top 20 评论
3. 去重（按帖子 URL）
4. 保存到 JSON + CSV

### 3.4 反爬对策

- 请求间随机延迟（2-5秒）
- 模拟真实滚动行为
- 失败自动重试（最多3次，指数退避）
- 已抓取数据实时写入文件，支持断点续抓

## 4. 数据模型

```json
{
    "id": "reddit_post_id",
    "subreddit": "forhire",
    "title": "Looking for AI agent developer...",
    "author": "username",
    "created_at": "2025-10-15T12:30:00Z",
    "url": "https://reddit.com/r/forhire/...",
    "upvotes": 42,
    "comment_count": 15,
    "body": "帖子正文内容...",
    "top_comments": ["评论1", "评论2"],
    "search_keyword": "hire AI agent",
    "keyword_group": "hiring",

    "category": "hiring",
    "industry": "e-commerce",
    "user_role": "startup_founder",
    "budget_range": "$500-2000",
    "urgency": "high",
    "use_case": "customer support chatbot",
    "competitors_mentioned": ["AutoGPT", "CrewAI"],
    "value_score": 8.5
}
```

## 5. 文件存储结构

```
reddit_research/
├── docs/
│   └── architecture.md          # Architect Agent 产出
├── src/
│   └── orchestrator.py          # 主控编排脚本
├── config/
│   └── search_config.py         # subreddits + keywords 配置
├── data/
│   ├── raw/
│   │   └── posts_raw.json       # 原始抓取数据
│   ├── analyzed/
│   │   ├── posts_analyzed.json  # LLM 分析后的完整数据
│   │   └── posts_analyzed.csv   # CSV 版本
│   └── reports/
│       └── analysis_report.md   # 最终分析报告
└── tests/
    └── test_smoke.py            # QA 冒烟测试
```

## 6. Agent 工作流详情

### 6.1 Review 循环机制

```python
# Phase 1: 架构设计（最多3轮）
for round in range(3):
    arch_doc = dispatch(Architect, input=requirements)
    review = dispatch(ArchReviewer, input=arch_doc)
    if review.passed:
        break

# Phase 2: 编码实现（最多3轮）
for round in range(3):
    code = dispatch(Coder, input=arch_doc)
    review = dispatch(CodeReviewer, input=code)
    if review.passed:
        break

# Phase 3: 测试验证
qa_result = dispatch(QA, input=code)
if not qa_result.passed:
    # 回到 Phase 2 修复

# Phase 4: 数据采集与分析
report = dispatch(DA, input=code + qa_result)
```

### 6.2 Architect Agent

- 输出 `docs/architecture.md`
- 内容：模块划分、Playwright 操作步骤、搜索策略、数据模型、异常处理策略

### 6.3 Arch Reviewer Agent

检查清单：
- 搜索覆盖率是否充分
- 反爬策略是否合理
- 数据模型是否完整
- 边界情况是否覆盖（空搜索结果、页面结构变化等）

### 6.4 Coder Agent

- 根据架构文档编写 Python 编排脚本
- 核心模块：配置管理、Playwright 浏览流程编排、数据持久化、进度追踪

### 6.5 Code Reviewer Agent

重点审核：
- 异常处理（网络超时、页面加载失败、元素找不到）
- 数据校验
- 断点续抓能力
- 代码可读性

### 6.6 QA Agent

- 用一个 subreddit + 一个关键词做端到端冒烟测试
- 验证：浏览器能打开 → 搜索能执行 → 数据能提取并保存 → JSON 格式正确

### 6.7 DA Agent

- 执行完整抓取流程（所有 subreddit × keyword 组合）
- 读取抓取数据，用 LLM 逐条分析填充分析字段
- 生成最终 Markdown 报告

## 7. 分析报告结构

```markdown
# Reddit AI Agent 需求分析报告
> 数据周期：2025-09-19 ~ 2026-03-19
> 采集帖子数：N 条 | 有效分析：M 条

## 一、需求分类统计
- 雇佣需求 / 购买需求 / 咨询讨论 占比

## 二、热门应用场景 Top 10

## 三、用户画像分析
- 3.1 行业分布
- 3.2 用户角色分布（创始人/开发者/运营/个人）
- 3.3 预算范围分布

## 四、时间趋势（按月统计）

## 五、需求紧迫度分布

## 六、竞品/工具提及排名

## 七、市场机会分析
- 高需求但供给不足的场景
- 用户痛点总结
- 可切入的细分市场建议

## 附录
- 数据来源 subreddit 列表
- 搜索关键词列表
- 高价值帖子清单（含链接）
```

## 8. 约束与风险

- **Reddit 反爬**：可能触发验证码或 IP 限制，通过延迟和重试缓解
- **页面结构变化**：Reddit 前端更新可能导致 snapshot 解析失败，需要 DA Agent 有容错能力
- **数据量**：预估 11 个 subreddit × 16 个关键词 = 176 个搜索组合，每个取 Top 20 帖子，最大约 3500 条（去重后预计 500-1000 条）
- **时间消耗**：浏览器操作 + 延迟，预计完整抓取需要较长时间
