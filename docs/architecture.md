# Reddit AI Agent 需求研究 — 技术架构文档

> 生成日期：2026-03-19
> 基于对 old.reddit.com 实际页面的 Playwright 浏览器探索

---

## 1. old.reddit.com 页面 DOM 结构分析

### 1.1 搜索结果页

**URL 格式**：`https://old.reddit.com/r/{subreddit}/search?q={keyword}&restrict_sr=on&sort=top&t=year`

**页面标识**：
- `body` class：`combined-search-page search-page`
- 页面 title 格式：`{subreddit}: search results - {keyword}`

**搜索结果容器**：
- 结果列表容器：`.search-result-listing`
- 每个结果项：`.search-result`（`<div>` 元素）
- 每页默认 25 条结果

**单条搜索结果的 DOM 结构**：
```html
<div class="search-result search-result-link has-thumbnail has-linkflair linkflair-fh-hiring"
     data-fullname="t3_1owaxmd">
  <a href="/r/forhire/comments/1owaxmd/..." class="may-blank thumbnail self"></a>
  <div>
    <header class="search-result-header">
      <span class="linkflairlabel" title="Hiring">Hiring</span>
      <a href="https://old.reddit.com/r/forhire/comments/..."
         class="search-title may-blank">[Hiring] Code / cloud help</a>
    </header>
    <div class="search-result-meta">
      <span class="search-result-icon search-result-icon-score"></span>
      <span class="search-score">120 points</span>
      <a href="..." class="search-comments may-blank">30 comments</a>
      <span class="search-time">
        submitted <time title="Thu Nov 13 19:47:09 2025 UTC"
                        datetime="2025-11-13T19:47:09+00:00">4 months ago</time>
      </span>
      <span class="search-author">
        by <a href="https://old.reddit.com/user/amirah920"
              class="author may-blank">amirah920</a>
      </span>
      <span>to <a href="..." class="search-subreddit-link may-blank">r/forhire</a></span>
    </div>
    <div class="search-expando collapsed">
      <div class="search-result-body">
        <div class="md"><p>帖子正文预览...</p></div>
      </div>
    </div>
  </div>
</div>
```

**关键选择器汇总**：

| 数据字段 | CSS 选择器 | 提取方式 |
|---------|-----------|---------|
| 帖子 ID | `.search-result` | `getAttribute('data-fullname')` |
| 标题 | `.search-title` | `.textContent.trim()` |
| URL | `.search-title` | `.href` |
| 分数/Upvotes | `.search-score` | `.textContent` → `parseInt(replace(/[^0-9]/g, ''))` |
| 评论数 | `.search-comments` | `.textContent` → `parseInt(replace(/[^0-9]/g, ''))` |
| 发布时间 | `.search-time time` | `getAttribute('datetime')` — ISO 8601 格式 |
| 作者 | `.search-author .author` | `.textContent.trim()` |
| Subreddit | `.search-subreddit-link` | `.textContent.trim().replace('r/', '')` |
| 正文预览 | `.search-result-body .md` | `.textContent.trim()` |

**分页结构**：
- 分页容器：`.nav-buttons`
- 下一页链接：`a[rel="nofollow next"]`
- 下一页 URL 格式：`...&count=25&after=t3_{last_post_id}`
- 当无下一页时，`.nav-buttons` 中不包含 `a[rel="nofollow next"]` 元素

**空结果检测**：
- 当 `document.querySelectorAll('.search-result').length === 0` 时，表示无搜索结果
- `.search-result-listing` 容器仍然存在，但内部无 `.search-result` 子元素

### 1.2 帖子详情页

**URL 格式**：`https://old.reddit.com/r/{subreddit}/comments/{post_id}/{slug}/`

**页面标识**：
- 帖子主体元素：`.thing.link`（有 `data-fullname` 属性）

