#!/usr/bin/env python3
"""
Reddit 市场调研自动化 CLI 工具。

用法：
    python run.py "调研 AI 写作工具的市场需求"
    python run.py "从 r/writing 和 r/freelanceWriters 抓取 AI writing tools 相关帖子，至少 5000 条"
    python run.py --resume <task_id>
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_RAW = PROJECT_ROOT / 'data' / 'raw'
DATA_ANALYZED = PROJECT_ROOT / 'data' / 'analyzed'
DATA_REPORTS = PROJECT_ROOT / 'data' / 'reports'
PROMPTS_DIR = PROJECT_ROOT / 'prompts'

# Global reference to the current status file path, set once task_id is known
_status_file = None


def ensure_dirs():
    """Ensure all required directories exist."""
    for d in [DATA_RAW, DATA_ANALYZED, DATA_REPORTS]:
        d.mkdir(parents=True, exist_ok=True)


def update_status(task_id: str, phase: int, phase_name: str, status: str,
                  detail: str = '', start_time: float = 0, **extra):
    """Write a JSON status file that external tools can poll for progress.

    File: data/raw/{task_id}_status.json
    """
    global _status_file
    if _status_file is None:
        _status_file = DATA_RAW / f"{task_id}_status.json"

    elapsed = time.time() - start_time if start_time else 0
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    payload = {
        'task_id': task_id,
        'current_phase': phase,
        'phase_name': phase_name,
        'status': status,       # running / completed / error
        'detail': detail,
        'elapsed': f'{minutes}m {seconds}s',
        'elapsed_seconds': round(elapsed, 1),
        'updated_at': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        'phases': {
            1: 'Task Planning',
            2: 'Data Scraping',
            3: 'Quantitative Analysis',
            4: 'Report Generation',
        },
    }
    payload.update(extra)

    with open(_status_file, 'w') as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return _status_file


def call_claude(prompt: str, timeout: int = 300) -> str:
    """Call Claude CLI with a prompt and return the output.

    Uses stdin to pass the prompt to avoid shell argument length limits.
    """
    try:
        result = subprocess.run(
            ['claude', '-p', '--allowedTools', '',
             '--system-prompt', '你是一个文本生成助手。直接输出用户要求的内容，不要使用任何工具，不要请求权限，不要输出摘要。'],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode != 0 and result.stderr:
            print(f"  Claude CLI warning: {result.stderr[:200]}", file=sys.stderr)
        return result.stdout.strip()
    except FileNotFoundError:
        print("Error: Claude CLI not found. Please install Claude Code and ensure 'claude' is in PATH.",
              file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print(f"Error: Claude CLI timed out after {timeout}s", file=sys.stderr)
        return ""


def phase1_plan(task_description: str, task_id: str = None,
                start_time: float = 0) -> dict:
    """Phase 1: Task Planning — use LLM to generate a structured search plan."""
    print("=" * 60)
    print("Phase 1: Task Planning")
    print("=" * 60)

    # Preliminary task_id for status updates before LLM generates one
    pre_id = task_id or 'pending'
    update_status(pre_id, 1, 'Task Planning', 'running',
                  'Calling Claude to generate search plan...', start_time)

    # Load prompt template
    template_path = PROMPTS_DIR / 'plan_task.md'
    template = template_path.read_text(encoding='utf-8')

    # Fill template
    prompt = template.replace('{task_description}', task_description)

    print("  Calling Claude to generate search plan...")
    output = call_claude(prompt, timeout=120)

    if not output:
        print("  Error: Empty response from Claude")
        sys.exit(1)

    # Parse JSON from output (LLM might include extra text)
    plan = None
    # First try: entire output is JSON
    try:
        plan = json.loads(output)
    except json.JSONDecodeError:
        # Try to extract JSON block from output
        json_match = re.search(r'\{[\s\S]*\}', output)
        if json_match:
            try:
                plan = json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

    if not plan:
        print("  Error: Could not parse plan JSON from Claude output")
        print(f"  Raw output:\n{output[:500]}")
        sys.exit(1)

    # Override task_id if provided
    if task_id:
        plan['task_id'] = task_id
    elif 'task_id' not in plan:
        # Generate from description
        words = re.sub(r'[^a-zA-Z0-9\s]', '', task_description.lower()).split()[:5]
        plan['task_id'] = '_'.join(words) + '_' + datetime.now().strftime('%Y%m%d')

    # Save plan
    plan_file = DATA_RAW / f"{plan['task_id']}_plan.json"
    with open(plan_file, 'w') as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)

    subs = len(plan.get('subreddits', []))
    kws = len(plan.get('keywords', []))
    target = plan.get('target_posts', 'N/A')
    print(f"  Plan saved: {plan_file}")
    print(f"  {subs} subreddits x {kws} keywords, target {target} posts")

    update_status(plan['task_id'], 1, 'Task Planning', 'completed',
                  f'{subs} subreddits x {kws} keywords, target {target} posts',
                  start_time)

    return plan


def phase2_scrape(plan: dict, start_time: float = 0) -> str:
    """Phase 2: Data Scraping — run the unified scraper."""
    print()
    print("=" * 60)
    print("Phase 2: Data Scraping")
    print("=" * 60)

    task_id = plan['task_id']
    plan_file = DATA_RAW / f"{task_id}_plan.json"
    output_file = DATA_RAW / f"{task_id}.jsonl"
    deduped_file = DATA_RAW / f"{task_id}_deduped.jsonl"
    progress_file = DATA_RAW / f"{task_id}_progress.json"

    update_status(task_id, 2, 'Data Scraping', 'running',
                  'Starting scraper...', start_time)

    # Check if deduped file already exists with sufficient data
    if deduped_file.exists():
        line_count = sum(1 for line in open(deduped_file) if line.strip())
        target = plan.get('target_posts', 5000)
        if line_count >= target * 0.5:
            print(f"  Deduped data already exists: {line_count} posts. Skipping scrape.")
            update_status(task_id, 2, 'Data Scraping', 'completed',
                          f'Skipped (existing data: {line_count} posts)', start_time)
            return str(deduped_file)

    print(f"  Running scraper...")
    print(f"  Plan: {plan_file}")
    print(f"  Output: {output_file}")
    print()

    # Run scraper as subprocess
    scraper_cmd = [
        sys.executable, str(PROJECT_ROOT / 'scripts' / 'scrape_reddit.py'),
        '--plan', str(plan_file),
        '--output', str(output_file),
    ]

    process = subprocess.Popen(
        scraper_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=str(PROJECT_ROOT),
    )

    # Stream output and periodically update status from progress.json
    last_status_update = 0
    target = plan.get('target_posts', 5000)
    for line in iter(process.stdout.readline, ''):
        print(f"  {line}", end='')
        # Update status every 30 seconds
        now = time.time()
        if now - last_status_update > 30:
            last_status_update = now
            try:
                if progress_file.exists():
                    with open(progress_file) as pf:
                        prog = json.load(pf)
                    collected = prog.get('total_posts', 0)
                    completed = len(prog.get('completed', []))
                    failed = len(prog.get('failed', []))
                    update_status(task_id, 2, 'Data Scraping', 'running',
                                  f'Collected {collected}/{target} posts '
                                  f'({completed} combos done, {failed} failed)',
                                  start_time, posts_collected=collected,
                                  target_posts=target)
            except Exception:
                pass
    process.wait()

    if process.returncode != 0:
        print(f"  Scraper exited with code {process.returncode}")

    # Check result
    if deduped_file.exists():
        line_count = sum(1 for line in open(deduped_file) if line.strip())
        print(f"\n  Deduped data: {line_count} posts")
        if line_count < target * 0.5:
            print(f"  Warning: Only {line_count} posts collected (target was {target})")
        update_status(task_id, 2, 'Data Scraping', 'completed',
                      f'{line_count} unique posts collected', start_time,
                      posts_collected=line_count, target_posts=target)
        return str(deduped_file)
    else:
        update_status(task_id, 2, 'Data Scraping', 'error',
                      'Deduped file not found after scraping', start_time)
        print("  Error: Deduped file not found after scraping")
        sys.exit(1)


def phase3_analyze(plan: dict, deduped_file: str, start_time: float = 0) -> str:
    """Phase 3: Quantitative Analysis — run the unified analyzer."""
    print()
    print("=" * 60)
    print("Phase 3: Quantitative Analysis")
    print("=" * 60)

    task_id = plan['task_id']
    update_status(task_id, 3, 'Quantitative Analysis', 'running',
                  'Running statistical analysis...', start_time)
    stats_file = DATA_ANALYZED / f"{task_id}_stats.json"
    focus = ','.join(plan.get('analysis_focus', []))

    print(f"  Input: {deduped_file}")
    print(f"  Output: {stats_file}")
    if focus:
        print(f"  Focus: {focus}")
    print()

    analyze_cmd = [
        sys.executable, str(PROJECT_ROOT / 'scripts' / 'analyze.py'),
        '--input', deduped_file,
        '--output', str(stats_file),
    ]
    if focus:
        analyze_cmd.extend(['--focus', focus])

    process = subprocess.Popen(
        analyze_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=str(PROJECT_ROOT),
    )

    for line in iter(process.stdout.readline, ''):
        print(f"  {line}", end='')
    process.wait()

    if not stats_file.exists():
        update_status(task_id, 3, 'Quantitative Analysis', 'error',
                      'Stats file not found after analysis', start_time)
        print("  Error: Stats file not found after analysis")
        sys.exit(1)

    update_status(task_id, 3, 'Quantitative Analysis', 'completed',
                  'Statistical analysis done', start_time)
    return str(stats_file)


def phase4_report(plan: dict, stats_file: str, start_time: float = 0) -> str:
    """Phase 4: Report Generation — use LLM to write the final report."""
    print()
    print("=" * 60)
    print("Phase 4: Report Generation")
    print("=" * 60)

    task_id = plan['task_id']
    update_status(task_id, 4, 'Report Generation', 'running',
                  'Calling Claude to generate report...', start_time)
    report_file = DATA_REPORTS / f"{task_id}_report.md"

    # Load stats
    with open(stats_file, 'r') as f:
        stats = json.load(f)

    # Load prompt template
    template_path = PROMPTS_DIR / 'generate_report.md'
    template = template_path.read_text(encoding='utf-8')

    # Prepare top posts content
    top_posts = stats.get('top_posts', [])
    top_posts_lines = []
    for i, p in enumerate(top_posts, 1):
        line = (
            f"{i}. [{p['title'][:100]}]({p['url']}) "
            f"(r/{p['subreddit']}, {p['upvotes']}↑, {p['comment_count']} comments)\n"
            f"   {p.get('selftext', '')[:300]}"
        )
        top_posts_lines.append(line)
    top_posts_content = '\n\n'.join(top_posts_lines)

    # Build stats JSON for prompt (exclude top_posts to save tokens)
    stats_for_prompt = {k: v for k, v in stats.items() if k != 'top_posts'}
    stats_json = json.dumps(stats_for_prompt, indent=2, ensure_ascii=False)

    # Fill template
    prompt = template.replace('{task_description}', plan.get('task_description', ''))
    prompt = prompt.replace('{stats_json}', stats_json)
    prompt = prompt.replace('{top_posts_content}', top_posts_content)
    prompt = prompt.replace('{top_n}', str(len(top_posts)))
    prompt = prompt.replace('{total_posts}', str(stats.get('total_posts', 0)))
    prompt = prompt.replace('{subreddit_count}', str(len(stats.get('subreddit_distribution', {}))))
    prompt = prompt.replace('{date_range}', ' ~ '.join(stats.get('date_range', ['N/A', 'N/A'])))
    prompt = prompt.replace('{report_date}', datetime.now().strftime('%Y-%m-%d'))

    print(f"  Calling Claude to generate report...")
    print(f"  Stats: {len(stats_json)} chars | Top posts: {len(top_posts)} entries")

    # Use longer timeout for report generation
    output = call_claude(prompt, timeout=600)

    if not output:
        print("  Error: Empty response from Claude")
        sys.exit(1)

    # Write report
    with open(report_file, 'w') as f:
        f.write(output)

    word_count = len(output)
    print(f"  Report saved: {report_file} ({word_count} chars)")

    update_status(task_id, 4, 'Report Generation', 'completed',
                  f'Report saved ({word_count} chars)', start_time,
                  report_file=str(report_file))
    return str(report_file)


def main():
    parser = argparse.ArgumentParser(
        description='Reddit 市场调研自动化 CLI 工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py "调研 AI 写作工具的市场需求"
  python run.py "从 r/writing 抓取 5000 条帖子，分析需求热度和定价"
  python run.py --task-id my_research_20260408 "AI writing tools market"
  python run.py --resume ai_writing_tools_20260408
  python run.py --resume ai_writing_tools_20260408 --from-phase 3
        """)

    parser.add_argument('task', nargs='?', help='Task description')
    parser.add_argument('--task-id', help='Override auto-generated task ID')
    parser.add_argument('--resume', metavar='TASK_ID', help='Resume a previous task by ID')
    parser.add_argument('--from-phase', type=int, choices=[1, 2, 3, 4], default=1,
                        help='Start from a specific phase (default: 1)')

    args = parser.parse_args()

    if not args.task and not args.resume:
        parser.print_help()
        sys.exit(1)

    ensure_dirs()

    start_time = time.time()

    if args.resume:
        # Resume mode: load existing plan
        task_id = args.resume
        plan_file = DATA_RAW / f"{task_id}_plan.json"
        if not plan_file.exists():
            print(f"Error: Plan file not found: {plan_file}")
            sys.exit(1)
        with open(plan_file, 'r') as f:
            plan = json.load(f)
        print(f"Resuming task: {task_id}")
        print(f"Description: {plan.get('task_description', 'N/A')}")
        from_phase = args.from_phase
    else:
        task_description = args.task
        print(f"Task: {task_description}")
        print()

        if args.from_phase > 1:
            print("Error: --from-phase > 1 requires --resume")
            sys.exit(1)

        # Phase 1
        plan = phase1_plan(task_description, task_id=args.task_id,
                           start_time=start_time)
        from_phase = 2  # Phase 1 done, continue from 2

    task_id = plan['task_id']
    deduped_file = str(DATA_RAW / f"{task_id}_deduped.jsonl")
    stats_file = str(DATA_ANALYZED / f"{task_id}_stats.json")

    # Phase 2
    if from_phase <= 2:
        deduped_file = phase2_scrape(plan, start_time=start_time)

    # Phase 3
    if from_phase <= 3:
        if not os.path.exists(deduped_file):
            print(f"Error: Deduped file not found: {deduped_file}")
            sys.exit(1)
        stats_file = phase3_analyze(plan, deduped_file, start_time=start_time)

    # Phase 4
    if from_phase <= 4:
        if not os.path.exists(stats_file):
            print(f"Error: Stats file not found: {stats_file}")
            sys.exit(1)
        report_file = phase4_report(plan, stats_file, start_time=start_time)

    # Summary
    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    print()
    print("=" * 60)
    print("Done!")
    print("=" * 60)
    print(f"  Task ID:  {task_id}")
    print(f"  Plan:     data/raw/{task_id}_plan.json")
    print(f"  Data:     data/raw/{task_id}_deduped.jsonl")
    print(f"  Stats:    data/analyzed/{task_id}_stats.json")
    print(f"  Report:   data/reports/{task_id}_report.md")
    print(f"  Status:   data/raw/{task_id}_status.json")
    print(f"  Time:     {minutes}m {seconds}s")

    update_status(task_id, 4, 'Done', 'done',
                  f'All phases completed in {minutes}m {seconds}s', start_time,
                  report_file=f'data/reports/{task_id}_report.md')


if __name__ == '__main__':
    main()
