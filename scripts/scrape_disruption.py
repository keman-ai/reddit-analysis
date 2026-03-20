#!/usr/bin/env python3
"""
Scrape Reddit for disruptive innovation signals — Christensen framework.
Find services with high demand barriers (price, complexity, access) that AI Agents can break down.
"""

import json, os, time, urllib.request, urllib.parse, random
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'raw')
OUTPUT_FILE = os.path.join(DATA_DIR, 'reddit_disruption.jsonl')
PROGRESS_FILE = os.path.join(DATA_DIR, 'reddit_disruption_progress.json')

# Subreddits: mix of advice-seeking, cost-conscious, and professional service communities
SUBREDDITS = {
    "cost_barrier": [
        "personalfinance", "povertyfinance", "Frugal", "EatCheapAndHealthy",
        "beermoney", "WorkOnline", "insurance", "HealthInsurance"
    ],
    "access_barrier": [
        "legaladvice", "tax", "Landlord", "immigration",
        "Advice", "needadvice", "NoStupidQuestions", "TooAfraidToAsk"
    ],
    "skill_barrier": [
        "learnprogramming", "webdev", "smallbusiness", "Entrepreneur",
        "startups", "ecommerce", "RealEstate", "Accounting"
    ],
    "life_services": [
        "relationship_advice", "dating_advice", "careerguidance",
        "resumes", "college", "GradSchool", "DIY", "HomeImprovement"
    ],
    "professional_services": [
        "therapists", "AskDocs", "medical_advice",
        "freelance", "graphic_design", "Photography"
    ]
}