**帖子正文 DOM 结构**：
```html
<div class="thing id-t3_1owaxmd linkflair ... link self" data-fullname="t3_1owaxmd">
  <div class="entry ...">
    <p class="title">
      <a class="title may-blank">[Hiring] Code / cloud help</a>
    </p>
    <p class="tagline">
      submitted <time datetime="2025-11-13T19:47:09+00:00">4 months ago</time>
      by <a class="author may-blank">amirah920</a>
    </p>
    <div class="expando">
      <div class="usertext-body">
        <div class="md"><p>帖子正文...</p></div>
      </div>
    </div>
  </div>
  <div class="score">
    <span class="score unvoted">121</span>
    <span class="score likes">122</span>
    <span class="score dislikes">120</span>
  </div>
</div>
```

**评论区 DOM 结构**：
```html
<div class="commentarea">
  <div class="sitetable nestedlisting">
    <!-- 每条顶级评论 -->
    <div class="thing comment noncollapsed" id="thing_t1_xxx">
      <div class="entry">
        <p class="tagline">
          <a class="author">username</a>
          <span class="score unvoted">5 points</span>
          <time datetime="2025-11-14T...">...</time>
        </p>
        <div class="usertext-body">
          <div class="md"><p>评论内容...</p></div>
        </div>
      </div>
      <!-- 子评论嵌套在 .child 中 -->
      <div class="child">...</div>
    </div>
  </div>
</div>
```

**关键选择器汇总**：

| 数据字段 | CSS 选择器 | 提取方式 |
|---------|-----------|---------|
| 帖子 ID | `.thing.link` | `getAttribute('data-fullname')` |
| 标题 | `.thing.link .title a.title` | `.textContent.trim()` |
| 作者 | `.thing.link .tagline .author` | `.textContent.trim()` |
| Upvotes | `.thing.link .score.unvoted` | `parseInt(text.replace(/[^0-9]/g, ''))` |
| 发布时间 | `.thing.link .tagline time` | `getAttribute('datetime')` |
| 正文 | `.thing.link .expando .usertext-body .md` | `.textContent.trim()` |
| 顶级评论列表 | `.commentarea > .sitetable > .thing.comment` | 遍历 NodeList |
| 评论作者 | `:scope > .entry .author` | `.textContent.trim()` |
| 评论内容 | `:scope > .entry .usertext-body .md` | `.textContent.trim()` |
| 评论分数 | `:scope > .entry .score.unvoted` | `parseInt(text.replace(/[^0-9-]/g, ''))` |
| 评论时间 | `:scope > .entry time` | `getAttribute('datetime')` |

**特殊评论标识**：
- 已删除评论：`.thing.comment.deleted`（class 包含 `deleted`）
- 置顶评论（AutoModerator）：`.thing.comment.stickied`（class 包含 `stickied`）
- 折叠评论：`.thing.comment.collapsed`（class 包含 `collapsed`）

---

## 2. JS 提取脚本代码

### 2.1 搜索结果页提取脚本

> 已在 old.reddit.com/r/forhire/search 实际验证通过，返回 25 条正确结构化数据

```javascript
() => {
  const posts = [];
  document.querySelectorAll('.search-result').forEach(el => {
    const titleEl = el.querySelector('.search-title');
    const scoreEl = el.querySelector('.search-score');
    const commentsEl = el.querySelector('.search-comments');
    const timeEl = el.querySelector('.search-time time');
    const authorEl = el.querySelector('.search-author .author');
    const subredditEl = el.querySelector('.search-subreddit-link');
    const bodyEl = el.querySelector('.search-result-body .md');

    const scoreText = scoreEl ? scoreEl.textContent.trim() : '0';
    const score = parseInt(scoreText.replace(/[^0-9]/g, '')) || 0;

    const commentsText = commentsEl ? commentsEl.textContent.trim() : '0';
    const commentCount = parseInt(commentsText.replace(/[^0-9]/g, '')) || 0;

    posts.push({
      id: el.getAttribute('data-fullname') || '',
      title: titleEl ? titleEl.textContent.trim() : '',
      url: titleEl ? titleEl.href : '',
      upvotes: score,
      comment_count: commentCount,
      created_at: timeEl ? timeEl.getAttribute('datetime') : '',
      author: authorEl ? authorEl.textContent.trim() : '[deleted]',
      subreddit: subredditEl ? subredditEl.textContent.trim().replace('r/', '') : '',
      body_preview: bodyEl ? bodyEl.textContent.trim().substring(0, 200) : ''
    });
  });

  // 获取下一页 URL
  const nextLink = document.querySelector('a[rel="nofollow next"]');
  const nextUrl = nextLink ? nextLink.href : null;

  return { total: posts.length, posts: posts, nextUrl: nextUrl };
}
```

