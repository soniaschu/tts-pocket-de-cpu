#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

usage() {
  cat <<EOF
Usage: ./scripts/railpack.sh <command> [args]

Commands:
  install          Install the official Railpack CLI from https://github.com/railwayapp/railpack
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

  if ! command -v curl >/dev/null 2>&1; then
    echo "curl is required to install Railpack." >&2
    exit 1
  fi

  local latest_tag
  if latest_tag="$(curl -fsSL https://api.github.com/repos/railwayapp/railpack/releases/latest | python3 -c 'import sys, json; data=json.load(sys.stdin); print(data.get("tag_name",""))' 2>/dev/null)" && [ -n "$latest_tag" ]; then
    echo "Installing official Railpack release ${latest_tag} from GitHub..."
  else
    echo "Unable to query the official release metadata; falling back to the upstream installer script."
    curl -fsSL https://railpack.com/install.sh | sh
    return 0
  fi

  local os_name arch_name asset_name asset_url tmpdir install_dir binary_path
  os_name="$(uname -s)"
  arch_name="$(uname -m)"

  case "$os_name" in
    Linux)
      os_name="unknown-linux-musl"
      ;;
    Darwin)
      os_name="apple-darwin"
      ;;
    *)
      echo "Unsupported OS for Railpack install: $os_name" >&2
      exit 1
      ;;
  esac

  case "$arch_name" in
    x86_64|amd64)
      arch_name="x86_64"
      ;;
    arm64|aarch64)
      arch_name="arm64"
      ;;
    *)
      echo "Unsupported architecture for Railpack install: $arch_name" >&2
      exit 1
      ;;
  esac

  asset_name="railpack-${latest_tag}-${arch_name}-${os_name}.tar.gz"
  asset_url="https://github.com/railwayapp/railpack/releases/download/${latest_tag}/${asset_name}"

  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN
  curl -fsSL "$asset_url" -o "$tmpdir/railpack.tar.gz"
  tar -xzf "$tmpdir/railpack.tar.gz" -C "$tmpdir"

  binary_path="$(find "$tmpdir" -type f -name railpack -perm /111 | head -n 1)"
  if [ -z "$binary_path" ]; then
    echo "Railpack binary was not found in the downloaded archive." >&2
    exit 1
  fi

  if [ "$(id -u)" -eq 0 ] || [ -w "/usr/local/bin" ]; then
    install_dir="/usr/local/bin"
  else
    install_dir="$HOME/.local/bin"
    mkdir -p "$install_dir"
  fi

  install -m 755 "$binary_path" "$install_dir/railpack"
  echo "Railpack installed successfully to $install_dir/railpack"

  if [ "$install_dir" = "$HOME/.local/bin" ]; then
    echo "Add this to your shell profile if needed: export PATH=\"$HOME/.local/bin:\$PATH\""
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
