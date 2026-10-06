#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

usage() {
  cat <<EOF
Usage: ./scripts/run.sh <command>

Commands:
  start       Start the stack in the background
  stop        Stop the stack
  status      Show running services
  restart     Restart the stack
  logs        Show logs
  help        Show this help
EOF
}

start_stack() {
  cd "$PROJECT_ROOT"
  docker compose up --build -d
}

stop_stack() {
  cd "$PROJECT_ROOT"
  docker compose down
}

status_stack() {
  cd "$PROJECT_ROOT"
  docker compose ps
}

restart_stack() {
  cd "$PROJECT_ROOT"
  docker compose restart
}

logs_stack() {
  cd "$PROJECT_ROOT"
  docker compose logs -f
}

case "${1:-help}" in
  start)
    start_stack
    ;;
  stop)
    stop_stack
    ;;
  status)
    status_stack
    ;;
  restart)
    restart_stack
    ;;
  logs)
    logs_stack
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "Unknown runtime command: ${1:-}" >&2
    usage >&2
    exit 1
    ;;
 esac
