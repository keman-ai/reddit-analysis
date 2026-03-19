#!/usr/bin/env python3
"""Analyze Reddit services data for AI Agent marketplace selection."""

import json
import re
from collections import Counter, defaultdict
import sys

DATA_FILE = "/Users/huanghaibin/Workspace/reddit_research/data/raw/reddit_services.jsonl"

# Service type classification rules: (category, subcategory, keywords)
SERVICE_CATEGORIES = {
    # Writing
    "copywriting": ("writing", ["copywriting", "copy writing", "copywriter"]),
    "resume_writing": ("writing", ["resume", "cv writing", "cv writer", "cover letter"]),
    "blog_article": ("writing", ["blog", "article", "content writing", "content writer", "ghostwrit", "ghost writ"]),
    "proofreading_editing": ("writing", ["proofread", "editing", "editor", "proofreader", "copy edit"]),
    "technical_writing": ("writing", ["technical writ", "documentation", "white paper", "whitepaper"]),
    "academic_writing": ("writing", ["essay", "academic", "research paper", "thesis", "dissertation"]),
    "creative_writing": ("writing", ["creative writ", "fiction", "storytell", "screenplay", "script writ"]),
    "email_writing": ("writing", ["email", "cold outreach", "outreach"]),
    "ebook": ("writing", ["ebook", "e-book", "kindle"]),

    # Design
    "logo_design": ("design", ["logo", "brand identity", "branding"]),
    "graphic_design": ("design", ["graphic design", "banner", "flyer", "brochure", "poster", "infographic"]),
    "illustration": ("design", ["illustrat", "drawing", "sketch", "cartoon", "comic", "digital art"]),
    "ui_ux": ("design", ["ui/ux", "ui ux", "ux design", "ui design", "user interface", "user experience", "figma"]),
    "web_design": ("design", ["web design", "website design", "landing page design"]),
    "thumbnail": ("design", ["thumbnail", "youtube thumbnail"]),
    "photo_editing": ("design", ["photo edit", "photoshop", "image edit", "retouching", "photo retouching", "background removal"]),
    "presentation_design": ("design", ["presentation", "powerpoint", "ppt", "slide", "pitch deck"]),

    # Programming
    "web_dev": ("programming", ["web develop", "website", "frontend", "front-end", "backend", "back-end", "full stack", "fullstack", "full-stack", "react", "angular", "vue", "next.js", "node.js", "django", "flask", "html", "css", "javascript"]),
    "app_dev": ("programming", ["app develop", "mobile app", "ios app", "android app", "flutter", "react native", "swift", "kotlin"]),
    "python_dev": ("programming", ["python", "django", "flask", "fastapi"]),
    "scraping": ("programming", ["scraping", "scraper", "web scraping", "data scraping", "crawl"]),
    "bot_dev": ("programming", ["discord bot", "telegram bot", "twitch bot", "chat bot", "chatbot"]),
    "wordpress": ("programming", ["wordpress", "woocommerce", "elementor"]),
    "shopify": ("programming", ["shopify", "ecommerce", "e-commerce"]),
    "automation": ("programming", ["automat", "zapier", "make.com", "n8n", "workflow"]),
    "api_dev": ("programming", ["api develop", "api integration", "rest api", "restful"]),
    "database": ("programming", ["database", "sql", "mysql", "postgresql", "mongodb"]),
    "game_dev": ("programming", ["game dev", "unity", "unreal", "godot", "game design"]),
    "ai_ml": ("programming", ["machine learning", "deep learning", "neural network", "ai develop", "nlp", "computer vision", "tensorflow", "pytorch", "gpt", "llm", "fine-tun", "finetun"]),

    # Audio/Video
    "video_editing": ("media", ["video edit", "video production", "after effects", "premiere", "davinci", "motion graphics"]),
    "voice_over": ("media", ["voice over", "voiceover", "voice actor", "narrator", "narration", "voice talent"]),
    "animation": ("media", ["animat", "2d animation", "3d animation", "explainer video"]),
    "audio_editing": ("media", ["audio edit", "audio engineer", "mixing", "mastering", "podcast edit", "sound design"]),
    "music_production": ("media", ["music produc", "beat", "jingle", "compose", "soundtrack"]),

    # Marketing
    "seo": ("marketing", ["seo", "search engine optim"]),
    "social_media": ("marketing", ["social media", "instagram", "tiktok", "twitter", "facebook", "linkedin", "pinterest", "social media manag"]),
    "ads_ppc": ("marketing", ["google ads", "facebook ads", "ppc", "paid ads", "ad campaign", "meta ads"]),
    "email_marketing": ("marketing", ["email market", "newsletter", "mailchimp", "email campaign"]),
    "content_strategy": ("marketing", ["content strateg", "content market", "marketing strateg"]),
    "lead_generation": ("marketing", ["lead gen", "lead generation", "cold call", "b2b"]),
    "amazon_fba": ("marketing", ["amazon", "fba", "amazon listing"]),

    # Data Processing
    "data_entry": ("data", ["data entry", "typing", "data input"]),
    "transcription": ("data", ["transcri", "subtitle", "caption"]),
    "excel_spreadsheet": ("data", ["excel", "spreadsheet", "google sheets", "csv"]),
    "research": ("data", ["research", "market research", "competitor research", "competitive analysis"]),
    "virtual_assistant": ("data", ["virtual assistant", " va ", "admin support", "administrative"]),
    "data_analysis": ("data", ["data analy", "data visual", "tableau", "power bi", "statistics"]),

    # Translation
    "translation": ("translation", ["translat", "localiz", "interpret"]),

    # Consulting
    "coaching_tutoring": ("consulting", ["coach", "tutor", "mentor", "teach", "lesson"]),
    "business_consulting": ("consulting", ["consult", "business plan", "startup advi", "strateg"]),
    "career_advice": ("consulting", ["career", "interview prep", "job search"]),
    "financial": ("consulting", ["accounting", "bookkeep", "tax", "financ"]),
}


