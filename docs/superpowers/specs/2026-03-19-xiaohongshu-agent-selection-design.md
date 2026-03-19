# 小红书 AI Agent 可替代服务选品调研设计

## 背景与目标

为 AI Agent 服务交易平台选品，以小红书为调研对象，从 ~24,676 条灰豚导出数据中，识别可被 AI Agent 替代的服务需求，筛选出平台第一批选品。

### 核心假设
- 小红书上大量"求助帖"和"有偿帖"反映了真实的服务需求
- 其中标准化程度高、交付物为数字化产物的服务，最适合被 AI Agent 替代
- 这些服务在闲鱼上已有定价和销量验证，可交叉确认付费意愿

## 数据源

### 已有数据（灰豚导出）
| 文件 | 记录数 | 说明 |
|------|--------|------|
| 在线求助 | 5,000 | 用户在线求助帖 |
| 求助帖子数据 | 5,000 | 通用求助帖 |
| 求助低粉爆文 | 4,671 | 低粉创作者的爆款求助帖 |
| 有偿数据 | 5,000 | 明确有偿需求的帖子 |
| 求推荐 | 5,000 | 求推荐产品/服务/工具的帖子 |

**字段：** 笔记URL、标题、内容、预估阅读量、互动量、点赞数、收藏数、评论数、分享数、发布时间、是否商业笔记、创作者名称、粉丝数、笔记类型等 22 个字段。

### 补充采集（按需）
如数据不足，用 Playwright 针对特定品类关键词补采。

## 处理流水线

### Stage 1: 数据清洗与合并

**输入：** 5 个 CSV 文件（UTF-8 BOM）
**输出：** `data/raw/xiaohongshu/posts_merged.jsonl`

1. 读取 5 个 CSV，统一编码
2. 合并，新增 `source_file` 字段标记来源
3. 按 `笔记官方地址` 去重
4. 清洗：去空标题/空内容、标准化时间字段
5. 字段重命名为英文：
   - `note_url`, `title`, `content`, `estimated_reads`, `engagement`
   - `likes`, `bookmarks`, `comments`, `shares`, `publish_time`
   - `is_commercial`, `creator_name`, `follower_count`, `note_type`
   - `source_file`

### Stage 2: 关键词规则粗筛

**输入：** `posts_merged.jsonl`（预估 ~20K 条）
**输出：** `posts_filtered.jsonl`（目标 3-5K 条）+ `filter_stats.json`

**筛选规则（命中任一即保留）：**

规则 1 — 服务交易信号词：
- 有偿类：有偿、付费、收费、接单、代做、代写、代画、代剪、包满意
- 求助类：帮我、帮忙做、谁能帮、求大佬、哪里可以、怎么找人
- 推荐类：求推荐工具、有没有好用的、求app、求软件

规则 2 — 服务品类关键词：
- 文档类：PPT、简历、论文、报告、文案、公文、翻译
- 设计类：logo、海报、头像、封面、P图、修图、UI
- 技术类：爬虫、网站、小程序、数据分析、Excel、Python、代码
- AI 工具：AI、ChatGPT、GPT、Midjourney、Stable Diffusion、Kimi、豆包、通义

规则 3 — 来源加权：
- `有偿` 文件全部保留
- 其他文件按规则 1+2 过滤

规则 4 — 排除规则（命中即排除）：
- 线下/实物服务：搬家、维修、安装、配送、上门、家政、保洁
- 医疗/法律敏感：就医、律师、法律咨询、诊断、处方
- 纯商品交易：二手、闲置、转让、出售实物
- 情感/社交：找对象、相亲、脱单、表白

粗筛后如数量偏离 3-5K 目标，动态调整关键词宽严度。

### Stage 3: LLM 批量打标

**输入：** `posts_filtered.jsonl`
**输出：** `posts_labeled.jsonl` + `labeling_progress.json`

每条记录新增打标字段：
| 字段 | 类型 | 说明 |
|------|------|------|
| `service_category` | string | 服务品类（从种子列表选择，必要时新增） |
| `standardization_score` | 1-5 | 标准化程度：5=完全模板化，1=高度个性化 |
| `digital_delivery` | bool | 交付物是否为纯数字化产物 |
| `ai_replaceability` | 1-5 | AI Agent 可替代度 |
| `demand_type` | enum | buying/selling/recommending/discussing |
| `confidence` | 1-5 | LLM 置信度 |

**种子品类列表（LLM 优先从此列表选择，不匹配时可新增）：**
PPT制作、简历优化、论文润色、文案撰写、翻译、公文写作、报告撰写、
Logo设计、海报设计、头像制作、封面设计、修图/P图、UI设计、
网站开发、小程序开发、数据分析、Excel处理、爬虫/数据采集、代码开发、
AI工具咨询、AI绘画、AI视频、
取名/命名、占卜/塔罗、心理咨询、教育辅导、职业规划

