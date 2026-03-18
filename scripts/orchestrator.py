#!/usr/bin/env python3
"""
Reddit AI Agent Research — Orchestrator Script

主控编排脚本，按顺序调度各 Agent 完成数据采集和分析流水线。
支持 review 循环（最多 3 轮）和 QA 返工循环（最多 2 轮）。

使用方式：
    python3 scripts/orchestrator.py

前置条件：
    - 已安装 Claude Code CLI（claude 命令可用）
    - 已配置 Playwright MCP 工具
    - config/search_config.json 已就绪
    - docs/architecture.md 已就绪
    - agents/*.md Agent prompt 文件已就绪
"""

import enum
import json
import logging
import subprocess
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# 项目根目录（脚本位于 scripts/ 下，项目根目录在上一级）
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)

# ---------------------------------------------------------------------------
# 日志配置
# ---------------------------------------------------------------------------
LOG_DIR = PROJECT_ROOT / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

log_file = LOG_DIR / f"orchestrator_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8"),
    ],
)
logger = logging.getLogger("orchestrator")


# ---------------------------------------------------------------------------
# Phase 枚举
# ---------------------------------------------------------------------------
class Phase(enum.Enum):
    ARCH_DESIGN = "Phase 1: Architecture Design & Review"
    CODE_IMPL = "Phase 2: Code Implementation & Review"
    QA_TEST = "Phase 3: QA Smoke Test"
    SCRAPING = "Phase 4: Data Scraping"
    ANALYSIS = "Phase 5: Data Analysis & Report"


# ---------------------------------------------------------------------------
# Agent 调度
# ---------------------------------------------------------------------------
MAX_REVIEW_ROUNDS = 3
MAX_QA_REWORK_ROUNDS = 2


def dispatch_agent(agent_name: str, prompt_file: str, extra_context: str = "") -> dict:
    """
    调度一个 Agent 执行任务。

    通过 Claude Code CLI 启动一个子 Agent，传入对应的 prompt 文件内容作为指令。

    Args:
        agent_name: Agent 名称（用于日志）
        prompt_file: Agent prompt 文件的相对路径（如 agents/scraper.md）
        extra_context: 额外上下文信息（如 review 反馈）

    Returns:
        dict: {"success": bool, "output": str, "passed": bool | None}
    """
    prompt_path = PROJECT_ROOT / prompt_file
    if not prompt_path.exists():
        logger.error(f"Agent prompt file not found: {prompt_path}")
        return {"success": False, "output": f"File not found: {prompt_path}", "passed": None}

    prompt_content = prompt_path.read_text(encoding="utf-8")

    # 构造完整指令
    instruction = prompt_content
    if extra_context:
        instruction += f"\n\n---\n\n## 额外上下文\n\n{extra_context}"

    logger.info(f"Dispatching {agent_name} ...")
    logger.info(f"  Prompt file: {prompt_file}")

    try:
        result = subprocess.run(
            [
                "claude",
                "--print",       # 非交互模式，直接输出结果
                "--prompt", instruction,
            ],
            capture_output=True,
            text=True,
            timeout=14400,  # 4 小时超时（Scraper 可能需要较长时间）
            cwd=str(PROJECT_ROOT),
        )

        output = result.stdout.strip()
        if result.returncode != 0:
            logger.warning(f"{agent_name} exited with code {result.returncode}")
            if result.stderr:
                logger.warning(f"  stderr: {result.stderr[:500]}")

        # 判断是否通过（用于 Review Agent）
        passed = None
        output_lower = output.lower()
        if "pass" in output_lower and "reject" not in output_lower:
            passed = True
        elif "reject" in output_lower or "not pass" in output_lower:
            passed = False

        logger.info(f"{agent_name} completed. Output length: {len(output)} chars. Passed: {passed}")
        return {"success": result.returncode == 0, "output": output, "passed": passed}

    except subprocess.TimeoutExpired:
        logger.error(f"{agent_name} timed out after 4 hours")
        return {"success": False, "output": "Agent timed out", "passed": None}
    except FileNotFoundError:
        logger.error("Claude CLI not found. Please install Claude Code and ensure 'claude' is in PATH.")
        return {"success": False, "output": "Claude CLI not found", "passed": None}
    except Exception as e:
        logger.error(f"{agent_name} failed with exception: {e}")
        return {"success": False, "output": str(e), "passed": None}


