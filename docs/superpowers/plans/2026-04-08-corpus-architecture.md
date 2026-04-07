# Corpus 历史库架构改造 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace online scraping in Phase 2 with local corpus search, making research tasks complete in seconds instead of minutes.

**Architecture:** New `data/corpus/` directory holds pre-built per-subreddit JSONL files. `search_corpus.py` scans them by keyword. `run.py` defaults to local search, with `--online` fallback. Separate `corpus_build.py` and `corpus_update.py` manage the corpus independently.

**Tech Stack:** Python standard library (json, argparse, os, re, time, urllib)

---

### Task 1: Create `scripts/search_corpus.py`

**Files:**
- Create: `scripts/search_corpus.py`

The core new script — reads a plan JSON, searches local corpus files by keyword, outputs matched posts.

- [ ] **Step 1: Create search_corpus.py**

```python
#!/usr/bin/env python3
"""
从本地 corpus 中按关键词检索帖子。

用法：
    python scripts/search_corpus.py \
        --plan data/raw/{task_id}_plan.json \
        --output data/raw/{task_id}_matched.jsonl
"""

import argparse
import json
import os
import re

CORPUS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'corpus')


def search_subreddit(corpus_file, keywords):
    """Scan a corpus JSONL file, return posts matching any keyword.

    Match is case-insensitive on title + selftext.
    Each post is returned at most once, tagged with the first matching keyword.
    """
    matched = []
    seen_ids = set()

    with open(corpus_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                post = json.loads(line)
            except Exception:
                continue

            pid = post.get('id', '')
            if pid in seen_ids:
                continue

            text = (post.get('title', '') + ' ' + post.get('selftext', '')).lower()

            for kw_term, kw_group in keywords:
                if kw_term.lower() in text:
                    post['search_keyword'] = kw_term
                    post['keyword_group'] = kw_group
                    matched.append(post)
                    seen_ids.add(pid)
                    break

    return matched


def main():
    parser = argparse.ArgumentParser(description='Search local corpus by keywords from plan JSON')
    parser.add_argument('--plan', required=True, help='Path to plan JSON file')
    parser.add_argument('--output', required=True, help='Path to output matched JSONL file')
    args = parser.parse_args()

    with open(args.plan, 'r') as f:
        plan = json.load(f)

    # Build keyword list: [(term, group), ...]
    keywords = [(kw['term'], kw.get('group', 'default')) for kw in plan.get('keywords', [])]

    target_subs = [s['name'] for s in plan.get('subreddits', [])]

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    total_matched = 0
    total_scanned = 0
    missing_subs = []

    with open(args.output, 'w') as fout:
        for sub in target_subs:
            corpus_file = os.path.join(CORPUS_DIR, f"{sub}.jsonl")
            if not os.path.exists(corpus_file):
                missing_subs.append(sub)
                print(f"  Warning: corpus not found for r/{sub}, skipping")
                continue

            # Count lines for progress
            line_count = sum(1 for _ in open(corpus_file))
            print(f"  Searching r/{sub} ({line_count} posts)...", end=' ', flush=True)
            total_scanned += line_count

            matched = search_subreddit(corpus_file, keywords)
            for post in matched:
                fout.write(json.dumps(post, ensure_ascii=False) + '\n')
            total_matched += len(matched)
            print(f"{len(matched)} matched")

    # Print summary
    print(f"\n=== Search Summary ===")
    print(f"Subreddits searched: {len(target_subs) - len(missing_subs)}/{len(target_subs)}")
    print(f"Posts scanned: {total_scanned}")
    print(f"Posts matched: {total_matched}")
    if missing_subs:
        print(f"Missing corpus: {', '.join(missing_subs)}")
    print(f"Output: {args.output}")

    # Write summary JSON
    summary = {
        'total_scanned': total_scanned,
        'total_matched': total_matched,
        'subreddits_searched': len(target_subs) - len(missing_subs),
        'subreddits_missing': missing_subs,
    }
    summary_file = args.output.replace('.jsonl', '_search_summary.json')
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Verify it loads**

Run: `python scripts/search_corpus.py --help`
Expected: argparse help with `--plan` and `--output`.

- [ ] **Step 3: Commit**

```bash
git add scripts/search_corpus.py
git commit -m "feat: add search_corpus.py for local keyword search"
```

---

### Task 2: Create `scripts/corpus_build.py`

**Files:**
- Create: `scripts/corpus_build.py`

One-time corpus builder. Imports core functions from `scrape_reddit.py`.

- [ ] **Step 1: Create corpus_build.py**

```python
#!/usr/bin/env python3
"""
一次性 corpus 灌库脚本。按 subreddit 抓取历史帖子到 data/corpus/。

用法：
    python scripts/corpus_build.py --subreddits personalfinance,writing,worldnews
    python scripts/corpus_build.py --subreddits personalfinance --months 12
    python scripts/corpus_build.py --list config/corpus_subreddits.txt
"""

