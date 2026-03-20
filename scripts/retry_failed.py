#!/usr/bin/env python3
"""Retry failed tasks from progress.json for target subreddits."""
import json
import time
import urllib.request
import urllib.parse
import random
from datetime import datetime, timezone

BASE_DIR = '/Users/huanghaibin/Workspace/reddit_research'
JSONL_PATH = f'{BASE_DIR}/data/raw/posts_raw.jsonl'
PROGRESS_PATH = f'{BASE_DIR}/data/raw/progress.json'
CUTOFF_DATE = '2025-09-19'
MAX_PAGES = 5
USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 research-bot/1.0'
TARGET_SUBS = {'Entrepreneur', 'SaaS', 'startups', 'smallbusiness', 'indiehackers', 'microsaas'}


def load_existing_ids():
    ids = set()
    try:
        with open(JSONL_PATH) as f:
            for line in f:
                line = line.strip()
                if line:
                    ids.add(json.loads(line).get('id', ''))
    except FileNotFoundError:
        pass
    return ids


def fetch_search(subreddit, keyword, after=None):
    q = urllib.parse.quote(keyword)
    url = f'https://old.reddit.com/r/{subreddit}/search.json?q={q}&restrict_sr=on&sort=new&t=year&limit=25'
    if after:
        url += f'&after=t3_{after}'
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        resp = urllib.request.urlopen(req, timeout=20)
        data = json.loads(resp.read())
        children = data.get('data', {}).get('children', [])
        after_token = data.get('data', {}).get('after')
        return children, after_token, None
    except urllib.error.HTTPError as e:
        return None, None, f'http_{e.code}'
    except Exception as e:
        return None, None, str(e)


def process_posts(children, subreddit, keyword, keyword_group, existing_ids):
    new_posts = []
    all_before_cutoff = True
    for child in children:
        d = child.get('data', {})
        post_id = f"t3_{d.get('id', '')}"
        created_utc = d.get('created_utc', 0)
        created_dt = datetime.fromtimestamp(created_utc, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')
        created_date = created_dt[:10]
        if created_date >= CUTOFF_DATE:
            all_before_cutoff = False
        if post_id in existing_ids:
            continue
        if created_date < CUTOFF_DATE:
            continue
        selftext = d.get('selftext', '')
        if selftext in ('[removed]', '[deleted]'):
            continue
        permalink = d.get('permalink', '')
        url = f'https://old.reddit.com{permalink}' if permalink else ''
        post = {
            'id': post_id,
            'subreddit': d.get('subreddit', subreddit),
            'title': d.get('title', ''),
            'author': d.get('author', '[deleted]'),
            'created_at': created_dt,
            'url': url,
            'upvotes': d.get('score', 0),
            'comment_count': d.get('num_comments', 0),
            'search_keyword': keyword,
            'keyword_group': keyword_group
        }
        if not post['id'].startswith('t3_') or not post['title']:
            continue
        if not post['url'].startswith('https://old.reddit.com/r/'):
            continue
        new_posts.append(post)
        existing_ids.add(post_id)
    return new_posts, all_before_cutoff


def main():
    with open(PROGRESS_PATH) as f:
        progress = json.load(f)

    existing_ids = load_existing_ids()
    completed_set = {(c['subreddit'], c['keyword']) for c in progress['completed']}

    # Get failed tasks for target subs that aren't banned
    retry_tasks = []
    new_failed = []
    for f_item in progress['failed']:
        sub = f_item['subreddit']
        if sub in TARGET_SUBS and f_item['error'] != 'banned_community' and (sub, f_item['keyword']) not in completed_set:
            retry_tasks.append((sub, f_item['keyword'], f_item['keyword_group']))
        else:
            new_failed.append(f_item)

    print(f'Retrying {len(retry_tasks)} failed tasks')
    total_new = 0

    for i, (sub, kw, group) in enumerate(retry_tasks):
        if (sub, kw) in completed_set:
            continue
        print(f'[{i+1}/{len(retry_tasks)}] r/{sub} "{kw}" ({group})...', end=' ', flush=True)

        delay = random.uniform(5.0, 8.0)
        time.sleep(delay)

        all_posts = []
        after_token = None
        page_count = 0
        error = None

        for page in range(MAX_PAGES):
            if page > 0:
                time.sleep(random.uniform(5.0, 8.0))

            children, after_token, err = fetch_search(sub, kw, after_token.replace('t3_', '') if after_token else None)
            if err:
                if 'rate' in str(err).lower() or '429' in str(err):
                    print(f'RATE LIMITED, waiting 120s...', end=' ', flush=True)
                    time.sleep(120)
                    children, after_token, err = fetch_search(sub, kw)
                    if err:
                        error = err
                        break
                else:
                    error = err
                    break

            if not children:
                break

            new_posts, all_before_cutoff = process_posts(children, sub, kw, group, existing_ids)
            all_posts.extend(new_posts)
            page_count += 1

            if all_before_cutoff or not after_token:
                break

        if all_posts:
            with open(JSONL_PATH, 'a') as f:
                for p in all_posts:
                    f.write(json.dumps(p, ensure_ascii=False) + '\n')

        total_new += len(all_posts)
        timestamp = datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

        if error:
            new_failed.append({
                'subreddit': sub, 'keyword': kw, 'keyword_group': group,
                'error': error, 'timestamp': timestamp
            })
            print(f'ERROR: {error}')
        else:
            progress['completed'].append({
                'subreddit': sub, 'keyword': kw, 'keyword_group': group,
                'timestamp': timestamp, 'posts_found': len(all_posts)
            })
            completed_set.add((sub, kw))
            print(f'{len(all_posts)} posts ({page_count} pages)')

    progress['failed'] = new_failed
    with open(PROGRESS_PATH, 'w') as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)

    print(f'\nDone! Retry saved {total_new} new posts')
    print(f'Total unique posts: {len(existing_ids)}')


if __name__ == '__main__':
    main()
