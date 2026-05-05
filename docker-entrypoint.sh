#!/bin/bash
set -e

if [ $# -gt 0 ]; then
    exec uv run --no-dev "$@"
fi

echo "╔══════════════════════════════════════════╗"
echo "║     Kronos — Docker Quickstart          ║"
echo "╚══════════════════════════════════════════╝"
echo ""

uv run --no-dev kronos quickstart

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  quickstart 完成！"
echo ""
echo "  报告保存在 Docker volume 中："
echo "  docker compose run --rm kronos ls /kronos/reports/research/experiments/"
echo ""
echo "  下次启动交互式 Agent："
echo "  docker compose run --rm kronos uv run kronos agent start"
echo ""
echo "  查看实时日志："
echo "  docker compose logs kronos"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
