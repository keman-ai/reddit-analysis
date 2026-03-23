#!/usr/bin/env python3
"""
Deep analysis: filter actual proxy ordering posts and analyze spread/opportunity.
Focus on posts that are genuinely about buying/ordering on someone's behalf.
"""

import json
import os
import re
from collections import Counter, defaultdict

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'raw')
INPUT_FILE = os.path.join(DATA_DIR, 'proxy_ordering_deduped.jsonl')

# Strict patterns that indicate genuine proxy ordering
PROXY_PATTERNS = {
    'cross_border': [
        r'ship.*(?:from|to)\s+\w+',
        r'(?:buy|order|purchase|get).*(?:from|in)\s+(?:japan|korea|china|uk|us|europe|germany|australia|canada|india|mexico|brazil|singapore|taiwan|hong kong)',
        r'forward.*package', r'package.*forward',
        r'reship', r'mail.*forward',
        r'international.*ship', r'ship.*international',
        r'(?:doesn\'t|won\'t|don\'t|cannot|can\'t).*ship.*(?:to|outside)',
        r'not.*(?:available|ship).*(?:country|region)',
        r'import.*from', r'customs',
    ],
    'discount_arbitrage': [
        r'(?:student|military|employee|edu|\.edu).*discount',
        r'discount.*(?:student|military|employee)',
        r'(?:someone|anyone).*(?:with|have|has).*(?:prime|membership|discount)',
        r'(?:use|using).*(?:your|someone\'s).*(?:discount|membership|prime)',
        r'(?:edu|\.edu).*(?:email|account|address)',
    ],
    'region_locked': [
        r'region.*lock', r'geo.*restrict',
        r'(?:need|want).*(?:us|uk|eu|jp).*(?:account|address|vpn)',
        r'(?:not|isn\'t|unavailable).*(?:available|accessible).*(?:my|this|our).*(?:country|region)',
        r'(?:us|uk|eu).*only',
        r'blocked.*(?:country|region)',
    ],
    'buy_for_me': [
        r'(?:buy|order|purchase|pick up|grab).*(?:for me|on my behalf)',
        r'(?:need|want|looking for).*(?:someone|anyone|person).*(?:to buy|to order|to purchase|to pick)',
        r'(?:can|could|would).*(?:someone|anyone|you).*(?:buy|order|purchase|pick up).*(?:for|and ship|and send)',
        r'personal.*shopp',
        r'proxy.*(?:buy|order|purchase)',
        r'buying.*(?:agent|service)',
        r'(?:order|buy).*(?:deliver|ship).*(?:to me|to my)',
    ],
    'food_proxy': [
        r'(?:order|get).*(?:food|pizza|meal|dinner|lunch|breakfast).*(?:for|deliver)',
        r'(?:uber eats|doordash|grubhub|deliveroo|just eat).*(?:for|order)',
        r'(?:hungry|starving).*(?:can|could|would).*(?:someone|anyone)',
        r'(?:need|want).*(?:food|meal).*(?:delivered|ordered)',
    ],
    'subscription_proxy': [
        r'(?:buy|get|need).*(?:subscription|license|key|activation)',
        r'(?:share|sharing).*(?:account|subscription|netflix|spotify|hulu)',
        r'(?:someone|anyone).*(?:with|have|has).*(?:subscription|account|access)',
    ],
    'limited_item': [
        r'(?:sold out|out of stock).*(?:buy|get|find)',
        r'(?:buy|get|find).*(?:sold out|out of stock)',
        r'(?:limited|exclusive).*(?:edition|drop|release).*(?:buy|get|help)',
        r'(?:help|need).*(?:buy|get|cop).*(?:limited|exclusive|drop|release)',
        r'(?:bot|auto).*(?:buy|purchase|checkout)',
    ],
}

def is_proxy_ordering(post):
    """Check if a post is genuinely about proxy ordering. Returns (bool, category)."""
    text = (post.get('title', '') + ' ' + post.get('selftext', '')).lower()

    for category, patterns in PROXY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text):
                return True, category
    return False, None

def extract_service_fee(post):
    """Try to extract the service fee / tip offered for proxy ordering."""
    text = (post.get('title', '') + ' ' + post.get('selftext', '')).lower()

    # Look for fee patterns
    fee_patterns = [
        r'(?:pay|tip|fee|charge|service|compensation|reward)\D{0,20}\$(\d+(?:\.\d{1,2})?)',
        r'\$(\d+(?:\.\d{1,2})?)\D{0,20}(?:tip|fee|extra|bonus|compensation|service)',
        r'(?:willing to pay|will pay|offering|budget)\D{0,20}\$(\d+(?:\.\d{1,2})?)',
    ]

    fees = []
    for pattern in fee_patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            try:
                val = float(m)
                if 0.5 <= val <= 500:
                    fees.append(val)
            except:
                pass
    return fees

