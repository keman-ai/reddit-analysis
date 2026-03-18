# Reddit AI Agent 需求研究 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个 Claude Code Agent Team 自动化系统，浏览 Reddit 采集 AI Agent 需求讨论并生成分析报告。

**Architecture:** 7 个 Agent 串行 Pipeline（Architect → Arch Reviewer → Coder → Code Reviewer → QA → Scraper → Analyst），通过文件系统传递数据。Scraper 用 Playwright MCP 工具操控浏览器抓取 old.reddit.com，Analyst 用 LLM 自身能力分析分类。Review 环节最多 3 轮打回。

**Tech Stack:** Claude Code Agent（subagent）、Playwright MCP、JSONL、Markdown

**Spec:** `docs/superpowers/specs/2026-03-19-reddit-ai-agent-research-design.md`

---

## File Structure

```
reddit_research/
├── .gitignore                      # 排除大数据文件
├── config/
│   └── search_config.json          # 搜索配置（subreddits + keywords + 阈值）
├── agents/
│   ├── architect.md                # Architect Agent prompt
│   ├── arch_reviewer.md            # Arch Reviewer Agent prompt
│   ├── coder.md                    # Coder Agent prompt
│   ├── code_reviewer.md            # Code Reviewer Agent prompt
│   ├── qa.md                       # QA Agent prompt
│   ├── scraper.md                  # Scraper Agent prompt（Coder 产出）
│   └── analyst.md                  # Analyst Agent prompt（Coder 产出）
├── scripts/
│   └── orchestrator.py             # 主控编排脚本（Coder 产出）
├── data/
│   ├── raw/                        # Scraper 产出
│   ├── analyzed/                   # Analyst 产出
│   └── reports/                    # 最终报告
└── docs/
    └── architecture.md             # Architect Agent 产出
```

---

### Task 1: 项目初始化 — 配置文件、目录结构、.gitignore

**Files:**
- Create: `config/search_config.json`
- Create: `.gitignore`

- [ ] **Step 1: 创建所有目录**

```bash
mkdir -p config agents scripts data/raw data/analyzed data/reports docs
```

- [ ] **Step 2: 创建 .gitignore**

```
# 大数据文件（保留在本地，不提交）
data/raw/*.jsonl
data/analyzed/*.json
data/analyzed/*.csv

# 保留目录结构
!data/raw/.gitkeep
!data/analyzed/.gitkeep
!data/reports/.gitkeep

# Python
__pycache__/
*.pyc
.venv/
```

- [ ] **Step 3: 创建配置文件**

```json
{
    "subreddits": {
        "hiring": ["forhire", "slavelabour", "freelance"],
        "ai_discussion": ["artificial", "ChatGPT", "LocalLLaMA", "MachineLearning"],
        "startup": ["Entrepreneur", "SaaS", "startups", "AItools"]
    },
    "keywords": {
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
    },
    "filters": {
        "min_upvotes": 5,
        "min_comments": 3,
        "max_posts": 1000,
        "months_back": 6,
        "top_comments_limit": 20
    },
    "scraping": {
        "delay_min_seconds": 2,
        "delay_max_seconds": 5,
        "max_retries": 3,
        "rate_limit_wait_seconds": 60,
        "batch_size_analyst": 50
    },
    "base_url": "https://old.reddit.com"
}
```

- [ ] **Step 4: 创建 .gitkeep 文件保留目录结构**

```bash
touch data/raw/.gitkeep data/analyzed/.gitkeep data/reports/.gitkeep
```

- [ ] **Step 5: 验证 Playwright MCP 可用**

```bash
# 确认 Playwright 插件已安装
ls ~/.claude/plugins/cache/claude-plugins-official/playwright/
```

- [ ] **Step 6: Commit**

```bash
git add .gitignore config/search_config.json data/raw/.gitkeep data/analyzed/.gitkeep data/reports/.gitkeep
git commit -m "feat: initialize project with search config, directories, and gitignore"
```