# Keywords designed around Christensen's two disruption types
KEYWORDS = {
    # === LOW-END DISRUPTION: "I need this but can't afford the current solution" ===
    "too_expensive": [
        "too expensive", "can't afford", "overpriced",
        "rip off", "not worth the price", "highway robbery",
        "costs too much", "why is it so expensive", "outrageous price"
    ],
    "cheaper_alternative": [
        "cheaper alternative", "budget option", "affordable",
        "free alternative", "DIY instead", "save money on",
        "low cost", "cheap way to", "frugal"
    ],
    "overserved": [
        "don't need all that", "overkill", "too complicated",
        "simpler option", "basic version", "just need something simple",
        "all I need is", "good enough"
    ],

    # === NEW-MARKET DISRUPTION: "I've never had access to this before" ===
    "non_consumer": [
        "never done this before", "first time",
        "is it worth paying for", "should I hire",
        "do I really need", "can I do this myself",
        "never had", "always wanted to but"
    ],
    "access_barrier_kw": [
        "don't know where to start", "overwhelmed",
        "too complicated", "intimidating", "confusing",
        "no idea how to", "wish someone would just",
        "wish I could afford", "out of reach"
    ],
    "diy_struggle": [
        "tried to do it myself", "gave up",
        "spent hours trying", "is there an easier way",
        "struggling with", "failed attempt",
        "how do people do this", "am I doing this right"
    ],

    # === PRICE SENSITIVITY SIGNALS ===
    "price_discovery": [
        "how much does it cost", "what should I expect to pay",
        "is this a fair price", "how much would you charge",
        "worth the money", "waste of money", "price check"
    ],
    "professional_vs_diy": [
        "hire a professional", "do it yourself",
        "worth hiring", "hire vs DIY", "professional or self",
        "should I pay someone", "can I do this without"
    ],

    # === SPECIFIC HIGH-VALUE SERVICE BARRIERS ===
    "legal_barrier": [
        "can't afford a lawyer", "free legal advice",
        "legal aid", "represent myself", "small claims",
        "need a lawyer but", "legal help"
    ],
    "financial_barrier": [
        "can't afford financial advisor", "free financial advice",
        "financial planning DIY", "budgeting help",
        "tax help affordable", "accountant too expensive"
    ],
    "health_barrier": [
        "can't afford therapy", "free mental health",
        "therapy too expensive", "affordable counseling",
        "no insurance", "self-help instead"
    ],
    "education_barrier": [
        "can't afford tutor", "free tutoring",
        "self-taught", "learn on my own",
        "college too expensive", "alternative to college"
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
                    try: ids.add(json.loads(line).get('id', ''))
                    except: pass
    return ids

def fetch(subreddit, keyword, sort='relevance', after=None):
    params = {'q': keyword, 'restrict_sr': 'on', 'sort': sort, 't': 'year', 'limit': 100, 'type': 'link'}
    if after: params['after'] = after
    url = f"https://old.reddit.com/r/{subreddit}/search.json?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return {'error': {429:'rate_limited',403:'forbidden',404:'not_found'}.get(e.code, f'http_{e.code}')}
    except Exception as e:
        return {'error': str(e)}

def extract(data, sub, kw, kg, sg, cutoff):
    posts, after = [], None
    if 'error' in data: return posts, None
    try:
        children = data.get('data',{}).get('children',[])
        after = data.get('data',{}).get('after')
        for c in children:
            d = c.get('data',{})
            created = datetime.utcfromtimestamp(d.get('created_utc',0))
            if created < cutoff: continue
            posts.append({
                'id': f"t3_{d.get('id','')}",
                'subreddit': d.get('subreddit', sub),
                'title': d.get('title',''),
                'selftext': d.get('selftext','')[:800],
                'author': d.get('author',''),
                'created_at': created.strftime('%Y-%m-%dT%H:%M:%S+00:00'),
                'url': f"https://old.reddit.com{d.get('permalink','')}",
                'upvotes': d.get('ups',0),
                'comment_count': d.get('num_comments',0),
                'link_flair_text': d.get('link_flair_text','') or '',
                'search_keyword': kw, 'keyword_group': kg,
                'subreddit_group': sg, 'score': d.get('score',0),
            })
    except Exception as e:
        print(f"  Parse err: {e}")
    return posts, after

def main():
    progress = load_progress()
    existing_ids = load_existing_ids()
    total_new = 0
    cutoff = datetime(2025, 3, 1)

    tasks = []
    for sg, subs in SUBREDDITS.items():
        for sub in subs:
            for kg, kws in KEYWORDS.items():
                for kw in kws:
                    tk = f"{sub}|{kw}"
                    if tk not in progress['completed'] and tk not in progress['failed']:
                        tasks.append((sg, sub, kg, kw, tk))

    print(f"Starting. Existing: {len(existing_ids)} | Remaining tasks: {len(tasks)}")

    rate_limit_count = 0
    consecutive_empty = 0
    current_sub = None

    for i, (sg, sub, kg, kw, tk) in enumerate(tasks):
        if sub != current_sub:
            current_sub = sub
            consecutive_empty = 0
        if consecutive_empty >= 8:
            progress['completed'].append(tk)
            save_progress(progress)
            continue

        print(f"[{i+1}/{len(tasks)}] r/{sub} \"{kw}\" ({kg})...", end=' ', flush=True)

        page_after = None
        combo_new = 0
        for page in range(3):
            data = fetch(sub, kw, after=page_after)
            if 'error' in data:
                err = data['error']
                if err == 'rate_limited':
                    rate_limit_count += 1
                    wait = 60 * (2 ** min(rate_limit_count - 1, 3))
                    print(f"429 wait {wait}s...", end=' ', flush=True)
                    time.sleep(wait)
                    data = fetch(sub, kw, after=page_after)
                    if 'error' in data:
                        progress['failed'].append(tk); save_progress(progress); break
                elif err in ('not_found','forbidden'):
                    consecutive_empty = 999
                    progress['failed'].append(tk); save_progress(progress); break
                else:
                    progress['failed'].append(tk); save_progress(progress); break
            else:
                rate_limit_count = max(0, rate_limit_count - 1)

            posts, page_after = extract(data, sub, kw, kg, sg, cutoff)
            new = [p for p in posts if p['id'] not in existing_ids]
            if new:
                with open(OUTPUT_FILE, 'a') as f:
                    for p in new:
                        f.write(json.dumps(p, ensure_ascii=False) + '\n')
                        existing_ids.add(p['id'])
                combo_new += len(new)
                total_new += len(new)
            if not page_after or len(posts) == 0: break
            time.sleep(random.uniform(1, 2))

        print(f"{combo_new} new")
        consecutive_empty = consecutive_empty + 1 if combo_new == 0 else 0
        progress['completed'].append(tk)
        progress['total_posts'] = len(existing_ids)
        save_progress(progress)
        time.sleep(random.uniform(1, 3))

    print(f"\nDone! New: {total_new} | Total: {len(existing_ids)}")

if __name__ == '__main__':
    main()