def escalate_to_user(phase: Phase, latest_output: str, all_feedback: list[str]):
    """
    Review 循环耗尽时，暂停流水线并将信息呈现给用户。
    """
    logger.warning("=" * 60)
    logger.warning(f"ESCALATION: {phase.value} — review 循环已达上限 ({MAX_REVIEW_ROUNDS} 轮)")
    logger.warning("=" * 60)
    logger.warning("最近一轮输出（截取前 2000 字符）：")
    logger.warning(latest_output[:2000])
    logger.warning("-" * 60)
    for i, fb in enumerate(all_feedback, 1):
        logger.warning(f"Review 反馈 #{i}（截取前 1000 字符）：")
        logger.warning(fb[:1000])
        logger.warning("-" * 40)
    logger.warning("=" * 60)
    logger.warning("请手动检查并决定是否继续。")
    logger.warning("如需继续，请修复问题后重新运行此脚本。")
    sys.exit(1)


# ---------------------------------------------------------------------------
# 各 Phase 执行逻辑
# ---------------------------------------------------------------------------

def run_phase_1_arch():
    """Phase 1: 架构设计 + 审核（最多 3 轮）"""
    logger.info("=" * 60)
    logger.info(f"Starting {Phase.ARCH_DESIGN.value}")
    logger.info("=" * 60)

    # 检查架构文档是否已存在（可能之前已完成）
    arch_doc = PROJECT_ROOT / "docs" / "architecture.md"
    if arch_doc.exists() and arch_doc.stat().st_size > 1000:
        logger.info("Architecture doc already exists, skipping Phase 1.")
        return True

    all_feedback = []
    for round_num in range(1, MAX_REVIEW_ROUNDS + 1):
        logger.info(f"--- Arch Design Round {round_num}/{MAX_REVIEW_ROUNDS} ---")

        # 调度 Architect
        feedback_ctx = ""
        if all_feedback:
            feedback_ctx = "之前的 review 反馈：\n" + "\n---\n".join(all_feedback)

        arch_result = dispatch_agent("Architect", "agents/architect.md", feedback_ctx)
        if not arch_result["success"]:
            logger.error("Architect Agent failed.")
            return False

        # 调度 Arch Reviewer
        review_result = dispatch_agent("Arch Reviewer", "agents/arch_reviewer.md")
        if review_result["passed"]:
            logger.info(f"Architecture review PASSED on round {round_num}.")
            return True

        all_feedback.append(review_result["output"])
        logger.warning(f"Architecture review REJECTED on round {round_num}.")

    # 3 轮未通过
    escalate_to_user(Phase.ARCH_DESIGN, arch_result["output"], all_feedback)
    return False  # 不会执行到这里


def run_phase_2_code():
    """Phase 2: 编码实现 + 审核（最多 3 轮）"""
    logger.info("=" * 60)
    logger.info(f"Starting {Phase.CODE_IMPL.value}")
    logger.info("=" * 60)

    # 检查 Agent prompt 文件是否已存在
    required_files = [
        "agents/scraper.md",
        "agents/analyst.md",
        "agents/qa.md",
    ]
    all_exist = all((PROJECT_ROOT / f).exists() for f in required_files)
    if all_exist:
        logger.info("Agent prompt files already exist, skipping Phase 2.")
        return True

    all_feedback = []
    for round_num in range(1, MAX_REVIEW_ROUNDS + 1):
        logger.info(f"--- Code Implementation Round {round_num}/{MAX_REVIEW_ROUNDS} ---")

        feedback_ctx = ""
        if all_feedback:
            feedback_ctx = "之前的 review 反馈：\n" + "\n---\n".join(all_feedback)

        code_result = dispatch_agent("Coder", "agents/coder.md", feedback_ctx)
        if not code_result["success"]:
            logger.error("Coder Agent failed.")
            return False

        review_result = dispatch_agent("Code Reviewer", "agents/code_reviewer.md")
        if review_result["passed"]:
            logger.info(f"Code review PASSED on round {round_num}.")
            return True

        all_feedback.append(review_result["output"])
        logger.warning(f"Code review REJECTED on round {round_num}.")

    escalate_to_user(Phase.CODE_IMPL, code_result["output"], all_feedback)
    return False


