#!/usr/bin/env bash

set -euo pipefail

DAEMON_PORT="${FREVANA_PORT:-12306}"
FREVANA_TIMEOUT_SEC="${FREVANA_TIMEOUT:-180}"
TIMEOUT_MS=$(( FREVANA_TIMEOUT_SEC * 1000 ))
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
SETUP_SCRIPT="${SCRIPT_DIR}/setup.sh"

usage() {
  cat <<'EOF'
Usage:
  generate_collector.sh --url "https://example.com/products" [--intent "..."] [--duration MS] [--output /path/to/collector.py]

Options:
  --url        Absolute URL of a page whose data feed to collect
  --intent     Optional description of the data you want (recorded in the script header)
  --duration   Optional explore capture window in milliseconds
  --output     Optional file path for saving the generated Python collector script
  -h, --help   Show this help message

Environment:
  FREVANA_PORT     Local daemon port, default 12306
  FREVANA_TIMEOUT  frevana call timeout in seconds, default 180
EOF
}

run_frevana_setup() {
  local setup_output setup_status

  if [[ ! -x "$SETUP_SCRIPT" ]]; then
    echo "Error: Frevana setup wrapper not found or not executable: $SETUP_SCRIPT" >&2
    exit 1
  fi

  setup_output="$(mktemp)"
  set +e
  bash "$SETUP_SCRIPT" > "$setup_output"
  setup_status=$?
  set -e

  if [[ "$setup_status" -eq 0 ]]; then
    rm -f "$setup_output"
    return 0
  fi

  cat "$setup_output" >&2
  rm -f "$setup_output"

  if [[ "$setup_status" -eq 2 ]]; then
    echo "Frevana setup completed, but Chrome is not connected." >&2
    echo "Open Chrome, connect the Frevana extension, then retry." >&2
    exit 2
  else
    echo "Error: Frevana setup script failed with exit code $setup_status." >&2
    exit "$setup_status"
  fi
}

URL=""
INTENT=""
DURATION=""
OUTPUT_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --url)
      URL="${2:-}"
      shift 2
      ;;
    --intent)
      INTENT="${2:-}"
      shift 2
      ;;
    --duration)
      DURATION="${2:-}"
      shift 2
      ;;
    --output)
      OUTPUT_PATH="${2:-}"
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

if [[ -z "$URL" ]]; then
  echo "Missing required argument: --url" >&2
  exit 1
fi

case "$URL" in
  http://*|https://*) ;;
  *)
    echo "Invalid --url value: $URL. Expected an absolute URL starting with http:// or https://." >&2
    exit 1
    ;;
esac

if [[ -n "$DURATION" ]]; then
  if ! [[ "$DURATION" =~ ^[0-9]+$ ]]; then
    echo "Invalid --duration value: $DURATION. Expected a positive integer (milliseconds)." >&2
    exit 1
  fi
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required but was not found in PATH." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required but was not found in PATH." >&2
  exit 1
fi

run_frevana_setup

EXT=""
case "$(uname -s 2>/dev/null || echo)" in
  MINGW*|MSYS*|CYGWIN*) EXT=".exe" ;;
esac

FREVANA_BIN="$HOME/.frevana/bin/frevana${EXT}"
if [[ ! -x "$FREVANA_BIN" ]]; then
  if command -v frevana >/dev/null 2>&1; then
    FREVANA_BIN="$(command -v frevana)"
  else
    echo "Error: Frevana setup completed but frevana binary was not found at $FREVANA_BIN or on PATH." >&2
    exit 1
  fi
fi

if ! curl -s --max-time 2 "http://127.0.0.1:${DAEMON_PORT}/health" >/dev/null 2>&1; then
  echo "Error: Frevana daemon is not running on port ${DAEMON_PORT}." >&2
  echo "Frevana setup was already run, but the daemon health check still failed." >&2
  exit 1
fi

PAYLOAD_FILE="$(mktemp)"
RESULT_FILE="$(mktemp)"
cleanup() {
  rm -f "$PAYLOAD_FILE" "$RESULT_FILE"
}
trap cleanup EXIT

export URL INTENT DURATION

python3 - "$PAYLOAD_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path

payload_path = Path(sys.argv[1])

payload = {
    "url": os.environ["URL"],
}

intent = os.environ.get("INTENT")
if intent:
    payload["intent"] = intent

duration = os.environ.get("DURATION")
if duration:
    payload["durationMs"] = int(duration)

payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
PY

"$FREVANA_BIN" call frevana_generate "$(cat "$PAYLOAD_FILE")" \
  --port "$DAEMON_PORT" \
  --timeout "$TIMEOUT_MS" > "$RESULT_FILE"

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  cp "$RESULT_FILE" "$OUTPUT_PATH"
  echo "Saved collector script to $OUTPUT_PATH" >&2
  echo "Run it with: python3 $OUTPUT_PATH --output data.csv" >&2
fi

cat "$RESULT_FILE"
