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

    for num_field in ['estimated_reads', 'engagement', 'likes', 'bookmarks', 'comments', 'shares', 'follower_count']:
        record[num_field] = parse_number(record[num_field])
    for bool_field in ['is_commercial', 'is_paid_promotion']:
        record[bool_field] = parse_bool_cn(record[bool_field])

    record['source_file'] = source_label
    return record


def main():
    seen_urls = set()
    total_read = 0
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