def run_phase_3_qa():
    """Phase 3: QA 冒烟测试 + 返工循环（最多 2 轮）"""
    logger.info("=" * 60)
    logger.info(f"Starting {Phase.QA_TEST.value}")
    logger.info("=" * 60)

    for rework_round in range(1, MAX_QA_REWORK_ROUNDS + 1):
        logger.info(f"--- QA Test Round {rework_round}/{MAX_QA_REWORK_ROUNDS} ---")

        qa_result = dispatch_agent("QA", "agents/qa.md")
        if not qa_result["success"]:
            logger.error("QA Agent failed to execute.")
            if rework_round < MAX_QA_REWORK_ROUNDS:
                logger.info("Sending QA failure back to Coder for rework...")
                rework_ctx = f"QA 测试失败，请修复以下问题：\n\n{qa_result['output']}"
                dispatch_agent("Coder (rework)", "agents/coder.md", rework_ctx)
                continue
            else:
                logger.error("QA rework rounds exhausted.")
                escalate_to_user(Phase.QA_TEST, qa_result["output"], [qa_result["output"]])
                return False

        # 检查 QA 结果文件
        qa_report_path = PROJECT_ROOT / "data" / "reports" / "qa_result.json"
        if qa_report_path.exists():
            try:
                qa_data = json.loads(qa_report_path.read_text(encoding="utf-8"))
                if qa_data.get("passed", False):
                    logger.info(f"QA PASSED on round {rework_round}. "
                                f"{qa_data.get('passed_tests', '?')}/{qa_data.get('total_tests', '?')} tests passed.")
                    return True
                else:
                    failures = qa_data.get("failures", [])
                    failure_summary = "\n".join(
                        f"  - Test {f.get('test_id')}: {f.get('name')} — {f.get('error', 'unknown')}"
                        for f in failures
                    )
                    logger.warning(f"QA FAILED on round {rework_round}:\n{failure_summary}")

                    if rework_round < MAX_QA_REWORK_ROUNDS:
                        logger.info("Sending QA failures back to Coder for rework...")
                        rework_ctx = (
                            f"QA 测试未通过，以下测试失败：\n{failure_summary}\n\n"
                            f"完整 QA 报告：\n{json.dumps(qa_data, indent=2, ensure_ascii=False)}"
                        )
                        dispatch_agent("Coder (rework)", "agents/coder.md", rework_ctx)
                        continue
                    else:
                        logger.error("QA rework rounds exhausted.")
                        escalate_to_user(Phase.QA_TEST, json.dumps(qa_data, indent=2), [failure_summary])
                        return False
            except json.JSONDecodeError:
                logger.warning("QA result file is not valid JSON.")
        else:
            logger.warning("QA result file not found. Checking agent output for pass/fail...")
            if qa_result.get("passed"):
                logger.info("QA appears to have passed (based on output text).")
                return True
            elif rework_round < MAX_QA_REWORK_ROUNDS:
                rework_ctx = f"QA 测试结果不明确，请重新检查：\n\n{qa_result['output'][:3000]}"
                dispatch_agent("Coder (rework)", "agents/coder.md", rework_ctx)
                continue

    logger.error("QA testing failed after all rework rounds.")
    return False


