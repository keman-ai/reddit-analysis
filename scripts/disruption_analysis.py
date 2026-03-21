#!/usr/bin/env python3
"""
Christensen Disruption Analysis on 92,858 Reddit posts.
Quantifies low-end and new-market disruption signals for AI Agent platform selection.
"""

import json, re, sys
from collections import Counter, defaultdict

DATA_FILE = "/Users/huanghaibin/Workspace/reddit_research/data/raw/reddit_disruption_deduped.jsonl"

# ── Service type extraction patterns ──
SERVICE_PATTERNS = {
    "法律服务": r"\b(lawyer|attorney|legal\s+(?:advice|help|service|counsel|fee|cost)|paralegal|law\s+firm)\b",
    "心理咨询": r"\b(therapist|therapy|counseling|counselor|psychologist|psychiatrist|mental\s+health\s+(?:professional|provider))\b",
    "财税服务": r"\b(accountant|CPA|tax\s+(?:professional|preparer|advisor|preparation|filing)|bookkeeper|bookkeeping)\b",
    "理财顾问": r"\b(financial\s+(?:advisor|planner|adviser|planning)|wealth\s+manage|investment\s+advi)\b",
    "家教辅导": r"\b(tutor|tutoring|private\s+lesson|test\s+prep|SAT\s+prep|ACT\s+prep|college\s+(?:counselor|consultant|admissions))\b",
    "医疗健康": r"\b(doctor|physician|medical\s+(?:bill|cost|fee|expense)|healthcare\s+cost|hospital\s+bill|copay|deductible|out.of.pocket)\b",
    "牙科服务": r"\b(dentist|dental|orthodont|braces|root\s+canal|crown|filling)\b",
    "家装维修": r"\b(contractor|plumber|plumbing|electrician|handyman|home\s+repair|renovation|remodel|HVAC)\b",
    "设计服务": r"\b(graphic\s+design|web\s+design|UI\s*\/?\s*UX|logo\s+design|brand\s+design|interior\s+design|designer)\b",
    "汽车维修": r"\b(mechanic|auto\s+repair|car\s+repair|body\s+shop|oil\s+change|brake|transmission\s+repair)\b",
    "房地产中介": r"\b(real\s*estate\s+agent|realtor|buyer'?s?\s+agent|listing\s+agent|real\s*estate\s+commission|closing\s+cost)\b",
    "保险服务": r"\b(insurance\s+(?:agent|broker|premium|cost|rate)|health\s+insurance|car\s+insurance|home\s*owner|life\s+insurance)\b",
    "搬家服务": r"\b(moving\s+company|mover|moving\s+cost|relocation\s+(?:service|cost))\b",
    "宠物护理": r"\b(vet(?:erinarian)?|vet\s+(?:bill|cost|fee)|pet\s+(?:insurance|care|sitter)|dog\s+(?:walker|training|trainer)|grooming)\b",
    "职业教练": r"\b(career\s+coach|resume\s+(?:writer|writing|service)|job\s+coach|interview\s+(?:coach|prep)|linkedin\s+(?:profile|optimization))\b",
    "婚礼服务": r"\b(wedding\s+(?:planner|photographer|venue|cost|budget|expensive)|marriage\s+(?:counselor|therapist))\b",
    "摄影服务": r"\b(photographer|photography|headshot|portrait\s+photo|photo\s+(?:session|shoot))\b",
    "清洁服务": r"\b(cleaning\s+(?:service|company|cost)|house\s*clean|maid\s+service|janitorial)\b",
    "儿童托管": r"\b(daycare|childcare|child\s+care|nanny|babysitter|preschool\s+cost|after.school\s+(?:care|program))\b",
    "健身训练": r"\b(personal\s+trainer|gym\s+(?:membership|cost)|fitness\s+(?:coach|class)|yoga\s+(?:class|instructor)|pilates)\b",
    "营养咨询": r"\b(dietitian|nutritionist|meal\s+plan|nutrition\s+(?:coach|counseling|advice))\b",
    "移民服务": r"\b(immigration\s+(?:lawyer|attorney|consultant)|visa\s+(?:application|process|lawyer)|green\s+card|citizenship\s+application)\b",
    "写作编辑": r"\b(copywriter|copywriting|editor|editing\s+service|proofreading|ghost\s*writ|content\s+writer)\b",
    "翻译服务": r"\b(translat(?:or|ion)|interpret(?:er|ing)|language\s+service)\b",
    "IT支持": r"\b(IT\s+(?:support|help|service|consultant)|tech\s+support|computer\s+repair|managed\s+(?:IT|service))\b",
    "驾校培训": r"\b(driving\s+(?:school|lesson|instructor|test)|learn\s+to\s+drive)\b",
    "丧葬服务": r"\b(funeral\s+(?:home|cost|service|expense)|burial\s+cost|cremation|casket)\b",
    "物业管理": r"\b(property\s+manag|HOA|homeowner.?s?\s+association|landlord\s+(?:service|fee))\b",
}

