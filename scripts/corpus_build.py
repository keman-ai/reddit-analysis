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
import sys
import time
from datetime import datetime

# Import core functions from scrape_reddit (same directory)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scrape_reddit import fetch_reddit_search, extract_posts, load_existing_ids

CORPUS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'corpus')
META_FILE = os.path.join(CORPUS_DIR, '_meta.json')

CONSECUTIVE_EMPTY_THRESHOLD = 5

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
