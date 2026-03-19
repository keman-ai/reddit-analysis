#!/usr/bin/env python3
"""Shared configuration for Xiaohongshu pipeline."""

BASE_DIR = '/Users/huanghaibin/Workspace/reddit_research'
SOURCE_DIR = f'{BASE_DIR}/灰豚-求助帖'
XHS_RAW_DIR = f'{BASE_DIR}/data/raw/xiaohongshu'
XHS_ANALYZED_DIR = f'{BASE_DIR}/data/analyzed/xiaohongshu'
REPORTS_DIR = f'{BASE_DIR}/data/reports'

CSV_FILES = {
    'xhs_export_excel20263_在线求助_1001158683_1773907768048.csv': '在线求助',
    'xhs_export_excel20263_求助帖子数据_1001158683_1773907474666.csv': '求助帖子数据',
    'xhs_export_excel20263_求助低粉爆文_1001158683_1773908321212.csv': '求助低粉爆文',
    'xhs_export_excel20263_有偿 数据_1001158683_1773908527262.csv': '有偿数据',
    'xhs_export_excel20263_求推荐_1001158683_1773908668786.csv': '求推荐',
}

FIELD_MAP = {
    '笔记官方地址': 'note_url',
    '笔记标题': 'title',
    '笔记内容': 'content',
    '预估阅读量': 'estimated_reads',
    '互动量': 'engagement',
    '点赞数': 'likes',
    '收藏数': 'bookmarks',
    '评论数': 'comments',
    '分享数': 'shares',
    '发布时间': 'publish_time',
    '封面图片地址': 'cover_image_url',
    '视频链接': 'video_url',
    '是否商业笔记': 'is_commercial',
    '报备品牌企业号': 'brand_account',
    '提及品牌': 'mentioned_brands',
    '是否参与付费推广': 'is_paid_promotion',
    '达人名称': 'creator_name',
    '小红书号': 'xhs_id',
    '主页链接': 'profile_url',
    '粉丝数': 'follower_count',
    '联系方式': 'contact_info',
    '笔记类型': 'note_type',
}

INCLUSION_KEYWORDS = {
    'service_signal': [
        '有偿', '付费', '收费', '接单', '代做', '代写', '代画', '代剪', '包满意',
        '帮我', '帮忙做', '谁能帮', '求大佬', '哪里可以', '怎么找人',
        '求推荐工具', '有没有好用的', '求app', '求软件',
    ],
    'document': ['PPT', 'ppt', '简历', '论文', '报告', '文案', '公文', '翻译'],
    'design': ['logo', 'Logo', 'LOGO', '海报', '头像', '封面', 'P图', 'p图', '修图', 'UI', 'ui'],
    'tech': ['爬虫', '网站', '小程序', '数据分析', 'Excel', 'excel', 'Python', 'python', '代码'],
    'ai_tool': ['AI工具', 'AI绘画', 'AI生成', 'AI代', 'AI写', 'ChatGPT', 'GPT', 'Midjourney', 'Stable Diffusion', 'Kimi', '豆包', '通义'],
}

EXCLUSION_KEYWORDS = [
    '搬家', '维修', '安装', '配送', '上门', '家政', '保洁',
    '就医', '律师', '法律咨询', '诊断', '处方',
    '二手', '闲置', '转让', '出售实物',
    '找对象', '相亲', '脱单', '表白',
]

SEED_CATEGORIES = [
    'PPT制作', '简历优化', '论文润色', '文案撰写', '翻译', '公文写作', '报告撰写',
    'Logo设计', '海报设计', '头像制作', '封面设计', '修图/P图', 'UI设计',
    '网站开发', '小程序开发', '数据分析', 'Excel处理', '爬虫/数据采集', '代码开发',
    'AI工具咨询', 'AI绘画', 'AI视频',
    '取名/命名', '占卜/塔罗', '心理咨询', '教育辅导', '职业规划',
]

SCORING_WEIGHTS = {
    'ai_replaceability': 0.35,
    'standardization': 0.25,
    'demand_heat': 0.20,
    'engagement': 0.10,
    'digital_ratio': 0.10,
}

XHS_TO_GOOFISH_MAP = {
    'writing': ['PPT制作', '简历优化', '论文润色', '文案撰写', '报告撰写', '公文写作'],
    'design': ['Logo设计', '海报设计', '头像制作', '封面设计', '修图/P图', 'UI设计'],
    'translation': ['翻译'],
    'programming': ['网站开发', '小程序开发', '代码开发', '爬虫/数据采集', '数据分析', 'Excel处理'],
    'ai_related': ['AI工具咨询', 'AI绘画', 'AI视频'],
    'education': ['教育辅导'],
    'consulting': ['心理咨询', '职业规划'],
}
