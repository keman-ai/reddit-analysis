# 小红书 AI Agent 选品分析流水线 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从灰豚导出的 ~24,676 条小红书数据中，通过清洗→粗筛→LLM打标→聚合评分，输出 AI Agent 可替代服务的选品报告。

**Architecture:** 4-stage Python pipeline，每个 stage 是独立脚本，通过 JSONL 文件传递数据。Stage 3 调用 Claude Haiku API 批量打标。

**Tech Stack:** Python 3, csv, json, anthropic SDK (Haiku), math (log normalization)

**Spec:** `docs/superpowers/specs/2026-03-19-xiaohongshu-agent-selection-design.md`

---

## File Structure

```
scripts/xiaohongshu/
├── stage1_merge.py          # Stage 1: CSV合并去重清洗
├── stage2_filter.py         # Stage 2: 关键词粗筛
├── stage3_label.py          # Stage 3: LLM批量打标
├── stage4_analyze.py        # Stage 4: 统计聚合+评分+报告生成
└── config.py                # 共享配置（路径、关键词、种子品类）

data/raw/xiaohongshu/        # Stage 1-3 输出
data/analyzed/xiaohongshu/   # Stage 4 输出
data/reports/                # 最终报告
```

---

### Task 1: 共享配置模块

**Files:**
- Create: `scripts/xiaohongshu/config.py`

- [ ] **Step 1: 创建 config.py**

```python
#!/usr/bin/env python3
"""Shared configuration for Xiaohongshu pipeline."""

BASE_DIR = '/Users/huanghaibin/Workspace/reddit_research'
SOURCE_DIR = f'{BASE_DIR}/灰豚-求助帖'
XHS_RAW_DIR = f'{BASE_DIR}/data/raw/xiaohongshu'
XHS_ANALYZED_DIR = f'{BASE_DIR}/data/analyzed/xiaohongshu'
REPORTS_DIR = f'{BASE_DIR}/data/reports'

# CSV files and their source labels
CSV_FILES = {
    'xhs_export_excel20263_在线求助_1001158683_1773907768048.csv': '在线求助',
    'xhs_export_excel20263_求助帖子数据_1001158683_1773907474666.csv': '求助帖子数据',
    'xhs_export_excel20263_求助低粉爆文_1001158683_1773908321212.csv': '求助低粉爆文',
    'xhs_export_excel20263_有偿 数据_1001158683_1773908527262.csv': '有偿数据',
    'xhs_export_excel20263_求推荐_1001158683_1773908668786.csv': '求推荐',
}

# Chinese field name -> English field name mapping
FIELD_MAP = {
    '笔记官方地址': 'note_url',
    '笔记标题': 'title',
    '笔记内容': 'content',
    '预估阅读量': 'estimated_reads',
    '互动量': 'engagement',
    '点赞数': 'likes',
    '收藏数': 'bookmarks',
    '评论数': 'comments',
    '分享数': 'shares',
    '发布时间': 'publish_time',
    '封面图片地址': 'cover_image_url',
    '视频链接': 'video_url',
    '是否商业笔记': 'is_commercial',
    '报备品牌企业号': 'brand_account',
    '提及品牌': 'mentioned_brands',
    '是否参与付费推广': 'is_paid_promotion',
    '达人名称': 'creator_name',
    '小红书号': 'xhs_id',
    '主页链接': 'profile_url',
    '粉丝数': 'follower_count',
    '联系方式': 'contact_info',
    '笔记类型': 'note_type',
}

# Stage 2: Inclusion keywords
INCLUSION_KEYWORDS = {
    'service_signal': [
        '有偿', '付费', '收费', '接单', '代做', '代写', '代画', '代剪', '包满意',
        '帮我', '帮忙做', '谁能帮', '求大佬', '哪里可以', '怎么找人',
        '求推荐工具', '有没有好用的', '求app', '求软件',
    ],
    'document': ['PPT', 'ppt', '简历', '论文', '报告', '文案', '公文', '翻译'],
    'design': ['logo', 'Logo', 'LOGO', '海报', '头像', '封面', 'P图', 'p图', '修图', 'UI', 'ui'],
    'tech': ['爬虫', '网站', '小程序', '数据分析', 'Excel', 'excel', 'Python', 'python', '代码'],
    'ai_tool': ['AI工具', 'AI绘画', 'AI生成', 'AI代', 'AI写', 'ChatGPT', 'GPT', 'Midjourney', 'Stable Diffusion', 'Kimi', '豆包', '通义'],
}

# Stage 2: Exclusion keywords
EXCLUSION_KEYWORDS = [
    '搬家', '维修', '安装', '配送', '上门', '家政', '保洁',
    '就医', '律师', '法律咨询', '诊断', '处方',
    '二手', '闲置', '转让', '出售实物',
    '找对象', '相亲', '脱单', '表白',
]

# Stage 3: Seed categories for LLM labeling
SEED_CATEGORIES = [
    'PPT制作', '简历优化', '论文润色', '文案撰写', '翻译', '公文写作', '报告撰写',
    'Logo设计', '海报设计', '头像制作', '封面设计', '修图/P图', 'UI设计',
    '网站开发', '小程序开发', '数据分析', 'Excel处理', '爬虫/数据采集', '代码开发',
    'AI工具咨询', 'AI绘画', 'AI视频',
    '取名/命名', '占卜/塔罗', '心理咨询', '教育辅导', '职业规划',
]

# Stage 4: Scoring weights
SCORING_WEIGHTS = {
    'ai_replaceability': 0.35,
    'standardization': 0.25,
    'demand_heat': 0.20,
    'engagement': 0.10,
    'digital_ratio': 0.10,
}

# Cross-validation: Xiaohongshu -> Goofish category mapping
# Goofish keyword_group values: ai_related, consulting, data_doc, design, education, errand, marketing, programming, translation, writing
XHS_TO_GOOFISH_MAP = {
    'writing': ['PPT制作', '简历优化', '论文润色', '文案撰写', '报告撰写', '公文写作'],
    'design': ['Logo设计', '海报设计', '头像制作', '封面设计', '修图/P图', 'UI设计'],
    'translation': ['翻译'],
    'programming': ['网站开发', '小程序开发', '代码开发', '爬虫/数据采集', '数据分析', 'Excel处理'],
    'ai_related': ['AI工具咨询', 'AI绘画', 'AI视频'],
    'education': ['教育辅导'],
    'consulting': ['心理咨询', '职业规划'],
}
```

