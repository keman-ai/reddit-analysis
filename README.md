# 市场调研数据采集与分析工程

一个基于 Claude Code 的市场调研自动化平台。大规模抓取互联网数据（Reddit、闲鱼、Upwork 等），自动清洗、统计、分析，产出结构化的选品/策略报告。

## 使用方法

在本项目目录下启动 Claude Code，直接给出调研任务即可：

```
调研背景：（你要做什么、为什么要调研）
目标网站：（从哪里采集数据，如 Reddit、闲鱼、小红书、Upwork 等）
数据规模：（期望采集多少条，如 1 万条）
分析视角：（你关心什么维度，如 AI 可替代性、市场规模、竞争格局）
```

**示例任务：**

> 我想做一个 AI 陪伴类产品，调研一下 Reddit 上关于孤独感、心理咨询、情感陪伴的讨论，看看需求量级和用户画像。目标 2 万条数据。

**执行过程（全自动）：**

1. 设计关键词和目标社区列表 → 启动采集脚本
2. 后台运行，定期汇报进度
3. 采集完成后自动去重 → Python 定量分析 → LLM 深度分析
4. 产出 Markdown 报告到 `data/reports/`

整个过程只需等结果，中间可以随时问进展或调整方向。

## 已有数据资产

| 数据集 | 数据量 | 来源 |
|--------|--------|------|
| Reddit 求助/生活帖 | 134,424 条 | 41 个 subreddit |
| Reddit 服务交易帖 | 23,865 条 | forhire/slavelabour 等 |
| Reddit AI 讨论帖 | 17,155 条 | 31 个 AI/创业 subreddit |
| 闲鱼服务商品 | 10,234 条 | goofish.com |
| Upwork / 模板 / 能力基准 / 采用信号 | 184 条 | 多源 |

## 已产出报告

| 报告 | 核心问题 |
|------|---------|
| `comprehensive_market_report_v2.md` | AI Agent 全球市场机会在哪 |
| `reddit_services_agent_analysis_v2.md` | 哪些人工服务可被 Agent 替代 |
| `reddit_needs_agent_analysis.md` | 日常需求中 Agent 能满足什么 |
| `reddit_life_services_agent_selection.md` | 生活服务选品（不被大厂切走） |
| `goofish_agent_marketplace_analysis_v2.md` | 中国市场 Agent 服务选品 |

## 项目结构

```
scripts/          # 采集和分析脚本
config/           # 搜索配置（关键词、subreddit、阈值）
data/raw/         # 原始采集数据（JSONL）
data/analyzed/    # 分析后的结构化数据
data/reports/     # Markdown 分析报告
agents/           # Agent Team prompt 定义
docs/             # 架构和设计文档
```
