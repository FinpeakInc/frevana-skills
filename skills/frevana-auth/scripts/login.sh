#!/usr/bin/env bash

set -euo pipefail

DEFAULT_INSTALL_PACKAGE="@frevana/frevana"
DEFAULT_SERVER_URL="https://api.frevana.com"
SERVER_URL="$DEFAULT_SERVER_URL"

usage() {
  cat <<'EOF'
Usage:
  login.sh [--server <url>]

Behavior:
  - Starts the device authorization flow with `frevana login --server <url>`
  - If `frevana` is unavailable, attempts to install it with `npm i -g @frevana/frevana` and retries
  - Prints the local credentials path when it exists

Options:
  --server <url>  Frevana server URL to pass to `frevana login` (default: https://api.frevana.com)
  -h, --help      Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --server)
      SERVER_URL="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

run_login() {
  frevana login --server "$SERVER_URL"
}

run_login_capture() {
  local login_status
  set +e
  run_login
  login_status=$?
  set -e
  return "$login_status"
}

if run_login_capture; then
  LOGIN_STATUS=0
else
  LOGIN_STATUS=$?
  if [[ "$LOGIN_STATUS" -ne 126 && "$LOGIN_STATUS" -ne 127 ]]; then
    exit "$LOGIN_STATUS"
  fi

  if ! command -v npm >/dev/null 2>&1; then
    echo "frevana is unavailable and npm was not found in PATH. Install Node.js/npm first." >&2
    exit 1
  fi

  echo "frevana was unavailable. Installing $DEFAULT_INSTALL_PACKAGE..." >&2
  if ! npm i -g "$DEFAULT_INSTALL_PACKAGE"; then
    echo "Failed to install $DEFAULT_INSTALL_PACKAGE." >&2
    echo "Verify that the package exists in your npm registry, or provide the correct private registry or local package source." >&2
    exit 1
  fi

  hash -r
  if run_login_capture; then
    LOGIN_STATUS=0
  else
    LOGIN_STATUS=$?
    if [[ "$LOGIN_STATUS" -eq 126 || "$LOGIN_STATUS" -eq 127 ]]; then
      echo "frevana is still unavailable in PATH after installation." >&2
    fi
    exit "$LOGIN_STATUS"
  fi
fi

CONFIG_PATH="$HOME/.frevana/cli-config.json"
if [[ -f "$CONFIG_PATH" ]]; then
  echo "Credentials saved to: $CONFIG_PATH"
fi
