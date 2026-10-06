#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

usage() {
  cat <<EOF
Usage: ./scripts/build.sh <command>

Commands:
  model-download   Download the bucket model assets and sync them into german/models
  voice-download   Download/prepare the voice assets into german/voices
  all              Download models + voices and build the stack
  help             Show this help
EOF
}

ensure_layout() {
  mkdir -p "$PROJECT_ROOT/german/models" "$PROJECT_ROOT/german/voices"
}

model_download() {
  ensure_layout
  cd "$PROJECT_ROOT"
  docker compose run --rm model-voice-assets
}

voice_download() {
  ensure_layout
  cd "$PROJECT_ROOT"
  docker compose run --rm model-voice-assets
}

all_build() {
  ensure_layout
  cd "$PROJECT_ROOT"
  docker compose build
  docker compose run --rm model-voice-assets
}

case "${1:-help}" in
  model-download)
    model_download
    ;;
  voice-download)
    voice_download
    ;;
  all)
    all_build
    ;;
  build)
    all_build
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "Unknown build command: ${1:-}" >&2
    usage >&2
    exit 1
    ;;
 esac