**验证结果示例**（搜索 `hire AI agent` in `r/forhire`，sort=top, t=year）：
```json
{
  "total": 25,
  "posts": [
    {
      "id": "t3_1owaxmd",
      "title": "[Hiring] Code / cloud help",
      "url": "https://old.reddit.com/r/forhire/comments/1owaxmd/hiring_code_cloud_help/",
      "upvotes": 120,
      "comment_count": 30,
      "created_at": "2025-11-13T19:47:09+00:00",
      "author": "amirah920",
      "subreddit": "forhire",
      "body_preview": "I'm trying to setup code in a cloud..."
    }
  ],
  "nextUrl": "https://old.reddit.com/r/forhire/search?q=hire+AI+agent&restrict_sr=on&sort=top&t=year&count=25&after=t3_1pn8ndk"
}
```

### 2.2 帖子详情页提取脚本

> 已在 old.reddit.com/r/forhire/comments/1owaxmd/ 实际验证通过

```javascript
() => {
  const postBody = document.querySelector('.thing.link .expando .usertext-body .md');
  const postTitle = document.querySelector('.thing.link .title a.title');
  const postAuthor = document.querySelector('.thing.link .tagline .author');
  const postScore = document.querySelector('.thing.link .score.unvoted');
  const postTime = document.querySelector('.thing.link .tagline time');
  const postId = document.querySelector('.thing.link')?.getAttribute('data-fullname');

  // 提取顶级非删除、非置顶评论
  const topComments = document.querySelectorAll('.commentarea > .sitetable > .thing.comment');
  const comments = [];
  for (const c of topComments) {
    if (c.classList.contains('deleted')) continue;
    if (c.classList.contains('stickied')) continue;

    const author = c.querySelector(':scope > .entry .author');
    const body = c.querySelector(':scope > .entry .usertext-body .md');
    const score = c.querySelector(':scope > .entry .score.unvoted');
    const time = c.querySelector(':scope > .entry time');

    if (!body || !body.textContent.trim()) continue;

    const scoreText = score ? score.textContent.trim() : '0';
    const scoreNum = parseInt(scoreText.replace(/[^0-9-]/g, '')) || 0;

    comments.push({
      author: author ? author.textContent.trim() : '[deleted]',
      body: body.textContent.trim(),
      score: scoreNum,
      time: time ? time.getAttribute('datetime') : ''
    });

    if (comments.length >= 20) break;
  }

  // 按分数降序排列
  comments.sort((a, b) => b.score - a.score);

  return {
    id: postId || '',
    title: postTitle ? postTitle.textContent.trim() : '',
    author: postAuthor ? postAuthor.textContent.trim() : '[deleted]',
    upvotes: postScore ? parseInt(postScore.textContent.replace(/[^0-9]/g, '')) || 0 : 0,
    created_at: postTime ? postTime.getAttribute('datetime') : '',
    body: postBody ? postBody.textContent.trim() : '',
    comment_count: topComments.length,
    top_comments: comments.slice(0, 20)
  };
}
```

**验证结果示例**：
```json
{
  "id": "t3_1owaxmd",
  "title": "[Hiring] Code / cloud help",
  "author": "amirah920",
  "upvotes": 121,
  "created_at": "2025-11-13T19:47:09+00:00",
  "body": "I'm trying to setup code in a cloud...",
  "comment_count": 14,
  "top_comments": [
    {
      "author": "gandalfdoughnut",
      "body": "I gotchu, hit up my dms...",
      "score": 1,
      "time": "2025-12-03T00:45:04+00:00"
    }
  ]
}
```

