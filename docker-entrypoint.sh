#!/bin/bash
set -e

if [ $# -gt 0 ]; then
    exec uv run --no-dev "$@"
fi

echo "╔══════════════════════════════════════════╗"
echo "║     Kronos — Docker Quickstart          ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "首次运行会先准备 Python 研究环境，然后生成一份 sample 流程试跑报告。"
echo "如果看到依赖安装或下载输出，只要最后出现结果卡，就是正常流程。"
echo ""

uv run --no-dev kronos quickstart

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  quickstart 完成！"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
