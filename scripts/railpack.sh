#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

usage() {
  cat <<EOF
Usage: ./scripts/railpack.sh <command> [args]

Commands:
  install          Install the Railpack CLI from https://railpack.com/
  build            Run the build helpers (model-download / voice-download / all)
  run              Run the runtime helpers (start / stop / status / restart)
  help             Show this help
EOF
}

install_railpack() {
  if command -v railpack >/dev/null 2>&1; then
    echo "Railpack already installed: $(command -v railpack)"
    return 0
  fi

  echo "Installing Railpack from https://railpack.com/ ..."
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL https://railpack.com/install.sh | sh
  else
    echo "curl is required to install Railpack." >&2
    exit 1
  fi

  if command -v railpack >/dev/null 2>&1; then
    echo "Railpack installed successfully."
  else
    echo "Railpack installation finished but the binary is not on PATH yet. Open a new shell and retry." >&2
    exit 1
  fi
}

case "${1:-help}" in
  install)
    install_railpack
    ;;
  build)
    shift || true
    exec "$PROJECT_ROOT/scripts/build.sh" "$@"
    ;;
  run)
    shift || true
    exec "$PROJECT_ROOT/scripts/run.sh" "$@"
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "Unknown command: ${1:-}" >&2
    usage >&2
    exit 1
    ;;
 esac