---

### Task 2: 编写 Architect Agent prompt

**Files:**
- Create: `agents/architect.md`

- [ ] **Step 1: 创建 Architect Agent prompt 文件**

文件结构：

```markdown
# Architect Agent — Reddit AI Agent 需求研究

## 角色
你是系统架构师。你的任务是设计 Reddit 数据抓取的详细技术架构。

## 输入
- 读取 `docs/superpowers/specs/2026-03-19-reddit-ai-agent-research-design.md`（设计文档）
- 读取 `config/search_config.json`（搜索配置）

## 输出
- 写入 `docs/architecture.md`

## 工具权限
- Read（读取文件）
- Write（写入文件）
- Playwright MCP 工具（browser_navigate, browser_snapshot, browser_evaluate）— 用于实际探索 old.reddit.com 页面结构

## 任务步骤

1. **探索 old.reddit.com 页面结构**
   - 用 browser_navigate 打开 https://old.reddit.com/r/forhire/search?q=hire+AI+agent&restrict_sr=on&sort=top&t=year
   - 用 browser_snapshot 查看页面结构
   - 用 browser_evaluate 测试 JS 选择器，找到帖子列表的 DOM 结构
   - 打开一个帖子详情页，分析正文和评论的 DOM 结构

2. **设计 JS 提取脚本**
   - 搜索结果页提取脚本：提取标题、作者、时间、upvotes、评论数、URL
   - 帖子详情页提取脚本：提取正文 + Top N 评论
   - 脚本必须在 old.reddit.com 上实际测试通过

3. **编写架构文档** `docs/architecture.md`，包含：
   - old.reddit.com 页面 DOM 结构分析
   - 完整的 JS 提取脚本代码（搜索页 + 详情页）
   - Playwright MCP 调用步骤（每一步的工具调用和参数）
   - 翻页策略（old.reddit.com 的分页 URL 规则）
   - 异常处理策略（各类错误的处理方式）
   - 数据校验规则（必填字段、类型检查）
   - 时间过滤逻辑（客户端过滤近6个月的帖子）

## 质量要求
- JS 脚本必须经过实际测试，不是猜测
- 每个 Playwright 步骤要给出具体的工具调用示例
- 异常处理要覆盖 spec 3.5 中列出的所有错误类型
```

- [ ] **Step 2: Commit**

```bash
git add agents/architect.md
git commit -m "feat: add Architect agent definition with full prompt"
```

---

### Task 3: 编写 Arch Reviewer Agent prompt

**Files:**
- Create: `agents/arch_reviewer.md`

- [ ] **Step 1: 创建 Arch Reviewer Agent prompt 文件**

文件结构：

```markdown
# Arch Reviewer Agent — 架构审核

## 角色
你是架构审核员。审核 Architect 产出的架构文档，确保技术方案可行且完整。

## 输入
- 读取 `docs/architecture.md`（待审核的架构文档）
- 读取 `docs/superpowers/specs/2026-03-19-reddit-ai-agent-research-design.md`（参照设计文档）

## 输出格式
在回复的最后，输出以下 JSON 块：
\```json
{"passed": true/false, "feedback": "具体反馈内容"}
\```

## 审核清单

### 必须通过项（任一不通过则 REJECT）
1. JS 提取脚本是否包含完整代码（不是伪代码）
2. JS 脚本是否针对 old.reddit.com 的 DOM 结构（不是新版 Reddit）
3. 是否覆盖了搜索结果页和帖子详情页两个场景
4. Playwright MCP 调用步骤是否具体且可执行
5. 异常处理是否覆盖 spec 3.5 的所有错误类型（429/超时/403/不存在）
6. 时间过滤逻辑是否正确（t=year + 客户端 6 个月过滤）

### 建议项（不影响通过，但建议改进）
7. 数据校验规则是否详细
8. 翻页策略是否考虑了最后一页的判断
9. 是否有性能优化建议

## 审核原则
- 只关注技术可行性和完整性，不重新设计
- feedback 中要指出具体问题的位置和改进建议
- 如果整体可行但有小问题，可以 PASS 并在 feedback 中提建议
```