**模型与成本：**
- 使用 Claude Haiku（成本最低，分类任务足够）
- 预估：3-5K 条 / 50 条每批 = 60-100 次 API 调用
- 每批约 3K tokens 输入 + 2K tokens 输出 = 5K tokens/批
- 总计约 500K tokens，Haiku 成本可忽略

**处理策略：**
- 每批 50 条（标题 + 内容截断前 300 字）
- 返回 JSON 数组
- 断点续做（labeling_progress.json 记录已处理的 record ID 集合）
- confidence < 3 标记为待复核，从最终评分中排除但保留在数据中
- 先跑 1 批（50 条）样本，人工检查打标质量后再全量执行

**LLM 输出校验：**
- JSON schema 校验：standardization_score/ai_replaceability 必须为 1-5 整数，demand_type 必须为枚举值之一，digital_delivery 必须为布尔
- 校验失败的批次自动重试（最多 2 次），仍失败则跳过并记录到 errors.log
- 未在种子列表中的新品类记录到 new_categories.json，供归一化阶段审查

### Stage 4: 统计聚合与选品报告

**输入：** `posts_labeled.jsonl`
**输出：** 结构化数据 + 选品报告

**Step 1 — 品类归一化：**
LLM 自由标签聚类归一，输出 `category_mapping.json`

**Step 2 — 统计聚合（按品类）：**
- 笔记数量（需求热度）
- 平均互动量/点赞/收藏
- demand_type 分布
- standardization_score 均值
- ai_replaceability 均值
- digital_delivery 占比

输出 `data/analyzed/xiaohongshu/category_stats.json`

**Step 3 — 选品评分：**
```
选品得分 = ai_replaceability × 0.35 + standardization × 0.25 + demand_heat × 0.2 + engagement × 0.1 + digital_ratio × 0.1
```
- demand_heat 和 engagement 使用 log 归一化到 1-5（避免长尾分布压缩大部分品类到低分段）
- 输出 `data/analyzed/xiaohongshu/category_ranking.json`

**Step 4 — 生成报告：**
- Top 20 品类排名
- 每个品类的典型帖子示例
- 与闲鱼数据交叉对比（见下方交叉验证方法论）
- 最终推荐 Top 10 选品及理由
- 输出 `data/reports/xiaohongshu_agent_selection_report.md`

## 目录结构

```
data/
├── raw/xiaohongshu/
│   ├── posts_merged.jsonl          # 合并去重后全量
│   ├── posts_filtered.jsonl        # 粗筛候选集
│   ├── posts_labeled.jsonl         # LLM 打标结果
│   ├── filter_stats.json           # 粗筛统计
│   └── labeling_progress.json      # 打标断点
├── analyzed/xiaohongshu/
│   ├── category_mapping.json       # 品类归一化映射
│   ├── category_stats.json         # 品类统计
│   └── category_ranking.json       # 选品排名
└── reports/
    └── xiaohongshu_agent_selection_report.md
```

## 筛选标准

核心维度（权重从高到低）：
1. **AI 可替代度**（0.35）— Agent 能否独立完成交付
2. **标准化程度**（0.25）— 需求是否可模板化
3. **需求热度**（0.20）— 小红书上讨论/求助量
4. **用户关注度**（0.10）— 互动量反映的关注强度
5. **数字化比例**（0.10）— 是否纯线上交付

## 交叉验证方法论

### 小红书 × 闲鱼品类映射
小红书品类（种子列表）与闲鱼品类（10 大类）的映射关系：
| 小红书品类 | 闲鱼品类 | 对比指标 |
|-----------|----------|---------|
| PPT制作/简历优化/论文润色/文案撰写/报告撰写/公文写作 | writing (15.2%) | 闲鱼 listings 数、median price、want count |
| Logo设计/海报设计/头像制作/封面设计/修图P图/UI设计 | design (23.7%) | 同上 |
| 翻译 | translation (16%) | 同上 |
| 网站开发/小程序开发/代码开发/爬虫数据采集/数据分析/Excel处理 | programming (17.1%) | 同上 |
| AI工具咨询/AI绘画/AI视频 | AI-related (14.5%) | 同上 |

### 验证逻辑
- **高置信选品：** 小红书需求 Top-10 且闲鱼有对应供给和销量的品类
- **隐性需求：** 小红书需求高但闲鱼供给少 → 供给缺口，优先切入机会
- **虚火品类：** 小红书讨论热但闲鱼无付费验证 → 降权处理

## 与已有数据的关系

- 闲鱼数据（10,234 条）提供供给侧定价和销量验证
- Reddit 数据（17,155 条）提供全球视角的需求趋势对比
- 小红书数据提供中国市场的真实用户需求信号
- 三者交叉验证可提高选品决策的可靠性