- [ ] **Step 2: 创建输出目录**

Run:
```bash
mkdir -p /Users/huanghaibin/Workspace/reddit_research/scripts/xiaohongshu
mkdir -p /Users/huanghaibin/Workspace/reddit_research/data/raw/xiaohongshu
mkdir -p /Users/huanghaibin/Workspace/reddit_research/data/analyzed/xiaohongshu
```

- [ ] **Step 3: Commit**

```bash
git add scripts/xiaohongshu/config.py
git commit -m "feat(xhs): add shared config for Xiaohongshu pipeline"
```

---

### Task 2: Stage 1 — CSV 合并去重清洗

**Files:**
- Create: `scripts/xiaohongshu/stage1_merge.py`

- [ ] **Step 1: 写 stage1_merge.py**

```python
#!/usr/bin/env python3
"""Stage 1: Merge, deduplicate, and clean Xiaohongshu CSV exports."""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import SOURCE_DIR, XHS_RAW_DIR, CSV_FILES, FIELD_MAP

OUTPUT_PATH = f'{XHS_RAW_DIR}/posts_merged.jsonl'


def parse_number(val):
    """Parse numeric string, return 0 for missing/invalid values."""
    if not val or val == '--':
        return 0
    val = val.replace(',', '').strip()
    try:
        return int(val)
    except ValueError:
        try:
            return float(val)
        except ValueError:
            return 0


def parse_bool_cn(val):
    """Parse Chinese boolean (是/否)."""
    return val.strip() == '是' if val else False


def process_row(row, source_label):
    """Convert a CSV row dict to cleaned English-key dict."""
    record = {}
    for cn_key, en_key in FIELD_MAP.items():
        record[en_key] = row.get(cn_key, '').strip() if row.get(cn_key) else ''

    # Type conversions
    for num_field in ['estimated_reads', 'engagement', 'likes', 'bookmarks', 'comments', 'shares', 'follower_count']:
        record[num_field] = parse_number(record[num_field])
    for bool_field in ['is_commercial', 'is_paid_promotion']:
        record[bool_field] = parse_bool_cn(record[bool_field])

    record['source_file'] = source_label
    return record


def main():
    seen_urls = set()
    total_read = 0
    total_deduped = 0
    records = []

    for filename, label in CSV_FILES.items():
        filepath = os.path.join(SOURCE_DIR, filename)
        if not os.path.exists(filepath):
            print(f'WARNING: {filepath} not found, skipping')
            continue

        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                total_read += 1
                url = row.get('笔记官方地址', '').strip()
                # Skip empty or duplicate
                if not url or url in seen_urls:
                    continue
                title = row.get('笔记标题', '').strip()
                content = row.get('笔记内容', '').strip()
                if not title and not content:
                    continue

                seen_urls.add(url)
                records.append(process_row(row, label))
                count += 1
            print(f'  {label}: {count} unique records from {filepath}')

    total_deduped = len(records)

    os.makedirs(XHS_RAW_DIR, exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

    print(f'\nTotal read: {total_read}')
    print(f'After dedup: {total_deduped}')
    print(f'Duplicates removed: {total_read - total_deduped}')
    print(f'Output: {OUTPUT_PATH}')


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: 运行并验证**

Run: `python3 scripts/xiaohongshu/stage1_merge.py`

Expected: 输出合并统计，生成 `data/raw/xiaohongshu/posts_merged.jsonl`。验证：
```bash
wc -l data/raw/xiaohongshu/posts_merged.jsonl
head -1 data/raw/xiaohongshu/posts_merged.jsonl | python3 -m json.tool
```
Expected: ~20K 行，JSON 字段为英文 key。

- [ ] **Step 3: Commit**

```bash
git add scripts/xiaohongshu/stage1_merge.py data/raw/xiaohongshu/posts_merged.jsonl
git commit -m "feat(xhs): stage 1 - merge and deduplicate 24K CSV records"
```

---

### Task 3: Stage 2 — 关键词规则粗筛

**Files:**
- Create: `scripts/xiaohongshu/stage2_filter.py`

- [ ] **Step 1: 写 stage2_filter.py**

```python
#!/usr/bin/env python3
"""Stage 2: Keyword-based filtering to reduce dataset to service-related candidates."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import XHS_RAW_DIR, INCLUSION_KEYWORDS, EXCLUSION_KEYWORDS

INPUT_PATH = f'{XHS_RAW_DIR}/posts_merged.jsonl'
OUTPUT_PATH = f'{XHS_RAW_DIR}/posts_filtered.jsonl'
STATS_PATH = f'{XHS_RAW_DIR}/filter_stats.json'


def matches_any(text, keywords):
    """Check if text contains any of the keywords."""
    text_lower = text.lower()
    for kw in keywords:
        if kw.lower() in text_lower:
            return True
    return False


def get_matched_keywords(text, keywords):
    """Return list of matched keywords."""
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def main():
    records = []
    with open(INPUT_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            records.append(json.loads(line))

    stats = {
        'total_input': len(records),
        'source_auto_include': 0,
        'keyword_matches': {group: 0 for group in INCLUSION_KEYWORDS},
        'exclusion_hits': 0,
        'total_output': 0,
    }

    filtered = []
    for r in records:
        text = f"{r.get('title', '')} {r.get('content', '')}"

        # Rule 3: Auto-include records from 有偿 source (before exclusion check)
        if r.get('source_file') == '有偿数据':
            stats['source_auto_include'] += 1
            r['filter_reason'] = 'source:有偿数据'
            filtered.append(r)
            continue

        # Exclusion check (only for non-有偿 records)
        if matches_any(text, EXCLUSION_KEYWORDS):
            stats['exclusion_hits'] += 1
            continue

        # Rule 1+2: Keyword matching
        matched_groups = []
        for group, keywords in INCLUSION_KEYWORDS.items():
            if matches_any(text, keywords):
                matched_groups.append(group)
                stats['keyword_matches'][group] += 1

        if matched_groups:
            r['filter_reason'] = ','.join(matched_groups)
            filtered.append(r)

    stats['total_output'] = len(filtered)

    os.makedirs(XHS_RAW_DIR, exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        for r in filtered:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

    with open(STATS_PATH, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f'Input: {stats["total_input"]}')
    print(f'Auto-included (有偿): {stats["source_auto_include"]}')
    print(f'Keyword matches by group:')
    for group, count in stats['keyword_matches'].items():
        print(f'  {group}: {count}')
    print(f'Excluded: {stats["exclusion_hits"]}')
    print(f'Output: {stats["total_output"]}')
    print(f'\nSaved to: {OUTPUT_PATH}')
    print(f'Stats: {STATS_PATH}')


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: 运行并验证**

Run: `python3 scripts/xiaohongshu/stage2_filter.py`

Expected: 输出筛选统计。验证数量在 3-5K 范围：
```bash
wc -l data/raw/xiaohongshu/posts_filtered.jsonl
cat data/raw/xiaohongshu/filter_stats.json
```

如果数量偏离目标，调整 `config.py` 中的关键词后重跑。

- [ ] **Step 3: Commit**

```bash
git add scripts/xiaohongshu/stage2_filter.py data/raw/xiaohongshu/posts_filtered.jsonl data/raw/xiaohongshu/filter_stats.json
git commit -m "feat(xhs): stage 2 - keyword filtering to ~3-5K candidates"
```

---

### Task 4: Stage 3 — LLM 批量打标

**Files:**
- Create: `scripts/xiaohongshu/stage3_label.py`

- [ ] **Step 1: 写 stage3_label.py**

```python
#!/usr/bin/env python3
"""Stage 3: LLM batch labeling using Claude Haiku."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import XHS_RAW_DIR, SEED_CATEGORIES

