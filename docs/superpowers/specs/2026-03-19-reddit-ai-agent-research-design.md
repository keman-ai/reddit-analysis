# Reddit AI Agent 需求研究 — 系统设计文档

## 概述

构建一个基于 Claude Code Agent Team 的自动化系统，自动浏览 Reddit，采集近半年内关于 AI Agent 雇佣/购买需求的高价值讨论，并进行分类统计和用户客群分析。

## 核心决策

- **数据采集**：Playwright MCP 工具，Agent 直接操控浏览器
- **LLM 分析**：Claude Code Agent 自身能力，零额外 API 成本
- **流程架构**：7 个 Agent 串行 Pipeline（DA 拆分为 Scraper + Analyst），review 环节最多 3 轮打回
- **输出格式**：Markdown 报告 + CSV 原始数据
- **Reddit 访问**：使用 `old.reddit.com` 避免登录墙和现代 UI 反爬
- **数据提取**：`browser_evaluate` 注入 JS 提取结构化数据，`browser_snapshot` 辅助 LLM 理解页面

---

## 1. 架构总览

```
┌──────────────────────────────────────────────────────┐
│                    主控 Orchestrator                    │
│   (用户在 Claude Code 中启动，按顺序调度各 Agent)        │
└──────┬───────────────────────────────────────────────┘
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
│      QA      │  冒烟测试，验证流程跑通
│  测试 Agent   │
└──────┬───────┘
       │ 通过
       ▼
┌──────────────┐
│   Scraper    │  操控浏览器，分批抓取数据存入文件
│  抓取 Agent   │
└──────┬───────┘
       │ 数据落盘
       ▼
┌──────────────┐
│   Analyst    │  读取数据 → LLM 分析分类 → 生成报告
│  分析 Agent   │
└──────────────┘
```

## 2. Agent 角色定义

| Agent | 类型 | 职责 | 输入 | 输出 |
|-------|------|------|------|------|
| Architect | Plan agent | 设计 Agent 工作流、数据模型、浏览策略 | 需求描述 + 本设计文档 | `docs/architecture.md` |
| Arch Reviewer | Review agent | 审核架构合理性、完整性，不通过则打回 | 架构文档 | PASS / REJECT + 反馈 |
| Coder | general-purpose agent | 编写 Agent 定义文件和配置 | 架构文档 | Agent prompt 文件 + 配置文件 |
| Code Reviewer | code-reviewer agent | 审核代码质量、异常处理、网络容错 | Agent 定义 + 配置 | PASS / REJECT + 反馈 |
| QA | general-purpose agent | 小范围端到端测试 | Agent 定义 + 配置 | 测试结果报告 |
| Scraper | general-purpose agent | 操控 Playwright MCP 浏览器抓取 Reddit | 配置文件 | `data/raw/posts_raw.jsonl` |
| Analyst | general-purpose agent | LLM 分析数据、生成报告 | 原始数据文件 | 分析报告 + CSV |

### 2.1 inter-Agent 数据传递

所有 Agent 通过 **文件系统** 传递数据：
- Architect → Coder：`docs/architecture.md`
- Coder → QA/Scraper：Agent 定义文件 + `config/search_config.json`
- Scraper → Analyst：`data/raw/posts_raw.jsonl`（分批追加写入）
- Analyst → 用户：`data/reports/analysis_report.md` + `data/analyzed/posts_analyzed.csv`

Review Agent 通过返回值传递 PASS/REJECT + 反馈文本。

### 2.2 Review 循环耗尽策略

3 轮 review 仍未通过时：**暂停流水线，将最近一轮的代码/架构 + 所有 review 反馈呈现给用户**，由用户决定是否继续或手动介入。

## 3. 数据采集设计

### 3.1 目标 Subreddits

**需求发布类**：r/forhire, r/slavelabour, r/freelance

**AI 讨论类**：r/artificial, r/ChatGPT, r/LocalLLaMA, r/MachineLearning

**创业/产品类**：r/Entrepreneur, r/SaaS, r/startups, r/AItools

### 3.2 搜索关键词

```json
{
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

### 3.3 Reddit 访问策略

- **使用 `old.reddit.com`**：避免现代 Reddit UI 的登录墙、"Continue in App" 弹窗和复杂 SPA 结构
- **搜索 URL 格式**：`https://old.reddit.com/r/{subreddit}/search?q={keyword}&restrict_sr=on&sort=top&t=year`
- **时间筛选**：Reddit 搜索仅支持 past hour/day/week/month/year 预设。使用 `t=year`，然后在数据提取时按 `created_at` 客户端过滤，仅保留近 6 个月的帖子

### 3.4 Playwright 操作流程

