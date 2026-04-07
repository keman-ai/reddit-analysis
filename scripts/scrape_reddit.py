#!/usr/bin/env python3
"""
统一 Reddit 数据抓取脚本。
从 plan JSON 读取 subreddit 和关键词配置，自动执行抓取、去重、断点续抓。

用法：
    python scripts/scrape_reddit.py --plan data/raw/{task_id}_plan.json --output data/raw/{task_id}.jsonl
"""

import argparse
import json
import os
import random
import re
import time
import urllib.request
import urllib.parse
from datetime import datetime


USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
MAX_PAGES_PER_COMBO = 5
CONSECUTIVE_EMPTY_THRESHOLD = 5


def load_progress(progress_file):
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            return json.load(f)
    return {"completed": [], "failed": [], "total_posts": 0}


def save_progress(progress, progress_file):
    with open(progress_file, 'w') as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)


def load_existing_ids(output_file):
    ids = set()
    if os.path.exists(output_file):
        with open(output_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        ids.add(json.loads(line).get('id', ''))
                    except Exception:
                        pass
    return ids


def fetch_reddit_search(subreddit, keyword, sort='top', time_filter='year', after=None, limit=100):
    """Fetch search results from Reddit JSON API."""
    params = {
        'q': keyword,
        'restrict_sr': 'on',
        'sort': sort,
        't': time_filter,
        'limit': limit,
        'type': 'link'
    }
    if after:
        params['after'] = after

    url = f"https://old.reddit.com/r/{subreddit}/search.json?{urllib.parse.urlencode(params)}"
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


def extract_posts(data, subreddit, keyword, keyword_group, subreddit_group):
    """Extract post data from Reddit API response."""
    posts = []
    if 'error' in data:
        return posts, None

    try:
        children = data.get('data', {}).get('children', [])
        after = data.get('data', {}).get('after')

        for child in children:
            d = child.get('data', {})
            created_utc = d.get('created_utc', 0)
            created_dt = datetime.utcfromtimestamp(created_utc)

            selftext = d.get('selftext', '')
            if selftext in ('[removed]', '[deleted]'):
                continue

            permalink = d.get('permalink', '')
            url = f"https://old.reddit.com{permalink}" if permalink else ''

            post = {
                'id': f"t3_{d.get('id', '')}",
                'subreddit': d.get('subreddit', subreddit),
                'title': d.get('title', ''),
                'author': d.get('author', ''),
                'created_at': created_dt.strftime('%Y-%m-%dT%H:%M:%S+00:00'),
                'url': url,
                'upvotes': d.get('ups', 0),
                'comment_count': d.get('num_comments', 0),
                'selftext': selftext[:500],
                'link_flair_text': d.get('link_flair_text', '') or '',
                'search_keyword': keyword,
                'keyword_group': keyword_group,
                'subreddit_group': subreddit_group,
                'score': d.get('score', 0),
            }

            if not post['id'] or not post['title']:
                continue

            posts.append(post)

    except Exception as e:
        print(f"    Parse error: {e}")

    return posts, after


def deduplicate_jsonl(input_file, output_file):
    """Read a JSONL file, deduplicate by id, write to output."""
    seen_ids = set()
    count = 0
    with open(input_file, 'r') as fin, open(output_file, 'w') as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            try:
                post = json.loads(line)
                pid = post.get('id', '')
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    fout.write(json.dumps(post, ensure_ascii=False) + '\n')
                    count += 1
            except Exception:
                pass
    return count


def main():
    parser = argparse.ArgumentParser(description='Reddit data scraper driven by plan JSON')
    parser.add_argument('--plan', required=True, help='Path to plan JSON file')
    parser.add_argument('--output', required=True, help='Path to output JSONL file')
    args = parser.parse_args()

    # Load plan
    with open(args.plan, 'r') as f:
        plan = json.load(f)

    output_file = args.output
    progress_file = output_file.replace('.jsonl', '_progress.json')
    deduped_file = output_file.replace('.jsonl', '_deduped.jsonl')

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    progress = load_progress(progress_file)
    existing_ids = load_existing_ids(output_file)
    completed_set = set(progress['completed'])

    sort = plan.get('sort', 'top')
    time_filter = plan.get('time_filter', 'year')
    target_posts = plan.get('target_posts', 5000)

    # Build task list: subreddit x keyword
    tasks = []
    for sub_info in plan.get('subreddits', []):
        sub_name = sub_info['name']
        sub_group = sub_info.get('group', 'default')
        for kw_info in plan.get('keywords', []):
            kw_term = kw_info['term']
            kw_group = kw_info.get('group', 'default')
            task_key = f"{sub_name}|{kw_term}"
            if task_key not in completed_set:
                tasks.append((sub_name, sub_group, kw_term, kw_group, task_key))

    total_new = 0
    rate_limit_count = 0
    consecutive_empty = 0
    current_sub = None

    print(f"Plan: {plan.get('task_description', 'N/A')}")
    print(f"Target: {target_posts} posts | {len(plan.get('subreddits', []))} subreddits x {len(plan.get('keywords', []))} keywords = {len(tasks)} remaining combos")
    print(f"Existing posts: {len(existing_ids)}")
    print()

    for i, (sub, sub_group, keyword, kw_group, task_key) in enumerate(tasks):
        # Check if we've hit target
        if len(existing_ids) >= target_posts:
            print(f"\nTarget reached: {len(existing_ids)} >= {target_posts}")
            break

        # Reset consecutive empty counter on subreddit change
        if sub != current_sub:
            current_sub = sub
            consecutive_empty = 0

        if consecutive_empty >= CONSECUTIVE_EMPTY_THRESHOLD:
            progress['completed'].append(task_key)
            save_progress(progress, progress_file)
            continue

        print(f"[{i+1}/{len(tasks)}] r/{sub} \"{keyword}\" ({kw_group})...", end=' ', flush=True)

        page_after = None
        combo_new = 0

        for page in range(MAX_PAGES_PER_COMBO):
            data = fetch_reddit_search(sub, keyword, sort=sort, time_filter=time_filter, after=page_after)

            if 'error' in data:
                err = data['error']
                if err == 'rate_limited':
                    rate_limit_count += 1
                    wait = 60 * (2 ** min(rate_limit_count - 1, 3))
                    print(f"429 wait {wait}s...", end=' ', flush=True)
                    time.sleep(wait)
                    data = fetch_reddit_search(sub, keyword, sort=sort, time_filter=time_filter, after=page_after)
                    if 'error' in data:
                        progress['failed'].append(task_key)
                        save_progress(progress, progress_file)
                        print(f"ERR: {data['error']}")
                        break
                elif err in ('not_found', 'forbidden'):
                    consecutive_empty = 999  # Skip remaining keywords for this sub
                    progress['failed'].append(task_key)
                    save_progress(progress, progress_file)
                    print(f"SKIP sub: {err}")
                    break
                else:
                    progress['failed'].append(task_key)
                    save_progress(progress, progress_file)
                    print(f"ERR: {err}")
                    break
            else:
                rate_limit_count = max(0, rate_limit_count - 1)

            posts, page_after = extract_posts(data, sub, keyword, kw_group, sub_group)

            new_posts = [p for p in posts if p['id'] not in existing_ids]
            if new_posts:
                with open(output_file, 'a') as f:
                    for p in new_posts:
                        f.write(json.dumps(p, ensure_ascii=False) + '\n')
                        existing_ids.add(p['id'])
                combo_new += len(new_posts)
                total_new += len(new_posts)

            if not page_after or len(posts) == 0:
                break

            time.sleep(random.uniform(2, 5))

        print(f"{combo_new} new")
        consecutive_empty = consecutive_empty + 1 if combo_new == 0 else 0

        progress['completed'].append(task_key)
        progress['total_posts'] = len(existing_ids)
        save_progress(progress, progress_file)

        time.sleep(random.uniform(2, 5))

    # Deduplication
    print(f"\nScraping done. Total new: {total_new} | Total: {len(existing_ids)}")
    print("Running deduplication...")
    deduped_count = deduplicate_jsonl(output_file, deduped_file)
    print(f"Deduped output: {deduped_count} unique posts -> {deduped_file}")

    # Write summary for run.py to read
    summary = {
        "total_raw": len(existing_ids),
        "total_deduped": deduped_count,
        "target": target_posts,
        "completed_combos": len(progress['completed']),
        "failed_combos": len(progress['failed']),
    }
    summary_file = output_file.replace('.jsonl', '_scrape_summary.json')
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"Summary: {summary_file}")


if __name__ == '__main__':
    main()