def extract_item_cost(post):
    """Try to extract the actual item cost."""
    text = (post.get('title', '') + ' ' + post.get('selftext', '')).lower()

    # Look for item cost patterns
    cost_patterns = [
        r'(?:item|product|cost|price|worth|retail|value|original)\D{0,20}\$(\d+(?:\.\d{1,2})?)',
        r'\$(\d+(?:\.\d{1,2})?)\D{0,20}(?:item|product|retail|worth|value)',
    ]

    costs = []
    for pattern in cost_patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            try:
                val = float(m)
                if 1 <= val <= 10000:
                    costs.append(val)
            except:
                pass
    return costs

def analyze():
    print("Loading deduped posts...")
    posts = []
    with open(INPUT_FILE, 'r') as f:
        for line in f:
            if line.strip():
                try:
                    posts.append(json.loads(line.strip()))
                except:
                    pass

    print(f"Total posts: {len(posts)}")

    # Filter for genuine proxy ordering
    proxy_posts = []
    non_proxy = []
    cat_counter = Counter()

    for p in posts:
        is_proxy, category = is_proxy_ordering(p)
        if is_proxy:
            p['_proxy_category'] = category
            proxy_posts.append(p)
            cat_counter[category] += 1
        else:
            non_proxy.append(p)

    print(f"\nGenuine proxy ordering posts: {len(proxy_posts)} ({len(proxy_posts)/len(posts)*100:.1f}%)")
    print(f"Non-proxy (filtered out): {len(non_proxy)}")

    print(f"\n--- Proxy ordering by category ---")
    for cat, count in cat_counter.most_common():
        pct = count / len(proxy_posts) * 100
        print(f"  {cat:<25} {count:>5} ({pct:.1f}%)")

    # === Demand vs Supply in proxy posts ===
    demand = [p for p in proxy_posts if any(x in (p.get('link_flair_text') or '').lower() for x in ['task', 'hiring', 'request']) or
              any(x in p.get('title', '').lower() for x in ['[task]', '[hiring]', '[request]', 'need someone', 'looking for', 'can someone', 'can anyone', 'help me'])]
    supply = [p for p in proxy_posts if any(x in (p.get('link_flair_text') or '').lower() for x in ['offer', 'for hire']) or
              any(x in p.get('title', '').lower() for x in ['[offer]', '[for hire]', 'i will', 'i can', 'offering'])]
    unclear = [p for p in proxy_posts if p not in demand and p not in supply]

    print(f"\n--- Demand vs Supply in proxy posts ---")
    print(f"  Demand: {len(demand)} ({len(demand)/len(proxy_posts)*100:.1f}%)")
    print(f"  Supply: {len(supply)} ({len(supply)/len(proxy_posts)*100:.1f}%)")
    print(f"  Unclear: {len(unclear)} ({len(unclear)/len(proxy_posts)*100:.1f}%)")

    # Category × demand/supply
    print(f"\n--- Category × Demand/Supply ---")
    cat_ds = defaultdict(lambda: {'demand': 0, 'supply': 0, 'unclear': 0})
    for p in demand:
        cat_ds[p['_proxy_category']]['demand'] += 1
    for p in supply:
        cat_ds[p['_proxy_category']]['supply'] += 1
    for p in unclear:
        cat_ds[p['_proxy_category']]['unclear'] += 1

    print(f"  {'Category':<25} {'Demand':>8} {'Supply':>8} {'D/S Ratio':>10}")
    print(f"  {'-'*25} {'-'*8} {'-'*8} {'-'*10}")
    for cat in sorted(cat_ds.keys(), key=lambda x: cat_ds[x]['demand'], reverse=True):
        d = cat_ds[cat]['demand']
        s = cat_ds[cat]['supply']
        ratio = f"{d/s:.1f}:1" if s > 0 else "∞:1"
        print(f"  {cat:<25} {d:>8} {s:>8} {ratio:>10}")

    # === Top demand posts (TRUE proxy ordering) ===
    print(f"\n{'='*60}")
    print("TOP 30 DEMAND POSTS (genuine proxy ordering)")
    print(f"{'='*60}")

    demand_sorted = sorted(demand, key=lambda x: x.get('upvotes', 0), reverse=True)
    for i, p in enumerate(demand_sorted[:30]):
        print(f"\n  #{i+1} [{p.get('upvotes',0):>4}↑ {p.get('comment_count',0):>3}💬] r/{p['subreddit']} | {p['_proxy_category']}")
        print(f"    {p['title'][:120]}")
        body = p.get('selftext', '')[:200].replace('\n', ' ')
        if body:
            print(f"    Body: {body}")
        print(f"    {p['url']}")

    # === Top supply posts ===
    print(f"\n{'='*60}")
    print("TOP 20 SUPPLY POSTS (genuine proxy ordering)")
    print(f"{'='*60}")

    supply_sorted = sorted(supply, key=lambda x: x.get('upvotes', 0), reverse=True)
    for i, p in enumerate(supply_sorted[:20]):
        print(f"\n  #{i+1} [{p.get('upvotes',0):>4}↑ {p.get('comment_count',0):>3}💬] r/{p['subreddit']} | {p['_proxy_category']}")
        print(f"    {p['title'][:120]}")
        body = p.get('selftext', '')[:200].replace('\n', ' ')
        if body:
            print(f"    Body: {body}")
        print(f"    {p['url']}")

    # === Pricing & Spread Analysis ===
    print(f"\n{'='*60}")
    print("PRICING & FEE ANALYSIS")
    print(f"{'='*60}")

    demand_fees_by_cat = defaultdict(list)
    supply_fees_by_cat = defaultdict(list)

    for p in demand:
        fees = extract_service_fee(p)
        for fee in fees:
            demand_fees_by_cat[p['_proxy_category']].append(fee)

    for p in supply:
        fees = extract_service_fee(p)
        for fee in fees:
            supply_fees_by_cat[p['_proxy_category']].append(fee)

    all_cats = set(list(demand_fees_by_cat.keys()) + list(supply_fees_by_cat.keys()))
    print(f"\n--- Service fees: Demand (willing to pay) vs Supply (charging) ---")
    print(f"  {'Category':<25} {'D_count':>8} {'D_median':>10} {'S_count':>8} {'S_median':>10} {'Spread':>10}")
    print(f"  {'-'*25} {'-'*8} {'-'*10} {'-'*8} {'-'*10} {'-'*10}")
    for cat in sorted(all_cats):
        dp = sorted(demand_fees_by_cat.get(cat, []))
        sp = sorted(supply_fees_by_cat.get(cat, []))
        d_med = dp[len(dp)//2] if dp else 0
        s_med = sp[len(sp)//2] if sp else 0
        spread = d_med - s_med if d_med and s_med else None
        spread_str = f"${spread:.2f}" if spread is not None else "N/A"
        print(f"  {cat:<25} {len(dp):>8} {'$'+f'{d_med:.2f}' if dp else 'N/A':>10} {len(sp):>8} {'$'+f'{s_med:.2f}' if sp else 'N/A':>10} {spread_str:>10}")

    # === Engagement patterns ===
    print(f"\n{'='*60}")
    print("ENGAGEMENT BY CATEGORY")
    print(f"{'='*60}")

    for cat in sorted(cat_counter.keys()):
        cat_posts = [p for p in proxy_posts if p['_proxy_category'] == cat]
        upvotes = [p.get('upvotes', 0) for p in cat_posts]
        comments = [p.get('comment_count', 0) for p in cat_posts]
        upvotes.sort()
        comments.sort()
        n = len(upvotes)
        print(f"\n  {cat} ({n} posts):")
        print(f"    Upvotes  — median: {upvotes[n//2]}, mean: {sum(upvotes)/n:.1f}, P90: {upvotes[int(n*0.9)]}")
        print(f"    Comments — median: {comments[n//2]}, mean: {sum(comments)/n:.1f}, P90: {comments[int(n*0.9)]}")

    # === Time trend for proxy categories ===
    print(f"\n{'='*60}")
    print("TIME TREND BY CATEGORY (2024-2026)")
    print(f"{'='*60}")

    from datetime import datetime
    monthly_cat = defaultdict(lambda: defaultdict(int))
    for p in proxy_posts:
        try:
            dt = datetime.fromisoformat(p['created_at'].replace('+00:00', ''))
            if dt.year >= 2024:
                month_key = dt.strftime('%Y-%m')
                monthly_cat[month_key][p['_proxy_category']] += 1
        except:
            pass

    top_cats = [c for c, _ in cat_counter.most_common(6)]
    header = f"  {'Month':<10}" + ''.join(f"{c[:15]:>16}" for c in top_cats)
    print(header)
    for month in sorted(monthly_cat.keys()):
        row = f"  {month:<10}"
        for cat in top_cats:
            row += f"{monthly_cat[month].get(cat, 0):>16}"
        print(row)

    # === Save filtered proxy posts ===
    output_file = os.path.join(DATA_DIR, 'proxy_ordering_filtered.jsonl')
    with open(output_file, 'w') as f:
        for p in proxy_posts:
            f.write(json.dumps(p, ensure_ascii=False) + '\n')
    print(f"\nSaved {len(proxy_posts)} filtered proxy ordering posts to {output_file}")

    # Save top demand for LLM analysis
    top_demand_file = os.path.join(DATA_DIR, 'proxy_ordering_top_demand.jsonl')
    with open(top_demand_file, 'w') as f:
        for p in demand_sorted[:200]:
            f.write(json.dumps(p, ensure_ascii=False) + '\n')
    print(f"Saved top 200 demand posts to {top_demand_file}")


if __name__ == '__main__':
    analyze()