def load_data():
    posts = []
    with open(DATA_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                posts.append(json.loads(line))
    return posts


def classify_post(post):
    """Classify a post into service categories based on title + selftext."""
    text = (post.get("title", "") + " " + post.get("selftext", "")).lower()
    matched = []
    for subcat, (cat, keywords) in SERVICE_CATEGORIES.items():
        for kw in keywords:
            if kw in text:
                matched.append((cat, subcat))
                break
    return matched


def extract_flair_type(flair):
    """Normalize flair to supply/demand."""
    if not flair:
        return "unknown"
    flair_lower = flair.lower()
    if "hiring" in flair_lower or "task" in flair_lower:
        return "demand"
    elif "for hire" in flair_lower or "offer" in flair_lower:
        return "supply"
    return "unknown"


def extract_prices(text):
    """Extract dollar amounts from text."""
    prices = []
    # Match $XX, $XX.XX, $XX/hr, $XX per hour, etc.
    patterns = [
        r'\$\s*(\d+(?:,\d{3})*(?:\.\d{1,2})?)',
        r'(\d+(?:,\d{3})*(?:\.\d{1,2})?)\s*(?:usd|dollars?)',
    ]
    for pat in patterns:
        for m in re.finditer(pat, text.lower()):
            val = float(m.group(1).replace(",", ""))
            if 1 <= val <= 10000:  # reasonable range
                prices.append(val)
    return prices


def analyze():
    posts = load_data()
    print(f"Total posts loaded: {len(posts)}")

    # 1. Flair distribution
    flair_counts = Counter(p.get("link_flair_text") or "None" for p in posts)
    print("\n=== FLAIR DISTRIBUTION ===")
    for flair, cnt in flair_counts.most_common(20):
        print(f"  {flair}: {cnt}")

    # 2. Subreddit distribution
    sub_counts = Counter(p.get("subreddit") for p in posts)
    print("\n=== SUBREDDIT DISTRIBUTION ===")
    for sub, cnt in sub_counts.most_common():
        print(f"  r/{sub}: {cnt}")

    # 3. keyword_group distribution
    kg_counts = Counter(p.get("keyword_group") for p in posts)
    print("\n=== KEYWORD GROUP DISTRIBUTION ===")
    for kg, cnt in kg_counts.most_common():
        print(f"  {kg}: {cnt}")

    # 4. Classify posts
    subcat_posts = defaultdict(list)
    cat_posts = defaultdict(list)
    unclassified = []

    for p in posts:
        matches = classify_post(p)
        if not matches:
            unclassified.append(p)
        for cat, subcat in matches:
            subcat_posts[subcat].append(p)
            cat_posts[cat].append(p)

    print(f"\n=== CLASSIFICATION ===")
    print(f"Classified: {len(posts) - len(unclassified)} ({100*(len(posts)-len(unclassified))/len(posts):.1f}%)")
    print(f"Unclassified: {len(unclassified)} ({100*len(unclassified)/len(posts):.1f}%)")

    # 5. Category level stats
    print("\n=== CATEGORY LEVEL STATS ===")
    print(f"{'Category':<15} {'Posts':>6} {'Avg Upvotes':>12} {'Avg Comments':>13} {'Demand':>7} {'Supply':>7} {'D/S Ratio':>10}")
    for cat in sorted(cat_posts.keys(), key=lambda c: len(cat_posts[c]), reverse=True):
        ps = cat_posts[cat]
        avg_up = sum(p.get("upvotes", 0) for p in ps) / len(ps)
        avg_com = sum(p.get("comment_count", 0) for p in ps) / len(ps)
        demand = sum(1 for p in ps if extract_flair_type(p.get("link_flair_text")) == "demand")
        supply = sum(1 for p in ps if extract_flair_type(p.get("link_flair_text")) == "supply")
        ratio = f"{demand/supply:.2f}" if supply > 0 else "N/A"
        print(f"  {cat:<15} {len(ps):>6} {avg_up:>12.1f} {avg_com:>13.1f} {demand:>7} {supply:>7} {ratio:>10}")

    # 6. Subcategory level stats
    print("\n=== TOP 40 SUBCATEGORY STATS ===")
    print(f"{'Subcategory':<25} {'Cat':<13} {'Posts':>6} {'Avg Up':>7} {'Avg Cmt':>8} {'Demand':>7} {'Supply':>7} {'D/S':>6}")
    sorted_subcats = sorted(subcat_posts.keys(), key=lambda s: len(subcat_posts[s]), reverse=True)
    for subcat in sorted_subcats[:40]:
        ps = subcat_posts[subcat]
        cat = SERVICE_CATEGORIES[subcat][0]
        avg_up = sum(p.get("upvotes", 0) for p in ps) / len(ps)
        avg_com = sum(p.get("comment_count", 0) for p in ps) / len(ps)
        demand = sum(1 for p in ps if extract_flair_type(p.get("link_flair_text")) == "demand")
        supply = sum(1 for p in ps if extract_flair_type(p.get("link_flair_text")) == "supply")
        ratio = f"{demand/supply:.2f}" if supply > 0 else "N/A"
        print(f"  {subcat:<25} {cat:<13} {len(ps):>6} {avg_up:>7.1f} {avg_com:>8.1f} {demand:>7} {supply:>7} {ratio:>6}")

    # 7. Price extraction per subcategory
    print("\n=== PRICE DISTRIBUTION BY SUBCATEGORY (top 30) ===")
    print(f"{'Subcategory':<25} {'Posts w/$':>9} {'Median$':>8} {'Avg$':>8} {'Min$':>6} {'Max$':>7} {'P25':>6} {'P75':>6}")
    subcat_prices = {}
    for subcat in sorted_subcats[:30]:
        ps = subcat_posts[subcat]
        all_prices = []
        for p in ps:
            text = (p.get("title", "") + " " + p.get("selftext", "")).lower()
            prices = extract_prices(text)
            all_prices.extend(prices)
        if all_prices:
            all_prices.sort()
            n = len(all_prices)
            median = all_prices[n // 2]
            avg = sum(all_prices) / n
            p25 = all_prices[n // 4]
            p75 = all_prices[3 * n // 4]
            subcat_prices[subcat] = {"median": median, "avg": avg, "min": all_prices[0], "max": all_prices[-1], "count": n, "p25": p25, "p75": p75}
            print(f"  {subcat:<25} {n:>9} {median:>8.0f} {avg:>8.0f} {all_prices[0]:>6.0f} {all_prices[-1]:>7.0f} {p25:>6.0f} {p75:>6.0f}")
        else:
            print(f"  {subcat:<25} {'0':>9}")

    # 8. Supply/demand by subcategory (sorted by demand count)
    print("\n=== SUPPLY/DEMAND ANALYSIS (sorted by demand) ===")
    demand_sorted = sorted(sorted_subcats, key=lambda s: sum(1 for p in subcat_posts[s] if extract_flair_type(p.get("link_flair_text")) == "demand"), reverse=True)
    print(f"{'Subcategory':<25} {'Demand':>7} {'Supply':>7} {'Unknown':>8} {'D/S Ratio':>10} {'Demand%':>8}")
    for subcat in demand_sorted[:35]:
        ps = subcat_posts[subcat]
        demand = sum(1 for p in ps if extract_flair_type(p.get("link_flair_text")) == "demand")
        supply = sum(1 for p in ps if extract_flair_type(p.get("link_flair_text")) == "supply")
        unknown = len(ps) - demand - supply
        ratio = f"{demand/supply:.2f}" if supply > 0 else "N/A"
        dpct = f"{100*demand/len(ps):.1f}%"
        print(f"  {subcat:<25} {demand:>7} {supply:>7} {unknown:>8} {ratio:>10} {dpct:>8}")

    # 9. Top 50 posts by engagement (upvotes + comments)
    print("\n=== TOP 50 POSTS BY ENGAGEMENT ===")
    scored = [(p, p.get("upvotes", 0) + p.get("comment_count", 0)) for p in posts]
    scored.sort(key=lambda x: x[1], reverse=True)
    for i, (p, score) in enumerate(scored[:50]):
        flair = p.get("link_flair_text", "")
        title = p["title"][:100]
        sub = p.get("subreddit", "")
        up = p.get("upvotes", 0)
        cmt = p.get("comment_count", 0)
        print(f"  {i+1:>2}. [{flair}] (↑{up} 💬{cmt}) r/{sub}: {title}")

    # 10. Top posts by upvotes only
    print("\n=== TOP 30 POSTS BY UPVOTES ===")
    by_upvotes = sorted(posts, key=lambda p: p.get("upvotes", 0), reverse=True)
    for i, p in enumerate(by_upvotes[:30]):
        flair = p.get("link_flair_text", "")
        title = p["title"][:100]
        up = p.get("upvotes", 0)
        cmt = p.get("comment_count", 0)
        sub = p.get("subreddit", "")
        print(f"  {i+1:>2}. [{flair}] (↑{up} 💬{cmt}) r/{sub}: {title}")

    # 11. Service type engagement ranking
    print("\n=== SUBCATEGORY ENGAGEMENT RANKING ===")
    print(f"{'Subcategory':<25} {'Posts':>6} {'Total Up':>9} {'Total Cmt':>10} {'Avg Eng':>8} {'Top Post Up':>11}")
    engagement_ranked = []
    for subcat in sorted_subcats:
        ps = subcat_posts[subcat]
        total_up = sum(p.get("upvotes", 0) for p in ps)
        total_cmt = sum(p.get("comment_count", 0) for p in ps)
        avg_eng = (total_up + total_cmt) / len(ps)
        top_up = max(p.get("upvotes", 0) for p in ps)
        engagement_ranked.append((subcat, len(ps), total_up, total_cmt, avg_eng, top_up))
    engagement_ranked.sort(key=lambda x: x[4], reverse=True)
    for subcat, cnt, tup, tcmt, aeng, topup in engagement_ranked[:35]:
        print(f"  {subcat:<25} {cnt:>6} {tup:>9} {tcmt:>10} {aeng:>8.1f} {topup:>11}")

    # 12. Hourly rate analysis
    print("\n=== HOURLY RATE ANALYSIS ===")
    hourly_pattern = re.compile(r'\$\s*(\d+(?:\.\d{1,2})?)\s*/?\s*(?:hr|hour|h\b)', re.IGNORECASE)
    subcat_hourly = defaultdict(list)
    for subcat in sorted_subcats:
        for p in subcat_posts[subcat]:
            text = (p.get("title", "") + " " + p.get("selftext", ""))
            for m in hourly_pattern.finditer(text):
                val = float(m.group(1))
                if 3 <= val <= 500:
                    subcat_hourly[subcat].append(val)
    print(f"{'Subcategory':<25} {'N':>5} {'Median$/hr':>10} {'Avg$/hr':>8} {'Min':>5} {'Max':>5}")
    for subcat in sorted(subcat_hourly.keys(), key=lambda s: len(subcat_hourly[s]), reverse=True):
        rates = sorted(subcat_hourly[subcat])
        n = len(rates)
        if n >= 3:
            median = rates[n // 2]
            avg = sum(rates) / n
            print(f"  {subcat:<25} {n:>5} {median:>10.0f} {avg:>8.0f} {rates[0]:>5.0f} {rates[-1]:>5.0f}")

    # 13. High-value demand posts (Hiring/Task with most comments - proxy for interest)
    print("\n=== TOP 30 DEMAND POSTS (Hiring/Task) BY COMMENTS ===")
    demand_posts = [p for p in posts if extract_flair_type(p.get("link_flair_text")) == "demand"]
    demand_posts.sort(key=lambda p: p.get("comment_count", 0), reverse=True)
    for i, p in enumerate(demand_posts[:30]):
        title = p["title"][:95]
        up = p.get("upvotes", 0)
        cmt = p.get("comment_count", 0)
        sub = p.get("subreddit", "")
        print(f"  {i+1:>2}. (↑{up} 💬{cmt}) r/{sub}: {title}")

    # 14. Keyword group × flair cross-tab
    print("\n=== KEYWORD GROUP × FLAIR CROSS-TAB ===")
    kg_flair = defaultdict(Counter)
    for p in posts:
        kg = p.get("keyword_group", "unknown")
        ft = extract_flair_type(p.get("link_flair_text"))
        kg_flair[kg][ft] += 1
    print(f"{'Keyword Group':<22} {'Demand':>7} {'Supply':>7} {'Unknown':>8} {'Total':>6} {'D/S':>6}")
    for kg in sorted(kg_flair.keys(), key=lambda k: sum(kg_flair[k].values()), reverse=True):
        d = kg_flair[kg]["demand"]
        s = kg_flair[kg]["supply"]
        u = kg_flair[kg]["unknown"]
        t = d + s + u
        ratio = f"{d/s:.2f}" if s > 0 else "N/A"
        print(f"  {kg:<22} {d:>7} {s:>7} {u:>8} {t:>6} {ratio:>6}")

    # 15. Output sample unclassified titles for inspection
    print(f"\n=== SAMPLE UNCLASSIFIED TITLES (first 30) ===")
    for p in unclassified[:30]:
        print(f"  [{p.get('link_flair_text','')}] {p['title'][:100]}")

    # Summary JSON for LLM analysis
    summary = {
        "total_posts": len(posts),
        "classified_pct": round(100 * (len(posts) - len(unclassified)) / len(posts), 1),
        "category_stats": {},
        "subcategory_stats": {},
    }
    for cat in sorted(cat_posts.keys(), key=lambda c: len(cat_posts[c]), reverse=True):
        ps = cat_posts[cat]
        demand = sum(1 for p in ps if extract_flair_type(p.get("link_flair_text")) == "demand")
        supply = sum(1 for p in ps if extract_flair_type(p.get("link_flair_text")) == "supply")
        summary["category_stats"][cat] = {
            "count": len(ps),
            "demand": demand,
            "supply": supply,
            "avg_upvotes": round(sum(p.get("upvotes", 0) for p in ps) / len(ps), 1),
            "avg_comments": round(sum(p.get("comment_count", 0) for p in ps) / len(ps), 1),
        }
    for subcat in sorted_subcats[:35]:
        ps = subcat_posts[subcat]
        cat = SERVICE_CATEGORIES[subcat][0]
        demand = sum(1 for p in ps if extract_flair_type(p.get("link_flair_text")) == "demand")
        supply = sum(1 for p in ps if extract_flair_type(p.get("link_flair_text")) == "supply")
        prices_data = subcat_prices.get(subcat, {})
        summary["subcategory_stats"][subcat] = {
            "category": cat,
            "count": len(ps),
            "demand": demand,
            "supply": supply,
            "ds_ratio": round(demand / supply, 2) if supply > 0 else None,
            "avg_upvotes": round(sum(p.get("upvotes", 0) for p in ps) / len(ps), 1),
            "avg_comments": round(sum(p.get("comment_count", 0) for p in ps) / len(ps), 1),
            "price_median": prices_data.get("median"),
            "price_avg": round(prices_data.get("avg", 0), 1) if prices_data.get("avg") else None,
            "price_count": prices_data.get("count", 0),
        }

    with open("/Users/huanghaibin/Workspace/reddit_research/data/raw/reddit_services_analysis_summary.json", "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print("\n[Summary JSON saved to reddit_services_analysis_summary.json]")


if __name__ == "__main__":
    analyze()
