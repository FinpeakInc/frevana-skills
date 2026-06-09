#!/usr/bin/env bash

set -euo pipefail

FREVANA_SETUP_URL="https://raw.githubusercontent.com/FinpeakInc/frevana-cli-releases/refs/heads/main/skills/frevana/scripts/setup.sh"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'HELP'
Frevana setup wrapper - download and run the latest official Frevana setup script.

Usage:
  bash scripts/setup.sh [--snooze]

Environment:
  FREVANA_PORT     Daemon port, forwarded to official setup
  FREVANA_VERSION  Pin a specific release version, forwarded to official setup
HELP
  exit 0
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "Error: curl is not installed." >&2
  exit 1
fi

setup_file="$(mktemp)"
cleanup() {
  rm -f "$setup_file"
}
trap cleanup EXIT

if ! curl -fsSL "$FREVANA_SETUP_URL" -o "$setup_file"; then
  echo "Error: failed to download Frevana setup script from $FREVANA_SETUP_URL" >&2
  exit 1
fi

exec bash "$setup_file" "$@"
