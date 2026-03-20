#!/usr/bin/env python3
"""Batch save posts from a file containing JSON extraction results."""
import json
import sys

def main():
    """Read a JSON file with multiple extraction results and save to JSONL."""
    input_file = sys.argv[1] if len(sys.argv) > 1 else '/dev/stdin'

    jsonl_path = '/Users/huanghaibin/Workspace/reddit_research/data/raw/posts_raw.jsonl'
    progress_path = '/Users/huanghaibin/Workspace/reddit_research/data/raw/progress.json'
    cutoff = '2025-09-19'

    # Load existing IDs
    existing_ids = set()
    try:
        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    existing_ids.add(json.loads(line).get('id', ''))
    except FileNotFoundError:
        pass

    # Load progress
    try:
        with open(progress_path) as f:
            progress = json.load(f)
    except FileNotFoundError:
        progress = {'completed': [], 'failed': []}

    # Read batch data
    with open(input_file) if input_file != '/dev/stdin' else sys.stdin as f:
        batch = json.load(f)

    total_saved = 0

    for item in batch:
        keyword = item['keyword']
        keyword_group = item['keyword_group']
        subreddit = item['subreddit']
        posts = item.get('posts', [])
        status = item.get('status', 'completed')
        error = item.get('error', '')

        saved_count = 0
        for p in posts:
            if not p.get('id') or not p['id'].startswith('t3_'):
                continue
            if p['id'] in existing_ids:
                continue
            if p.get('created_at') and p['created_at'][:10] < cutoff:
                continue
            p['search_keyword'] = keyword
            p['keyword_group'] = keyword_group
            p.pop('body_preview', None)

            with open(jsonl_path, 'a') as f:
                f.write(json.dumps(p, ensure_ascii=False) + '\n')

            existing_ids.add(p['id'])
            saved_count += 1

        total_saved += saved_count

        if status == 'completed':
            progress['completed'].append({
                'subreddit': subreddit,
                'keyword': keyword,
                'keyword_group': keyword_group,
                'timestamp': item.get('timestamp', ''),
                'posts_found': saved_count
            })
        elif status == 'failed':
            progress['failed'].append({
                'subreddit': subreddit,
                'keyword': keyword,
                'keyword_group': keyword_group,
                'error': error,
                'timestamp': item.get('timestamp', '')
            })

    # Save progress
    with open(progress_path, 'w') as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)

    print(f'Total saved: {total_saved} posts from {len(batch)} tasks')

if __name__ == '__main__':
    main()