INPUT_PATH = f'{XHS_RAW_DIR}/posts_filtered.jsonl'
OUTPUT_PATH = f'{XHS_RAW_DIR}/posts_labeled.jsonl'
PROGRESS_PATH = f'{XHS_RAW_DIR}/labeling_progress.json'
NEW_CATS_PATH = f'{XHS_RAW_DIR}/new_categories.json'
ERROR_LOG_PATH = f'{XHS_RAW_DIR}/errors.log'

BATCH_SIZE = 50
MAX_CONTENT_LENGTH = 300
MAX_RETRIES = 2
MODEL = 'claude-haiku-4-5-20251001'

SYSTEM_PROMPT = """你是一个数据标注专家。你的任务是对小红书帖子进行服务品类分类和评分。

对每条帖子，返回以下字段：
- service_category: 服务品类，优先从以下种子列表中选择，不匹配时可新增：
  {categories}
- standardization_score: 标准化程度 (1-5)，5=完全模板化，1=高度个性化
- digital_delivery: 交付物是否为纯数字化产物 (true/false)
- ai_replaceability: AI Agent 可替代度 (1-5)，5=完全可替代，1=基本不可替代
- demand_type: 需求类型，必须为以下之一: buying, selling, recommending, discussing
- confidence: 你对这条判断的置信度 (1-5)

返回严格的 JSON 数组，每个元素对应一条帖子，按输入顺序排列。不要输出其他内容。"""


