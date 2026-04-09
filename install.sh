#!/bin/bash
set -e

echo "========================================"
echo "Reddit Research — 安装脚本"
echo "========================================"
echo

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"

# 1. Python version check
echo "[1/5] 检查 Python..."
if ! command -v python3 &>/dev/null; then
    echo "  ERROR: 未找到 python3，请先安装 Python 3.9+"
    echo "  macOS:  brew install python@3.12"
    echo "  Linux:  sudo apt install python3 python3-pip python3-venv"
    exit 1
fi

PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "  Python $PY_VER"

# 2. System dependencies (pango for weasyprint)
echo "[2/5] 检查系统依赖..."
if [[ "$(uname)" == "Darwin" ]]; then
    if ! brew list pango &>/dev/null 2>&1; then
        echo "  安装 pango (WeasyPrint 依赖)..."
        brew install pango
    else
        echo "  pango: OK"
    fi
elif command -v apt &>/dev/null; then
    if ! dpkg -l libpango-1.0-0 &>/dev/null 2>&1; then
        echo "  安装 pango (WeasyPrint 依赖)..."
        sudo apt install -y libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0
    else
        echo "  pango: OK"
    fi
fi

# 3. Create venv and install Python deps
echo "[3/5] 创建虚拟环境并安装 Python 依赖..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
pip install -e "$PROJECT_DIR" --quiet
echo "  已安装到 $VENV_DIR"

# 4. Claude Code CLI
echo "[4/5] 检查 Claude Code CLI..."
if command -v claude &>/dev/null; then
    CLAUDE_VER=$(claude --version 2>/dev/null || echo "unknown")
    echo "  Claude Code: $CLAUDE_VER"
else
    echo "  WARNING: Claude Code CLI 未找到"
    echo "  安装: npm install -g @anthropic-ai/claude-code"
    echo "  安装后运行 'claude' 完成登录"
fi

# 5. Create convenience wrapper
echo "[5/5] 创建启动脚本..."
WRAPPER="$PROJECT_DIR/reddit-research"
cat > "$WRAPPER" << 'WRAPPER_EOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/.venv/bin/activate"
python "$SCRIPT_DIR/run.py" "$@"
WRAPPER_EOF
chmod +x "$WRAPPER"
echo "  已创建: $WRAPPER"

# Done
echo
echo "========================================"
echo "安装完成!"
echo "========================================"
echo
echo "使用方式:"
echo "  ./reddit-research --check                      # 环境检查"
echo "  ./reddit-research \"调研 AI 写作工具的市场需求\"    # 运行调研"
echo "  ./reddit-research --online \"...\"               # 在线抓取模式"
echo "  ./reddit-research --no-pdf \"...\"               # 仅输出 Markdown"
echo "  ./reddit-research --resume <task_id>           # 恢复中断任务"
echo
echo "首次使用建议先构建语料库（约 30 分钟）:"
echo "  source .venv/bin/activate"
echo "  python scripts/corpus_build.py --list config/corpus_subreddits.txt"