def run_phase_4_scraping():
    """Phase 4: 数据抓取"""
    logger.info("=" * 60)
    logger.info(f"Starting {Phase.SCRAPING.value}")
    logger.info("=" * 60)

    # 检查是否已有足够数据
    posts_file = PROJECT_ROOT / "data" / "raw" / "posts_raw.jsonl"
    if posts_file.exists():
        line_count = sum(1 for line in posts_file.read_text().splitlines() if line.strip())
        logger.info(f"Existing data: {line_count} posts in posts_raw.jsonl")
        if line_count >= 100:
            logger.info("Sufficient data already exists. Skipping scraping or resuming from checkpoint.")

    # 确保数据目录存在
    (PROJECT_ROOT / "data" / "raw").mkdir(parents=True, exist_ok=True)

    result = dispatch_agent("Scraper", "agents/scraper.md")
    if not result["success"]:
        logger.error("Scraper Agent failed.")
        # Scraper 支持断点续抓，不一定需要从头重来
        logger.info("Scraper may have made partial progress. Check data/raw/progress.json")

    # 验证输出
    if posts_file.exists():
        line_count = sum(1 for line in posts_file.read_text().splitlines() if line.strip())
        logger.info(f"Scraping result: {line_count} posts collected.")
        if line_count == 0:
            logger.error("No posts collected. Scraping may have completely failed.")
            return False
        return True
    else:
        logger.error("posts_raw.jsonl not found after scraping.")
        return False


def run_phase_5_analysis():
    """Phase 5: 数据分析与报告"""
    logger.info("=" * 60)
    logger.info(f"Starting {Phase.ANALYSIS.value}")
    logger.info("=" * 60)

    # 确保数据目录存在
    (PROJECT_ROOT / "data" / "analyzed").mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "data" / "reports").mkdir(parents=True, exist_ok=True)

    result = dispatch_agent("Analyst", "agents/analyst.md")
    if not result["success"]:
        logger.error("Analyst Agent failed.")
        return False

    # 验证输出文件
    expected_outputs = [
        "data/analyzed/posts_analyzed.json",
        "data/analyzed/posts_analyzed.csv",
        "data/reports/analysis_report.md",
    ]

    all_present = True
    for output_file in expected_outputs:
        path = PROJECT_ROOT / output_file
        if path.exists():
            size = path.stat().st_size
            logger.info(f"  Output: {output_file} ({size} bytes)")
        else:
            logger.error(f"  Missing output: {output_file}")
            all_present = False

    return all_present


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def main():
    """主控编排流程"""
    start_time = datetime.now(timezone.utc)
    logger.info("=" * 60)
    logger.info("Reddit AI Agent Research — Orchestrator")
    logger.info(f"Start time: {start_time.isoformat()}")
    logger.info(f"Project root: {PROJECT_ROOT}")
    logger.info("=" * 60)

    # 依次执行各 Phase
    phases = [
        ("Phase 1", run_phase_1_arch),
        ("Phase 2", run_phase_2_code),
        ("Phase 3", run_phase_3_qa),
        ("Phase 4", run_phase_4_scraping),
        ("Phase 5", run_phase_5_analysis),
    ]

    for phase_name, phase_fn in phases:
        try:
            success = phase_fn()
            if not success:
                logger.error(f"{phase_name} failed. Pipeline stopped.")
                sys.exit(1)
            logger.info(f"{phase_name} completed successfully.")
        except SystemExit:
            raise  # 让 escalate_to_user 的 sys.exit 传播
        except Exception as e:
            logger.error(f"{phase_name} encountered an unexpected error: {e}", exc_info=True)
            sys.exit(1)

    # 全部完成
    end_time = datetime.now(timezone.utc)
    duration = end_time - start_time
    logger.info("=" * 60)
    logger.info("Pipeline completed successfully!")
    logger.info(f"End time: {end_time.isoformat()}")
    logger.info(f"Total duration: {duration}")
    logger.info("=" * 60)
    logger.info("Output files:")
    logger.info("  - data/raw/posts_raw.jsonl        (raw scraped data)")
    logger.info("  - data/analyzed/posts_analyzed.json (analyzed data)")
    logger.info("  - data/analyzed/posts_analyzed.csv  (CSV format)")
    logger.info("  - data/reports/analysis_report.md   (final report)")


if __name__ == "__main__":
    main()
