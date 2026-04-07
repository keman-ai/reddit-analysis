# Reddit 市场调研自动化工具

一行描述：输入调研任务描述，自动完成 Reddit 数据采集、定量分析和报告生成。

## 快速开始

### 粗粒度（只给目标，agent 自己规划）

```bash
python run.py "调研 AI 写作工具的市场需求"
```

### 细粒度（指定 subreddit 和参数）

```bash
python run.py "从 r/writing 和 r/freelanceWriters 抓取关于 AI writing tools 的帖子，至少 5000 条，分析需求热度和定价信号"
```

### 自定义 task ID

```bash
python run.py --task-id ai_writing_20260408 "AI writing tools market demand"
```

## 前置条件

- Python 3.8+（仅使用标准库，无需 pip install）
- Claude Code CLI 已安装且 `claude` 命令可用
- 网络可访问 `old.reddit.com`

## 参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| `task` | 调研任务描述（位置参数） | `"调研 AI 写作工具"` |
| `--task-id` | 自定义任务 ID（默认由 LLM 生成） | `--task-id my_task_20260408` |
| `--resume TASK_ID` | 恢复之前中断的任务 | `--resume ai_writing_20260408` |
| `--from-phase N` | 从第 N 阶段开始（需配合 --resume） | `--from-phase 3` |

## 执行流程

```
Phase 1: 任务规划    → LLM 生成搜索计划（subreddit + 关键词 + 数据量）
Phase 2: 数据抓取    → Python 脚本调 Reddit JSON API，断点续抓
Phase 3: 定量分析    → Python 脚本做统计（分布、热度、价格、分类）
Phase 4: 报告生成    → LLM 基于统计数据 + 高热帖子生成中文报告
```

## 输出文件

一次完整执行会在以下位置产生文件：

| 文件 | 说明 |
|------|------|
| `data/raw/{task_id}_plan.json` | 搜索计划（subreddit、关键词、目标数据量） |
| `data/raw/{task_id}.jsonl` | 原始抓取数据 |
| `data/raw/{task_id}_progress.json` | 抓取进度（支持断点续抓） |
| `data/raw/{task_id}_deduped.jsonl` | 去重后数据 |
| `data/analyzed/{task_id}_stats.json` | 定量统计结果 |
| `data/reports/{task_id}_report.md` | 最终分析报告 |

## 断点续跑

抓取过程中如果中断（Ctrl+C、网络断开、限流过多），已抓取的数据和进度都会保存。恢复方法：

```bash
# 从头恢复（自动跳过已完成的抓取组合）
python run.py --resume ai_writing_20260408

# 跳过抓取，直接从分析阶段开始
python run.py --resume ai_writing_20260408 --from-phase 3

# 只重新生成报告
python run.py --resume ai_writing_20260408 --from-phase 4
```

## 常见问题

### 抓取被限流怎么办？

脚本内置了指数退避（60s → 120s → 240s → 480s）。如果频繁被限流，可以等待 10 分钟后用 `--resume` 恢复。

### 数据量不够怎么办？

如果去重后数据量低于目标的 50%，工具会打印警告。可以：
1. 编辑 `data/raw/{task_id}_plan.json`，增加更多 subreddit 或关键词
2. 用 `--resume` + `--from-phase 2` 重新抓取

### 想调整报告风格怎么办？

编辑 `prompts/generate_report.md` 模板，修改报告结构或质量要求，然后用 `--resume` + `--from-phase 4` 重新生成。

### 想在 Claude Code 会话中使用这个工具？

在 Claude Code 对话中直接说：

> "运行 `python run.py '调研 AI 写作工具的市场需求'`，后台执行，完成后告诉我报告路径"
