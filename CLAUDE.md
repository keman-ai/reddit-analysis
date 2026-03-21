# 市场调研数据采集与分析工程

## 项目定位

本工程是一个**市场调研自动化平台**，核心能力是：大规模数据抓取 → 去重清洗 → 定量统计 → LLM 深度分析 → 选品/策略报告。

用户会给出调研任务，通常包含：**调研背景**、**目标网站/数据源**、**数据规模要求**、**分析视角**。工程已有成熟的抓取和分析流水线，新任务应复用已有模式。

---

## 工作流程（标准范式）

### 1. 数据抓取阶段

**输入：** 用户指定目标网站 + 关键词 + 数据规模
**输出：** `data/raw/{task_name}.jsonl`（JSONL 格式，每行一条 JSON）

标准步骤：
1. 写 Python 抓取脚本到 `scripts/scrape_{task}.py`
2. 首选目标网站的 JSON API（如 Reddit 的 `search.json`），比 Playwright 浏览器快 10 倍
3. Playwright MCP 仅用于：首次探索页面结构、需要登录的场景（如闲鱼）
4. 进度文件 `data/raw/{task}_progress.json` 支持断点续抓
5. 后台运行（`run_in_background`），定期汇报进度
6. 连续 5 个关键词返回 0 新结果时自动跳过该分组（避免浪费时间）
7. 完成后做去重，输出 `data/raw/{task}_deduped.jsonl`

**反爬策略（已验证有效）：**
- 请求间随机延迟 2-5 秒（大规模采集可加到 5-10 秒）
- 429 Rate Limit：指数退避 60s → 120s → 240s → 480s
- 403/Captcha/SSL EOF：跳过并记录，不阻塞整体流程
- 多 Agent 并行时按数据分片（不同 subreddit/关键词组）避免冲突

### 2. 数据分析阶段

**输入：** 去重后的 JSONL 数据文件
**输出：** `data/reports/{report_name}.md`（Markdown 报告）

标准步骤：
1. **先用 Python 脚本做定量分析**（不要直接用 LLM 读原始数据）
   - 分布统计：各类目/关键词组的数量、占比
   - 热度分析：upvotes/评论数/想要数的中位数、P90、P99
   - 价格提取：从文本中正则提取价格信号
   - 需求聚类：从标题关键词做服务/需求类型分类
   - 时间趋势：按月/季度统计变化
2. **提取高价值子集**（upvotes > 阈值）给 LLM 做深度分析
3. **LLM 分析**产出洞察、评估矩阵、选品推荐

### 3. 报告产出阶段

**报告直接写入文件**，不要在对话中输出长篇报告。在对话中只呈现核心结论表格。

---

## 分析报告质量标准

### 报告结构（必须包含）

```markdown
# {报告标题}

> 数据规模：X 条 | 来源：Y | 时间：Z
> 报告时间：YYYY-MM-DD

## 一、执行摘要（300-500字）
3-4 个核心发现，每个用一句话概括 + 关键数据点

## 二、数据概览
定量统计图表，让读者对数据全貌有感知

## 三、核心分析（报告的主体）
根据具体任务展开，但必须：
- 每个观点引用具体数据（帖子数、百分比、价格）
- 用表格呈现对比和评估矩阵
- 有交叉验证（多数据源对比发现虚火 vs 真需求）

## 四、选品/策略推荐
- TOP N 排序，每个有：数据支撑 + 实现方案 + 定价 + 风险
- 分层/分波策略（MVP → Phase 2 → Phase 3）

## 五、风险警示
明确列出不应做的方向和原因

## 附录
数据来源、方法论说明
```

### 质量红线（必须遵守）

1. **每个结论必须引用具体数据** — 不能写"大量用户需要"，要写"r/personalfinance 6,704 条帖子中 12.9% 提到预算规划"
2. **引用帖子必须附 URL** — 引用样例帖子时，用 Markdown 链接格式附上原帖 URL，方便读者点击查看原文。格式：`["帖子标题"](https://old.reddit.com/r/xxx/comments/xxx/)（1,006↑）`。需要从原始 JSONL 数据中匹配帖子的 url 字段
3. **定量先于定性** — 先跑 Python 脚本出统计数字，再用 LLM 解读
4. **数据量大时不要逐条 LLM 分析** — 1 万条以上用 Python 做聚类和统计，只对 Top 100 高热帖做 LLM 深度分析
5. **交叉验证** — 多数据源（如 Reddit vs Upwork vs 闲鱼）对比是最有价值的分析
6. **评估矩阵用表格** — 多维度评分必须用表格呈现，不要纯文字描述
7. **报告长度 4000-7000 字** — 太短缺少深度，太长没人看
8. **中文撰写** — 除专有名词外用中文

### 评估维度模板（选品类报告）

| 维度 | 权重 | 说明 |
|------|------|------|
| AI 技术可行性 | 25% | 当前 LLM/Agent 能否达到人工 80%+ 质量 |
| 标准化程度 | 20% | 输入输出是否可模板化 |
| 交付验证性 | 20% | 用户能否快速判断质量 |
| 市场规模 | 15% | 数据量级 × 价格区间 |
| 口碑传播性 | 10% | 用户满意后推荐概率 |
| 成交容易度 | 10% | 决策成本、复购率 |

