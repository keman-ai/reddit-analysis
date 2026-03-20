#!/usr/bin/env python3
"""Scrape all remaining subreddit x keyword combinations via Reddit JSON API."""
import json
import time
import urllib.request
import urllib.parse
import random
from datetime import datetime

BASE_DIR = '/Users/huanghaibin/Workspace/reddit_research'
JSONL_PATH = f'{BASE_DIR}/data/raw/posts_raw.jsonl'
PROGRESS_PATH = f'{BASE_DIR}/data/raw/progress.json'
CUTOFF_DATE = '2025-09-19'
MAX_PAGES = 5
USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 research-bot/1.0'

SUBREDDITS = ['Entrepreneur', 'SaaS', 'startups', 'smallbusiness', 'indiehackers', 'microsaas']

KEYWORDS = {
    'hiring': [
        'hire AI agent', 'looking for AI agent', 'need AI developer',
        'AI automation developer', 'build me an AI agent', 'hiring AI engineer',
        'looking for AI automation', 'need someone to build AI', 'AI freelancer',
        'contract AI developer'
    ],
    'buying': [
        'best AI agent tool', 'AI agent service', 'buy AI agent',
        'AI agent platform', 'pay for AI automation', 'AI agent software',
        'AI agent pricing', 'recommend AI agent', 'AI tool for business',
        'which AI agent should I use'
    ],
    'demand': [
        'need automation', 'AI agent for', 'automate my', 'AI workflow',
        'AI agent use case', 'who uses AI agents', 'AI agent', 'AI bot',
        'AI assistant for work', 'automate business', 'AI replace',
        'AI taking over', 'AI in production', 'deploy AI agent', 'building AI agent'
    ],
    'tools': [
        'n8n AI', 'make.com AI', 'zapier AI', 'langchain agent', 'crewai',
        'autogpt', 'claude agent', 'openai agent', 'AI workflow tool'
    ]
}


def load_progress():
    try:
        with open(PROGRESS_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        return {'completed': [], 'failed': []}


def save_progress(progress):
    with open(PROGRESS_PATH, 'w') as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)


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


def get_completed_set(progress):
    return {(c['subreddit'], c['keyword']) for c in progress['completed']}


def fetch_search(subreddit, keyword, after=None):
    """Fetch search results from Reddit JSON API."""
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
        if e.code == 429:
            return None, None, 'rate_limited'
        elif e.code == 403:
            return None, None, 'forbidden'
        elif e.code == 404:
            return None, None, 'not_found'
        else:
            return None, None, f'http_{e.code}'
    except Exception as e:
        return None, None, str(e)


def process_posts(children, subreddit, keyword, keyword_group, existing_ids):
    """Process and filter posts, return list of valid posts."""
    new_posts = []
    all_before_cutoff = True

    for child in children:
        d = child.get('data', {})
        post_id = f"t3_{d.get('id', '')}"
        created_utc = d.get('created_utc', 0)
        created_dt = datetime.utcfromtimestamp(created_utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')
        created_date = created_dt[:10]

        if created_date >= CUTOFF_DATE:
            all_before_cutoff = False

        # Skip if already exists
        if post_id in existing_ids:
            continue

        # Skip if before cutoff
        if created_date < CUTOFF_DATE:
            continue

        # Skip deleted/removed
        selftext = d.get('selftext', '')
        if selftext in ('[removed]', '[deleted]'):
            continue

        # Build URL
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

        # Validate
        if not post['id'] or not post['id'].startswith('t3_'):
            continue
        if not post['title']:
            continue
        if not post['url'].startswith('https://old.reddit.com/r/'):
            continue

        new_posts.append(post)
        existing_ids.add(post_id)

    return new_posts, all_before_cutoff


def main():
    progress = load_progress()
    completed_set = get_completed_set(progress)
    existing_ids = load_existing_ids()

    # Build task list
    tasks = []
    for sub in SUBREDDITS:
        for group, kws in KEYWORDS.items():
            for kw in kws:
                if (sub, kw) not in completed_set:
                    tasks.append((sub, kw, group))

    print(f'Total remaining tasks: {len(tasks)}')
    print(f'Existing posts: {len(existing_ids)}')

    total_new = 0
    blocked_subreddits = set()
    consecutive_rate_limits = 0

    for i, (sub, kw, group) in enumerate(tasks):
        if sub in blocked_subreddits:
            progress['failed'].append({
                'subreddit': sub,
                'keyword': kw,
                'keyword_group': group,
                'error': 'blocked_subreddit',
                'timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
            })
            continue

        print(f'[{i+1}/{len(tasks)}] r/{sub} "{kw}" ({group})...', end=' ', flush=True)

        all_posts = []
        after_token = None
        page_count = 0
        error = None

        for page in range(MAX_PAGES):
            # Random delay between requests
            delay = random.uniform(4.0, 7.0)
            time.sleep(delay)

            children, after_token, err = fetch_search(sub, kw, after_token.replace('t3_', '') if after_token else None)

            if err:
                if err == 'rate_limited':
                    consecutive_rate_limits += 1
                    print(f'RATE LIMITED (#{consecutive_rate_limits})', end=' ')
                    if consecutive_rate_limits >= 5:
                        print('\nToo many rate limits, stopping.')
                        save_progress(progress)
                        print(f'\nTotal new posts saved: {total_new}')
                        return
                    # Wait and retry
                    wait_time = 60 * (2 ** (consecutive_rate_limits - 1))
                    print(f'waiting {wait_time}s...', end=' ', flush=True)
                    time.sleep(wait_time)
                    children, after_token, err = fetch_search(sub, kw)
                    if err:
                        error = err
                        break

                elif err in ('forbidden', 'not_found'):
                    error = err
                    break
                elif 'private' in str(err).lower() or 'banned' in str(err).lower():
                    blocked_subreddits.add(sub)
                    error = err
                    break
                else:
                    error = err
                    break

            consecutive_rate_limits = 0

            if not children:
                break

            new_posts, all_before_cutoff = process_posts(
                children, sub, kw, group, existing_ids
            )
            all_posts.extend(new_posts)
            page_count += 1

            # Stop if all posts are before cutoff
            if all_before_cutoff:
                break

            # Stop if no more pages
            if not after_token:
                break

        # Save posts
        if all_posts:
            with open(JSONL_PATH, 'a') as f:
                for p in all_posts:
                    f.write(json.dumps(p, ensure_ascii=False) + '\n')

        total_new += len(all_posts)
        timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

        if error:
            progress['failed'].append({
                'subreddit': sub,
                'keyword': kw,
                'keyword_group': group,
                'error': error,
                'timestamp': timestamp
            })
            print(f'ERROR: {error}')
        else:
            progress['completed'].append({
                'subreddit': sub,
                'keyword': kw,
                'keyword_group': group,
                'timestamp': timestamp,
                'posts_found': len(all_posts)
            })
            print(f'{len(all_posts)} posts ({page_count} pages)')

        # Save progress every 5 tasks
        if (i + 1) % 5 == 0:
            save_progress(progress)

    save_progress(progress)
    print(f'\nDone! Total new posts saved: {total_new}')
    print(f'Total posts in JSONL: {len(existing_ids)}')


if __name__ == '__main__':
    main()