1. 使用 `browser_navigate` 打开 `old.reddit.com` 搜索页
2. 对每个 subreddit × keyword 组合：
   a. 构造搜索 URL
   b. 使用 `browser_evaluate` 注入 JS 提取帖子列表的结构化数据（标题、作者、时间、upvotes、评论数、URL）
   c. 辅助使用 `browser_snapshot` 让 LLM 理解页面状态、处理异常
   d. 使用 `browser_click` 翻页（old.reddit.com 有传统分页，比无限滚动更可靠）
   e. 按 upvotes ≥ 5 或 comments ≥ 3 过滤高价值帖子
   f. 进入高价值帖子页面，用 `browser_evaluate` 提取正文 + Top 20 评论
3. 去重（按帖子 URL）
4. 实时追加写入 `data/raw/posts_raw.jsonll`（JSONL 格式，每行一条 JSON 记录，方便追加和分批读取）

### 3.5 反爬对策

- 请求间随机延迟（2-5秒）
- 失败自动重试（最多3次，指数退避）
- **区分错误类型**：
  - 429 Rate Limit → 等待 60 秒后重试
  - 页面加载超时 → 标准指数退避重试
  - 403/Captcha → 记录日志，跳过当前搜索组合，继续下一个
  - Subreddit 不存在/私有 → 跳过并记录
- **断点续抓**：已完成的 subreddit×keyword 组合记录在 `data/raw/progress.json`，重启时跳过已完成的

### 3.6 分批策略（上下文窗口管理）

Scraper Agent 按 subreddit 分批执行：
- 每完成一个 subreddit 的所有关键词搜索，将结果追加到 `data/raw/posts_raw.jsonl`
- 每批完成后写入进度文件
- 如果单个 Agent 上下文接近溢出，可终止当前 Agent 并启动新 Scraper Agent 从断点续抓

Analyst Agent 分批分析：
- 每次从 JSON 文件读取一批帖子（50条），分析后写入 `data/analyzed/posts_analyzed.json`
- 最终汇总生成报告

## 4. 数据模型

### 4.1 原始数据（Scraper 产出）

```json
{
    "id": "reddit_post_id",
    "subreddit": "forhire",
    "title": "Looking for AI agent developer...",
    "author": "username",
    "created_at": "2025-10-15T12:30:00Z",
    "url": "https://old.reddit.com/r/forhire/...",
    "upvotes": 42,
    "comment_count": 15,
    "body": "帖子正文内容...",
    "top_comments": ["评论1", "评论2"],
    "search_keyword": "hire AI agent",
    "keyword_group": "hiring"
}
```

### 4.2 分析数据（Analyst 产出，在原始数据基础上新增字段）

```json
{
    "...原始字段...",
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

### 4.3 LLM 分析评判标准

| 字段 | 取值范围 | 判定标准 |
|------|---------|---------|
| category | hiring / buying / consulting / discussion | hiring=明确招人或外包；buying=寻找现成工具/服务；consulting=寻求建议；discussion=一般讨论 |
| industry | 自由文本 | 从帖子内容推断用户所在行业，无法推断则填 "unknown" |
| user_role | founder / developer / marketer / operator / individual / unknown | 从发帖人自述或语境推断 |
| budget_range | 具体范围或 "not_mentioned" | 仅当帖子中明确提到预算/价格时填写 |
| urgency | high / medium / low | high=有明确时间要求或"ASAP"；medium=近期需要；low=调研阶段或无时间压力 |
| use_case | 自由文本 | 一句话描述具体应用场景 |
| competitors_mentioned | 字符串数组 | 帖子或评论中提到的具体 AI Agent 工具/平台名称 |
| value_score | 1-10 浮点数 | 综合评分：upvotes权重30% + 评论质量30% + 需求明确度20% + 预算信息20% |

## 5. 文件存储结构

```
reddit_research/
├── docs/
│   ├── superpowers/specs/       # 设计文档
│   └── architecture.md          # Architect Agent 产出
├── agents/
│   ├── architect.md             # Architect Agent 定义
│   ├── arch_reviewer.md         # Arch Reviewer Agent 定义
│   ├── coder.md                 # Coder Agent 定义
│   ├── code_reviewer.md         # Code Reviewer Agent 定义
│   ├── qa.md                    # QA Agent 定义
│   ├── scraper.md               # Scraper Agent 定义
│   └── analyst.md               # Analyst Agent 定义
├── config/
│   └── search_config.json       # subreddits + keywords + 过滤阈值
├── data/
│   ├── raw/
│   │   ├── posts_raw.jsonll       # 原始抓取数据（JSONL格式，逐条追加）
│   │   └── progress.json        # 抓取进度（已完成的组合）
│   ├── analyzed/
│   │   ├── posts_analyzed.json  # LLM 分析后的完整数据
│   │   └── posts_analyzed.csv   # CSV 版本
│   └── reports/
│       └── analysis_report.md   # 最终分析报告
└── scripts/
    └── run.sh                   # 一键启动脚本（可选）
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
else:
    escalate_to_user(arch_doc, all_review_feedback)