def build_prompt(batch):
    """Build user prompt from a batch of records."""
    items = []
    for i, r in enumerate(batch):
        title = r.get('title', '')
        content = r.get('content', '')[:MAX_CONTENT_LENGTH]
        items.append(f"[{i+1}] 标题: {title}\n内容: {content}")
    return '\n\n'.join(items)


def validate_label(label):
    """Validate a single label dict. Returns (is_valid, errors)."""
    errors = []
    if not isinstance(label.get('service_category'), str) or not label['service_category']:
        errors.append('service_category must be non-empty string')
    if label.get('standardization_score') not in [1, 2, 3, 4, 5]:
        errors.append('standardization_score must be 1-5 integer')
    if not isinstance(label.get('digital_delivery'), bool):
        errors.append('digital_delivery must be boolean')
    if label.get('ai_replaceability') not in [1, 2, 3, 4, 5]:
        errors.append('ai_replaceability must be 1-5 integer')
    if label.get('demand_type') not in ['buying', 'selling', 'recommending', 'discussing']:
        errors.append('demand_type must be one of: buying, selling, recommending, discussing')
    if label.get('confidence') not in [1, 2, 3, 4, 5]:
        errors.append('confidence must be 1-5 integer')
    return len(errors) == 0, errors


_client = None

def get_client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic()
    return _client


def call_llm(batch):
    """Call Claude Haiku API with a batch of records. Returns parsed JSON array."""
    client = get_client()

    system = SYSTEM_PROMPT.format(categories='、'.join(SEED_CATEGORIES))
    user_prompt = build_prompt(batch)

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=system,
        messages=[{'role': 'user', 'content': user_prompt}],
    )

    text = response.content[0].text.strip()
    # Extract JSON array from response
    if text.startswith('```'):
        text = text.split('\n', 1)[1].rsplit('```', 1)[0].strip()

    return json.loads(text)


def load_progress():
    """Load set of already-processed note URLs."""
    if os.path.exists(PROGRESS_PATH):
        with open(PROGRESS_PATH, 'r') as f:
            return set(json.load(f))
    return set()


def save_progress(processed_urls):
    """Save processed URL set."""
    with open(PROGRESS_PATH, 'w') as f:
        json.dump(sorted(processed_urls), f)