# ── Price extraction pattern ──
PRICE_RE = re.compile(r'\$\s*([\d,]+(?:\.\d{1,2})?)\s*(?:/\s*(hr|hour|session|visit|month|year|consult|appointment))?', re.IGNORECASE)

# ── Load data ──
print("Loading data...", file=sys.stderr)
posts = []
with open(DATA_FILE) as f:
    for line in f:
        posts.append(json.loads(line))
print(f"Loaded {len(posts)} posts", file=sys.stderr)

# ── Compile patterns ──
compiled_patterns = {name: re.compile(pat, re.IGNORECASE) for name, pat in SERVICE_PATTERNS.items()}

# ── Analysis 1: Service type extraction by disruption signal ──
print("Analysis 1: Service type extraction...", file=sys.stderr)

LOW_END_GROUPS = {"too_expensive", "cheaper_alternative", "overserved"}
NEW_MARKET_GROUPS = {"non_consumer", "access_barrier", "diy_struggle"}
PROF_VS_DIY = {"professional_vs_diy"}

service_low_end = defaultdict(list)
service_new_market = defaultdict(list)
service_prof_diy = defaultdict(list)
service_all = defaultdict(list)

for p in posts:
    text = (p.get("title", "") + " " + p.get("selftext", "")).lower()
    kg = p.get("keyword_group", "")
    for svc_name, pat in compiled_patterns.items():
        if pat.search(text):
            service_all[svc_name].append(p)
            if kg in LOW_END_GROUPS:
                service_low_end[svc_name].append(p)
            if kg in NEW_MARKET_GROUPS:
                service_new_market[svc_name].append(p)
            if kg in PROF_VS_DIY:
                service_prof_diy[svc_name].append(p)

print("\n=== LOW-END DISRUPTION SIGNALS (too_expensive + cheaper_alternative + overserved) ===")
low_end_sorted = sorted(service_low_end.items(), key=lambda x: -len(x[1]))
for svc, ps in low_end_sorted:
    avg_up = sum(p["upvotes"] for p in ps) / len(ps) if ps else 0
    print(f"  {svc}: {len(ps)} posts, avg upvotes {avg_up:.0f}")

print("\n=== NEW-MARKET DISRUPTION SIGNALS (non_consumer + access_barrier + diy_struggle) ===")
new_market_sorted = sorted(service_new_market.items(), key=lambda x: -len(x[1]))
for svc, ps in new_market_sorted:
    avg_up = sum(p["upvotes"] for p in ps) / len(ps) if ps else 0
    print(f"  {svc}: {len(ps)} posts, avg upvotes {avg_up:.0f}")

print("\n=== PROFESSIONAL vs DIY (4,213 posts) ===")
prof_diy_sorted = sorted(service_prof_diy.items(), key=lambda x: -len(x[1]))
for svc, ps in prof_diy_sorted:
    avg_up = sum(p["upvotes"] for p in ps) / len(ps) if ps else 0
    print(f"  {svc}: {len(ps)} posts, avg upvotes {avg_up:.0f}")

# ── Analysis 2: Price pain points ──
print("\n=== PRICE PAIN POINTS ===", file=sys.stderr)
price_mentions = defaultdict(list)  # service -> [(amount, unit, post)]

for p in posts:
    kg = p.get("keyword_group", "")
    if kg not in LOW_END_GROUPS:
        continue
    text = p.get("selftext", "") + " " + p.get("title", "")
    for svc_name, pat in compiled_patterns.items():
        if pat.search(text.lower()):
            for m in PRICE_RE.finditer(text):
                amount_str = m.group(1).replace(",", "")
                try:
                    amount = float(amount_str)
                except ValueError:
                    continue
                unit = m.group(2) or ""
                if 1 <= amount <= 50000:  # reasonable range
                    price_mentions[svc_name].append((amount, unit.lower() if unit else "unspecified", p))