# Phase 2: 编码实现（最多3轮）
for round in range(3):
    code = dispatch(Coder, input=arch_doc)
    review = dispatch(CodeReviewer, input=code)
    if review.passed:
        break
else:
    escalate_to_user(code, all_review_feedback)

# Phase 3: 测试验证
qa_result = dispatch(QA)
if not qa_result.passed:
    # 回到 Phase 2，带上 QA 的失败信息（最多2轮 QA 返工，超出则升级给用户）

# Phase 4: 数据采集
dispatch(Scraper)  # 结果写入 data/raw/

# Phase 5: 数据分析
dispatch(Analyst)  # 读取 data/raw/，输出 data/reports/ + data/analyzed/
```

### 6.2 Architect Agent

- 输出 `docs/architecture.md`
- 内容：Agent 调用 Playwright MCP 的详细步骤、old.reddit.com 页面结构分析、JS 提取脚本模板、数据校验规则、异常处理策略

### 6.3 Arch Reviewer Agent

检查清单：
- 搜索覆盖率是否充分
- old.reddit.com 访问策略是否可行
- JS 数据提取方案是否可靠
- 数据模型是否完整
- 边界情况是否覆盖（空搜索结果、已删除帖子、非英文内容、私有 subreddit）
- 分批策略是否能防止上下文溢出

### 6.4 Coder Agent

- 编写 Agent 定义文件（`agents/*.md`）：每个 Agent 的 system prompt + 工具权限 + 输入输出规范
- 编写 `config/search_config.json`：搜索配置
- 编写 JS 提取脚本（嵌入 Agent prompt 或独立文件）

### 6.5 Code Reviewer Agent

重点审核：
- 异常处理（网络超时、页面加载失败、元素找不到、429 rate limit）
- 数据校验（必填字段检查、类型校验）
- 断点续抓能力（progress.json 机制）
- Agent prompt 的清晰度和完整性
- JS 提取脚本在 old.reddit.com 的兼容性

### 6.6 QA Agent

测试范围：
- 用 r/forhire + "hire AI agent" 做端到端冒烟测试
- 验证项：
  - 浏览器能打开 old.reddit.com
  - 搜索能执行并返回结果
  - JS 能正确提取帖子结构化数据
  - 数据能保存为正确的 JSON 格式
  - 能处理帖子详情页（正文 + 评论提取）
  - 翻页功能正常
  - 进度文件正确写入
  - 空搜索结果能优雅处理

### 6.7 Scraper Agent

- 读取 `config/search_config.json` 获取搜索配置
- 检查 `data/raw/progress.json` 跳过已完成的组合
- 按 subreddit 分批执行浏览器抓取
- 每条帖子抓取后实时追加到 `data/raw/posts_raw.jsonl`
- 完成一个组合后更新 `progress.json`
- 全部完成后汇总去重

### 6.8 Analyst Agent

- 分批读取 `data/raw/posts_raw.jsonl`（每批50条）
- 对每条帖子用 LLM 分析填充分析字段（按 4.3 的评判标准）
- 将分析结果写入 `data/analyzed/posts_analyzed.json` 和 `.csv`
- 汇总统计，生成 `data/reports/analysis_report.md`

## 7. 分析报告结构

```markdown
# Reddit AI Agent 需求分析报告
> 数据周期：2025-09-19 ~ 2026-03-19
> 采集帖子数：N 条 | 有效分析：M 条

## 一、需求分类统计
- 雇佣需求：X 条 (XX%)
- 购买需求：X 条 (XX%)
- 咨询需求：X 条 (XX%)
- 一般讨论：X 条 (XX%)

## 二、热门应用场景 Top 10
| 排名 | 场景 | 提及次数 | 代表帖子 |

## 三、用户画像分析
### 3.1 行业分布
### 3.2 用户角色分布（创始人/开发者/运营/个人）
### 3.3 预算范围分布

## 四、时间趋势（按月统计需求量变化）

## 五、需求紧迫度分布（高/中/低）

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

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| Reddit 反爬（429/Captcha） | 抓取中断 | 延迟+退避+跳过策略，断点续抓 |
| old.reddit.com 页面结构变化 | JS 提取失败 | browser_snapshot 辅助 LLM 理解页面，Agent 可自适应调整 |
| 上下文窗口溢出 | Agent 无法处理所有数据 | 分批处理，Scraper/Analyst 分离 |
| 搜索结果不精准 | 采集到无关帖子 | LLM 在 Analyst 阶段过滤，value_score < 3 的丢弃 |
| 时间筛选局限 | 包含6个月前的数据 | 客户端按 created_at 过滤 |
| 数据量过大 | 处理时间过长 | 按高价值优先排序，默认最大帖子数上限 1000 条 |
