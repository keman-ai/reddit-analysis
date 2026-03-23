#!/usr/bin/env python3
"""
Analyze proxy ordering / 代下单 data from Reddit.
Phase 1: Quantitative analysis — dedup, classify, extract pricing, find patterns.
"""

import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'raw')
INPUT_FILE = os.path.join(DATA_DIR, 'proxy_ordering.jsonl')
DEDUPED_FILE = os.path.join(DATA_DIR, 'proxy_ordering_deduped.jsonl')
REPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'reports')

def load_posts():
    posts = []
    with open(INPUT_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    posts.append(json.loads(line))
                except:
                    pass
    return posts

def dedup_posts(posts):
    seen = set()
    deduped = []
    for p in posts:
        pid = p.get('id', '')
        if pid and pid not in seen:
            seen.add(pid)
            deduped.append(p)
    return deduped

def extract_price(text):
    """Extract price mentions from text."""
    prices = []
    # Match $X, $X.XX, $XXX
    matches = re.findall(r'\$(\d+(?:\.\d{1,2})?)', text)
    for m in matches:
        try:
            val = float(m)
            if 0.5 <= val <= 10000:
                prices.append(val)
        except:
            pass
    return prices

def classify_post_type(post):
    """Classify if post is TASK (demand) or OFFER (supply)."""
    title = post.get('title', '').lower()
    flair = (post.get('link_flair_text') or '').lower()
    text = post.get('selftext', '').lower()

    # Check flair first
    if 'task' in flair or 'hiring' in flair or 'looking' in flair:
        return 'demand'
    if 'offer' in flair or 'for hire' in flair:
        return 'supply'

    # Check title markers
    if any(x in title for x in ['[task]', '[hiring]', '[request]', 'looking for', 'need someone', 'help me', 'can someone', 'can anyone']):
        return 'demand'
    if any(x in title for x in ['[offer]', '[for hire]', 'offering', 'i will', 'i can', 'i\'ll']):
        return 'supply'

    # Check keyword group
    kg = post.get('keyword_group', '')
    if kg in ('buy_for_me', 'shipping_restrictions', 'discount_access', 'limited_exclusive', 'region_locked', 'food_ordering'):
        return 'demand'
    if kg == 'offering_proxy':
        return 'supply'

    return 'unclear'

def classify_category(post):
    """Classify the proxy ordering category."""
    title = (post.get('title', '') + ' ' + post.get('selftext', '')).lower()

    categories = {
        'cross_border_purchase': [
            'japan', 'korea', 'china', 'uk', 'germany', 'europe', 'australia',
            'international', 'ship to', 'ship from', 'country', 'overseas',
            'import', 'customs', 'forward', 'reship'
        ],
        'discount_arbitrage': [
            'student discount', 'military discount', 'employee discount',
            'edu email', '.edu', 'prime', 'membership', 'wholesale',
            'insider', 'referral', 'promo code', 'coupon'
        ],
        'region_locked_digital': [
            'region lock', 'geo restrict', 'vpn', 'not available in',
            'blocked', 'us only', 'us account', 'uk account',
            'subscription', 'streaming', 'spotify', 'netflix', 'hulu',
            'game key', 'steam', 'playstation', 'xbox', 'nintendo'
        ],
        'limited_exclusive': [
            'sold out', 'out of stock', 'limited edition', 'exclusive',
            'drop', 'restock', 'bot', 'sneaker', 'shoe', 'yeezy',
            'jordan', 'nike', 'supreme', 'ticket', 'concert'
        ],
        'food_delivery': [
            'food', 'pizza', 'uber eats', 'doordash', 'grubhub',
            'delivery', 'hungry', 'meal', 'restaurant', 'order food'
        ],
        'digital_goods': [
            'account', 'license', 'key', 'software', 'activation',
            'windows', 'office', 'adobe', 'photoshop', 'antivirus',
            'vpn subscription', 'email', 'domain'
        ],
        'physical_goods': [
            'buy', 'purchase', 'order', 'product', 'item', 'package',
            'amazon', 'ebay', 'walmart', 'target', 'costco', 'store'
        ],
        'fashion_luxury': [
            'rep', 'replica', 'designer', 'luxury', 'bag', 'watch',
            'fashion', 'brand', 'gucci', 'louis vuitton', 'chanel',
            'taobao', 'weidian', 'agent'
        ]
    }

    scores = {}
    for cat, keywords in categories.items():
        score = sum(1 for kw in keywords if kw in title)
        if score > 0:
            scores[cat] = score

    if scores:
        return max(scores, key=scores.get)
    return 'other'

def analyze():
    print("Loading posts...")
    posts = load_posts()
    print(f"Total raw posts: {len(posts)}")

    # Dedup
    posts = dedup_posts(posts)
    print(f"After dedup: {len(posts)}")

    # Save deduped
    with open(DEDUPED_FILE, 'w') as f:
        for p in posts:
            f.write(json.dumps(p, ensure_ascii=False) + '\n')

    # === Basic stats ===
    print("\n" + "="*60)
    print("BASIC STATISTICS")
    print("="*60)

    # By subreddit
    sub_counts = Counter(p['subreddit'] for p in posts)
    print(f"\n--- Posts by subreddit (top 20) ---")
    for sub, count in sub_counts.most_common(20):
        print(f"  r/{sub}: {count}")

    # By subreddit group
    sg_counts = Counter(p.get('subreddit_group', 'unknown') for p in posts)
    print(f"\n--- Posts by subreddit group ---")
    for sg, count in sg_counts.most_common():
        print(f"  {sg}: {count}")

    # By keyword group
    kg_counts = Counter(p.get('keyword_group', 'unknown') for p in posts)
    print(f"\n--- Posts by keyword group ---")
    for kg, count in kg_counts.most_common():
        print(f"  {kg}: {count}")

    # === Demand vs Supply ===
    print("\n" + "="*60)
    print("DEMAND vs SUPPLY")
    print("="*60)

    for p in posts:
        p['_type'] = classify_post_type(p)
        p['_category'] = classify_category(p)

    type_counts = Counter(p['_type'] for p in posts)
    print(f"  Demand (TASK/looking): {type_counts.get('demand', 0)}")
    print(f"  Supply (OFFER): {type_counts.get('supply', 0)}")
    print(f"  Unclear: {type_counts.get('unclear', 0)}")

    demand_posts = [p for p in posts if p['_type'] == 'demand']
    supply_posts = [p for p in posts if p['_type'] == 'supply']

    # === Category Analysis ===
    print("\n" + "="*60)
    print("CATEGORY BREAKDOWN")
    print("="*60)

    cat_counts = Counter(p['_category'] for p in posts)
    print(f"\n--- All posts by category ---")
    for cat, count in cat_counts.most_common():
        pct = count / len(posts) * 100
        print(f"  {cat}: {count} ({pct:.1f}%)")

    # Category × Demand/Supply
    print(f"\n--- Category × Type ---")
    cat_type = defaultdict(lambda: {'demand': 0, 'supply': 0, 'unclear': 0})
    for p in posts:
        cat_type[p['_category']][p['_type']] += 1

    print(f"  {'Category':<25} {'Demand':>8} {'Supply':>8} {'Ratio':>8}")
    print(f"  {'-'*25} {'-'*8} {'-'*8} {'-'*8}")
    for cat, counts in sorted(cat_type.items(), key=lambda x: x[1]['demand'], reverse=True):
        d = counts['demand']
        s = counts['supply']
        ratio = f"{d/s:.1f}:1" if s > 0 else "∞:1"
        print(f"  {cat:<25} {d:>8} {s:>8} {ratio:>8}")

    # === Pricing Analysis ===
    print("\n" + "="*60)
    print("PRICING ANALYSIS")
    print("="*60)

    posts_with_price = []
    for p in posts:
        text = p.get('title', '') + ' ' + p.get('selftext', '')
        prices = extract_price(text)
        if prices:
            p['_prices'] = prices
            posts_with_price.append(p)

    print(f"Posts mentioning prices: {len(posts_with_price)} ({len(posts_with_price)/len(posts)*100:.1f}%)")

    # Price by category
    cat_prices = defaultdict(list)
    for p in posts_with_price:
        for price in p['_prices']:
            cat_prices[p['_category']].append(price)

    print(f"\n--- Price ranges by category ---")
    print(f"  {'Category':<25} {'Count':>6} {'Median':>8} {'Mean':>8} {'P25':>8} {'P75':>8}")
    print(f"  {'-'*25} {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
    for cat, prices in sorted(cat_prices.items(), key=lambda x: len(x[1]), reverse=True):
        prices.sort()
        n = len(prices)
        median = prices[n//2]
        mean = sum(prices) / n
        p25 = prices[n//4]
        p75 = prices[3*n//4]
        print(f"  {cat:<25} {n:>6} ${median:>7.2f} ${mean:>7.2f} ${p25:>7.2f} ${p75:>7.2f}")

    # === Demand-side price vs Supply-side price (the spread!) ===
    print(f"\n--- Demand vs Supply pricing (looking for spread) ---")
    demand_prices_by_cat = defaultdict(list)
    supply_prices_by_cat = defaultdict(list)
    for p in posts_with_price:
        for price in p['_prices']:
            if p['_type'] == 'demand':
                demand_prices_by_cat[p['_category']].append(price)
            elif p['_type'] == 'supply':
                supply_prices_by_cat[p['_category']].append(price)

    all_cats = set(list(demand_prices_by_cat.keys()) + list(supply_prices_by_cat.keys()))
    print(f"  {'Category':<25} {'Demand Med':>10} {'Supply Med':>10} {'Spread':>10}")
    print(f"  {'-'*25} {'-'*10} {'-'*10} {'-'*10}")
    for cat in sorted(all_cats):
        dp = sorted(demand_prices_by_cat.get(cat, []))
        sp = sorted(supply_prices_by_cat.get(cat, []))
        d_med = dp[len(dp)//2] if dp else 0
        s_med = sp[len(sp)//2] if sp else 0
        if d_med > 0 and s_med > 0:
            spread = d_med - s_med
            print(f"  {cat:<25} ${d_med:>9.2f} ${s_med:>9.2f} ${spread:>9.2f}")
        else:
            d_str = f"${d_med:.2f}" if dp else "N/A"
            s_str = f"${s_med:.2f}" if sp else "N/A"
            print(f"  {cat:<25} {d_str:>10} {s_str:>10} {'N/A':>10}")

    # === Engagement Analysis ===
    print("\n" + "="*60)
    print("ENGAGEMENT ANALYSIS (high demand signals)")
    print("="*60)

    # Top upvoted demand posts
    demand_sorted = sorted(demand_posts, key=lambda x: x.get('upvotes', 0), reverse=True)
    print(f"\n--- Top 20 demand posts by upvotes ---")
    for p in demand_sorted[:20]:
        print(f"  [{p.get('upvotes',0):>4}↑ {p.get('comment_count',0):>3}💬] r/{p['subreddit']} | {p['_category']}")
        print(f"    {p['title'][:100]}")
        print(f"    {p['url']}")

    # Top upvoted supply posts
    supply_sorted = sorted(supply_posts, key=lambda x: x.get('upvotes', 0), reverse=True)
    print(f"\n--- Top 20 supply posts by upvotes ---")
    for p in supply_sorted[:20]:
        print(f"  [{p.get('upvotes',0):>4}↑ {p.get('comment_count',0):>3}💬] r/{p['subreddit']} | {p['_category']}")
        print(f"    {p['title'][:100]}")
        print(f"    {p['url']}")

    # === Time Trends ===
    print("\n" + "="*60)
    print("TIME TRENDS")
    print("="*60)

    monthly = defaultdict(int)
    monthly_by_cat = defaultdict(lambda: defaultdict(int))
    for p in posts:
        try:
            dt = datetime.fromisoformat(p['created_at'].replace('+00:00', ''))
            month_key = dt.strftime('%Y-%m')
            monthly[month_key] += 1
            monthly_by_cat[month_key][p['_category']] += 1
        except:
            pass

    print(f"\n--- Posts by month ---")
    for month in sorted(monthly.keys()):
        bar = '█' * (monthly[month] // 20)
        print(f"  {month}: {monthly[month]:>5} {bar}")

    # === Subreddit × Category heatmap ===
    print("\n" + "="*60)
    print("SUBREDDIT × CATEGORY HEATMAP (top 15 subs)")
    print("="*60)

    sub_cat = defaultdict(lambda: defaultdict(int))
    for p in posts:
        sub_cat[p['subreddit']][p['_category']] += 1

    top_subs = [s for s, _ in sub_counts.most_common(15)]
    top_cats = [c for c, _ in cat_counts.most_common(8)]

    header = f"  {'Subreddit':<20}" + ''.join(f"{c[:12]:>14}" for c in top_cats)
    print(header)
    print("  " + "-" * (20 + 14 * len(top_cats)))
    for sub in top_subs:
        row = f"  {sub:<20}"
        for cat in top_cats:
            count = sub_cat[sub].get(cat, 0)
            row += f"{count:>14}"
        print(row)

    # === High-value posts for LLM analysis ===
    print("\n" + "="*60)
    print("EXTRACTING HIGH-VALUE POSTS FOR DEEP ANALYSIS")
    print("="*60)

    # Posts with price + upvotes > 3 OR comments > 5
    high_value = [p for p in posts if (p.get('upvotes', 0) > 3 or p.get('comment_count', 0) > 5)]
    high_value.sort(key=lambda x: x.get('upvotes', 0) + x.get('comment_count', 0) * 2, reverse=True)

    print(f"High-value posts (upvotes>3 or comments>5): {len(high_value)}")

    # Save high-value posts for LLM analysis
    hv_file = os.path.join(DATA_DIR, 'proxy_ordering_high_value.jsonl')
    with open(hv_file, 'w') as f:
        for p in high_value[:500]:
            f.write(json.dumps(p, ensure_ascii=False) + '\n')
    print(f"Saved top 500 high-value posts to {hv_file}")

    # === Summary Stats ===
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total unique posts: {len(posts)}")
    print(f"Demand posts: {type_counts.get('demand', 0)} ({type_counts.get('demand', 0)/len(posts)*100:.1f}%)")
    print(f"Supply posts: {type_counts.get('supply', 0)} ({type_counts.get('supply', 0)/len(posts)*100:.1f}%)")
    print(f"Posts with price: {len(posts_with_price)} ({len(posts_with_price)/len(posts)*100:.1f}%)")
    print(f"High-value posts: {len(high_value)}")
    print(f"Subreddits covered: {len(sub_counts)}")
    print(f"Date range: {min(p.get('created_at','') for p in posts if p.get('created_at'))[:10]} to {max(p.get('created_at','') for p in posts if p.get('created_at'))[:10]}")


if __name__ == '__main__':
    analyze()
