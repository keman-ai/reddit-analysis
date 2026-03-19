#!/usr/bin/env python3
"""
Scrape Reddit service marketplace subreddits for freelance service listings.
Target: 10,000+ service posts that could potentially be replaced by AI Agents.
"""

import json
import os
import time
import urllib.request
import urllib.parse
import random
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'raw')
OUTPUT_FILE = os.path.join(DATA_DIR, 'reddit_services.jsonl')
PROGRESS_FILE = os.path.join(DATA_DIR, 'reddit_services_progress.json')

# Service marketplace subreddits grouped by category
SUBREDDITS = {
    "general_services": [
        "forhire", "slavelabour", "freelance_forhire", "DoneDirtCheap",
        "jobbit", "B2BForHire", "hiring"
    ],
    "writing": [
        "HireAWriter", "WritingOpportunities", "freelanceWriters"
    ],
    "design_art": [
        "DesignJobs", "commissions", "hungryartists",
        "artcommissions", "hireanartist", "artistsforhire"
    ],
    "programming": [
        "programmingrequests", "GameDevClassifieds",
        "webdev", "ProgrammingTasks"
    ],
    "virtual_assistant": [
        "VirtualAssistant", "remotejobs"
    ]
}

# Service-oriented search keywords
KEYWORDS = {
    "for_hire": [
        "for hire", "offering services", "available for work",
        "freelancer available", "will do", "I can help"
    ],
    "hiring": [
        "hiring", "looking for", "need someone", "help wanted",
        "seeking freelancer", "budget"
    ],
    "writing_services": [
        "writing", "copywriting", "content writing", "blog post",
        "resume writing", "proofreading", "editing", "translation",
        "ghostwriting", "SEO writing", "article writing"
    ],
    "design_services": [
        "logo design", "graphic design", "illustration", "UI design",
        "web design", "banner", "flyer", "branding", "thumbnail",
        "social media design", "infographic"
    ],
    "tech_services": [
        "web development", "app development", "python",
        "data entry", "scraping", "bot", "automation",
        "wordpress", "shopify", "excel", "database"
    ],
    "media_services": [
        "video editing", "animation", "voice over", "audio editing",
        "podcast editing", "music production", "photo editing",
        "photoshop", "3D modeling"
    ],
    "marketing_services": [
        "SEO", "social media management", "marketing",
        "email marketing", "ads management", "PPC",
        "content strategy", "influencer"
    ],
    "consulting": [
        "consulting", "coaching", "tutoring", "mentoring",
        "career advice", "business plan", "strategy"
    ],
    "admin_services": [
        "virtual assistant", "data entry", "transcription",
        "research", "bookkeeping", "customer service",
        "administrative", "scheduling"
    ]
}


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {"completed": [], "failed": [], "total_posts": 0}


def save_progress(progress):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)


def load_existing_ids():
    ids = set()
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        post = json.loads(line)
                        ids.add(post.get('id', ''))
                    except:
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

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }

    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return {'error': 'rate_limited'}
        elif e.code == 403:
            return {'error': 'forbidden'}
        elif e.code == 404:
            return {'error': 'not_found'}
        else:
            return {'error': f'http_{e.code}'}
    except Exception as e:
        return {'error': str(e)}


def extract_posts(data, subreddit, keyword, keyword_group, cutoff_date):
    """Extract post data from Reddit API response."""
    posts = []
    after = None

    if 'error' in data:
        return posts, None

    try:
        children = data.get('data', {}).get('children', [])
        after = data.get('data', {}).get('after')

        for child in children:
            post_data = child.get('data', {})
            created_utc = post_data.get('created_utc', 0)
            created_dt = datetime.utcfromtimestamp(created_utc)

            if created_dt < cutoff_date:
                continue

            post = {
                'id': f"t3_{post_data.get('id', '')}",
                'subreddit': post_data.get('subreddit', subreddit),
                'title': post_data.get('title', ''),
                'author': post_data.get('author', ''),
                'created_at': created_dt.strftime('%Y-%m-%dT%H:%M:%S+00:00'),
                'url': f"https://old.reddit.com{post_data.get('permalink', '')}",
                'upvotes': post_data.get('ups', 0),
                'comment_count': post_data.get('num_comments', 0),
                'selftext': post_data.get('selftext', '')[:500],  # First 500 chars of body
                'link_flair_text': post_data.get('link_flair_text', ''),
                'search_keyword': keyword,
                'keyword_group': keyword_group,
                'subreddit_group': '',  # Will be filled
                'score': post_data.get('score', 0),
                'is_self': post_data.get('is_self', True),
            }
            posts.append(post)

    except Exception as e:
        print(f"    Parse error: {e}")

    return posts, after


