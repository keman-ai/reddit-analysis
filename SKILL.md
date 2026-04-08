---
name: reddit-research
description: >
  Reddit 市场调研自动化工具。用户给出调研任务描述，自动完成关键词规划、数据检索、定量分析和报告生成。
  当用户提到以下场景时使用此 skill：市场调研、用户需求分析、竞品分析、Reddit 数据分析、
  舆情分析、选品调研、行业趋势研究、消费者洞察、产品市场调研、用户画像分析。
  即使用户没有明确提到 Reddit，只要涉及"帮我调研一下"、"分析一下市场"、"看看用户怎么说"等调研意图，
  都应该使用此 skill。
---

# Reddit 市场调研自动化

将用户的调研任务描述转化为结构化的 Reddit 数据分析报告。整个流程自动化执行，产出 Markdown 格式的中文调研报告。

## 工作原理

四阶段流水线，前三阶段秒级完成，第四阶段需要 3-5 分钟（LLM 生成报告）：

```
Phase 1: 任务规划    → LLM 将用户描述转为搜索计划（subreddit + 关键词）
Phase 2: Corpus 检索  → 从本地 10 万条历史库中按关键词匹配（秒级）
Phase 3: 定量分析    → Python 统计分布、热度、价格、分类
Phase 4: 报告生成    → LLM 基于数据生成 4000-7000 字中文报告
```

## 执行步骤

收到用户的调研请求后，按以下步骤执行：

### 1. 确认任务

用户的描述可以是粗粒度（"调研 AI 写作工具的市场需求"）或细粒度（"从 r/writing 分析 AI writing tools 的定价和竞品"）。两者都支持，直接执行即可。

### 2. 运行调研任务

在项目根目录执行（后台运行，因为 Phase 4 需要几分钟）：

```bash
python run.py "用户的调研任务描述"
```

如果用户指定了具体参数，可以传 `--task-id`：

```bash
python run.py --task-id custom_id "用户的调研任务描述"
```

如果本地没有 corpus 数据或匹配量太少，加 `--online` 走在线抓取（更慢但不依赖历史库）：

```bash
python run.py --online "用户的调研任务描述"
```

### 3. 监控进度

任务运行期间，定期读取 status 文件汇报进度：

```bash
cat data/raw/{task_id}_status.json
```

status 字段含义：`running`（进行中）、`completed`（当前阶段完成）、`done`（全部完成）、`error`（出错）。

### 4. 返回结果

任务完成后，告诉用户报告路径，并呈现报告的核心结论表格（不要在对话中输出完整报告）：

```
报告已生成：data/reports/{task_id}_report.md
```

### 5. 断点续跑

如果任务中断或用户想重新生成报告：

```bash
python run.py --resume {task_id}                # 从中断处继续
python run.py --resume {task_id} --from-phase 3  # 跳到分析阶段
python run.py --resume {task_id} --from-phase 4  # 只重新生成报告
```

## Corpus 历史库

工具默认从 `data/corpus/` 目录的本地历史库检索数据。历史库按 subreddit 存储（每个 sub 一个 JSONL 文件），需要提前构建。

### 构建和更新

```bash
# 一次性灌入（指定 subreddit）
python scripts/corpus_build.py --subreddits personalfinance,writing,worldnews

# 从配置文件批量灌入
python scripts/corpus_build.py --list config/corpus_subreddits.txt

# 增量更新（最近 7 天新帖）
python scripts/corpus_update.py

# 查看 corpus 状态
cat data/corpus/_meta.json
```

### 当前 corpus 规模

配置文件 `config/corpus_subreddits.txt` 定义了目标 subreddit 列表（325 个），覆盖商业、AI、职场、理财、学术、写作、消费等领域。

## 报告质量标准

生成的报告遵循 CLAUDE.md 中定义的质量红线：
- 每个结论引用具体数据（帖子数、百分比、中位数）
- 引用帖子附可点击的 Reddit URL
- 评估矩阵用表格呈现
- 中文撰写，4000-7000 字
- 包含：执行摘要、数据概览、核心分析、策略推荐、风险警示、附录

## 前置条件

- Python 3.8+（仅标准库）
- Claude Code CLI（`claude` 命令可用）
- `data/corpus/` 目录有历史数据（或使用 `--online` 模式）

## 项目结构

```
run.py                          # 主入口
scripts/
├── scrape_reddit.py            # Reddit JSON API 抓取
├── search_corpus.py            # 本地 corpus 关键词检索
├── analyze.py                  # 定量统计分析
├── corpus_build.py             # 一次性 corpus 构建
└── corpus_update.py            # 增量 corpus 更新
prompts/
├── plan_task.md                # 任务规划 prompt 模板
└── generate_report.md          # 报告生成 prompt 模板
config/
└── corpus_subreddits.txt       # corpus 目标 subreddit 列表
data/
├── corpus/                     # 历史库（按 subreddit 存储）
├── raw/                        # 任务中间数据
├── analyzed/                   # 统计结果
└── reports/                    # 最终报告
```
