#!/usr/bin/env python3
"""Stage 3: Hybrid labeling — rule-based for clear matches, file-based for LLM review.

This version uses keyword rules to auto-label records where the category is clear,
and writes ambiguous records to a separate file for LLM batch review via subagents.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import XHS_RAW_DIR, SEED_CATEGORIES

INPUT_PATH = f'{XHS_RAW_DIR}/posts_filtered.jsonl'
OUTPUT_PATH = f'{XHS_RAW_DIR}/posts_labeled.jsonl'
AMBIGUOUS_PATH = f'{XHS_RAW_DIR}/posts_ambiguous.jsonl'
NEW_CATS_PATH = f'{XHS_RAW_DIR}/new_categories.json'
STATS_PATH = f'{XHS_RAW_DIR}/labeling_stats.json'

# Category detection rules: keyword patterns -> (category, standardization, digital, ai_replaceability)
CATEGORY_RULES = [
    # Document/Writing - high standardization, high AI replaceability
    (['PPT', 'ppt', '幻灯片', 'PPT制作', 'PPT代做'], 'PPT制作', 4, True, 5),
    (['简历', '求职简历', '简历优化', '简历代写'], '简历优化', 4, True, 5),
    (['论文', '毕业论文', '论文润色', '论文降重', '查重'], '论文润色', 3, True, 4),
    (['文案', '文案代写', '种草文案', '营销文案', '小红书文案', '朋友圈文案'], '文案撰写', 4, True, 5),
    (['翻译', '英译中', '中译英', '日语翻译', '韩语翻译', '翻译代做'], '翻译', 4, True, 4),
    (['公文', '公文写作', '工作总结', '述职报告', '汇报材料'], '公文写作', 4, True, 5),
    (['报告', '分析报告', '调研报告', '可行性报告'], '报告撰写', 3, True, 4),

    # Design - moderate standardization, moderate-high AI replaceability
    (['logo', 'Logo', 'LOGO', '商标设计'], 'Logo设计', 3, True, 4),
    (['海报', '海报设计', '活动海报', '宣传海报'], '海报设计', 3, True, 4),
    (['头像', '头像设计', '头像定制', '卡通头像', '情侣头像'], '头像制作', 4, True, 5),
    (['封面', '封面设计', '公众号封面', '小红书封面'], '封面设计', 4, True, 5),
    (['P图', 'p图', '修图', '精修', '证件照', '照片修复', '抠图'], '修图/P图', 3, True, 4),
    (['UI', 'ui', 'UI设计', '界面设计', '图标设计'], 'UI设计', 2, True, 3),

    # Tech - lower standardization, high digital delivery
    (['网站', '建站', '网页', '官网', '落地页'], '网站开发', 2, True, 3),
    (['小程序', '微信小程序', '支付宝小程序'], '小程序开发', 2, True, 3),
    (['数据分析', '数据处理', '数据可视化', '数据报表'], '数据分析', 3, True, 4),
    (['Excel', 'excel', '表格', '电子表格', 'WPS'], 'Excel处理', 4, True, 5),
    (['爬虫', '数据采集', '自动化脚本', '批量采集'], '爬虫/数据采集', 3, True, 4),
    (['Python', 'python', 'Java', 'java', '编程', '代码', '程序'], '代码开发', 2, True, 3),

    # AI tools
    (['AI工具', 'AI软件', 'AI推荐', 'AI平台'], 'AI工具咨询', 4, True, 4),
    (['AI绘画', 'AI画', 'AI生图', 'AI生成图', 'Midjourney', 'midjourney', 'Stable Diffusion', 'SD绘画'], 'AI绘画', 4, True, 5),
    (['AI视频', 'AI剪辑', 'AI生成视频'], 'AI视频', 3, True, 4),

    # Other services
    (['取名', '起名', '命名', '公司名', '品牌名'], '取名/命名', 4, True, 5),
    (['塔罗', '占卜', '星盘', '算命', '八字'], '占卜/塔罗', 2, False, 2),
    (['心理咨询', '心理疏导', '情绪', '焦虑', '抑郁'], '心理咨询', 1, False, 1),
    (['辅导', '家教', '补课', '作业', '答疑', '教学'], '教育辅导', 2, True, 3),
    (['职业规划', '求职', '面试', '跳槽', '转行', '职业发展'], '职业规划', 2, True, 3),
]


def detect_demand_type(text, source_file):
    """Infer demand type from text and source."""
    text_lower = text.lower()

    selling_signals = ['接单', '接稿', '承接', '可做', '私我', '有需要的', '接各种', '代做', '可代']
    buying_signals = ['有偿', '付费求', '花钱找', '求做', '求代', '谁能帮', '哪里找', '怎么找人']
    recommend_signals = ['推荐', '求推荐', '有没有好用', '求app', '求软件', '什么工具', '哪个好']

    for kw in selling_signals:
        if kw in text_lower:
            return 'selling'
    for kw in buying_signals:
        if kw in text_lower:
            return 'buying'
    for kw in recommend_signals:
        if kw in text_lower:
            return 'recommending'

    # Source-based fallback
    if source_file == '有偿数据':
        return 'buying'
    return 'discussing'


def rule_label(record):
    """Try to label a record using rules. Returns label dict or None if ambiguous."""
    text = f"{record.get('title', '')} {record.get('content', '')}".lower()
    title = record.get('title', '').lower()

    best_match = None
    best_score = 0

    for keywords, category, std_score, digital, ai_score in CATEGORY_RULES:
        match_count = 0
        for kw in keywords:
            if kw.lower() in text:
                match_count += 1
                # Title matches are worth more
                if kw.lower() in title:
                    match_count += 2
        if match_count > best_score:
            best_score = match_count
            best_match = (category, std_score, digital, ai_score)

    if best_match is None or best_score == 0:
        return None

    category, std_score, digital, ai_score = best_match
    demand_type = detect_demand_type(text, record.get('source_file', ''))

    return {
        'service_category': category,
        'standardization_score': std_score,
        'digital_delivery': digital,
        'ai_replaceability': ai_score,
        'demand_type': demand_type,
        'confidence': min(5, best_score + 2),  # Higher match count = higher confidence
        'label_method': 'rule',
    }


def main():
    # Load input
    records = []
    with open(INPUT_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            records.append(json.loads(line))

    print(f'Loaded {len(records)} filtered records')

    labeled = []
    ambiguous = []
    category_counts = {}

    for r in records:
        label = rule_label(r)
        if label:
            r.update(label)
            labeled.append(r)
            cat = label['service_category']
            category_counts[cat] = category_counts.get(cat, 0) + 1
        else:
            r['label_method'] = 'pending'
            ambiguous.append(r)

    # Write labeled records
    os.makedirs(XHS_RAW_DIR, exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        for r in labeled:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

    # Write ambiguous records for LLM review
    with open(AMBIGUOUS_PATH, 'w', encoding='utf-8') as f:
        for r in ambiguous:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

    # Stats
    stats = {
        'total_input': len(records),
        'rule_labeled': len(labeled),
        'ambiguous': len(ambiguous),
        'rule_coverage': round(len(labeled) / len(records) * 100, 1),
        'category_distribution': dict(sorted(category_counts.items(), key=lambda x: -x[1])),
    }

    with open(STATS_PATH, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f'\nRule-labeled: {len(labeled)} ({stats["rule_coverage"]}%)')
    print(f'Ambiguous (needs LLM): {len(ambiguous)} ({100 - stats["rule_coverage"]:.1f}%)')
    print(f'\nCategory distribution:')
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1])[:15]:
        print(f'  {cat}: {count}')

    print(f'\nOutput: {OUTPUT_PATH}')
    print(f'Ambiguous: {AMBIGUOUS_PATH}')
    print(f'Stats: {STATS_PATH}')


if __name__ == '__main__':
    main()
