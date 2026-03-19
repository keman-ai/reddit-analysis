#!/usr/bin/env python3
"""Stage 4: Aggregate statistics, score categories, generate selection report."""
import json
import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (
    XHS_RAW_DIR, XHS_ANALYZED_DIR, REPORTS_DIR,
    SCORING_WEIGHTS, SEED_CATEGORIES, XHS_TO_GOOFISH_MAP,
    BASE_DIR,
)

INPUT_PATH = f'{XHS_RAW_DIR}/posts_labeled.jsonl'
MAPPING_PATH = f'{XHS_ANALYZED_DIR}/category_mapping.json'
STATS_PATH = f'{XHS_ANALYZED_DIR}/category_stats.json'
RANKING_PATH = f'{XHS_ANALYZED_DIR}/category_ranking.json'
REPORT_PATH = f'{REPORTS_DIR}/xiaohongshu_agent_selection_report.md'
GOOFISH_PATH = f'{BASE_DIR}/data/raw/goofish/services_deduped.jsonl'


def normalize_log(value, min_val, max_val, target_min=1, target_max=5):
    """Normalize value to target range using log1p scaling."""
    if max_val <= min_val:
        return (target_min + target_max) / 2
    log_val = math.log1p(value)
    log_min = math.log1p(min_val)
    log_max = math.log1p(max_val)
    if log_max <= log_min:
        return (target_min + target_max) / 2
    normalized = (log_val - log_min) / (log_max - log_min)
    return target_min + normalized * (target_max - target_min)


def build_category_mapping(raw_categories):
    """Map raw category names to seed categories or themselves."""
    mapping = {}
    for cat in raw_categories:
        matched = None
        for seed in SEED_CATEGORIES:
            if seed in cat or cat in seed:
                matched = seed
                break
        mapping[cat] = matched if matched else cat
    return mapping


