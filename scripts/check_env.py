#!/usr/bin/env python3
"""
环境检查脚本 — 安装后运行，验证所有依赖是否就绪。

用法：
    python scripts/check_env.py
    reddit-research --check  (安装后)
"""

import shutil
import subprocess
import sys


def check(name, ok, hint=""):
    status = "OK" if ok else "MISSING"
    symbol = "+" if ok else "-"
    line = f"  [{symbol}] {name}: {status}"
    if not ok and hint:
        line += f"  ({hint})"
    print(line)
    return ok


def main():
    print("Reddit Research — 环境检查")
    print("=" * 50)
    all_ok = True

    # Python version
    v = sys.version_info
    all_ok &= check(
        f"Python {v.major}.{v.minor}.{v.micro}",
        v >= (3, 9),
        "需要 Python 3.9+"
    )

    # Claude Code CLI
    claude_path = shutil.which("claude")
    all_ok &= check(
        "Claude Code CLI",
        claude_path is not None,
        "安装: npm install -g @anthropic-ai/claude-code"
    )

    if claude_path:
        try:
            result = subprocess.run(
                [claude_path, "--version"],
                capture_output=True, text=True, timeout=10
            )
            ver = result.stdout.strip() or result.stderr.strip()
            print(f"        版本: {ver[:80]}")
        except Exception:
            pass

    # Python packages
    pkgs = {
        "markdown2": "pip install markdown2",
        "weasyprint": "pip install weasyprint (macOS 需先 brew install pango)",
    }
    for pkg, hint in pkgs.items():
        try:
            __import__(pkg)
            all_ok &= check(f"Python 包: {pkg}", True)
        except ImportError:
            all_ok &= check(f"Python 包: {pkg}", False, hint)

    # System libs (weasyprint needs pango)
    pango = shutil.which("pango-view") or shutil.which("pango-list")
    if not pango:
        # Try ldconfig or pkg-config as fallback
        try:
            r = subprocess.run(
                ["pkg-config", "--exists", "pangocairo"],
                capture_output=True, timeout=5
            )
            pango = r.returncode == 0
        except Exception:
            pango = False
    all_ok &= check(
        "系统库: pango",
        bool(pango),
        "macOS: brew install pango | Linux: apt install libpango-1.0-0"
    )

    # Project structure
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    dirs = ["config", "prompts", "scripts", "data"]
    for d in dirs:
        p = root / d
        all_ok &= check(f"目录: {d}/", p.is_dir(), f"mkdir -p {d}")

    # Corpus data
    corpus_dir = root / "data" / "corpus"
    if corpus_dir.is_dir():
        jsonl_count = len(list(corpus_dir.glob("*.jsonl")))
        if jsonl_count > 0:
            check(f"语料库: {jsonl_count} 个 subreddit", True)
        else:
            check("语料库: 空", False,
                  "python scripts/corpus_build.py --list config/corpus_subreddits.txt")
    else:
        check("语料库: 未构建", False,
              "python scripts/corpus_build.py --list config/corpus_subreddits.txt")

    print()
    if all_ok:
        print("所有检查通过，可以开始使用:")
        print('  reddit-research "调研 AI 写作工具的市场需求"')
    else:
        print("请先修复上述 MISSING 项，再运行工具。")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