def log_error(batch_idx, error_msg):
    """Append error to log file."""
    with open(ERROR_LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(f'Batch {batch_idx}: {error_msg}\n')


def main():
    sample_mode = '--sample' in sys.argv

    # Load input
    records = []
    with open(INPUT_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            records.append(json.loads(line))

    # Load progress
    processed_urls = load_progress()
    pending = [r for r in records if r['note_url'] not in processed_urls]
    print(f'Total: {len(records)}, Already processed: {len(processed_urls)}, Pending: {len(pending)}')
    if sample_mode:
        print('SAMPLE MODE: processing only first batch (50 records)')

    # Count existing labeled records (for progress display)
    labeled_count = 0
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, 'r', encoding='utf-8') as f:
            for _ in f:
                labeled_count += 1

    new_categories = set()
    seed_set = set(SEED_CATEGORIES)

    # Process in batches
    batches = [pending[i:i+BATCH_SIZE] for i in range(0, len(pending), BATCH_SIZE)]
    if sample_mode:
        batches = batches[:1]
    for batch_idx, batch in enumerate(batches):
        print(f'\nBatch {batch_idx+1}/{len(batches)} ({len(batch)} records)...')

        labels = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                labels = call_llm(batch)
                if len(labels) != len(batch):
                    raise ValueError(f'Expected {len(batch)} labels, got {len(labels)}')

                # Validate all labels
                all_valid = True
                for i, label in enumerate(labels):
                    valid, errs = validate_label(label)
                    if not valid:
                        raise ValueError(f'Record {i}: {errs}')
                break
            except Exception as e:
                if attempt < MAX_RETRIES:
                    print(f'  Retry {attempt+1}: {e}')
                    time.sleep(2)
                else:
                    log_error(batch_idx, str(e))
                    print(f'  FAILED after {MAX_RETRIES+1} attempts, skipping batch')
                    labels = None

        if labels is None:
            continue

        # Merge labels into records and append to output (crash-safe)
        with open(OUTPUT_PATH, 'a', encoding='utf-8') as f:
            for r, label in zip(batch, labels):
                r.update(label)
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
                processed_urls.add(r['note_url'])
                labeled_count += 1

                if label['service_category'] not in seed_set:
                    new_categories.add(label['service_category'])

        # Save progress after each batch
        save_progress(processed_urls)

        print(f'  Done. Total labeled: {labeled_count}')
        time.sleep(1)  # Rate limiting

    # Save new categories
    if new_categories:
        with open(NEW_CATS_PATH, 'w', encoding='utf-8') as f:
            json.dump(sorted(new_categories), f, ensure_ascii=False, indent=2)
        print(f'\nNew categories (not in seed list): {len(new_categories)}')
        print(f'Saved to: {NEW_CATS_PATH}')

    print(f'\nFinal labeled count: {len(labeled)}')
    print(f'Output: {OUTPUT_PATH}')


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: 先跑 1 批样本验证打标质量**

```bash
python3 scripts/xiaohongshu/stage3_label.py --sample
```

检查输出：
```bash
head -3 data/raw/xiaohongshu/posts_labeled.jsonl | python3 -m json.tool
```

人工检查：service_category 是否合理、ai_replaceability 评分是否准确。如有问题，调整 SYSTEM_PROMPT 后重跑。

- [ ] **Step 3: 确认样本质量后，删除样本数据，全量执行**

```bash
# 清除样本数据（重新全量跑）
rm -f data/raw/xiaohongshu/posts_labeled.jsonl data/raw/xiaohongshu/labeling_progress.json
python3 scripts/xiaohongshu/stage3_label.py
```

预计 60-100 批，每批约 3-5 秒，总计 5-10 分钟。

- [ ] **Step 4: 验证结果**

```bash
wc -l data/raw/xiaohongshu/posts_labeled.jsonl
# 检查 new_categories
cat data/raw/xiaohongshu/new_categories.json
# 检查 errors
cat data/raw/xiaohongshu/errors.log 2>/dev/null || echo "No errors"
```

- [ ] **Step 5: Commit**

```bash
git add scripts/xiaohongshu/stage3_label.py
git commit -m "feat(xhs): stage 3 - LLM batch labeling with Haiku"
```

注意：`posts_labeled.jsonl` 和 `labeling_progress.json` 体积较大，可选择性 commit。

---

### Task 5: Stage 4 — 统计聚合、评分与报告

**Files:**
- Create: `scripts/xiaohongshu/stage4_analyze.py`

- [ ] **Step 1: 写 stage4_analyze.py**

```python
#!/usr/bin/env python3
"""Stage 4: Aggregate statistics, score categories, generate selection report."""
import json
import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (
    XHS_RAW_DIR, XHS_ANALYZED_DIR, REPORTS_DIR,
    SCORING_WEIGHTS, SEED_CATEGORIES, XHS_TO_GOOFISH_MAP,
    BASE_DIR,
)

INPUT_PATH = f'{XHS_RAW_DIR}/posts_labeled.jsonl'
MAPPING_PATH = f'{XHS_ANALYZED_DIR}/category_mapping.json'
STATS_PATH = f'{XHS_ANALYZED_DIR}/category_stats.json'
RANKING_PATH = f'{XHS_ANALYZED_DIR}/category_ranking.json'
REPORT_PATH = f'{REPORTS_DIR}/xiaohongshu_agent_selection_report.md'
GOOFISH_PATH = f'{BASE_DIR}/data/raw/goofish/services_deduped.jsonl'


def load_records():
    records = []
    with open(INPUT_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            records.append(json.loads(line))
    return records


def build_category_mapping(records):
    """Group similar category names into canonical categories."""
    raw_cats = defaultdict(int)
    for r in records:
        cat = r.get('service_category', '')
        if cat:
            raw_cats[cat] += 1

    # Simple approach: seed categories are canonical; map similar names
    mapping = {}
    seed_set = set(SEED_CATEGORIES)

    for cat, count in sorted(raw_cats.items(), key=lambda x: -x[1]):
        if cat in seed_set:
            mapping[cat] = cat
        else:
            # Try to find closest seed category
            matched = False
            for seed in SEED_CATEGORIES:
                if seed in cat or cat in seed:
                    mapping[cat] = seed
                    matched = True
                    break
            if not matched:
                mapping[cat] = cat  # Keep as new category

    return mapping


def log_normalize(values, target_min=1, target_max=5):
    """Log-normalize a list of values to [target_min, target_max]."""
    if not values:
        return []
    log_vals = [math.log1p(v) for v in values]
    min_v, max_v = min(log_vals), max(log_vals)
    if max_v == min_v:
        return [3.0] * len(values)
    return [
        target_min + (target_max - target_min) * (v - min_v) / (max_v - min_v)
        for v in log_vals
    ]


def compute_stats(records, mapping):
    """Compute per-category statistics."""
    cats = defaultdict(lambda: {
        'count': 0, 'engagement_sum': 0, 'likes_sum': 0, 'bookmarks_sum': 0,
        'standardization_sum': 0, 'ai_replaceability_sum': 0,
        'digital_true': 0, 'demand_types': defaultdict(int),
        'examples': [],
    })

    for r in records:
        if r.get('confidence', 0) < 3:
            continue
        raw_cat = r.get('service_category', '')
        cat = mapping.get(raw_cat, raw_cat)
        if not cat:
            continue

        d = cats[cat]
        d['count'] += 1
        d['engagement_sum'] += r.get('engagement', 0)
        d['likes_sum'] += r.get('likes', 0)
        d['bookmarks_sum'] += r.get('bookmarks', 0)
        d['standardization_sum'] += r.get('standardization_score', 3)
        d['ai_replaceability_sum'] += r.get('ai_replaceability', 3)
        if r.get('digital_delivery'):
            d['digital_true'] += 1
        d['demand_types'][r.get('demand_type', 'discussing')] += 1

        # Keep top 3 examples by engagement
        if len(d['examples']) < 3:
            d['examples'].append({
                'title': r.get('title', ''),
                'engagement': r.get('engagement', 0),
                'note_url': r.get('note_url', ''),
            })
        else:
            min_ex = min(d['examples'], key=lambda x: x['engagement'])
            if r.get('engagement', 0) > min_ex['engagement']:
                d['examples'].remove(min_ex)
                d['examples'].append({
                    'title': r.get('title', ''),
                    'engagement': r.get('engagement', 0),
                    'note_url': r.get('note_url', ''),
                })

    # Compute averages
    stats = {}
    for cat, d in cats.items():
        n = d['count']
        if n == 0:
            continue
        stats[cat] = {
            'count': n,
            'avg_engagement': round(d['engagement_sum'] / n, 1),
            'avg_likes': round(d['likes_sum'] / n, 1),
            'avg_bookmarks': round(d['bookmarks_sum'] / n, 1),
            'avg_standardization': round(d['standardization_sum'] / n, 2),
            'avg_ai_replaceability': round(d['ai_replaceability_sum'] / n, 2),
            'digital_ratio': round(d['digital_true'] / n, 2),
            'demand_types': dict(d['demand_types']),
            'examples': sorted(d['examples'], key=lambda x: -x['engagement']),
        }

    return stats


def compute_ranking(stats):
    """Score and rank categories using weighted formula with log normalization."""
    cats = list(stats.keys())
    counts = [stats[c]['count'] for c in cats]
    engagements = [stats[c]['avg_engagement'] for c in cats]

    norm_counts = log_normalize(counts)
    norm_engagements = log_normalize(engagements)

    w = SCORING_WEIGHTS
    ranking = []
    for i, cat in enumerate(cats):
        s = stats[cat]
        score = (
            s['avg_ai_replaceability'] * w['ai_replaceability'] +
            s['avg_standardization'] * w['standardization'] +
            norm_counts[i] * w['demand_heat'] +
            norm_engagements[i] * w['engagement'] +
            s['digital_ratio'] * 5 * w['digital_ratio']  # scale 0-1 to 0-5
        )
        ranking.append({
            'category': cat,
            'score': round(score, 2),
            'count': s['count'],
            'avg_ai_replaceability': s['avg_ai_replaceability'],
            'avg_standardization': s['avg_standardization'],
            'digital_ratio': s['digital_ratio'],
            'avg_engagement': s['avg_engagement'],
            'demand_heat_normalized': round(norm_counts[i], 2),
        })

    ranking.sort(key=lambda x: -x['score'])
    return ranking


def load_goofish_stats():
    """Load Goofish data for cross-validation."""
    if not os.path.exists(GOOFISH_PATH):
        return None
    cats = defaultdict(lambda: {'count': 0, 'total_wants': 0, 'prices': []})
    with open(GOOFISH_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            cat = r.get('keyword_group', 'other')
            cats[cat]['count'] += 1
            wants = r.get('want_count', 0)
            if isinstance(wants, (int, float)):
                cats[cat]['total_wants'] += wants
            price = r.get('price', 0)
            if isinstance(price, (int, float)) and price > 0:
                cats[cat]['prices'].append(price)

    result = {}
    for cat, d in cats.items():
        prices = sorted(d['prices'])
        median_price = prices[len(prices)//2] if prices else 0
        result[cat] = {
            'listings': d['count'],
            'total_wants': d['total_wants'],
            'median_price': median_price,
        }
    return result


def generate_report(stats, ranking, goofish):
    """Generate Markdown selection report."""
    lines = []
    lines.append('# 小红书 AI Agent 可替代服务选品报告\n')
    lines.append(f'> 数据来源: 灰豚导出小红书数据，经清洗→粗筛→LLM打标→统计聚合\n')

    # Summary
    total_labeled = sum(s['count'] for s in stats.values())
    total_cats = len(stats)
    lines.append('## 概览\n')
    lines.append(f'- 有效打标记录数: {total_labeled}')
    lines.append(f'- 服务品类数: {total_cats}')
    lines.append(f'- 评分公式: ai_replaceability×0.35 + standardization×0.25 + demand_heat×0.20 + engagement×0.10 + digital_ratio×0.10\n')

    # Top 20 ranking
    lines.append('## Top 20 品类排名\n')
    lines.append('| 排名 | 品类 | 综合得分 | AI替代度 | 标准化 | 数字交付率 | 笔记数 | 平均互动 |')
    lines.append('|------|------|---------|---------|--------|-----------|--------|---------|')
    for i, r in enumerate(ranking[:20]):
        lines.append(
            f'| {i+1} | {r["category"]} | {r["score"]} | '
            f'{r["avg_ai_replaceability"]} | {r["avg_standardization"]} | '
            f'{r["digital_ratio"]:.0%} | {r["count"]} | {r["avg_engagement"]:.0f} |'
        )
    lines.append('')

    # Detail for top 20
    lines.append('## 品类详情\n')
    for i, r in enumerate(ranking[:20]):
        cat = r['category']
        s = stats[cat]
        lines.append(f'### {i+1}. {cat}\n')
        lines.append(f'- 综合得分: {r["score"]}')
        lines.append(f'- AI 可替代度: {s["avg_ai_replaceability"]}/5')
        lines.append(f'- 标准化程度: {s["avg_standardization"]}/5')
        lines.append(f'- 数字交付率: {s["digital_ratio"]:.0%}')
        lines.append(f'- 笔记数量: {s["count"]}')
        lines.append(f'- 需求类型分布: {s["demand_types"]}')
        lines.append(f'\n**典型帖子:**')
        for ex in s['examples']:
            lines.append(f'- [{ex["title"][:50]}]({ex["note_url"]}) (互动: {ex["engagement"]:,})')
        lines.append('')

    # Cross-validation with Goofish
    if goofish:
        lines.append('## 闲鱼交叉验证\n')
        lines.append('| 小红书品类 | 闲鱼对应类目 | 闲鱼 listings | 闲鱼 median price | 验证结论 |')
        lines.append('|-----------|------------|--------------|------------------|---------|')
        for gf_cat, xhs_cats in XHS_TO_GOOFISH_MAP.items():
            gf = goofish.get(gf_cat, {})
            # Find matching XHS categories in top 20
            matched = [r for r in ranking[:20] if r['category'] in xhs_cats]
            if matched:
                xhs_names = ', '.join(r['category'] for r in matched)
                gf_listings = gf.get('listings', 0)
                gf_price = gf.get('median_price', 0)
                if gf_listings > 0 and matched:
                    conclusion = '高置信'
                elif matched and gf_listings == 0:
                    conclusion = '隐性需求（闲鱼供给缺口）'
                else:
                    conclusion = '待验证'
                lines.append(f'| {xhs_names} | {gf_cat} | {gf_listings} | ¥{gf_price:.0f} | {conclusion} |')
        lines.append('')

    # Final recommendations
    lines.append('## 第一批选品推荐（Top 10）\n')
    for i, r in enumerate(ranking[:10]):
        cat = r['category']
        s = stats[cat]
        lines.append(f'### {i+1}. {cat}\n')
        lines.append(f'- **选品得分:** {r["score"]}')
        lines.append(f'- **AI替代度:** {s["avg_ai_replaceability"]}/5 | **标准化:** {s["avg_standardization"]}/5 | **数字交付:** {s["digital_ratio"]:.0%}')
        lines.append(f'- **需求规模:** {s["count"]} 条笔记，平均互动 {s["avg_engagement"]:.0f}')

        # Cross-validation note
        for gf_cat, xhs_cats in XHS_TO_GOOFISH_MAP.items():
            if cat in xhs_cats and goofish and gf_cat in goofish:
                gf = goofish[gf_cat]
                lines.append(f'- **闲鱼验证:** {gf_cat} 类目 {gf["listings"]} 个 listings，中位价 ¥{gf["median_price"]:.0f}')
                break
        lines.append('')

    return '\n'.join(lines)


def main():
    records = load_records()
    print(f'Loaded {len(records)} labeled records')

    # Step 1: Category mapping
    mapping = build_category_mapping(records)
    os.makedirs(XHS_ANALYZED_DIR, exist_ok=True)
    with open(MAPPING_PATH, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    print(f'Category mapping: {len(mapping)} raw -> {len(set(mapping.values()))} canonical')

    # Step 2: Compute stats
    stats = compute_stats(records, mapping)
    with open(STATS_PATH, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f'Stats computed for {len(stats)} categories')

    # Step 3: Ranking
    ranking = compute_ranking(stats)
    with open(RANKING_PATH, 'w', encoding='utf-8') as f:
        json.dump(ranking, f, ensure_ascii=False, indent=2)
    print(f'Ranking computed, top 3: {[(r["category"], r["score"]) for r in ranking[:3]]}')

    # Step 4: Report
    goofish = load_goofish_stats()
    if goofish:
        print(f'Goofish data loaded: {len(goofish)} categories')
    else:
        print('Goofish data not found, skipping cross-validation')

    report = generate_report(stats, ranking, goofish)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f'\nReport saved to: {REPORT_PATH}')


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: 运行并验证**

Run: `python3 scripts/xiaohongshu/stage4_analyze.py`

验证输出：
```bash
cat data/analyzed/xiaohongshu/category_ranking.json | python3 -c "import json,sys; d=json.load(sys.stdin); [print(f'{r[\"category\"]}: {r[\"score\"]}') for r in d[:10]]"
head -50 data/reports/xiaohongshu_agent_selection_report.md
```

- [ ] **Step 3: Commit**

```bash
git add scripts/xiaohongshu/stage4_analyze.py data/analyzed/xiaohongshu/ data/reports/xiaohongshu_agent_selection_report.md
git commit -m "feat(xhs): stage 4 - aggregation, scoring, and selection report"
```

---

### Task 6: 端到端验收

- [ ] **Step 1: 全流程顺序执行**

```bash
python3 scripts/xiaohongshu/stage1_merge.py
python3 scripts/xiaohongshu/stage2_filter.py
python3 scripts/xiaohongshu/stage3_label.py
python3 scripts/xiaohongshu/stage4_analyze.py
```

- [ ] **Step 2: 检查最终产出物**

验证所有输出文件存在且非空：
```bash
wc -l data/raw/xiaohongshu/posts_merged.jsonl
wc -l data/raw/xiaohongshu/posts_filtered.jsonl
wc -l data/raw/xiaohongshu/posts_labeled.jsonl
ls -la data/analyzed/xiaohongshu/
ls -la data/reports/xiaohongshu_agent_selection_report.md
```

- [ ] **Step 3: 审阅选品报告**

人工阅读 `data/reports/xiaohongshu_agent_selection_report.md`，确认：
- Top 10 选品是否合理
- 闲鱼交叉验证是否有价值
- 是否需要调整评分权重后重跑 Stage 4

- [ ] **Step 4: Final commit**

```bash
git add -A data/raw/xiaohongshu/ data/analyzed/xiaohongshu/ data/reports/xiaohongshu_agent_selection_report.md
git commit -m "data(xhs): complete Xiaohongshu AI Agent selection analysis"
```
