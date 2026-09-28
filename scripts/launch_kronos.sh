#!/usr/bin/env bash
# Kronos v0.5.0 一键启动器（macOS / Linux）。
#
# 用法:
#   scripts/launch_kronos.sh          # 启动（幂等：已在运行的服务不会重复启动）
#   scripts/launch_kronos.sh stop     # 停止后台与前端
#   scripts/launch_kronos.sh status   # 查看运行状态
#
# 行为:
# - 后端: uv run kronos web --port 8000（nohup 后台运行，日志与 pid 存于 .tools/）。
#   v0.5.0 的对话任务 worker 运行在后端进程内，无需单独进程。
# - 前端: web/node_modules 存在时启动 next dev（127.0.0.1:3000）；缺失时打印安装提示并跳过。
# - 就绪后自动打开 http://127.0.0.1:3000。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS_DIR="$ROOT/.tools"
BACKEND_PID_FILE="$TOOLS_DIR/kronos-web-backend.pid"
FRONTEND_PID_FILE="$TOOLS_DIR/kronos-web-frontend.pid"
BACKEND_LOG="$TOOLS_DIR/kronos-web-backend.log"
FRONTEND_LOG="$TOOLS_DIR/kronos-web-frontend.log"

BACKEND_PORT="${KRONOS_WEB_PORT:-8000}"
FRONTEND_PORT="${KRONOS_WEB_FRONTEND_PORT:-3000}"
BACKEND_URL="http://127.0.0.1:$BACKEND_PORT"
FRONTEND_URL="http://127.0.0.1:$FRONTEND_PORT"
BACKEND_WAIT_S="${KRONOS_LAUNCH_WAIT_S:-90}"

info() { printf '%s\n' "$*"; }
warn() { printf '警告: %s\n' "$*" >&2; }

ensure_tools_dir() { mkdir -p "$TOOLS_DIR"; }

read_pid() {
  local pid=""
  if [ -f "$1" ]; then
    pid="$(tr -dc '0-9' <"$1" 2>/dev/null || true)"
  fi
  printf '%s' "$pid"
}

pid_alive() {
  local pid="$1"
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

backend_healthy() {
  curl -fsS --max-time 2 "$BACKEND_URL/api/health" >/dev/null 2>&1
}

frontend_up() {
  curl -fsS --max-time 2 "$FRONTEND_URL" >/dev/null 2>&1
}

wait_for() {
  # wait_for <check_fn> <名称> <超时秒>
  local check_fn="$1" name="$2" timeout="$3" waited=0
  until "$check_fn"; do
    if [ "$waited" -ge "$timeout" ]; then
      warn "$name 在 ${timeout}s 内未就绪，请查看 $TOOLS_DIR 下的日志。"
      return 1
    fi
    sleep 2
    waited=$((waited + 2))
  done
}

start_backend() {
  if backend_healthy; then
    info "后端已在运行: $BACKEND_URL"
    return 0
  fi
  local pid
  pid="$(read_pid "$BACKEND_PID_FILE")"
  if pid_alive "$pid"; then
    info "后端进程已存在 (pid $pid)，等待健康检查…"
  else
    ensure_tools_dir
    info "启动后端: uv run kronos web --port $BACKEND_PORT (日志: $BACKEND_LOG)"
    (
      cd "$ROOT"
      nohup uv run kronos web --port "$BACKEND_PORT" >>"$BACKEND_LOG" 2>&1 &
      echo $! >"$BACKEND_PID_FILE"
    )
  fi
  wait_for backend_healthy "后端 API" "$BACKEND_WAIT_S"
  info "后端就绪: $BACKEND_URL (API 文档: $BACKEND_URL/api/docs)"
}

start_frontend() {
  if frontend_up; then
    info "前端已在运行: $FRONTEND_URL"
    return 0
  fi
  if [ ! -d "$ROOT/web/node_modules" ]; then
    warn "web/node_modules 不存在，已跳过前端启动。请先执行: cd web && npm install"
    return 1
  fi
  local pid
  pid="$(read_pid "$FRONTEND_PID_FILE")"
  if ! pid_alive "$pid"; then
    ensure_tools_dir
    info "启动前端: npm run dev -- -H 127.0.0.1 -p $FRONTEND_PORT (日志: $FRONTEND_LOG)"
    (
      cd "$ROOT/web"
      nohup npm run dev -- -H 127.0.0.1 -p "$FRONTEND_PORT" >>"$FRONTEND_LOG" 2>&1 &
      echo $! >"$FRONTEND_PID_FILE"
    )
  else
    info "前端进程已存在 (pid $pid)，等待就绪…"
  fi
  if wait_for frontend_up "前端" 60; then
    info "前端就绪: $FRONTEND_URL"
    return 0
  fi
  return 1
}

open_browser() {
  local url="$1"
  case "$(uname -s)" in
    Darwin) open "$url" 2>/dev/null || true ;;
    Linux) xdg-open "$url" 2>/dev/null || true ;;
    *) info "请手动打开: $url" ;;
  esac
}

stop_one() {
  # stop_one <pid文件> <名称>
  local pid_file="$1" name="$2" pid waited=0
  pid="$(read_pid "$pid_file")"
  if pid_alive "$pid"; then
    info "停止 $name (pid $pid)…"
    kill "$pid" 2>/dev/null || true
    # uv/npm 会派生子进程，一并回收。
    pkill -TERM -P "$pid" 2>/dev/null || true
    while pid_alive "$pid" && [ "$waited" -lt 10 ]; do
      sleep 1
      waited=$((waited + 1))
    done
    if pid_alive "$pid"; then
      warn "$name 未在 10s 内退出，强制结束。"
      kill -9 "$pid" 2>/dev/null || true
      pkill -KILL -P "$pid" 2>/dev/null || true
    fi
  else
    info "$name 未在运行。"
  fi
  rm -f "$pid_file"
}

cmd_start() {
  start_backend
  if start_frontend; then
    open_browser "$FRONTEND_URL"
  else
    info "前端未启动，可先使用后端 API: $BACKEND_URL/api/docs"
  fi
}

cmd_stop() {
  stop_one "$FRONTEND_PID_FILE" "前端"
  stop_one "$BACKEND_PID_FILE" "后端"
  if backend_healthy; then
    warn "端口 $BACKEND_PORT 仍有服务响应，可能有残留进程占用，请手动检查。"
  fi
}

cmd_status() {
  local backend_pid frontend_pid
  backend_pid="$(read_pid "$BACKEND_PID_FILE")"
  frontend_pid="$(read_pid "$FRONTEND_PID_FILE")"

  if backend_healthy; then
    info "后端: 运行中  $BACKEND_URL  (pid ${backend_pid:-未知})"
  elif pid_alive "$backend_pid"; then
    info "后端: 进程存在但未就绪 (pid $backend_pid)，日志: $BACKEND_LOG"
  else
    info "后端: 未运行"
  fi

  if frontend_up; then
    info "前端: 运行中  $FRONTEND_URL  (pid ${frontend_pid:-未知})"
  elif pid_alive "$frontend_pid"; then
    info "前端: 进程存在但未就绪 (pid $frontend_pid)，日志: $FRONTEND_LOG"
  else
    info "前端: 未运行"
  fi
}

case "${1:-start}" in
  start) cmd_start ;;
  stop) cmd_stop ;;
  status) cmd_status ;;
  *)
    info "用法: scripts/launch_kronos.sh [start|stop|status]"
    exit 2
    ;;
esac
