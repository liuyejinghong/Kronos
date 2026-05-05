#!/bin/bash
set -e

echo "╔══════════════════════════════════════════╗"
echo "║     Kronos — Docker Quickstart          ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Run quickstart
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