import argparse
import json
import os
import random
import time
from datetime import datetime

# Import core functions from scrape_reddit
from scrape_reddit import (
    fetch_reddit_search, extract_posts, load_existing_ids,
    USER_AGENT, MAX_PAGES_PER_COMBO, CONSECUTIVE_EMPTY_THRESHOLD
)

CORPUS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'corpus')
META_FILE = os.path.join(CORPUS_DIR, '_meta.json')

# Generic high-frequency search terms to get broad coverage
GENERIC_KEYWORDS = [
    '', 'help', 'best', 'recommend', 'how to', 'need', 'looking for',
    'advice', 'question', 'what', 'anyone', 'experience',
]


def load_meta():
    if os.path.exists(META_FILE):
        with open(META_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_meta(meta):
    with open(META_FILE, 'w') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


def build_subreddit(subreddit, months=12, sort='new', max_pages=10):
    """Scrape a subreddit's historical posts into corpus."""
    corpus_file = os.path.join(CORPUS_DIR, f"{subreddit}.jsonl")
    existing_ids = load_existing_ids(corpus_file)
    initial_count = len(existing_ids)

    time_filter = 'year' if months >= 12 else 'month'

    print(f"\n  Building corpus for r/{subreddit} (existing: {initial_count})")
    total_new = 0
    consecutive_empty = 0

    for keyword in GENERIC_KEYWORDS:
        if consecutive_empty >= CONSECUTIVE_EMPTY_THRESHOLD:
            print(f"    Skipping remaining keywords (5 consecutive empty)")
            break

        label = f'"{keyword}"' if keyword else '(all)'
        print(f"    Keyword {label}...", end=' ', flush=True)

        page_after = None
        kw_new = 0

        for page in range(max_pages):
            data = fetch_reddit_search(subreddit, keyword, sort=sort,
                                       time_filter=time_filter, after=page_after)

            if 'error' in data:
                err = data['error']
                if err == 'rate_limited':
                    wait = 60
                    print(f"429 wait {wait}s...", end=' ', flush=True)
                    time.sleep(wait)
                    data = fetch_reddit_search(subreddit, keyword, sort=sort,
                                               time_filter=time_filter, after=page_after)
                    if 'error' in data:
                        print(f"ERR: {data['error']}")
                        break
                else:
                    print(f"ERR: {err}")
                    break

            posts, page_after = extract_posts(data, subreddit, keyword, 'corpus', 'corpus')

            new_posts = [p for p in posts if p['id'] not in existing_ids]
            if new_posts:
                with open(corpus_file, 'a') as f:
                    for p in new_posts:
                        f.write(json.dumps(p, ensure_ascii=False) + '\n')
                        existing_ids.add(p['id'])
                kw_new += len(new_posts)
                total_new += len(new_posts)

            if not page_after or len(posts) == 0:
                break

            time.sleep(random.uniform(2, 5))

        print(f"{kw_new} new")
        consecutive_empty = consecutive_empty + 1 if kw_new == 0 else 0

        time.sleep(random.uniform(1, 3))

    final_count = len(existing_ids)
    print(f"  r/{subreddit}: {total_new} new posts added (total: {final_count})")
    return final_count


def main():
    parser = argparse.ArgumentParser(description='Build corpus from Reddit subreddits')
    parser.add_argument('--subreddits', help='Comma-separated subreddit names')
    parser.add_argument('--list', help='File with one subreddit per line')
    parser.add_argument('--months', type=int, default=12, help='Months of history (default: 12)')
    parser.add_argument('--max-pages', type=int, default=10, help='Max pages per keyword (default: 10)')
    args = parser.parse_args()

    if not args.subreddits and not args.list:
        parser.print_help()
        return

    # Parse subreddit list
    if args.list:
        with open(args.list) as f:
            subs = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    else:
        subs = [s.strip() for s in args.subreddits.split(',') if s.strip()]

    os.makedirs(CORPUS_DIR, exist_ok=True)
    meta = load_meta()

    print(f"Building corpus for {len(subs)} subreddits, {args.months} months history")

    for sub in subs:
        post_count = build_subreddit(sub, months=args.months, max_pages=args.max_pages)
        meta[sub] = {
            'last_updated': datetime.now().strftime('%Y-%m-%d'),
            'post_count': post_count,
        }
        save_meta(meta)

    print(f"\nCorpus build complete. Meta saved to {META_FILE}")


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Verify it loads**

Run: `python scripts/corpus_build.py --help`
Expected: argparse help with `--subreddits`, `--list`, `--months`, `--max-pages`.

- [ ] **Step 3: Commit**

```bash
git add scripts/corpus_build.py
git commit -m "feat: add corpus_build.py for one-time corpus population"
```

---

### Task 3: Create `scripts/corpus_update.py`

**Files:**
- Create: `scripts/corpus_update.py`

Incremental updater — fetches only recent posts for existing corpus subreddits.

- [ ] **Step 1: Create corpus_update.py**

```python
#!/usr/bin/env python3
"""
增量更新 corpus。遍历已有 corpus 的 subreddit，只抓最近 N 天新帖。

用法：
    python scripts/corpus_update.py                    # 更新所有，最近 7 天
    python scripts/corpus_update.py --days 3           # 最近 3 天
    python scripts/corpus_update.py --subreddits writing,worldnews  # 只更新指定的
"""

import argparse
import json
import os
import random
import time
from datetime import datetime

from scrape_reddit import (
    fetch_reddit_search, extract_posts, load_existing_ids,
)

CORPUS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'corpus')
META_FILE = os.path.join(CORPUS_DIR, '_meta.json')


def load_meta():
    if os.path.exists(META_FILE):
        with open(META_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_meta(meta):
    with open(META_FILE, 'w') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


def update_subreddit(subreddit, days=7):
    """Fetch recent posts for a subreddit and append new ones to corpus."""
    corpus_file = os.path.join(CORPUS_DIR, f"{subreddit}.jsonl")
    existing_ids = load_existing_ids(corpus_file)
    initial_count = len(existing_ids)

    time_filter = 'week' if days <= 7 else 'month'

    print(f"  Updating r/{subreddit} (existing: {initial_count})...", end=' ', flush=True)

    total_new = 0
    # Use sort=new to get the most recent posts
    for sort in ['new', 'hot']:
        page_after = None
        for page in range(3):  # Max 3 pages per sort
            data = fetch_reddit_search(subreddit, '', sort=sort,
                                       time_filter=time_filter, after=page_after)

            if 'error' in data:
                err = data['error']
                if err == 'rate_limited':
                    time.sleep(60)
                    data = fetch_reddit_search(subreddit, '', sort=sort,
                                               time_filter=time_filter, after=page_after)
                    if 'error' in data:
                        break
                else:
                    break

            posts, page_after = extract_posts(data, subreddit, '', 'update', 'corpus')

            new_posts = [p for p in posts if p['id'] not in existing_ids]
            if new_posts:
                with open(corpus_file, 'a') as f:
                    for p in new_posts:
                        f.write(json.dumps(p, ensure_ascii=False) + '\n')
                        existing_ids.add(p['id'])
                total_new += len(new_posts)

            if not page_after or len(posts) == 0:
                break

            time.sleep(random.uniform(2, 5))

        time.sleep(random.uniform(1, 3))

    final_count = len(existing_ids)
    print(f"+{total_new} new (total: {final_count})")
    return final_count


def main():
    parser = argparse.ArgumentParser(description='Incrementally update corpus with recent posts')
    parser.add_argument('--subreddits', help='Comma-separated subreddits (default: all in corpus)')
    parser.add_argument('--days', type=int, default=7, help='Fetch posts from last N days (default: 7)')
    args = parser.parse_args()

    meta = load_meta()

    if args.subreddits:
        subs = [s.strip() for s in args.subreddits.split(',') if s.strip()]
    else:
        # Update all subreddits that have corpus files
        subs = list(meta.keys())
        if not subs:
            # Fallback: scan directory
            subs = [f.replace('.jsonl', '') for f in os.listdir(CORPUS_DIR)
                    if f.endswith('.jsonl') and not f.startswith('_')]

    if not subs:
        print("No subreddits to update. Run corpus_build.py first.")
        return

    print(f"Updating {len(subs)} subreddits (last {args.days} days)")

    for sub in subs:
        corpus_file = os.path.join(CORPUS_DIR, f"{sub}.jsonl")
        if not os.path.exists(corpus_file):
            print(f"  Warning: no corpus file for r/{sub}, skipping (use corpus_build.py)")
            continue

        post_count = update_subreddit(sub, days=args.days)
        meta[sub] = {
            'last_updated': datetime.now().strftime('%Y-%m-%d'),
            'post_count': post_count,
        }
        save_meta(meta)

    print(f"\nUpdate complete. Meta saved to {META_FILE}")


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Verify it loads**

Run: `python scripts/corpus_update.py --help`
Expected: argparse help with `--subreddits`, `--days`.

- [ ] **Step 3: Commit**

```bash
git add scripts/corpus_update.py
git commit -m "feat: add corpus_update.py for incremental corpus updates"
```

---

### Task 4: Modify `run.py` — add `--online` flag and `phase2_search`

**Files:**
- Modify: `run.py`

Replace the default Phase 2 with local corpus search. Keep online scraping as `--online` fallback.

- [ ] **Step 1: Add `--online` argument and `phase2_search` function, update main()**

In `run.py`, make the following changes:

**Add `DATA_CORPUS` constant after line 25:**
```python
DATA_CORPUS = PROJECT_ROOT / 'data' / 'corpus'
```

**Update `ensure_dirs()` to include corpus dir:**
```python
def ensure_dirs():
    """Ensure all required directories exist."""
    for d in [DATA_RAW, DATA_ANALYZED, DATA_REPORTS, DATA_CORPUS]:
        d.mkdir(parents=True, exist_ok=True)
```

**Update status phases dict** in `update_status()` — change phase 2 name:
```python
        'phases': {
            1: 'Task Planning',
            2: 'Corpus Search',
            3: 'Quantitative Analysis',
            4: 'Report Generation',
        },
```

**Add `phase2_search` function** after `phase1_plan` (before `phase2_scrape`):

```python
def phase2_search(plan: dict, start_time: float = 0) -> str:
    """Phase 2: Search local corpus for matching posts."""
    print()
    print("=" * 60)
    print("Phase 2: Corpus Search")
    print("=" * 60)

    task_id = plan['task_id']
    matched_file = DATA_RAW / f"{task_id}_matched.jsonl"

    update_status(task_id, 2, 'Corpus Search', 'running',
                  'Searching local corpus...', start_time)

    search_cmd = [
        sys.executable, str(PROJECT_ROOT / 'scripts' / 'search_corpus.py'),
        '--plan', str(DATA_RAW / f"{task_id}_plan.json"),
        '--output', str(matched_file),
    ]

    process = subprocess.Popen(
        search_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=str(PROJECT_ROOT),
    )

    for line in iter(process.stdout.readline, ''):
        print(f"  {line}", end='')
    process.wait()

    if not matched_file.exists() or matched_file.stat().st_size == 0:
        print("  Warning: No matching posts found in corpus.")
        print("  Hint: Build corpus first with: python scripts/corpus_build.py --subreddits <subs>")
        print("  Or use --online flag to scrape directly.")
        # Create empty file so pipeline can continue (analysis will show 0 posts)
        matched_file.touch()

    line_count = sum(1 for line in open(matched_file) if line.strip()) if matched_file.exists() else 0
    print(f"\n  Matched posts: {line_count}")

    update_status(task_id, 2, 'Corpus Search', 'completed',
                  f'{line_count} posts matched from corpus', start_time,
                  posts_matched=line_count)
    return str(matched_file)
```

**Add `--online` to argparse** in `main()`:
```python
    parser.add_argument('--online', action='store_true',
                        help='Use online scraping instead of local corpus search')
```

**Update Phase 2 dispatch in `main()`** — replace the current phase 2 block:
```python
    # Phase 2
    if from_phase <= 2:
        if args.online:
            data_file = phase2_scrape(plan, start_time=start_time)
        else:
            data_file = phase2_search(plan, start_time=start_time)
    else:
        # When resuming from phase 3+, try matched file first, then deduped
        matched = str(DATA_RAW / f"{task_id}_matched.jsonl")
        deduped = str(DATA_RAW / f"{task_id}_deduped.jsonl")
        data_file = matched if os.path.exists(matched) else deduped
```

**Update Phase 3 call** to use `data_file` instead of `deduped_file`:
```python
    # Phase 3
    if from_phase <= 3:
        if not os.path.exists(data_file):
            print(f"Error: Data file not found: {data_file}")
            sys.exit(1)
        stats_file = phase3_analyze(plan, data_file, start_time=start_time)
```

**Update final summary** to show the correct data file:
```python
    print(f"  Data:     {os.path.relpath(data_file, PROJECT_ROOT)}")
```

- [ ] **Step 2: Verify run.py loads**

Run: `python run.py --help`
Expected: Shows `--online` in the options list.

- [ ] **Step 3: Commit**

```bash
git add run.py
git commit -m "feat: add --online flag and phase2_search for corpus-based lookup"
```

---

### Task 5: Update `SKILL.md`

**Files:**
- Modify: `SKILL.md`

- [ ] **Step 1: Add corpus management section**

Add the following section after the "查看实时进度" section and before "常见问题":

```markdown
## Corpus 历史库管理

默认模式下，工具从本地 corpus 检索帖子（秒级），不做在线抓取。需要先构建 corpus。

### 初始化 corpus（一次性）

```bash
# 灌入指定 subreddit 的最近 12 个月帖子
python scripts/corpus_build.py --subreddits personalfinance,writing,worldnews

# 从文件批量灌入
python scripts/corpus_build.py --list config/corpus_subreddits.txt

# 指定月份数
python scripts/corpus_build.py --subreddits politics --months 6
```

### 增量更新（每日/每周）

```bash
# 更新所有已有 corpus（最近 7 天）
python scripts/corpus_update.py

# 只更新指定 subreddit
python scripts/corpus_update.py --subreddits politics,worldnews

# 更新最近 3 天
python scripts/corpus_update.py --days 3
```

### 查看 corpus 状态

```bash
cat data/corpus/_meta.json
```

### 在线抓取模式

如果不想维护 corpus，可以用 `--online` 回退到旧的在线抓取模式：

```bash
python run.py --online "调研 AI 写作工具"
```
```

- [ ] **Step 2: Update the execution flow diagram** to reflect the change:

Replace the existing execution flow section:

```markdown
## 执行流程

```
Phase 1: 任务规划    → LLM 生成搜索计划（subreddit + 关键词 + 数据量）
Phase 2: Corpus 检索  → 从本地历史库按关键词匹配帖子（秒级）
Phase 3: 定量分析    → Python 脚本做统计（分布、热度、价格、分类）
Phase 4: 报告生成    → LLM 基于统计数据 + 高热帖子生成中文报告

如果使用 --online 模式：
Phase 2: 在线抓取    → Python 脚本调 Reddit JSON API，断点续抓（分钟级）
```
```

- [ ] **Step 3: Commit**

```bash
git add SKILL.md
git commit -m "docs: update SKILL.md with corpus management instructions"
```

---

### Task 6: End-to-end test

**Files:**
- No new files

- [ ] **Step 1: Build a small test corpus**

```bash
python scripts/corpus_build.py --subreddits learnprogramming --months 1 --max-pages 2
```

Expected: Creates `data/corpus/learnprogramming.jsonl` and `data/corpus/_meta.json`.

- [ ] **Step 2: Verify corpus files**

```bash
wc -l data/corpus/learnprogramming.jsonl
cat data/corpus/_meta.json
```

Expected: Non-zero line count, meta shows `learnprogramming` with today's date.

- [ ] **Step 3: Test corpus search with a plan**

Create a test plan:
```bash
cat > data/raw/corpus_test_plan.json << 'EOF'
{
  "task_id": "corpus_test",
  "task_description": "test corpus search",
  "subreddits": [
    {"name": "learnprogramming", "group": "core"},
    {"name": "nonexistent_sub_12345", "group": "extended"}
  ],
  "keywords": [
    {"term": "python", "group": "language"},
    {"term": "javascript", "group": "language"}
  ],
  "target_posts": 100,
  "analysis_focus": ["test"]
}
EOF
python scripts/search_corpus.py --plan data/raw/corpus_test_plan.json --output data/raw/corpus_test_matched.jsonl
```

Expected: 
- Prints warning for `nonexistent_sub_12345`
- Shows match count for `learnprogramming`
- Creates `corpus_test_matched.jsonl`

- [ ] **Step 4: Test full pipeline with corpus mode (default)**

```bash
python run.py --resume corpus_test --from-phase 3
```

Expected: Phase 3 reads `corpus_test_matched.jsonl`, produces stats. Phase 4 generates report.

- [ ] **Step 5: Test --online flag still works**

```bash
python run.py --online --task-id online_test "从 r/learnprogramming 抓取 python 相关帖子，目标 30 条"
```

Expected: Uses old scraping path, creates `online_test_deduped.jsonl`.

- [ ] **Step 6: Clean up test data**

```bash
rm -f data/raw/corpus_test* data/raw/online_test* data/analyzed/corpus_test* data/analyzed/online_test* data/reports/corpus_test* data/reports/online_test*
rm -rf data/corpus/learnprogramming.jsonl
```

- [ ] **Step 7: Commit any remaining fixes**

```bash
git add -A && git status
# Only commit if there are fixes from testing
```