### 2.3 错误检测脚本

```javascript
() => {
  const bodyText = document.body.textContent || '';
  const title = document.title || '';
  const searchResults = document.querySelectorAll('.search-result');

  return {
    // 被网络安全封锁
    isBlocked: bodyText.includes("You've been blocked") || bodyText.includes("blocked by network security"),
    // 429 限流
    isRateLimited: bodyText.includes("429") || bodyText.includes("Too Many Requests") || title.includes("Too Many Requests"),
    // 403 禁止访问
    isForbidden: bodyText.includes("Forbidden") || title.includes("403"),
    // 私有社区
    isPrivate: bodyText.includes("This community is private") || bodyText.includes("private community"),
    // 被封禁/不存在的社区
    isBanned: bodyText.includes("This community has been banned"),
    isNotFound: bodyText.includes("there doesn't seem to be anything here") && searchResults.length === 0,
    // 搜索结果为空（正常情况）
    isEmptyResults: searchResults.length === 0,
    // 搜索结果数量
    resultCount: searchResults.length
  };
}
```

---

## 3. Playwright MCP 调用步骤

### 3.1 完整抓取流程

对每个 `(subreddit, keyword, keyword_group)` 组合执行以下步骤：

#### 步骤 1：导航到搜索页

```
工具：browser_navigate
参数：{ "url": "https://old.reddit.com/r/{subreddit}/search?q={keyword_encoded}&restrict_sr=on&sort=top&t=year" }
```

其中 `keyword_encoded` 是将关键词中的空格替换为 `+`（URL 编码）。

示例：
```
browser_navigate({ url: "https://old.reddit.com/r/forhire/search?q=hire+AI+agent&restrict_sr=on&sort=top&t=year" })
```

#### 步骤 2：检测页面状态

```
工具：browser_evaluate
参数：{ "function": "<错误检测脚本（2.3节）>" }
```

根据返回结果判断：
- `isBlocked` / `isRateLimited` → 进入重试逻辑（见第 6 节）
- `isForbidden` / `isPrivate` / `isBanned` → 跳过该 subreddit，记录日志
- `isEmptyResults` → 正常，无结果，进入下一个组合
- `resultCount > 0` → 继续步骤 3

#### 步骤 3：提取搜索结果

```
工具：browser_evaluate
参数：{ "function": "<搜索结果页提取脚本（2.1节）>" }
```

返回值包含 `posts` 数组和 `nextUrl`。

#### 步骤 4：客户端过滤

在 Agent 侧（非浏览器内）对返回的 `posts` 进行过滤：

```python
# 伪代码
six_months_ago = current_date - timedelta(days=180)  # 2025-09-19

filtered_posts = []
for post in posts:
    created = parse_iso8601(post['created_at'])
    # 时间过滤：仅保留近6个月
    if created < six_months_ago:
        continue
    # 高价值过滤：upvotes >= 5 OR comments >= 3
    if post['upvotes'] >= 5 or post['comment_count'] >= 3:
        filtered_posts.append(post)
```

#### 步骤 5：获取高价值帖子详情

对每个通过过滤的帖子：

```
工具：browser_navigate
参数：{ "url": "{post.url}" }
```

等待页面加载后：

```
工具：browser_evaluate
参数：{ "function": "<帖子详情页提取脚本（2.2节）>" }
```

将返回的 `body` 和 `top_comments` 合并到帖子数据中。

#### 步骤 6：翻页

如果步骤 3 返回的 `nextUrl` 不为 `null`：

```
工具：browser_navigate
参数：{ "url": "{nextUrl}" }
```

然后重复步骤 2-6。

**翻页上限**：每个 `(subreddit, keyword)` 组合最多翻 4 页（100 条结果），避免过度抓取。

#### 步骤 7：保存数据

每完成一个帖子的详情提取后，立即追加写入 `data/raw/posts_raw.jsonl`：