- [ ] **Step 2: Commit**

```bash
git add agents/arch_reviewer.md
git commit -m "feat: add Arch Reviewer agent definition"
```

---

### Task 4: 编写 Coder Agent prompt

**Files:**
- Create: `agents/coder.md`

- [ ] **Step 1: 创建 Coder Agent prompt 文件**

文件结构：

```markdown
# Coder Agent — 编码实现

## 角色
你是编码工程师。根据架构文档编写所有执行层的 Agent prompt 文件和编排脚本。

## 输入
- 读取 `docs/architecture.md`（架构文档，包含 JS 脚本和 Playwright 步骤）
- 读取 `config/search_config.json`（搜索配置）
- 读取 `docs/superpowers/specs/2026-03-19-reddit-ai-agent-research-design.md`（设计文档）

## 输出文件（必须全部创建）
1. `agents/scraper.md` — Scraper Agent prompt
2. `agents/analyst.md` — Analyst Agent prompt
3. `agents/qa.md` — QA Agent prompt
4. `scripts/orchestrator.py` — 主控编排脚本

**注意**：不要修改 `config/search_config.json`，它已经存在。

## 各文件要求

### agents/scraper.md
Scraper Agent 的完整 prompt，必须包含：
- 角色描述：操控 Playwright MCP 浏览器抓取 Reddit 数据
- 工具权限：Read, Write, Bash, 所有 Playwright MCP 工具
- 完整的 JS 提取脚本代码（从 architecture.md 复制）
- 逐步操作指南：
  1. 读取 config/search_config.json
  2. 读取 data/raw/progress.json（如存在），跳过已完成组合
  3. 对每个 subreddit × keyword：构造 URL → navigate → evaluate JS → 过滤 → 详情页 → 写入 JSONL
  4. 每完成一个组合，更新 progress.json
  5. 全部完成后，用 Bash 工具运行 Python 去重脚本
- 错误处理指南（429/超时/403 分别如何处理）
- JSONL 写入格式说明（每行一个 JSON 对象，用 Bash 的 echo >> 追加）
- 数据校验规则

### agents/analyst.md
Analyst Agent 的完整 prompt，必须包含：
- 角色描述：分析 Reddit 帖子数据，生成研究报告
- 工具权限：Read, Write, Bash
- LLM 分析评判标准（完整引用 spec 4.3 的表格）
- 分批处理逻辑：用 Bash 读取 JSONL 每批 50 条
- 输出文件格式：
  - data/analyzed/posts_analyzed.json（JSON 数组）
  - data/analyzed/posts_analyzed.csv（CSV 表头和字段映射）
  - data/reports/analysis_report.md（完整报告模板，引用 spec 第 7 节）
- 丢弃 value_score < 3 的帖子的逻辑

### agents/qa.md
QA Agent 的完整 prompt，必须包含：
- 角色描述：对抓取流程做端到端冒烟测试
- 工具权限：Read, Write, Bash, 所有 Playwright MCP 工具
- 测试用例：
  1. 打开 old.reddit.com 搜索页 → 验证页面加载
  2. 执行 JS 提取 → 验证返回帖子数组
  3. 打开帖子详情页 → 验证正文和评论提取
  4. 写入测试数据到 data/raw/test_posts.jsonl → 验证 JSONL 格式
  5. 写入 progress.json → 验证格式
  6. 测试空搜索结果 → 验证优雅处理
  7. 测试翻页 → 验证能获取下一页
- 每个测试的预期结果和通过标准
- 输出格式：结构化 JSON {"passed": true/false, "results": [...], "failures": [...]}

### scripts/orchestrator.py
编排脚本，包含：
- Phase 枚举（ARCH_DESIGN, ARCH_REVIEW, CODING, CODE_REVIEW, QA, SCRAPING, ANALYSIS）
- review 循环逻辑（最多 3 轮，超出升级给用户）
- QA 返工循环（最多 2 轮）
- Agent 调度顺序和数据依赖
- 日志输出
- 脚本作为流程文档使用，不直接调用 Claude Code Agent tool

## 质量要求
- Agent prompt 必须足够详细，让一个没有上下文的 Agent 能独立执行
- JS 代码必须完整，不能用注释代替实现
- 所有文件路径必须使用相对路径
```