def main():
    progress = load_progress()
    existing_ids = load_existing_ids()
    total_new = 0
    cutoff_date = datetime(2024, 9, 1)  # Last ~18 months for more data

    print(f"Starting scrape. Existing posts: {len(existing_ids)}")
    print(f"Already completed: {len(progress['completed'])} combos")

    # Build task list
    tasks = []
    for sub_group, subs in SUBREDDITS.items():
        for sub in subs:
            for kw_group, keywords in KEYWORDS.items():
                for keyword in keywords:
                    task_key = f"{sub}|{keyword}"
                    if task_key not in progress['completed'] and task_key not in progress['failed']:
                        tasks.append((sub_group, sub, kw_group, keyword, task_key))

    print(f"Total remaining tasks: {len(tasks)}")

    rate_limit_count = 0
    consecutive_empty = 0  # Track consecutive zero-new-post combos per subreddit
    current_sub = None

    for i, (sub_group, sub, kw_group, keyword, task_key) in enumerate(tasks):
        # Reset counter when switching subreddit
        if sub != current_sub:
            current_sub = sub
            consecutive_empty = 0

        # Skip rest of subreddit if 5 consecutive keywords returned 0 new posts
        if consecutive_empty >= 5:
            print(f"[{i+1}/{len(tasks)}] r/{sub} \"{keyword}\" ({kw_group})... SKIP (5 consecutive empty)")
            progress['completed'].append(task_key)
            save_progress(progress)
            continue

        print(f"[{i+1}/{len(tasks)}] r/{sub} \"{keyword}\" ({kw_group})...", end=' ', flush=True)

        # Fetch up to 3 pages (reduced from 5 for speed)
        page_after = None
        combo_posts = 0

        for page in range(3):
            data = fetch_reddit_search(sub, keyword, after=page_after)

            if 'error' in data:
                error = data['error']
                if error == 'rate_limited':
                    rate_limit_count += 1
                    wait_time = 60 * (2 ** min(rate_limit_count - 1, 3))
                    print(f"RATE LIMITED (#{rate_limit_count}) waiting {wait_time}s...", end=' ', flush=True)
                    time.sleep(wait_time)
                    data = fetch_reddit_search(sub, keyword, after=page_after)
                    if 'error' in data:
                        print(f"ERROR: {data['error']}")
                        progress['failed'].append(task_key)
                        save_progress(progress)
                        break
                elif error in ('not_found', 'forbidden'):
                    print(f"SKIP: {error}")
                    progress['failed'].append(task_key)
                    save_progress(progress)
                    break
                else:
                    print(f"ERROR: {error}")
                    progress['failed'].append(task_key)
                    save_progress(progress)
                    break
            else:
                rate_limit_count = max(0, rate_limit_count - 1)

            posts, page_after = extract_posts(data, sub, keyword, kw_group, cutoff_date)

            # Dedup and write
            new_posts = []
            for p in posts:
                if p['id'] not in existing_ids:
                    p['subreddit_group'] = sub_group
                    existing_ids.add(p['id'])
                    new_posts.append(p)

            if new_posts:
                with open(OUTPUT_FILE, 'a') as f:
                    for p in new_posts:
                        f.write(json.dumps(p, ensure_ascii=False) + '\n')
                combo_posts += len(new_posts)
                total_new += len(new_posts)

            if not page_after or len(posts) == 0:
                break

            # Delay between pages
            time.sleep(random.uniform(1, 3))

        print(f"{combo_posts} posts ({page+1} pages)")

        # Track consecutive empty for early skip
        if combo_posts == 0:
            consecutive_empty += 1
        else:
            consecutive_empty = 0

        # Mark completed
        progress['completed'].append(task_key)
        progress['total_posts'] = len(existing_ids)
        save_progress(progress)

        # Shorter delay
        time.sleep(random.uniform(1, 3))

    print(f"\nDone! Total new posts saved: {total_new}")
    print(f"Total unique posts: {len(existing_ids)}")


if __name__ == '__main__':
    main()
