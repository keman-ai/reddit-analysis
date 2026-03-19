#!/usr/bin/env python3
"""Stage 3b: Process ambiguous records with expanded rules + LLM for remainder.

Reads posts_ambiguous.jsonl, applies expanded rules, writes results back to posts_labeled.jsonl.
Records that still can't be classified are marked as not_service.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import XHS_RAW_DIR

AMBIGUOUS_PATH = f'{XHS_RAW_DIR}/posts_ambiguous.jsonl'
OUTPUT_PATH = f'{XHS_RAW_DIR}/posts_labeled.jsonl'
STATS_PATH = f'{XHS_RAW_DIR}/labeling_stats.json'

# Expanded category rules for catching more service posts
EXPANDED_RULES = [
    # Photography/Video production
    (['拍照', '摄影', '写真', '证件照', '形象照', '拍摄', '约拍', '跟拍'], '摄影服务', 3, True, 2),
    # Video editing
    (['剪辑', '视频剪辑', '后期', '视频制作', '短视频', '视频代做', '剪视频'], '视频剪辑', 3, True, 4),
    # Music/Audio
    (['配音', '录音', '混音', '伴奏', '编曲', '作曲', '写歌'], '音频制作', 2, True, 3),
    # E-commerce
    (['代运营', '店铺', '电商', '淘宝', '拼多多', '抖音运营', '直播', '带货'], '电商运营', 2, True, 3),
    # Social media
    (['代发', '推广', '涨粉', '引流', '小红书运营', '新媒体', '自媒体'], '新媒体运营', 3, True, 4),
    # Calligraphy / handwriting
    (['手写', '书法', '手抄', '抄写', '手绘'], '手写/书法', 3, True, 2),
    # Accounting/Finance
    (['记账', '报税', '财务', '会计', '做账'], '财务服务', 3, True, 3),
    # Legal document
    (['合同', '协议', '法律文书', '起诉书', '律师函'], '法律文书', 2, True, 3),
    # Drawing/Illustration
    (['画画', '插画', '手绘', '漫画', '绘画', '画师', '约稿', '画稿'], '插画/绘画', 2, True, 3),
    # 3D/CAD
    (['3D', '建模', 'CAD', 'cad', '渲染', '效果图'], '3D建模', 2, True, 3),
    # Resume/Job
    (['面试辅导', '模拟面试', '面试准备'], '面试辅导', 3, True, 4),
    # Naming (broader)
    (['起个名', '想个名', '取个名', '求名字', '帮取名'], '取名/命名', 4, True, 5),
]

# Strong non-service signals
NOT_SERVICE_SIGNALS = [
    # Pet related
    '寻猫', '寻狗', '找猫', '找狗', '领养', '宠物', '猫猫', '狗狗', '寻鸟',
    '布偶', '金渐层', '英短', '美短', '橘猫', '走失', '丢失',
    # Physical goods trading
    '出售', '转让', '收购', '出二手', '全新', '包邮', '到付',
    # Travel/Transport
    '拼车', '顺风车', '飞友', '结伴', '自驾',
    # Food
    '好吃', '餐厅', '外卖', '美食', '蛋糕',
    # Housing
    '租房', '合租', '整租', '转租', '房源',
    # Dating/Social
    '约饭', '聚会', '交友',
    # Medical
    '看病', '挂号', '医院', '牙科', '皮肤',
    # Very vague
    '笔记暂未设置标题',
]


def matches_any(text, keywords):
    text_lower = text.lower()
    for kw in keywords:
        if kw.lower() in text_lower:
            return True
    return False


def detect_demand_type(text, source_file):
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
    if source_file == '有偿数据':
        return 'buying'
    return 'discussing'


def main():
    records = []
    with open(AMBIGUOUS_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            records.append(json.loads(line))

    print(f'Loaded {len(records)} ambiguous records')

    newly_labeled = []
    not_service = []
    still_ambiguous = []

    for r in records:
        text = f"{r.get('title', '')} {r.get('content', '')}"
        title = r.get('title', '').lower()

        # First check: is it clearly not a service?
        if matches_any(text, NOT_SERVICE_SIGNALS):
            r['service_category'] = 'not_service'
            r['standardization_score'] = 0
            r['digital_delivery'] = False
            r['ai_replaceability'] = 0
            r['demand_type'] = 'discussing'
            r['confidence'] = 4
            r['label_method'] = 'rule_not_service'
            not_service.append(r)
            continue

        # Second check: try expanded rules
        best_match = None
        best_score = 0
        for keywords, category, std_score, digital, ai_score in EXPANDED_RULES:
            match_count = 0
            for kw in keywords:
                if kw.lower() in text.lower():
                    match_count += 1
                    if kw.lower() in title:
                        match_count += 2
            if match_count > best_score:
                best_score = match_count
                best_match = (category, std_score, digital, ai_score)

        if best_match and best_score > 0:
            category, std_score, digital, ai_score = best_match
            r['service_category'] = category
            r['standardization_score'] = std_score
            r['digital_delivery'] = digital
            r['ai_replaceability'] = ai_score
            r['demand_type'] = detect_demand_type(text, r.get('source_file', ''))
            r['confidence'] = min(5, best_score + 1)
            r['label_method'] = 'rule_expanded'
            newly_labeled.append(r)
        else:
            # Can't determine — mark as not_service with low confidence
            r['service_category'] = 'not_service'
            r['standardization_score'] = 0
            r['digital_delivery'] = False
            r['ai_replaceability'] = 0
            r['demand_type'] = 'discussing'
            r['confidence'] = 2
            r['label_method'] = 'rule_unknown'
            still_ambiguous.append(r)

    # Append newly labeled and not_service to output
    with open(OUTPUT_PATH, 'a', encoding='utf-8') as f:
        for r in newly_labeled:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
        for r in not_service:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
        for r in still_ambiguous:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

    # Update stats
    existing_stats = {}
    if os.path.exists(STATS_PATH):
        with open(STATS_PATH, 'r') as f:
            existing_stats = json.load(f)

    existing_stats['stage3b'] = {
        'input_ambiguous': len(records),
        'newly_labeled': len(newly_labeled),
        'not_service': len(not_service),
        'still_unknown': len(still_ambiguous),
    }

    # Count new categories
    new_cats = {}
    for r in newly_labeled:
        cat = r['service_category']
        new_cats[cat] = new_cats.get(cat, 0) + 1

    existing_stats['stage3b']['new_categories'] = dict(sorted(new_cats.items(), key=lambda x: -x[1]))

    with open(STATS_PATH, 'w', encoding='utf-8') as f:
        json.dump(existing_stats, f, ensure_ascii=False, indent=2)

    print(f'\nNewly labeled: {len(newly_labeled)}')
    print(f'Not service: {len(not_service)}')
    print(f'Still unknown (marked not_service, low confidence): {len(still_ambiguous)}')
    print(f'\nNew category distribution:')
    for cat, count in sorted(new_cats.items(), key=lambda x: -x[1]):
        print(f'  {cat}: {count}')

    # Total counts
    total_labeled = 0
    service_labeled = 0
    with open(OUTPUT_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            total_labeled += 1
            if r.get('service_category') != 'not_service':
                service_labeled += 1

    print(f'\nTotal in output: {total_labeled}')
    print(f'Service-related: {service_labeled}')
    print(f'Not service: {total_labeled - service_labeled}')


if __name__ == '__main__':
    main()