```jsonl
{"id":"t3_1owaxmd","subreddit":"forhire","title":"[Hiring] Code / cloud help","author":"amirah920","created_at":"2025-11-13T19:47:09+00:00","url":"https://old.reddit.com/r/forhire/comments/1owaxmd/hiring_code_cloud_help/","upvotes":121,"comment_count":14,"body":"I'm trying to setup code...","top_comments":[...],"search_keyword":"hire AI agent","keyword_group":"hiring"}
```

#### 步骤 8：更新进度

每完成一个 `(subreddit, keyword)` 组合后更新 `data/raw/progress.json`：

```json
{
  "completed": [
    {"subreddit": "forhire", "keyword": "hire AI agent", "keyword_group": "hiring", "timestamp": "2026-03-19T10:30:00Z", "posts_found": 12}
  ],
  "failed": [
    {"subreddit": "slavelabour", "keyword": "hire AI agent", "keyword_group": "hiring", "error": "private_community", "timestamp": "2026-03-19T10:35:00Z"}
  ]
}
```

### 3.2 请求间延迟

每次 `browser_navigate` 调用之间，Agent 应等待 2-5 秒的随机延迟。由于 Agent 本身有思考时间，实际间隔通常已超过 2 秒，但仍建议在高频操作（如连续翻页）时显式等待。

---

## 4. 翻页策略

### 4.1 old.reddit.com 分页 URL 规则

old.reddit.com 搜索结果使用基于游标的分页：

| 参数 | 说明 | 示例 |
|------|------|------|
| `count` | 当前已显示的结果数 | `count=25`（第2页）、`count=50`（第3页） |
| `after` | 上一页最后一个帖子的 fullname | `after=t3_1pn8ndk` |

**完整分页 URL 示例**：
```
第1页：https://old.reddit.com/r/forhire/search?q=hire+AI+agent&restrict_sr=on&sort=top&t=year
第2页：https://old.reddit.com/r/forhire/search?q=hire+AI+agent&restrict_sr=on&sort=top&t=year&count=25&after=t3_1pn8ndk
第3页：https://old.reddit.com/r/forhire/search?q=hire+AI+agent&restrict_sr=on&sort=top&t=year&count=50&after=t3_xxx
```

### 4.2 翻页提取逻辑

```
获取下一页 URL：
  工具：browser_evaluate
  参数：{ "function": "() => document.querySelector('a[rel=\"nofollow next\"]')?.href || null" }
```

**翻页终止条件**：
1. `nextUrl` 为 `null`（已到最后一页）
2. 已翻页 4 次（最多 100 条结果/组合）
3. 当前页的所有帖子 `created_at` 均早于 6 个月前（时间排序下可提前终止）
4. 已达到全局最大帖子数上限（1000 条）

---

## 5. 异常处理策略

### 5.1 错误类型与处理方式

| 错误类型 | 检测方式 | 处理策略 | 重试 |
|---------|---------|---------|------|
| **429 Rate Limit** | `bodyText` 包含 "429" 或 "Too Many Requests" | 等待 60 秒后重试 | 最多 3 次，每次等待时间翻倍（60s → 120s → 240s） |
| **页面加载超时** | `browser_navigate` 超时错误 | 指数退避重试 | 3 次：10s → 20s → 40s 间隔 |
| **403/Captcha** | `bodyText` 包含 "Forbidden" 或 "403"；页面出现验证码 | 跳过当前组合，记录到 `progress.json` 的 `failed` 数组 | 不重试 |
| **网络安全封锁** | `bodyText` 包含 "blocked by network security" | 等待 120 秒后重试，如果连续 3 次被封则终止整个抓取 | 最多 3 次 |
| **Subreddit 不存在** | `bodyText` 包含 "there doesn't seem to be anything here" | 跳过该 subreddit，记录日志 | 不重试 |
| **Subreddit 私有** | `bodyText` 包含 "private community" | 跳过该 subreddit，记录日志 | 不重试 |
| **Subreddit 被封禁** | `bodyText` 包含 "community has been banned" | 跳过该 subreddit，记录日志 | 不重试 |
| **DOM 选择器失败** | 提取脚本返回空数据 | 使用 `browser_snapshot` 让 LLM 理解页面结构，尝试自适应调整选择器 | 1 次自适应尝试 |
| **帖子已删除** | 正文为 "[removed]" 或 "[deleted]" | 跳过该帖子，不写入数据 | 不重试 |