- [ ] **Step 2: Commit**

```bash
git add agents/coder.md
git commit -m "feat: add Coder agent definition with detailed output specs"
```

---

### Task 5: 编写 Code Reviewer Agent prompt

**Files:**
- Create: `agents/code_reviewer.md`

- [ ] **Step 1: 创建 Code Reviewer Agent prompt 文件**

文件结构：

```markdown
# Code Reviewer Agent — 代码审核

## 角色
你是代码审核员。审核 Coder Agent 产出的所有文件的质量和完整性。

## 输入（必须全部读取）
- `agents/scraper.md`
- `agents/analyst.md`
- `agents/qa.md`
- `scripts/orchestrator.py`
- `config/search_config.json`（配置参照）
- `docs/architecture.md`（架构参照）

## 输出格式
在回复的最后，输出以下 JSON 块：
\```json
{"passed": true/false, "feedback": "具体反馈内容"}
\```

## 审核清单

### Scraper Agent prompt 审核
1. 是否包含完整的 JS 提取脚本代码（不是"参考 architecture.md"）
2. 是否有逐步操作指南（不是概述）
3. 错误处理是否覆盖 429/超时/403/subreddit不存在
4. JSONL 追加写入逻辑是否正确
5. progress.json 读写逻辑是否完整
6. 是否有去重步骤
7. 延迟策略是否符合 config 中的设定

### Analyst Agent prompt 审核
8. LLM 分析评判标准是否完整引用（不是摘要）
9. 分批处理逻辑是否可行
10. 报告模板是否包含 spec 第 7 节的所有章节
11. CSV 输出是否定义了表头
12. value_score < 3 的丢弃逻辑是否存在

### QA Agent prompt 审核
13. 测试用例是否覆盖 spec 6.6 的所有验证项
14. 每个测试是否有明确的预期结果
15. 是否测试了空搜索结果和翻页

### orchestrator.py 审核
16. review 循环是否有 3 轮上限
17. QA 返工是否有 2 轮上限
18. 是否有用户升级逻辑

## 审核原则
- 重点关注 Agent prompt 是否能让一个零上下文的 Agent 独立执行
- 关注异常情况处理和网络容错
- 如果发现缺失的关键内容，必须 REJECT
- feedback 中要指出具体文件、具体位置、具体问题
```

- [ ] **Step 2: Commit**

```bash
git add agents/code_reviewer.md
git commit -m "feat: add Code Reviewer agent definition with checklist"
```

---

### Task 6: 执行 Phase 1 — 调度 Architect Agent

**前置条件**：Task 1-5 完成

- [ ] **Step 1: 调度 Architect Agent**

```
使用 Agent tool:
  description: "Architect designs Reddit scraping architecture"
  subagent_type: "general-purpose"
  prompt: 读取 agents/architect.md 的完整内容
```

等待 Agent 完成，检查 `docs/architecture.md` 已创建。

- [ ] **Step 2: Commit architecture doc**

```bash
git add docs/architecture.md
git commit -m "feat: add architecture document (Architect Agent output)"
```

---

### Task 7: 执行 Phase 1 — 调度 Arch Reviewer Agent

**前置条件**：Task 6 完成，`docs/architecture.md` 已存在

- [ ] **Step 1: 调度 Arch Reviewer Agent**

```
使用 Agent tool:
  description: "Review architecture document"
  subagent_type: "general-purpose"
  prompt: 读取 agents/arch_reviewer.md 的完整内容
```

