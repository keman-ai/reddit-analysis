#!/usr/bin/env python3
"""
一次性 corpus 灌库脚本。按 subreddit 全量抓取历史帖子到 data/corpus/。

策略：使用 Reddit listing API（new/top/hot）直接遍历帖子，不依赖关键词搜索。
这样能获取 subreddit 的全量内容，关键词过滤留给查询阶段。

用法：
    python scripts/corpus_build.py --subreddits personalfinance,writing,worldnews
    python scripts/corpus_build.py --subreddits personalfinance --months 6
    python scripts/corpus_build.py --list config/corpus_subreddits.txt
"""

import argparse
import json
import os
import random
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scrape_reddit import extract_posts, load_existing_ids, USER_AGENT

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


def fetch_listing(subreddit, sort='new', time_filter='year', after=None, limit=100):
    """Fetch posts from Reddit listing API (no keyword, gets ALL posts)."""
    params = {'limit': limit, 't': time_filter, 'raw_json': 1}
    if after:
        params['after'] = after

    url = f"https://old.reddit.com/r/{subreddit}/{sort}.json?{urllib.parse.urlencode(params)}"
    headers = {'User-Agent': USER_AGENT}
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        codes = {429: 'rate_limited', 403: 'forbidden', 404: 'not_found'}
        return {'error': codes.get(e.code, f'http_{e.code}')}
    except Exception as e:
        return {'error': str(e)}


def build_subreddit(subreddit, months=6, max_pages=50):
    """Scrape a subreddit's full post history into corpus using listing API."""
    corpus_file = os.path.join(CORPUS_DIR, f"{subreddit}.jsonl")
    existing_ids = load_existing_ids(corpus_file)
    initial_count = len(existing_ids)

    time_filter = 'year' if months >= 12 else ('month' if months <= 1 else 'year')

    print(f"\n  Building corpus for r/{subreddit} (existing: {initial_count})")
    total_new = 0

    # Use multiple sort orders + time filters to maximize coverage
    # Reddit limits pagination to ~1000 per sort, so we use multiple combos
    sorts = [
        ('new', 'all', max_pages),       # Most recent posts (chronological)
        ('top', 'all', max_pages),       # All-time top posts
        ('top', 'year', max_pages),      # Past year top
        ('top', 'month', max_pages),     # Past month top
        ('hot', 'all', min(max_pages, 10)),  # Currently active
        ('rising', 'all', 5),            # Up-and-coming
    ]

    for sort, tf, pages in sorts:
        print(f"    Sort={sort} t={tf} (max {pages} pages)...", end=' ', flush=True)
        page_after = None
        sort_new = 0
        consecutive_existing = 0

        for page in range(pages):
            data = fetch_listing(subreddit, sort=sort, time_filter=tf, after=page_after)

            if 'error' in data:
                err = data['error']
                if err == 'rate_limited':
                    print(f"429 wait 60s...", end=' ', flush=True)
                    time.sleep(60)
                    data = fetch_listing(subreddit, sort=sort, time_filter=tf, after=page_after)
                    if 'error' in data:
                        print(f"ERR: {data['error']}")
                        break
                else:
                    print(f"ERR: {err}")
                    break

            posts, page_after = extract_posts(data, subreddit, '', 'corpus', 'corpus')

            if not posts:
                break

            new_posts = [p for p in posts if p['id'] not in existing_ids]

            if new_posts:
                with open(corpus_file, 'a') as f:
                    for p in new_posts:
                        f.write(json.dumps(p, ensure_ascii=False) + '\n')
                        existing_ids.add(p['id'])
                sort_new += len(new_posts)
                total_new += len(new_posts)
                consecutive_existing = 0
            else:
                consecutive_existing += 1
                # If 3 consecutive pages have no new posts, skip remaining pages
                if consecutive_existing >= 3:
                    break

            if not page_after:
                break

            time.sleep(random.uniform(1, 3))

        print(f"{sort_new} new (page {page + 1})")
        time.sleep(random.uniform(1, 2))

    final_count = len(existing_ids)
    print(f"  r/{subreddit}: +{total_new} new (total: {final_count})")
    return final_count


def main():
    parser = argparse.ArgumentParser(description='Build corpus from Reddit subreddits (full listing)')
    parser.add_argument('--subreddits', help='Comma-separated subreddit names')
    parser.add_argument('--list', help='File with one subreddit per line')
    parser.add_argument('--months', type=int, default=6, help='Months of history (default: 6)')
    parser.add_argument('--max-pages', type=int, default=50, help='Max pages per sort order (default: 50, ~5000 posts)')
    args = parser.parse_args()

    if not args.subreddits and not args.list:
        parser.print_help()
        return

    if args.list:
        with open(args.list) as f:
            subs = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    else:
        subs = [s.strip() for s in args.subreddits.split(',') if s.strip()]

    os.makedirs(CORPUS_DIR, exist_ok=True)
    meta = load_meta()

    print(f"Building corpus for {len(subs)} subreddits, {args.months} months history")
    print(f"Strategy: listing API (new + top + hot), max {args.max_pages} pages per sort")

    for sub in subs:
        post_count = build_subreddit(sub, months=args.months, max_pages=args.max_pages)
        meta[sub] = {
            'last_updated': datetime.now().strftime('%Y-%m-%d'),
            'post_count': post_count,
        }
        save_meta(meta)

    # Final summary
    total = sum(v['post_count'] for v in meta.values())
    print(f"\nCorpus build complete: {len(meta)} subreddits, {total:,} total posts")
    print(f"Meta saved to {META_FILE}")


if __name__ == '__main__':
    main()