### 5.2 重试伪代码

```python
async def navigate_with_retry(url, max_retries=3):
    for attempt in range(max_retries):
        try:
            result = browser_navigate(url)

            # 检测页面状态
            status = browser_evaluate(error_detection_script)

            if status['isRateLimited']:
                wait_time = 60 * (2 ** attempt)  # 60s, 120s, 240s
                log(f"Rate limited, waiting {wait_time}s...")
                sleep(wait_time)
                continue

            if status['isBlocked']:
                wait_time = 120
                log(f"Blocked, waiting {wait_time}s...")
                sleep(wait_time)
                continue

            if status['isForbidden'] or status['isPrivate'] or status['isBanned']:
                log(f"Skipping: {url} - access denied")
                return None  # 不重试

            return result  # 成功

        except TimeoutError:
            wait_time = 10 * (2 ** attempt)  # 10s, 20s, 40s
            log(f"Timeout, retrying in {wait_time}s...")
            sleep(wait_time)

    log(f"Failed after {max_retries} retries: {url}")
    return None
```

### 5.3 browser_snapshot 辅助诊断

当 `browser_evaluate` 返回意外结果（如所有字段为空）时，使用 `browser_snapshot` 捕获页面可访问性快照：

```
工具：browser_snapshot
参数：{}
```

Agent（LLM）可以通过阅读 snapshot 来理解当前页面状态，判断是否需要：
- 关闭弹窗（如 cookie consent）
- 处理重定向
- 调整 CSS 选择器

---

## 6. 数据校验规则

### 6.1 必填字段校验

每条帖子写入 JSONL 前必须通过以下校验：

| 字段 | 类型 | 必填 | 校验规则 |
|------|------|------|---------|
| `id` | string | 是 | 非空，以 `t3_` 开头 |
| `subreddit` | string | 是 | 非空 |
| `title` | string | 是 | 非空，长度 > 0 |
| `author` | string | 是 | 非空（可以是 `[deleted]`） |
| `created_at` | string | 是 | 有效 ISO 8601 日期时间格式 |
| `url` | string | 是 | 以 `https://old.reddit.com/r/` 开头 |
| `upvotes` | number | 是 | 非负整数 |
| `comment_count` | number | 是 | 非负整数 |
| `body` | string | 否 | 可为空（链接帖子无正文） |
| `top_comments` | array | 否 | 数组，每个元素有 `author`、`body` 字段 |
| `search_keyword` | string | 是 | 非空，来自配置文件 |
| `keyword_group` | string | 是 | 枚举值：`hiring` / `buying` / `demand` |

### 6.2 校验伪代码

```python
def validate_post(post):
    errors = []

    # 必填字符串字段
    for field in ['id', 'subreddit', 'title', 'author', 'created_at', 'url', 'search_keyword', 'keyword_group']:
        if not post.get(field) or not isinstance(post[field], str) or not post[field].strip():
            errors.append(f"Missing or empty required field: {field}")

    # ID 格式
    if post.get('id') and not post['id'].startswith('t3_'):
        errors.append(f"Invalid post ID format: {post['id']}")

    # URL 格式
    if post.get('url') and not post['url'].startswith('https://old.reddit.com/r/'):
        errors.append(f"Invalid URL format: {post['url']}")

    # 日期格式
    if post.get('created_at'):
        try:
            parse_iso8601(post['created_at'])
        except:
            errors.append(f"Invalid datetime format: {post['created_at']}")

    # 数值字段
    if not isinstance(post.get('upvotes'), (int, float)) or post['upvotes'] < 0:
        errors.append(f"Invalid upvotes: {post.get('upvotes')}")
    if not isinstance(post.get('comment_count'), (int, float)) or post['comment_count'] < 0:
        errors.append(f"Invalid comment_count: {post.get('comment_count')}")

    # keyword_group 枚举
    if post.get('keyword_group') not in ('hiring', 'buying', 'demand'):
        errors.append(f"Invalid keyword_group: {post.get('keyword_group')}")

    # top_comments 结构
    if post.get('top_comments'):
        if not isinstance(post['top_comments'], list):
            errors.append("top_comments must be an array")
        else:
            for i, comment in enumerate(post['top_comments']):
                if not isinstance(comment, dict) or 'body' not in comment:
                    errors.append(f"Invalid comment structure at index {i}")

    return errors
```