def load_labeled_posts():
    """Load and filter posts_labeled.jsonl."""
    posts = []
    with open(INPUT_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                post = json.loads(line)
            except json.JSONDecodeError:
                continue
            # Filter out not_service and low confidence
            if post.get('service_category') == 'not_service':
                continue
            if post.get('confidence', 0) < 3:
                continue
            posts.append(post)
    return posts


def compute_category_stats(posts, category_mapping):
    """Group by normalized category and compute per-category stats."""
    groups = defaultdict(list)
    for post in posts:
        raw_cat = post.get('service_category', '')
        norm_cat = category_mapping.get(raw_cat, raw_cat)
        groups[norm_cat].append(post)

    stats = {}
    for cat, cat_posts in groups.items():
        n = len(cat_posts)
        engagements = [p.get('engagement', 0) or 0 for p in cat_posts]
        std_scores = [p.get('standardization_score', 3) or 3 for p in cat_posts]
        ai_scores = [p.get('ai_replaceability', 3) or 3 for p in cat_posts]
        digital_flags = [1 if p.get('digital_delivery') else 0 for p in cat_posts]
        demand_types = [p.get('demand_type', '') for p in cat_posts]

        avg_engagement = sum(engagements) / n if n > 0 else 0
        avg_standardization = sum(std_scores) / n if n > 0 else 3
        avg_ai_replaceability = sum(ai_scores) / n if n > 0 else 3
        digital_ratio = sum(digital_flags) / n if n > 0 else 0

        demand_counts = defaultdict(int)
        for dt in demand_types:
            demand_counts[dt] += 1

        # buying/selling posts indicate strong demand heat
        buying_selling = demand_counts.get('buying', 0) + demand_counts.get('selling', 0)
        demand_heat_raw = buying_selling

        # Top 3 posts by engagement as examples
        top_posts = sorted(cat_posts, key=lambda p: p.get('engagement', 0) or 0, reverse=True)[:3]
        examples = []
        for p in top_posts:
            examples.append({
                'title': p.get('title', ''),
                'engagement': p.get('engagement', 0),
                'demand_type': p.get('demand_type', ''),
                'note_url': p.get('note_url', ''),
            })

        stats[cat] = {
            'count': n,
            'avg_engagement': round(avg_engagement, 2),
            'avg_standardization': round(avg_standardization, 2),
            'avg_ai_replaceability': round(avg_ai_replaceability, 2),
            'digital_ratio': round(digital_ratio, 2),
            'demand_heat_raw': demand_heat_raw,
            'demand_counts': dict(demand_counts),
            'total_engagement': sum(engagements),
            'examples': examples,
        }
    return stats


def score_categories(stats):
    """Apply scoring formula with log normalization."""
    if not stats:
        return []

    # Compute global ranges for log normalization
    all_demand_heat = [v['demand_heat_raw'] for v in stats.values()]
    all_engagement = [v['avg_engagement'] for v in stats.values()]
    min_dh, max_dh = min(all_demand_heat), max(all_demand_heat)
    min_eng, max_eng = min(all_engagement), max(all_engagement)

    ranking = []
    for cat, s in stats.items():
        demand_heat_norm = normalize_log(s['demand_heat_raw'], min_dh, max_dh)
        engagement_norm = normalize_log(s['avg_engagement'], min_eng, max_eng)
        digital_ratio_scaled = s['digital_ratio'] * 5  # 0-1 → 0-5

        score = (
            s['avg_ai_replaceability'] * SCORING_WEIGHTS['ai_replaceability'] +
            s['avg_standardization'] * SCORING_WEIGHTS['standardization'] +
            demand_heat_norm * SCORING_WEIGHTS['demand_heat'] +
            engagement_norm * SCORING_WEIGHTS['engagement'] +
            digital_ratio_scaled * SCORING_WEIGHTS['digital_ratio']
        )

        ranking.append({
            'category': cat,
            'score': round(score, 4),
            'count': s['count'],
            'avg_engagement': s['avg_engagement'],
            'avg_standardization': s['avg_standardization'],
            'avg_ai_replaceability': s['avg_ai_replaceability'],
            'digital_ratio': s['digital_ratio'],
            'demand_heat_raw': s['demand_heat_raw'],
            'demand_heat_norm': round(demand_heat_norm, 4),
            'engagement_norm': round(engagement_norm, 4),
            'digital_ratio_scaled': round(digital_ratio_scaled, 4),
            'demand_counts': s['demand_counts'],
            'examples': s['examples'],
        })

    ranking.sort(key=lambda x: x['score'], reverse=True)
    return ranking


def load_goofish_data():
    """Load Goofish services data."""
    records = []
    if not os.path.exists(GOOFISH_PATH):
        print(f"Warning: Goofish data not found at {GOOFISH_PATH}")
        return records
    with open(GOOFISH_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def compute_goofish_cross_validation(goofish_records):
    """Compute per goofish keyword_group stats."""
    groups = defaultdict(list)
    for rec in goofish_records:
        kg = rec.get('keyword_group', 'unknown')
        groups[kg].append(rec)

    # Reverse XHS_TO_GOOFISH_MAP: goofish_group -> list of XHS categories
    goofish_to_xhs = {}
    for gf_group, xhs_cats in XHS_TO_GOOFISH_MAP.items():
        goofish_to_xhs[gf_group] = xhs_cats

    result = {}
    for kg, recs in groups.items():
        prices = []
        for r in recs:
            try:
                p = float(r.get('price', 0) or 0)
                if p > 0:
                    prices.append(p)
            except (ValueError, TypeError):
                pass

        want_counts = []
        for r in recs:
            try:
                wc = int(r.get('wantCount', 0) or 0)
                want_counts.append(wc)
            except (ValueError, TypeError):
                want_counts.append(0)

        prices.sort()
        median_price = prices[len(prices) // 2] if prices else 0

        result[kg] = {
            'listings_count': len(recs),
            'median_price': round(median_price, 2),
            'total_wantCount': sum(want_counts),
            'avg_wantCount': round(sum(want_counts) / len(recs), 2) if recs else 0,
            'xhs_categories': goofish_to_xhs.get(kg, []),
        }
    return result


def generate_report(ranking, stats, goofish_cross, total_input, total_service, total_filtered):
    """Generate Markdown report in Chinese."""
    top20 = ranking[:20]
    top10 = ranking[:10]

    lines = []
    lines.append("# 小红书 AI Agent 选品分析报告")
    lines.append("")
    lines.append(f"> 生成时间：2026-03-19  |  数据来源：小红书求助/有偿帖子 + 闲鱼服务列表交叉验证")
    lines.append("")

    # 概览
    lines.append("## 一、数据概览")
    lines.append("")
    lines.append(f"| 指标 | 数值 |")
    lines.append(f"|------|------|")
    lines.append(f"| 原始标注记录数 | {total_input:,} |")
    lines.append(f"| 服务类帖子数（排除 not_service） | {total_service:,} |")
    lines.append(f"| 置信度≥3 有效记录数 | {total_filtered:,} |")
    lines.append(f"| 识别出的服务品类数 | {len(stats):,} |")
    lines.append(f"| 参与排名品类数 | {len(ranking):,} |")
    lines.append("")

    # Top 20 排名表
    lines.append("## 二、Top 20 品类综合评分排名")
    lines.append("")
    lines.append("评分公式：`score = AI替代性×0.35 + 标准化程度×0.25 + 需求热度×0.20 + 互动热度×0.10 + 数字化率×0.10`")
    lines.append("")
    lines.append("| 排名 | 品类 | 综合评分 | 帖子数 | 平均互动 | AI替代性 | 标准化 | 数字化率 |")
    lines.append("|------|------|----------|--------|----------|----------|--------|----------|")
    for i, item in enumerate(top20, 1):
        lines.append(
            f"| {i} | {item['category']} | {item['score']:.4f} | "
            f"{item['count']} | {item['avg_engagement']:.0f} | "
            f"{item['avg_ai_replaceability']:.2f} | {item['avg_standardization']:.2f} | "
            f"{item['digital_ratio']:.0%} |"
        )
    lines.append("")

    # 品类详情
    lines.append("## 三、Top 20 品类详情")
    lines.append("")
    for i, item in enumerate(top20, 1):
        cat = item['category']
        lines.append(f"### {i}. {cat}")
        lines.append("")
        dc = item.get('demand_counts', {})
        demand_breakdown = "、".join([f"{k}:{v}" for k, v in sorted(dc.items(), key=lambda x: -x[1])])
        lines.append(f"- **帖子数**：{item['count']}  **综合评分**：{item['score']:.4f}")
        lines.append(f"- **需求分布**：{demand_breakdown or '无'}")
        lines.append(f"- **AI替代性**：{item['avg_ai_replaceability']:.2f}/5  **标准化**：{item['avg_standardization']:.2f}/5  **数字化率**：{item['digital_ratio']:.0%}")
        lines.append("")
        if item.get('examples'):
            lines.append("  **典型帖子（按互动量排序）：**")
            for ex in item['examples']:
                title_short = ex['title'][:40] + '...' if len(ex['title']) > 40 else ex['title']
                lines.append(f"  - [{title_short}]({ex['note_url']}) — 互动：{ex['engagement']}  类型：{ex['demand_type']}")
        lines.append("")

    # 闲鱼交叉验证
    lines.append("## 四、闲鱼交叉验证")
    lines.append("")
    lines.append("将闲鱼服务品类与小红书需求品类进行对比，验证市场供需匹配度。")
    lines.append("")
    lines.append("| 闲鱼品类 | 商品数 | 中位价格(¥) | 总想要数 | 对应XHS品类 |")
    lines.append("|----------|--------|------------|----------|------------|")

    for kg, gf in sorted(goofish_cross.items(), key=lambda x: -x[1]['listings_count']):
        xhs_cats = "、".join(gf['xhs_categories']) if gf['xhs_categories'] else "—"
        lines.append(
            f"| {kg} | {gf['listings_count']:,} | {gf['median_price']:.0f} | "
            f"{gf['total_wantCount']:,} | {xhs_cats} |"
        )
    lines.append("")

    # 第一批选品推荐 Top 10
    lines.append("## 五、第一批 Agent 选品推荐（Top 10）")
    lines.append("")
    lines.append("综合小红书需求热度、闲鱼市场验证、AI替代可行性三维度，推荐第一批重点布局的服务品类：")
    lines.append("")

    # Build goofish lookup by XHS category
    xhs_to_gf_stats = {}
    for gf_group, xhs_cats in XHS_TO_GOOFISH_MAP.items():
        gf_stat = goofish_cross.get(gf_group, {})
        for xcat in xhs_cats:
            xhs_to_gf_stats[xcat] = {
                'gf_group': gf_group,
                'listings_count': gf_stat.get('listings_count', 0),
                'median_price': gf_stat.get('median_price', 0),
                'total_wantCount': gf_stat.get('total_wantCount', 0),
            }

    for i, item in enumerate(top10, 1):
        cat = item['category']
        gf = xhs_to_gf_stats.get(cat, {})
        lines.append(f"### Top {i}：{cat}")
        lines.append("")

        reasons = []
        if item['avg_ai_replaceability'] >= 4:
            reasons.append(f"AI替代性高（{item['avg_ai_replaceability']:.1f}/5），适合AI Agent自动化交付")
        if item['avg_standardization'] >= 4:
            reasons.append(f"标准化程度高（{item['avg_standardization']:.1f}/5），易于产品化")
        if item['digital_ratio'] >= 0.8:
            reasons.append(f"全数字化交付（{item['digital_ratio']:.0%}），无地域限制")
        if item['count'] >= 50:
            reasons.append(f"小红书需求旺盛（{item['count']}条帖子）")
        if gf.get('listings_count', 0) > 0:
            reasons.append(f"闲鱼验证：{gf['listings_count']}个商品，中位价¥{gf['median_price']:.0f}，想要{gf['total_wantCount']}次")
        if not reasons:
            reasons.append(f"综合评分领先（{item['score']:.4f}），需求与交付能力均衡")

        for r in reasons:
            lines.append(f"- {r}")
        lines.append(f"- **综合评分**：{item['score']:.4f}  |  **帖子数**：{item['count']}  |  **平均互动**：{item['avg_engagement']:.0f}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*报告由 AI Agent 自动生成，基于 Stage 3 标注数据和闲鱼市场数据综合分析。*")

    return "\n".join(lines)


def main():
    os.makedirs(XHS_ANALYZED_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)

    print("=== Stage 4: 统计聚合、评分与报告生成 ===")
    print(f"读取标注数据: {INPUT_PATH}")

    # 1. Load posts
    all_posts = []
    total_input = 0
    total_service = 0
    with open(INPUT_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                post = json.loads(line)
            except json.JSONDecodeError:
                continue
            total_input += 1
            if post.get('service_category') != 'not_service':
                total_service += 1

    posts = load_labeled_posts()
    total_filtered = len(posts)
    print(f"原始记录: {total_input}, 服务类: {total_service}, 有效(置信度≥3): {total_filtered}")

    # 2. Build category mapping
    raw_cats = set(p.get('service_category', '') for p in posts)
    category_mapping = build_category_mapping(raw_cats)

    with open(MAPPING_PATH, 'w', encoding='utf-8') as f:
        json.dump(category_mapping, f, ensure_ascii=False, indent=2)
    print(f"品类映射保存至: {MAPPING_PATH}")

    # 3. Compute stats
    stats = compute_category_stats(posts, category_mapping)
    print(f"品类数: {len(stats)}")

    with open(STATS_PATH, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"品类统计保存至: {STATS_PATH}")

    # 4. Score and rank
    ranking = score_categories(stats)

    with open(RANKING_PATH, 'w', encoding='utf-8') as f:
        json.dump(ranking, f, ensure_ascii=False, indent=2)
    print(f"品类排名保存至: {RANKING_PATH}")

    # 5. Goofish cross-validation
    print(f"加载闲鱼数据: {GOOFISH_PATH}")
    goofish_records = load_goofish_data()
    print(f"闲鱼记录数: {len(goofish_records)}")
    goofish_cross = compute_goofish_cross_validation(goofish_records)

    # 6. Generate report
    report = generate_report(ranking, stats, goofish_cross, total_input, total_service, total_filtered)
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"报告生成至: {REPORT_PATH}")

    # Print top 10
    print("\n=== Top 10 品类排名 ===")
    for i, item in enumerate(ranking[:10], 1):
        print(f"{i:2d}. {item['category']:20s}  score={item['score']:.4f}  count={item['count']:4d}  "
              f"ai={item['avg_ai_replaceability']:.2f}  std={item['avg_standardization']:.2f}  "
              f"digital={item['digital_ratio']:.0%}")

    print("\n完成！")


if __name__ == '__main__':
    main()
