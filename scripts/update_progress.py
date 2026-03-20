#!/usr/bin/env python3
"""Update progress.json with completed/failed tasks."""
import json
import sys

def main():
    data = json.load(sys.stdin)
    action = data['action']  # 'completed' or 'failed'

    progress_path = '/Users/huanghaibin/Workspace/reddit_research/data/raw/progress.json'
    try:
        with open(progress_path) as f:
            progress = json.load(f)
    except FileNotFoundError:
        progress = {'completed': [], 'failed': []}

    if action == 'completed':
        progress['completed'].append({
            'subreddit': data['subreddit'],
            'keyword': data['keyword'],
            'keyword_group': data['keyword_group'],
            'timestamp': data['timestamp'],
            'posts_found': data['posts_found']
        })
    elif action == 'failed':
        progress['failed'].append({
            'subreddit': data['subreddit'],
            'keyword': data['keyword'],
            'keyword_group': data['keyword_group'],
            'error': data['error'],
            'timestamp': data['timestamp']
        })

    with open(progress_path, 'w') as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)

    print(f"Updated: {action}")

if __name__ == '__main__':
    main()