### 6.3 去重规则

- 主键：帖子 `id`（`data-fullname`，如 `t3_1owaxmd`）
- 同一帖子可能被不同关键词搜索命中，只保留第一次出现的记录
- 去重时机：每批数据写入前，对比已写入的 `posts_raw.jsonl` 中已有的 ID

```python
def deduplicate(new_posts, existing_ids):
    unique = []
    for post in new_posts:
        if post['id'] not in existing_ids:
            existing_ids.add(post['id'])
            unique.append(post)
    return unique
```

---

## 7. 时间过滤逻辑

### 7.1 为什么需要客户端过滤

Reddit 搜索 API 的时间范围参数 `t` 仅支持预设值：`hour`、`day`、`week`、`month`、`year`。没有"近6个月"选项。

策略：使用 `t=year` 获取近一年数据，然后在客户端按 `created_at` 字段过滤，仅保留近 6 个月的帖子。

### 7.2 过滤逻辑

```python
from datetime import datetime, timedelta, timezone

def is_within_six_months(created_at_iso):
    """判断帖子是否在近6个月内发布"""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=180)  # 2025-09-19

    # 解析 ISO 8601 日期
    # 格式示例："2025-11-13T19:47:09+00:00"
    created = datetime.fromisoformat(created_at_iso)

    return created >= cutoff_date
```

### 7.3 过滤时机

1. **搜索结果页过滤**：提取搜索结果后，先过滤时间范围，再判断是否进入详情页
2. **提前终止优化**：由于搜索结果按 `sort=top` 排序（非时间排序），无法通过时间提前终止翻页。但如果按 `sort=new` 排序，当遇到 6 个月前的帖子时可立即停止翻页

### 7.4 高价值过滤

时间过滤后，再按以下条件筛选高价值帖子（仅对这些帖子获取详情）：

```python
def is_high_value(post):
    """满足任一条件即为高价值"""
    return post['upvotes'] >= 5 or post['comment_count'] >= 3
```

---

## 8. 完整工作流伪代码

