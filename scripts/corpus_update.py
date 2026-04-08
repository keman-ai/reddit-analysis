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
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scrape_reddit import fetch_reddit_search, extract_posts, load_existing_ids

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
            if os.path.exists(CORPUS_DIR):
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
