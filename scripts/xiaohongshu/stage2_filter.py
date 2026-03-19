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