- [ ] **Step 2: 检查 review 结果**

- 如果 `passed: true` → 标记通过，进入 Task 8
- 如果 `passed: false` → 记录 feedback，回到 Task 6 重新调度 Architect Agent（带上 feedback）
- 最多 3 轮。3 轮后仍不通过 → 将架构文档和所有 feedback 呈现给用户决定

---

### Task 8: 执行 Phase 2 — 调度 Coder Agent

**前置条件**：Task 7 通过

- [ ] **Step 1: 调度 Coder Agent**

```
使用 Agent tool:
  description: "Coder implements agent prompts and orchestrator"
  subagent_type: "general-purpose"
  prompt: 读取 agents/coder.md 的完整内容
```

等待 Agent 完成，检查以下文件已创建：
- `agents/scraper.md`
- `agents/analyst.md`
- `agents/qa.md`
- `scripts/orchestrator.py`

- [ ] **Step 2: Commit all Coder outputs**

```bash
git add agents/scraper.md agents/analyst.md agents/qa.md scripts/orchestrator.py
git commit -m "feat: add Scraper, Analyst, QA agent prompts and orchestrator script"
```

---

### Task 9: 执行 Phase 2 — 调度 Code Reviewer Agent

**前置条件**：Task 8 完成

- [ ] **Step 1: 调度 Code Reviewer Agent**

```
使用 Agent tool:
  description: "Review Coder agent outputs"
  subagent_type: "superpowers:code-reviewer"
  prompt: 读取 agents/code_reviewer.md 的完整内容
```

- [ ] **Step 2: 检查 review 结果**

- 如果 `passed: true` → 标记通过，进入 Task 10
- 如果 `passed: false` → 记录 feedback，回到 Task 8 重新调度 Coder Agent（prompt 附加 feedback）
- 最多 3 轮。3 轮后仍不通过 → 升级给用户

---

### Task 10: 执行 Phase 3 — 调度 QA Agent 冒烟测试

**前置条件**：Task 9 通过

- [ ] **Step 1: 调度 QA Agent**

```
使用 Agent tool:
  description: "QA smoke test Reddit scraping"
  subagent_type: "general-purpose"
  prompt: 读取 agents/qa.md 的完整内容
```

QA Agent 将使用 Playwright MCP 工具执行冒烟测试。

- [ ] **Step 2: 检查 QA 结果**

- 如果 `passed: true` → 进入 Task 11
- 如果 `passed: false` → 记录失败信息，回到 Task 8 让 Coder 修复（最多 2 轮 QA 返工）
- 2 轮后仍不通过 → 升级给用户

- [ ] **Step 3: 清理测试数据**

```bash
rm -f data/raw/test_posts.jsonl
```

---

### Task 11: 执行 Phase 4 — Scraper 抓取（需求发布类 subreddits）

**前置条件**：Task 10 通过

- [ ] **Step 1: 调度 Scraper Agent — 第一批**

```
使用 Agent tool:
  description: "Scrape hiring subreddits"
  subagent_type: "general-purpose"
  prompt: |
    读取 agents/scraper.md 的完整内容。
    本批次只处理 hiring 类 subreddits: forhire, slavelabour, freelance
    其余 subreddits 由后续批次处理。
```

- [ ] **Step 2: 验证第一批数据**

检查 `data/raw/posts_raw.jsonl` 存在且有数据，`data/raw/progress.json` 记录了已完成的组合。

---

### Task 12: 执行 Phase 4 — Scraper 抓取（AI 讨论类 subreddits）

- [ ] **Step 1: 调度 Scraper Agent — 第二批**

```
使用 Agent tool:
  description: "Scrape AI discussion subreddits"
  subagent_type: "general-purpose"
  prompt: |
    读取 agents/scraper.md 的完整内容。
    本批次只处理 ai_discussion 类 subreddits: artificial, ChatGPT, LocalLLaMA, MachineLearning
    检查 data/raw/progress.json 跳过已完成的组合。
```

