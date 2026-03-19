#!/usr/bin/env python3
"""
Scrape Reddit help/advice/life subreddits for everyday needs that AI Agents could fulfill.
Unlike service marketplaces (forhire/slavelabour), these capture organic demand signals.
"""

import json
import os
import time
import urllib.request
import urllib.parse
import random
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'raw')
OUTPUT_FILE = os.path.join(DATA_DIR, 'reddit_needs.jsonl')
PROGRESS_FILE = os.path.join(DATA_DIR, 'reddit_needs_progress.json')

# Subreddits where people express needs/ask for help — grouped by domain
SUBREDDITS = {
    "life_advice": [
        "Advice", "needadvice", "internetparents", "NoStupidQuestions",
        "TooAfraidToAsk", "LifeProTips"
    ],
    "career_finance": [
        "personalfinance", "careerguidance", "resumes", "jobs",
        "FinancialPlanning", "povertyfinance", "cscareerquestions"
    ],
    "small_business": [
        "smallbusiness", "Entrepreneur", "sweatystartup",
        "ecommerce", "dropship", "AmazonSeller"
    ],
    "creative_help": [
        "writing", "screenwriting", "selfpublish",
        "WeAreTheMusicMakers", "graphic_design", "Photography"
    ],
    "tech_help": [
        "techsupport", "learnprogramming", "webdev",
        "excel", "GoogleSheets", "Wordpress"
    ],
    "education": [
        "HomeworkHelp", "college", "GradSchool",
        "languagelearning", "ENGLISH", "ChineseLanguage"
    ],
    "health_wellness": [
        "HealthAnxiety", "loseit", "Fitness",
        "MealPrepSunday", "EatCheapAndHealthy"
    ],
    "legal_tax": [
        "legaladvice", "tax", "Landlord"
    ],
    "relationships": [
        "relationship_advice", "dating_advice", "socialskills"
    ],
    "home_life": [
        "HomeImprovement", "Cooking", "DIY",
        "CleaningTips", "organization", "moving"
    ]
}

