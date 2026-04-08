#!/usr/bin/env python3
"""
从本地 corpus 中按关键词检索帖子。

用法：
    python scripts/search_corpus.py \
        --plan data/raw/{task_id}_plan.json \
        --output data/raw/{task_id}_matched.jsonl
"""

import argparse
import json
import os
import re

CORPUS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'corpus')


def _keyword_matches(text_lower, keyword_lower):
    """Check if a keyword matches text.

    Strategy:
    - Single word keyword: simple substring match
    - Multi-word keyword: ALL words must appear in text (order-independent)
    This catches "Copilot vs Cursor" matching text with "switched from Copilot to Cursor"
    """
    words = keyword_lower.split()
    if len(words) == 1:
        return words[0] in text_lower
    return all(w in text_lower for w in words)


def search_subreddit(corpus_file, keywords):
    """Scan a corpus JSONL file, return posts matching any keyword.

    Match is case-insensitive on title + selftext.
    Multi-word keywords use all-words-present matching (not exact substring).
    Each post is returned at most once, tagged with the first matching keyword.
    """
    matched = []
    seen_ids = set()

    # Pre-process keywords
    kw_list = [(kw_term, kw_group, kw_term.lower()) for kw_term, kw_group in keywords]

    with open(corpus_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                post = json.loads(line)
            except Exception:
                continue

            pid = post.get('id', '')
            if pid in seen_ids:
                continue

            text = (post.get('title', '') + ' ' + post.get('selftext', '')).lower()

            for kw_term, kw_group, kw_lower in kw_list:
                if _keyword_matches(text, kw_lower):
                    post['search_keyword'] = kw_term
                    post['keyword_group'] = kw_group
                    matched.append(post)
                    seen_ids.add(pid)
                    break

    return matched


def main():
    parser = argparse.ArgumentParser(description='Search local corpus by keywords from plan JSON')
    parser.add_argument('--plan', required=True, help='Path to plan JSON file')
    parser.add_argument('--output', required=True, help='Path to output matched JSONL file')
    args = parser.parse_args()

    with open(args.plan, 'r') as f:
        plan = json.load(f)

    # Build keyword list: [(term, group), ...]
    keywords = [(kw['term'], kw.get('group', 'default')) for kw in plan.get('keywords', [])]

    target_subs = [s['name'] for s in plan.get('subreddits', [])]

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    total_matched = 0
    total_scanned = 0
    missing_subs = []

    with open(args.output, 'w') as fout:
        for sub in target_subs:
            corpus_file = os.path.join(CORPUS_DIR, f"{sub}.jsonl")
            if not os.path.exists(corpus_file):
                missing_subs.append(sub)
                print(f"  Warning: corpus not found for r/{sub}, skipping")
                continue

            # Count lines for progress
            line_count = sum(1 for _ in open(corpus_file))
            print(f"  Searching r/{sub} ({line_count} posts)...", end=' ', flush=True)
            total_scanned += line_count

            matched = search_subreddit(corpus_file, keywords)
            for post in matched:
                fout.write(json.dumps(post, ensure_ascii=False) + '\n')
            total_matched += len(matched)
            print(f"{len(matched)} matched")

    # Print summary
    print(f"\n=== Search Summary ===")
    print(f"Subreddits searched: {len(target_subs) - len(missing_subs)}/{len(target_subs)}")
    print(f"Posts scanned: {total_scanned}")
    print(f"Posts matched: {total_matched}")
    if missing_subs:
        print(f"Missing corpus: {', '.join(missing_subs)}")
    print(f"Output: {args.output}")

    # Write summary JSON
    summary = {
        'total_scanned': total_scanned,
        'total_matched': total_matched,
        'subreddits_searched': len(target_subs) - len(missing_subs),
        'subreddits_missing': missing_subs,
    }
    summary_file = args.output.replace('.jsonl', '_search_summary.json')
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)


if __name__ == '__main__':
    main()