可根据具体任务调整维度（如加入"被大厂切走的风险"、"情感连接需求"等）。

---

## 项目结构

```
scripts/
├── scrape_reddit_services.py    # Reddit 服务交易类采集（forhire/slavelabour）
├── scrape_reddit_needs.py       # Reddit 求助/生活类采集（advice/life）
├── scrape_all.py                # Reddit AI 讨论类采集
├── analyze_reddit_services.py   # 服务数据定量分析
├── orchestrator.py              # Agent Team 编排脚本
├── batch_save.py                # 批量保存工具
├── retry_failed.py              # 重试失败任务
├── save_posts.py                # 帖子保存工具
└── update_progress.py           # 进度更新工具

config/
├── search_config.json           # 基础搜索配置
└── search_config_expanded.json  # 扩展搜索配置（36 subreddits × 44 keywords）

data/
├── raw/                         # 原始采集数据（JSONL）
│   ├── reddit_needs.jsonl       # 134,424 条 Reddit 求助/生活帖
│   ├── reddit_services.jsonl    # 23,865 条 Reddit 服务交易帖
│   ├── posts_raw.jsonl          # 17,155 条 Reddit AI 讨论帖
│   ├── upwork_jobs.jsonl        # 69 条 Upwork 职位
│   ├── automation_templates.jsonl # 63 条 n8n/Make/Zapier 模板
│   ├── agent_capabilities.jsonl # 17 条 Agent 能力基准
│   ├── adoption_signals.jsonl   # 35 条生产采用信号
│   ├── goofish/services.jsonl   # 10,234 条闲鱼服务商品
│   └── *_progress.json          # 各任务断点续抓进度
├── analyzed/                    # LLM 分析后的数据
└── reports/                     # 分析报告（Markdown）

agents/                          # Agent Team prompt 定义
docs/                            # 架构和设计文档
```

---

## 已有数据资产

| 数据集 | 数据量 | 来源 | 用途 |
|--------|--------|------|------|
| Reddit 求助/生活帖 | 134,424 条 | 41 个 subreddit | 生活服务需求挖掘 |
| Reddit 服务交易帖 | 23,865 条 | forhire/slavelabour 等 5 个 | 服务品类和定价分析 |
| Reddit AI 讨论帖 | 17,155 条 | 31 个 AI/创业 subreddit | AI Agent 市场趋势 |
| 闲鱼服务商品 | 10,234 条 | goofish.com | 中国市场服务品类 |
| Upwork 职位 | 69 条 | upwork.com | 付费需求验证 |
| 自动化模板 | 63 条 | n8n/Make/Zapier | 模板生态饱和度 |
| Agent 能力基准 | 17 条 | Anthropic/OpenAI/SWE-bench | 技术可行性评估 |
| 生产采用信号 | 35 条 | Anthropic Index/McKinsey/Gartner | 企业采用率数据 |

---

## 已产出报告

| 报告 | 数据基础 | 核心问题 |
|------|---------|---------|
| `comprehensive_market_report_v2.md` | Reddit 17K + Upwork + 模板 + 能力 + 采用 | AI Agent 全球市场机会在哪 |
| `reddit_services_agent_analysis_v2.md` | Reddit 服务交易 23K | 哪些人工服务可被 Agent 替代 |
| `reddit_needs_agent_analysis.md` | Reddit 求助 134K | 日常生活中哪些需求 Agent 能满足 |
| `reddit_life_services_agent_selection.md` | Reddit 求助 80K（筛除办公） | 生活服务 Agent 选品（不被大厂切走） |
| `goofish_agent_marketplace_analysis_v2.md` | 闲鱼 7K | 中国市场 Agent 服务选品 |

---

## 关键技术经验

### Reddit 数据采集
- **首选 JSON API**（`old.reddit.com/r/{sub}/search.json?q={kw}&limit=100`），每页 100 条
- Playwright 仅用于首次探索和需要登录的场景
- 并行 Agent 按 subreddit 分组，通过 progress.json 协调
- 连续空结果自动跳过（consecutive_empty >= 5）

### 闲鱼数据采集
- 网页版需要登录（用户手动扫码后 Agent 继续采集）
- 搜索 URL：`goofish.com/search?q={keyword}`，每页约 30 条，最多 50 页
- 用 Playwright MCP 的 `browser_evaluate` 注入 JS 提取结构化数据
- 分轮采集（每轮扩展关键词），断点续抓

### 大规模数据分析
- 10 万条级别数据：Python 脚本做聚类统计，LLM 只分析高价值子集（Top 100-500）
- 1 万条级别数据：Python 统计 + LLM 分析 Top 50 高热帖
- 交叉验证（Reddit × Upwork × 闲鱼）是最有洞察力的分析方法
- 报告质量公式：定量数据 + 交叉验证 + 评估矩阵 + 分层策略