# Keywords that signal a need an Agent could potentially fulfill
KEYWORDS = {
    "help_me": [
        "help me", "can someone help", "need help with",
        "how do I", "anyone know how to", "struggling with"
    ],
    "looking_for": [
        "looking for", "recommend", "suggestion",
        "best way to", "what tool", "what app"
    ],
    "do_it_for_me": [
        "can someone do", "willing to pay", "is there a service",
        "who can", "where can I find someone", "hire someone to"
    ],
    "writing_needs": [
        "write a letter", "write an email", "cover letter",
        "resume help", "statement of purpose", "personal statement",
        "thank you note", "complaint letter", "business plan"
    ],
    "analysis_needs": [
        "analyze", "spreadsheet help", "data analysis",
        "budget", "financial plan", "compare options",
        "research for me", "summarize"
    ],
    "creative_needs": [
        "design", "logo", "create a", "make me a",
        "edit my photo", "edit my video", "presentation"
    ],
    "translation_needs": [
        "translate", "translation", "proofread",
        "grammar check", "rewrite", "rephrase"
    ],
    "planning_needs": [
        "plan a trip", "meal plan", "workout plan",
        "study plan", "schedule", "organize",
        "to-do list", "project plan"
    ],
    "learning_needs": [
        "explain", "teach me", "learn",
        "understand", "tutor", "course recommendation"
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
                if line.strip():
                    try:
                        ids.add(json.loads(line).get('id', ''))
                    except:
                        pass
    return ids


def fetch_reddit(subreddit, keyword, sort='relevance', time_filter='year', after=None, limit=100):
    params = {
        'q': keyword, 'restrict_sr': 'on', 'sort': sort,
        't': time_filter, 'limit': limit, 'type': 'link'
    }
    if after:
        params['after'] = after
    url = f"https://old.reddit.com/r/{subreddit}/search.json?{urllib.parse.urlencode(params)}"
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        codes = {429: 'rate_limited', 403: 'forbidden', 404: 'not_found'}
        return {'error': codes.get(e.code, f'http_{e.code}')}
    except Exception as e:
        return {'error': str(e)}


def extract_posts(data, subreddit, keyword, kw_group, sub_group, cutoff):
    posts, after = [], None
    if 'error' in data:
        return posts, None
    try:
        children = data.get('data', {}).get('children', [])
        after = data.get('data', {}).get('after')
        for c in children:
            d = c.get('data', {})
            created = datetime.utcfromtimestamp(d.get('created_utc', 0))
            if created < cutoff:
                continue
            posts.append({
                'id': f"t3_{d.get('id', '')}",
                'subreddit': d.get('subreddit', subreddit),
                'title': d.get('title', ''),
                'author': d.get('author', ''),
                'created_at': created.strftime('%Y-%m-%dT%H:%M:%S+00:00'),
                'url': f"https://old.reddit.com{d.get('permalink', '')}",
                'upvotes': d.get('ups', 0),
                'comment_count': d.get('num_comments', 0),
                'selftext': d.get('selftext', '')[:500],
                'link_flair_text': d.get('link_flair_text', '') or '',
                'search_keyword': keyword,
                'keyword_group': kw_group,
                'subreddit_group': sub_group,
                'score': d.get('score', 0),
            })
    except Exception as e:
        print(f"    Parse error: {e}")
    return posts, after


def main():
    progress = load_progress()
    existing_ids = load_existing_ids()
    total_new = 0
    cutoff = datetime(2025, 3, 1)  # Last 12 months

    print(f"Starting. Existing: {len(existing_ids)} | Completed combos: {len(progress['completed'])}")

    # Build tasks
    tasks = []
    for sg, subs in SUBREDDITS.items():
        for sub in subs:
            for kg, kws in KEYWORDS.items():
                for kw in kws:
                    tk = f"{sub}|{kw}"
                    if tk not in progress['completed'] and tk not in progress['failed']:
                        tasks.append((sg, sub, kg, kw, tk))

    print(f"Remaining tasks: {len(tasks)}")

    rate_limit_count = 0
    consecutive_empty = 0
    current_sub = None

    for i, (sg, sub, kg, kw, tk) in enumerate(tasks):
        if sub != current_sub:
            current_sub = sub
            consecutive_empty = 0

        if consecutive_empty >= 5:
            print(f"[{i+1}/{len(tasks)}] r/{sub} \"{kw}\" ... SKIP (5 empty)")
            progress['completed'].append(tk)
            save_progress(progress)
            continue

        print(f"[{i+1}/{len(tasks)}] r/{sub} \"{kw}\" ({kg})...", end=' ', flush=True)

        page_after = None
        combo_new = 0

        for page in range(3):  # Max 3 pages
            data = fetch_reddit(sub, kw, after=page_after)

            if 'error' in data:
                err = data['error']
                if err == 'rate_limited':
                    rate_limit_count += 1
                    wait = 60 * (2 ** min(rate_limit_count - 1, 3))
                    print(f"429 wait {wait}s...", end=' ', flush=True)
                    time.sleep(wait)
                    data = fetch_reddit(sub, kw, after=page_after)
                    if 'error' in data:
                        print(f"ERR: {data['error']}")
                        progress['failed'].append(tk)
                        save_progress(progress)
                        break
                else:
                    if err in ('not_found', 'forbidden'):
                        # Mark all remaining keywords for this sub as failed
                        print(f"SKIP sub: {err}")
                        consecutive_empty = 999
                    else:
                        print(f"ERR: {err}")
                    progress['failed'].append(tk)
                    save_progress(progress)
                    break
            else:
                rate_limit_count = max(0, rate_limit_count - 1)

            posts, page_after = extract_posts(data, sub, kw, kg, sg, cutoff)

            new = [p for p in posts if p['id'] not in existing_ids]
            if new:
                with open(OUTPUT_FILE, 'a') as f:
                    for p in new:
                        f.write(json.dumps(p, ensure_ascii=False) + '\n')
                        existing_ids.add(p['id'])
                combo_new += len(new)
                total_new += len(new)

            if not page_after or len(posts) == 0:
                break
            time.sleep(random.uniform(1, 2))

        else:
            # Loop completed normally (no break)
            pass

        print(f"{combo_new} new")
        consecutive_empty = consecutive_empty + 1 if combo_new == 0 else 0

        progress['completed'].append(tk)
        progress['total_posts'] = len(existing_ids)
        save_progress(progress)
        time.sleep(random.uniform(1, 3))

    print(f"\nDone! New: {total_new} | Total: {len(existing_ids)}")


if __name__ == '__main__':
    main()