```python
import json
from pathlib import Path

# 加载配置
config = json.loads(Path('config/search_config.json').read_text())
base_url = config['base_url']  # https://old.reddit.com
filters = config['filters']

# 加载进度
progress_file = Path('data/raw/progress.json')
if progress_file.exists():
    progress = json.loads(progress_file.read_text())
else:
    progress = {"completed": [], "failed": []}

# 加载已有数据的 ID（去重用）
existing_ids = set()
posts_file = Path('data/raw/posts_raw.jsonl')
if posts_file.exists():
    for line in posts_file.read_text().splitlines():
        existing_ids.add(json.loads(line)['id'])

# 构建任务列表
completed_keys = {(c['subreddit'], c['keyword']) for c in progress['completed']}
tasks = []
for group_name, subreddit_list in config['subreddits'].items():
    for subreddit in subreddit_list:
        for keyword_group, keywords in config['keywords'].items():
            for keyword in keywords:
                if (subreddit, keyword) not in completed_keys:
                    tasks.append((subreddit, keyword, keyword_group))

total_posts_collected = len(existing_ids)

# 主循环
for subreddit, keyword, keyword_group in tasks:
    if total_posts_collected >= filters['max_posts']:
        break

    keyword_encoded = keyword.replace(' ', '+')
    search_url = f"{base_url}/r/{subreddit}/search?q={keyword_encoded}&restrict_sr=on&sort=top&t=year"

    page_count = 0
    max_pages = 4  # 每个组合最多翻4页

    while search_url and page_count < max_pages:
        page_count += 1

        # 步骤1: 导航
        # browser_navigate(url=search_url)
        # 随机等待 2-5 秒

        # 步骤2: 检测错误
        # status = browser_evaluate(function=error_detection_script)
        # 处理错误...

        # 步骤3: 提取搜索结果
        # result = browser_evaluate(function=search_extraction_script)

        posts = result['posts']
        search_url = result['nextUrl']  # 下一页 URL

        # 步骤4: 过滤
        for post in posts:
            if not is_within_six_months(post['created_at']):
                continue
            if not is_high_value(post):
                continue
            if post['id'] in existing_ids:
                continue

            # 步骤5: 获取帖子详情
            # browser_navigate(url=post['url'])
            # detail = browser_evaluate(function=detail_extraction_script)

            # 合并数据
            post['body'] = detail['body']
            post['top_comments'] = detail['top_comments']
            post['search_keyword'] = keyword
            post['keyword_group'] = keyword_group

            # 校验
            errors = validate_post(post)
            if errors:
                log(f"Validation failed for {post['id']}: {errors}")
                continue

            # 步骤7: 写入 JSONL
            with open('data/raw/posts_raw.jsonl', 'a') as f:
                f.write(json.dumps(post, ensure_ascii=False) + '\n')

            existing_ids.add(post['id'])
            total_posts_collected += 1

    # 步骤8: 更新进度
    progress['completed'].append({
        'subreddit': subreddit,
        'keyword': keyword,
        'keyword_group': keyword_group,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'posts_found': page_count  # 简化计数
    })
    progress_file.write_text(json.dumps(progress, indent=2, ensure_ascii=False))

# 最终去重（跨关键词）
# 已在写入时通过 existing_ids 实时去重
```

---

## 9. 抓取规模估算

### 9.1 组合数量

| 类别 | Subreddits | Keywords | 组合数 |
|------|-----------|----------|--------|
| hiring | 3 | 5 | 15 |
| buying | 3 + 4 + 4 = 11 | 5 | 55 |
| demand | 11 | 6 | 66 |
| **合计** | | | **136 组合** |

注：每个 keyword 会在所有 subreddit 中搜索，实际为 11 个 subreddit × (5+5+6) = 11 × 16 = **176 组合**。

### 9.2 时间估算

- 每个组合：1 页搜索 + 平均 5 个帖子详情 = 约 6 次页面导航
- 每次导航：页面加载 2-3 秒 + Agent 思考/提取 2-3 秒 + 延迟 2-5 秒 ≈ 8 秒
- 每个组合：约 48 秒
- 176 组合总计：约 2.3 小时
- 加上重试和异常处理：预估 **3-4 小时**

### 9.3 分批策略

按 subreddit 分批，每个 subreddit 完成所有 keyword 后写入进度。如果 Agent 上下文接近溢出，可在任一 subreddit 边界处终止，启动新 Agent 从断点续抓。

---

## 10. 关键注意事项

1. **old.reddit.com 的多语言 UI**：old.reddit.com 会根据浏览器语言设置显示不同语言的 UI 文本（如"指標"、"留言"替代 "points"、"comments"）。因此分数和评论数的提取使用 `replace(/[^0-9]/g, '')` 正则去除所有非数字字符，与语言无关。

2. **score-hidden 评论**：部分新评论的分数是隐藏的（class 包含 `score-hidden`），此时 `.score.unvoted` 可能不存在或文本为空。提取脚本默认为 0 分。

3. **已删除帖子的正文**：正文为 `[removed]` 或 `[deleted]` 的帖子应跳过，正文内容无分析价值。

4. **首次请求可能被封锁**：实际测试中发现，直接访问搜索页可能触发 "blocked by network security"，但先访问 `old.reddit.com` 首页建立会话后再访问搜索页可以正常加载。**建议 Scraper 启动时先访问 `https://old.reddit.com` 首页**。

5. **每页 25 条结果**：old.reddit.com 搜索结果固定每页 25 条，不可自定义。
