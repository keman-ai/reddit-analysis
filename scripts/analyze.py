#!/usr/bin/env python3
"""
统一 Reddit 数据定量分析脚本。
读取去重后的 JSONL 数据，输出统计结果 JSON（供报告生成阶段使用）。

用法：
    python scripts/analyze.py \
        --input data/raw/{task_id}_deduped.jsonl \
        --output data/analyzed/{task_id}_stats.json \
        --focus "需求热度,定价信号,痛点分类"
"""

import argparse
import json
import os
import re
from collections import Counter, defaultdict


def load_posts(input_file):
    posts = []
    with open(input_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    posts.append(json.loads(line))
                except Exception:
                    pass
    return posts


def extract_prices(text):
    """Extract dollar amounts from text."""
    prices = []
    patterns = [
        r'\$\s*(\d+(?:,\d{3})*(?:\.\d{1,2})?)',
        r'(\d+(?:,\d{3})*(?:\.\d{1,2})?)\s*(?:usd|dollars?)',
    ]
    for pat in patterns:
        for m in re.finditer(pat, text.lower()):
            val = float(m.group(1).replace(",", ""))
            if 1 <= val <= 10000:
                prices.append(val)
    return prices


def percentile(sorted_list, p):
    """Calculate percentile from a sorted list."""
    if not sorted_list:
        return 0
    idx = int(len(sorted_list) * p / 100)
    idx = min(idx, len(sorted_list) - 1)
    return sorted_list[idx]


def classify_post_simple(post):
    """Simple keyword-based classification of post type."""
    text = (post.get('title', '') + ' ' + post.get('selftext', '')).lower()
    categories = []

    rules = {
        '求助': ['help me', 'need help', 'can someone', 'how do i', 'struggling'],
        '推荐': ['recommend', 'suggestion', 'best way', 'what tool', 'which app'],
        '招聘': ['hiring', 'looking for', 'need someone', 'for hire', 'freelancer'],
        '讨论': ['what do you think', 'opinion', 'thoughts on', 'discussion', 'debate'],
        '展示': ['i built', 'i made', 'i created', 'just launched', 'check out my'],
        '吐槽': ['frustrated', 'annoyed', 'terrible', 'worst', 'scam', 'rant'],
        '教程': ['tutorial', 'guide', 'how to', 'step by step', 'walkthrough'],
    }

    for cat, keywords in rules.items():
        for kw in keywords:
            if kw in text:
                categories.append(cat)
                break

    return categories if categories else ['其他']


def analyze(input_file, output_file, focus_areas):
    posts = load_posts(input_file)
    if not posts:
        print("No posts to analyze.")
        return

    print(f"Loaded {len(posts)} posts")

    # === Basic distributions ===
    subreddit_dist = Counter(p.get('subreddit', '') for p in posts)
    keyword_group_dist = Counter(p.get('keyword_group', '') for p in posts)
    subreddit_group_dist = Counter(p.get('subreddit_group', '') for p in posts)

    # === Unique authors ===
    unique_authors = len(set(p.get('author', '') for p in posts if p.get('author') not in ('[deleted]', '')))

    # === Date range ===
    dates = [p.get('created_at', '')[:10] for p in posts if p.get('created_at')]
    dates = [d for d in dates if d]
    date_range = [min(dates), max(dates)] if dates else ['N/A', 'N/A']

    # === Monthly distribution ===
    monthly = Counter(p.get('created_at', '')[:7] for p in posts if p.get('created_at'))

    # === Engagement stats ===
    upvotes = sorted(p.get('upvotes', 0) for p in posts)
    comments = sorted(p.get('comment_count', 0) for p in posts)

    engagement = {
        'upvotes': {
            'median': percentile(upvotes, 50),
            'mean': round(sum(upvotes) / len(upvotes), 1) if upvotes else 0,
            'p90': percentile(upvotes, 90),
            'p99': percentile(upvotes, 99),
            'max': max(upvotes) if upvotes else 0,
        },
        'comments': {
            'median': percentile(comments, 50),
            'mean': round(sum(comments) / len(comments), 1) if comments else 0,
            'p90': percentile(comments, 90),
            'p99': percentile(comments, 99),
            'max': max(comments) if comments else 0,
        }
    }

    # === Price signals ===
    all_prices = []
    for p in posts:
        text = (p.get('title', '') + ' ' + p.get('selftext', '')).lower()
        all_prices.extend(extract_prices(text))

    all_prices.sort()
    price_signals = {
        'count': len(all_prices),
        'prices': {}
    }
    if all_prices:
        price_signals['prices'] = {
            'median': all_prices[len(all_prices) // 2],
            'mean': round(sum(all_prices) / len(all_prices), 2),
            'p25': percentile(all_prices, 25),
            'p75': percentile(all_prices, 75),
            'min': all_prices[0],
            'max': all_prices[-1],
        }

    # === Post type classification ===
    category_dist = Counter()
    for p in posts:
        cats = classify_post_simple(p)
        for c in cats:
            category_dist[c] += 1

    # === Flair distribution (if available) ===
    flair_dist = Counter(p.get('link_flair_text', '') or 'None' for p in posts)

    # === Top posts by upvotes ===
    n = len(posts)
    if n < 1000:
        top_n = 50
    elif n < 10000:
        top_n = 100
    else:
        top_n = 200

    sorted_by_upvotes = sorted(posts, key=lambda p: p.get('upvotes', 0), reverse=True)
    top_posts = []
    for p in sorted_by_upvotes[:top_n]:
        top_posts.append({
            'id': p.get('id', ''),
            'title': p.get('title', ''),
            'url': p.get('url', ''),
            'subreddit': p.get('subreddit', ''),
            'upvotes': p.get('upvotes', 0),
            'comment_count': p.get('comment_count', 0),
            'selftext': p.get('selftext', '')[:500],
            'created_at': p.get('created_at', ''),
            'link_flair_text': p.get('link_flair_text', ''),
            'keyword_group': p.get('keyword_group', ''),
        })

    # === Assemble stats JSON ===
    stats = {
        'total_posts': len(posts),
        'unique_authors': unique_authors,
        'date_range': date_range,
        'subreddit_distribution': dict(subreddit_dist.most_common()),
        'keyword_group_distribution': dict(keyword_group_dist.most_common()),
        'subreddit_group_distribution': dict(subreddit_group_dist.most_common()),
        'monthly_distribution': dict(sorted(monthly.items())),
        'engagement': engagement,
        'price_signals': price_signals,
        'category_distribution': dict(category_dist.most_common()),
        'flair_distribution': dict(flair_dist.most_common(20)),
        'top_posts': top_posts,
        'top_posts_count': len(top_posts),
        'focus_areas': focus_areas,
    }

    # Write output
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    # Print summary
    print(f"\n=== Analysis Summary ===")
    print(f"Total posts: {len(posts)}")
    print(f"Unique authors: {unique_authors}")
    print(f"Date range: {date_range[0]} ~ {date_range[1]}")
    print(f"Upvotes: median={engagement['upvotes']['median']}, p90={engagement['upvotes']['p90']}, max={engagement['upvotes']['max']}")
    print(f"Comments: median={engagement['comments']['median']}, p90={engagement['comments']['p90']}, max={engagement['comments']['max']}")
    print(f"Price signals: {price_signals['count']} found")
    print(f"Top {len(top_posts)} posts extracted")
    print(f"\nTop 10 subreddits:")
    for sub, cnt in subreddit_dist.most_common(10):
        print(f"  r/{sub}: {cnt}")
    print(f"\nStats saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Reddit data quantitative analysis')
    parser.add_argument('--input', required=True, help='Path to deduped JSONL file')
    parser.add_argument('--output', required=True, help='Path to output stats JSON file')
    parser.add_argument('--focus', default='', help='Comma-separated focus areas for analysis')
    args = parser.parse_args()

    focus_areas = [a.strip() for a in args.focus.split(',') if a.strip()] if args.focus else []
    analyze(args.input, args.output, focus_areas)


if __name__ == '__main__':
    main()
