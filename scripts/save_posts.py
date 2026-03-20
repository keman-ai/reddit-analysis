#!/usr/bin/env python3
"""Helper script to filter and save scraped posts to JSONL."""
import json
import sys

def main():
    # Read posts JSON from stdin
    data = json.load(sys.stdin)
    posts = data['posts']
    keyword = data['keyword']
    keyword_group = data['keyword_group']
    cutoff = data.get('cutoff', '2025-09-19')

    # Load existing IDs
    existing_ids = set()
    jsonl_path = '/Users/huanghaibin/Workspace/reddit_research/data/raw/posts_raw.jsonl'
    try:
        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    existing_ids.add(json.loads(line).get('id', ''))
    except FileNotFoundError:
        pass

    new_posts = []
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
        new_posts.append(p)
        existing_ids.add(p['id'])

    # Append to JSONL
    with open(jsonl_path, 'a') as f:
        for p in new_posts:
            f.write(json.dumps(p, ensure_ascii=False) + '\n')

    print(json.dumps({'saved': len(new_posts), 'skipped': len(posts) - len(new_posts)}))

if __name__ == '__main__':
    main()