- [ ] **Step 2: 验证第二批数据**

检查 progress.json 更新，posts_raw.jsonl 追加了新数据。

---

### Task 13: 执行 Phase 4 — Scraper 抓取（创业/产品类 subreddits）

- [ ] **Step 1: 调度 Scraper Agent — 第三批**

```
使用 Agent tool:
  description: "Scrape startup subreddits"
  subagent_type: "general-purpose"
  prompt: |
    读取 agents/scraper.md 的完整内容。
    本批次只处理 startup 类 subreddits: Entrepreneur, SaaS, startups, AItools
    检查 data/raw/progress.json 跳过已完成的组合。
```

- [ ] **Step 2: 验证全量数据并去重**

```bash
# 检查总行数
wc -l data/raw/posts_raw.jsonl
# 验证 JSONL 格式（每行是合法 JSON）
python3 -c "
import json
with open('data/raw/posts_raw.jsonl') as f:
    lines = f.readlines()
    valid = sum(1 for l in lines if json.loads(l))
    print(f'Total: {len(lines)}, Valid: {valid}')
"
```

- [ ] **Step 3: Commit raw data**

```bash
git add data/raw/progress.json
git commit -m "data: complete Reddit scraping for all subreddits"
```

---

### Task 14: 执行 Phase 5 — Analyst 数据分析

**前置条件**：Task 13 完成

- [ ] **Step 1: 调度 Analyst Agent**

```
使用 Agent tool:
  description: "Analyze scraped Reddit data"
  subagent_type: "general-purpose"
  prompt: 读取 agents/analyst.md 的完整内容
```

Analyst Agent 将：
1. 分批读取 `data/raw/posts_raw.jsonl`（每批 50 条）
2. 对每条帖子 LLM 分析，填充分析字段
3. 丢弃 value_score < 3 的帖子
4. 写入 `data/analyzed/posts_analyzed.json` 和 `posts_analyzed.csv`
5. 汇总生成 `data/reports/analysis_report.md`

**注意**：如果数据量大，可能需要分多次 Agent 调用。Analyst Agent 应支持增量处理。

- [ ] **Step 2: 验证分析报告**

检查 `data/reports/analysis_report.md` 包含以下章节：
- 需求分类统计
- 热门应用场景 Top 10
- 用户画像（行业/角色/预算）
- 时间趋势
- 需求紧迫度分布
- 竞品/工具提及排名
- 市场机会分析
- 附录

- [ ] **Step 3: Commit analysis results**

```bash
git add data/reports/analysis_report.md
git commit -m "analysis: generate AI agent demand research report"
```

---

### Task 15: 最终验证与交付

- [ ] **Step 1: 验证所有产出物完整性**

检查文件清单：
- `config/search_config.json` — 搜索配置
- `agents/architect.md` — Architect Agent
- `agents/arch_reviewer.md` — Arch Reviewer Agent
- `agents/coder.md` — Coder Agent
- `agents/code_reviewer.md` — Code Reviewer Agent
- `agents/scraper.md` — Scraper Agent（Coder 产出）
- `agents/analyst.md` — Analyst Agent（Coder 产出）
- `agents/qa.md` — QA Agent（Coder 产出）
- `scripts/orchestrator.py` — 编排脚本（Coder 产出）
- `docs/architecture.md` — 架构文档（Architect 产出）
- `data/raw/posts_raw.jsonl` — 原始数据
- `data/raw/progress.json` — 抓取进度
- `data/analyzed/posts_analyzed.json` — 分析数据
- `data/analyzed/posts_analyzed.csv` — CSV 版本
- `data/reports/analysis_report.md` — 最终报告

- [ ] **Step 2: 向用户呈现报告摘要**

读取 `data/reports/analysis_report.md`，向用户呈现关键发现。

- [ ] **Step 3: Final commit**

```bash
git add agents/ scripts/ docs/architecture.md
git commit -m "docs: complete Reddit AI Agent demand research project"
```
