# Corpus 历史库架构改造设计

> 日期：2026-04-08
> 状态：设计完成，待实施

## 一、目标

将 run.py 的 Phase 2 从在线抓取（5-10 分钟）改为本地 corpus 检索（秒级）。Corpus 由独立脚本预先构建和增量更新，与调研任务解耦。

## 二、整体架构

```
data/corpus/                          独立维护的历史库
├── personalfinance.jsonl             每个 subreddit 一个文件
├── writing.jsonl
├── worldnews.jsonl
├── ...
└── _meta.json                        元数据索引

用户输入 → Phase 1      → Phase 2        → Phase 3  → Phase 4
           构造关键词      本地检索          分析        报告
           (LLM ~30s)    (Python ~2s)    (Python ~1s) (LLM ~3min)
```

## 三、新增文件

### 3.1 `scripts/corpus_build.py`

一次性灌库脚本。复用 `scrape_reddit.py` 的核心抓取函数。

```bash
# 灌入指定 subreddit
python scripts/corpus_build.py --subreddits personalfinance,writing,worldnews

# 指定时间范围
python scripts/corpus_build.py --subreddits personalfinance --months 12

# 从文件读取 subreddit 列表
python scripts/corpus_build.py --list config/corpus_subreddits.txt
```

行为：
- 对每个 subreddit，用通用搜索词（空字符串或高频词）抓取 top/new 帖子
- 输出到 `data/corpus/{subreddit}.jsonl`
- 如果 corpus 文件已存在，跳过已有 ID（增量追加）
- 更新 `data/corpus/_meta.json`
- 支持断点续抓（复用 progress.json 机制）

### 3.2 `scripts/corpus_update.py`

增量更新脚本。遍历已有 corpus，只抓最近 N 天新帖。

```bash
# 更新所有已有 corpus 的 subreddit
python scripts/corpus_update.py

# 只更新指定的
python scripts/corpus_update.py --subreddits personalfinance,writing

# 指定天数（默认 7）
python scripts/corpus_update.py --days 3
```

行为：
- 读取 `_meta.json` 获取已有 subreddit 列表
- 对每个 sub，用 `sort=new&t=week` 抓取最近帖子
- 跳过已有 ID，只追加新帖
- 更新 `_meta.json` 的 `last_updated` 和 `post_count`

### 3.3 `scripts/search_corpus.py`

本地关键词检索脚本。

```bash
python scripts/search_corpus.py \
  --plan data/raw/{task_id}_plan.json \
  --output data/raw/{task_id}_matched.jsonl
```

行为：
1. 读取 plan JSON 中的 subreddits 和 keywords
2. 对每个目标 subreddit，检查 `data/corpus/{sub}.jsonl` 是否存在
   - 存在：扫描文件，对每条帖子的 title + selftext 做大小写无关的关键词匹配
   - 不存在：打印警告 `Warning: corpus not found for r/{sub}, skipping`
3. 匹配到的帖子写入 output JSONL（自动去重）
4. 输出匹配统计摘要

匹配规则：帖子的 `title + selftext` 中包含任一 keyword（大小写无关）即命中。每条帖子只输出一次（即使匹配多个关键词），但记录匹配到的第一个 keyword 和 keyword_group。

### 3.4 `data/corpus/_meta.json`

```json
{
  "personalfinance": {
    "last_updated": "2026-04-08",
    "post_count": 45000,
    "oldest_post": "2025-04-01",
    "newest_post": "2026-04-08"
  },
  "writing": {
    "last_updated": "2026-04-07",
    "post_count": 32000,
    "oldest_post": "2025-04-01",
    "newest_post": "2026-04-07"
  }
}
```

## 四、现有文件改动

### 4.1 `run.py`

Phase 2 改为调用 `search_corpus.py`：

```python
def phase2_search(plan, start_time=0):
    """Phase 2: Search local corpus for matching posts."""
    # 调用 search_corpus.py
    # 输出 data/raw/{task_id}_matched.jsonl
    # 如果匹配数为 0，提示用户检查 corpus 或使用 --online 模式
```

新增 `--online` 标志保留旧的在线抓取模式：

```bash
# 默认：本地检索（秒级）
python run.py "调研 AI 写作工具"

# 强制在线抓取（旧模式）
python run.py --online "调研 AI 写作工具"
```

Phase 3 的输入从 `_deduped.jsonl` 改为 `_matched.jsonl`（在线模式下仍用 `_deduped.jsonl`）。

### 4.2 `scripts/scrape_reddit.py`

不做改动。`corpus_build.py` 和 `corpus_update.py` 通过 import 复用其核心函数：
- `fetch_reddit_search()`
- `extract_posts()`
- `load_existing_ids()`

为此需要确保这些函数可以被外部 import（当前已经是模块级函数，无需改动）。

### 4.3 `SKILL.md`

新增 corpus 管理章节：
- 如何初始化 corpus
- 如何增量更新
- 如何查看 corpus 状态
- `--online` 模式说明

## 五、数据流对比

### 改造前
```
用户输入 → 关键词(LLM) → 在线抓取(5-10min) → 去重 → 分析 → 报告
```

### 改造后
```
[预先] corpus_build.py → data/corpus/
[每日] corpus_update.py → data/corpus/ (追加)

用户输入 → 关键词(LLM) → 本地检索(2s) → 分析 → 报告
                            ↓ (如果 --online)
                         在线抓取(旧模式)
```

## 六、不做的事

- 不做全文搜索引擎或倒排索引（逐行扫描 JSONL 对 10 万条级数据足够快）
- 不自动触发抓取（corpus 缺失时只警告）
- 不改 Phase 1（关键词构造）、Phase 3（分析）、Phase 4（报告）
- 不做 corpus 的自动清理或过期机制
- corpus_build/update 不需要 Claude CLI（纯 Python）