print("\n=== PRICE PAIN POINTS (from low-end disruption posts) ===")
for svc in sorted(price_mentions.keys(), key=lambda x: -len(price_mentions[x])):
    entries = price_mentions[svc]
    amounts = [e[0] for e in entries]
    if not amounts:
        continue
    # Group by unit
    unit_amounts = defaultdict(list)
    for amt, unit, _ in entries:
        unit_amounts[unit].append(amt)

    print(f"\n  {svc} ({len(entries)} price mentions):")
    for unit, amts in sorted(unit_amounts.items(), key=lambda x: -len(x[1])):
        amts_sorted = sorted(amts)
        median = amts_sorted[len(amts_sorted)//2]
        print(f"    /{unit}: median=${median:.0f}, range=${amts_sorted[0]:.0f}-${amts_sorted[-1]:.0f}, n={len(amts)}")

# ── Analysis 3: Top 100 by upvotes ──
print("\n=== TOP 100 POSTS BY UPVOTES ===")
top100 = sorted(posts, key=lambda x: -x.get("upvotes", 0))[:100]
for i, p in enumerate(top100[:50]):  # print top 50
    print(f"  {i+1}. [{p['upvotes']}↑] r/{p['subreddit']} | {p['keyword_group']} | {p['title'][:100]}")

# ── Analysis 4: Disruption Matrix ──
print("\n=== DISRUPTION MATRIX ===")
all_services = set(list(service_low_end.keys()) + list(service_new_market.keys()))
matrix_data = []
for svc in all_services:
    le_count = len(service_low_end.get(svc, []))
    nm_count = len(service_new_market.get(svc, []))
    pd_count = len(service_prof_diy.get(svc, []))
    total = len(service_all.get(svc, []))
    le_avg_up = sum(p["upvotes"] for p in service_low_end.get(svc, [])) / max(le_count, 1)
    nm_avg_up = sum(p["upvotes"] for p in service_new_market.get(svc, [])) / max(nm_count, 1)
    matrix_data.append({
        "service": svc,
        "low_end_count": le_count,
        "new_market_count": nm_count,
        "prof_diy_count": pd_count,
        "total": total,
        "le_avg_upvotes": le_avg_up,
        "nm_avg_upvotes": nm_avg_up,
        "combined_score": le_count + nm_count,
    })

matrix_data.sort(key=lambda x: -x["combined_score"])

# Determine thresholds for quadrant placement
le_counts = [m["low_end_count"] for m in matrix_data if m["low_end_count"] > 0]
nm_counts = [m["new_market_count"] for m in matrix_data if m["new_market_count"] > 0]
le_median = sorted(le_counts)[len(le_counts)//2] if le_counts else 0
nm_median = sorted(nm_counts)[len(nm_counts)//2] if nm_counts else 0

print(f"\nMedian thresholds: low-end={le_median}, new-market={nm_median}")
print(f"\n{'Service':<16} {'LowEnd':>8} {'NewMkt':>8} {'ProfDIY':>8} {'Total':>8} {'Quadrant':<20}")
print("-" * 80)
for m in matrix_data:
    if m["low_end_count"] >= le_median and m["new_market_count"] >= nm_median:
        quad = "DUAL DISRUPTION"
    elif m["low_end_count"] >= le_median:
        quad = "Low-end"
    elif m["new_market_count"] >= nm_median:
        quad = "New-market"
    else:
        quad = "Non-disruption"
    m["quadrant"] = quad
    print(f"  {m['service']:<16} {m['low_end_count']:>8} {m['new_market_count']:>8} {m['prof_diy_count']:>8} {m['total']:>8} {quad:<20}")

# ── Analysis 5: Sample posts for key services ──
print("\n=== SAMPLE HIGH-UPVOTE POSTS FOR KEY SERVICES ===")
key_services = [m["service"] for m in matrix_data[:12]]
for svc in key_services:
    all_p = service_all.get(svc, [])
    top_posts = sorted(all_p, key=lambda x: -x.get("upvotes", 0))[:5]
    print(f"\n--- {svc} (top 5 posts) ---")
    for p in top_posts:
        print(f"  [{p['upvotes']}↑] [{p['keyword_group']}] {p['title'][:120]}")
        if p.get("selftext"):
            print(f"    {p['selftext'][:200]}")

# ── Analysis 6: Subreddit distribution for key services ──
print("\n=== SUBREDDIT DISTRIBUTION FOR TOP SERVICES ===")
for svc in key_services[:8]:
    sub_counter = Counter(p["subreddit"] for p in service_all.get(svc, []))
    print(f"\n  {svc}:")
    for sub, cnt in sub_counter.most_common(5):
        print(f"    r/{sub}: {cnt}")

# ── Save matrix data as JSON for report generation ──
output = {
    "matrix": matrix_data,
    "price_summary": {},
    "top100_titles": [(p["upvotes"], p["subreddit"], p["keyword_group"], p["title"]) for p in top100],
}

for svc in price_mentions:
    entries = price_mentions[svc]
    amounts = [e[0] for e in entries]
    output["price_summary"][svc] = {
        "count": len(entries),
        "median": sorted(amounts)[len(amounts)//2] if amounts else 0,
        "min": min(amounts) if amounts else 0,
        "max": max(amounts) if amounts else 0,
        "sample_units": dict(Counter(e[1] for e in entries).most_common(5)),
    }

# Save sample posts for report
output["sample_posts"] = {}
for svc in key_services:
    all_p = service_all.get(svc, [])
    top_posts = sorted(all_p, key=lambda x: -x.get("upvotes", 0))[:8]
    output["sample_posts"][svc] = [{
        "title": p["title"],
        "upvotes": p["upvotes"],
        "subreddit": p["subreddit"],
        "keyword_group": p["keyword_group"],
        "selftext_preview": (p.get("selftext", "") or "")[:300],
        "url": p.get("url", ""),
    } for p in top_posts]

with open("/Users/huanghaibin/Workspace/reddit_research/data/raw/disruption_analysis_results.json", "w") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("\n\nAnalysis complete. Results saved.", file=sys.stderr)
