#!/usr/bin/env python3
"""
Scrape Reddit for proxy ordering / 代下单 demand and supply signals.
Focus areas:
  1. Cross-border proxy purchasing (buy from country X, ship to Y)
  2. Discount arbitrage (student/military/employee discounts)
  3. Platform-restricted purchasing (region-locked, account-required)
  4. Limited/exclusive item purchasing (sneakers, tickets, drops)
"""

import json
import os
import time
import urllib.request
import urllib.parse
import random
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'raw')
OUTPUT_FILE = os.path.join(DATA_DIR, 'proxy_ordering.jsonl')
PROGRESS_FILE = os.path.join(DATA_DIR, 'proxy_ordering_progress.json')

# Subreddits where proxy ordering demand/supply appears
SUBREDDITS = {
    "service_marketplaces": [
        "slavelabour", "forhire", "DoneDirtCheap",
        "signupsforpay", "redditbay"
    ],
    "cross_border_shopping": [
        "snackexchange", "AmazonGlobal", "Buyingfromamazon",
        "japanlife", "JapanTravel", "korea",
        "AsianBeauty", "KoreanBeauty"
    ],
    "fashion_reps": [
        "FashionReps", "Repsneakers", "RepLadies",
        "DesignerReps", "QualityReps"
    ],
    "deal_hunting": [
        "deals", "buildapcsales", "hardwareswap",
        "GameSale", "SteamGameSwap",
        "giftcardexchange"
    ],
    "reselling_flipping": [
        "Flipping", "sneakermarket", "shoebots",
        "FulfillmentByAmazon", "dropship"
    ],
    "help_favors": [
        "favors", "Assistance", "RandomKindness",
        "RandomActsOfPizza", "RandomActsOfGaming"
    ],
    "subscription_sharing": [
        "redditbay", "AccountSharing",
        "microsoftsoftwareswap"
    ],
    "food_delivery": [
        "UberEATS", "doordash", "grubhub",
        "fooddelivery"
    ],
    "tickets_events": [
        "TicketSwap", "ConcertTickets",
        "stubhub"
    ]
}

# Keywords capturing proxy ordering demand and supply
KEYWORDS = {
    # Demand: someone wants others to order for them
    "buy_for_me": [
        "buy for me", "order for me", "purchase for me",
        "can someone order", "can someone buy",
        "need someone to order", "need someone to buy",
        "willing to pay someone to order",
        "anyone willing to buy"
    ],
    "proxy_purchase": [
        "proxy order", "proxy purchase", "proxy buy",
        "proxy service", "personal shopper",
        "buying agent", "purchasing agent",
        "shopping service", "forwarding service"
    ],
    "shipping_restrictions": [
        "doesn't ship to", "won't ship to",
        "not available in my country", "US only",
        "can't order from", "not shipping internationally",
        "ship internationally", "international shipping",
        "forward package", "package forwarding",
        "reship", "mail forwarding"
    ],
    "discount_access": [
        "student discount", "military discount",
        "employee discount", "edu email",
        "someone with Prime", "Amazon Prime",
        "membership discount", "insider pricing",
        "referral code", "promo code",
        "wholesale price", "bulk discount"
    ],
    "limited_exclusive": [
        "sold out", "out of stock",
        "limited edition", "exclusive drop",
        "can't get", "help me get",
        "bot to buy", "auto purchase",
        "restock alert", "notify when available"
    ],
    "region_locked": [
        "region locked", "geo restricted",
        "VPN purchase", "US address needed",
        "need US account", "need UK account",
        "not available in", "blocked in my country",
        "access from outside"
    ],
    # Supply: someone offers to order for others
    "offering_proxy": [
        "I can order for you", "I'll buy for you",
        "offering proxy", "offering to buy",
        "I have access to", "I have Prime",
        "I have student discount", "I have employee discount",
        "I can get you", "personal shopping service",
        "will order for", "can purchase for"
    ],
    "food_ordering": [
        "order food for", "order delivery for",
        "order uber eats", "order doordash",
        "order grubhub", "food delivery for",
        "can someone order food", "hungry no money"
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


def fetch_reddit_search(subreddit, keyword, sort='relevance', time_filter='all', after=None, limit=100):
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


def extract_posts(data, subreddit, keyword, keyword_group, sub_group):
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

            post = {
                'id': f"t3_{post_data.get('id', '')}",
                'subreddit': post_data.get('subreddit', subreddit),
                'title': post_data.get('title', ''),
                'author': post_data.get('author', ''),
                'created_at': created_dt.strftime('%Y-%m-%dT%H:%M:%S+00:00'),
                'url': f"https://old.reddit.com{post_data.get('permalink', '')}",
                'upvotes': post_data.get('ups', 0),
                'comment_count': post_data.get('num_comments', 0),
                'selftext': post_data.get('selftext', '')[:1000],
                'link_flair_text': post_data.get('link_flair_text', ''),
                'search_keyword': keyword,
                'keyword_group': keyword_group,
                'subreddit_group': sub_group,
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

    print(f"Starting proxy ordering scrape. Existing posts: {len(existing_ids)}")
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
    consecutive_empty = 0
    current_sub = None

    for i, (sub_group, sub, kw_group, keyword, task_key) in enumerate(tasks):
        if sub != current_sub:
            current_sub = sub
            consecutive_empty = 0

        # Skip rest of subreddit if 5 consecutive keywords returned 0 new posts
        if consecutive_empty >= 5:
            progress['completed'].append(task_key)
            continue

        print(f"[{i+1}/{len(tasks)}] r/{sub} | \"{keyword}\" ({kw_group})")

        page = 0
        after = None
        new_in_combo = 0

        while page < 5:  # Max 5 pages per combo
            delay = random.uniform(2, 5)
            time.sleep(delay)

            data = fetch_reddit_search(sub, keyword, after=after)

            if not data or 'error' in data:
                error = data.get('error', 'unknown') if data else 'no_response'
                if error == 'rate_limited':
                    rate_limit_count += 1
                    wait = min(60 * (2 ** rate_limit_count), 480)
                    print(f"    Rate limited! Waiting {wait}s (attempt {rate_limit_count})")
                    time.sleep(wait)
                    continue
                elif error in ('forbidden', 'not_found'):
                    print(f"    {error} — skipping r/{sub}")
                    progress['failed'].append(task_key)
                    break
                else:
                    print(f"    Error: {error}")
                    break

            rate_limit_count = 0
            posts, after = extract_posts(data, sub, keyword, kw_group, sub_group)

            new_posts = [p for p in posts if p['id'] not in existing_ids]

            if new_posts:
                with open(OUTPUT_FILE, 'a') as f:
                    for post in new_posts:
                        f.write(json.dumps(post, ensure_ascii=False) + '\n')
                        existing_ids.add(post['id'])

                new_in_combo += len(new_posts)
                total_new += len(new_posts)

            if not after or len(posts) == 0:
                break
            page += 1

        if new_in_combo == 0:
            consecutive_empty += 1
        else:
            consecutive_empty = 0

        progress['completed'].append(task_key)
        progress['total_posts'] = len(existing_ids)
        save_progress(progress)

        if (i + 1) % 50 == 0:
            print(f"\n--- Progress: {i+1}/{len(tasks)} tasks, {total_new} new posts, {len(existing_ids)} total ---\n")

    print(f"\nDone! Total new posts: {total_new}, Total posts: {len(existing_ids)}")


if __name__ == '__main__':
    main()
