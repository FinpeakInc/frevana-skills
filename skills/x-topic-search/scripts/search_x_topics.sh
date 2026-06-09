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
  search_x_topics.sh --topic "vibe coding" [--sort top|live] [--count 20] [--fetch-mode quick|full] [--cursor CURSOR] [--include-replies] [--include-quotes] [--include-media] [--max-scroll-rounds N] [--min-count N] [--timeout MS] [--output /path/to/result.txt]

Options:
  --topic              Topic or query to search on X
  --query              Alias for --topic
  --q                  Alias for --topic
  --sort               Optional sort: top or live
  --count              Optional number of posts to fetch, 1 through 100
  --fetch-mode         Optional fetch mode: quick or full, default quick
  --cursor             Optional cursor from a previous result set
  --include-replies    Include replies when available
  --include-quotes     Include quotes when available
  --include-media      Include media metadata when available
  --max-scroll-rounds  Optional maximum scroll rounds during collection
  --min-count          Optional minimum number of posts before stopping
  --timeout            Optional Frevana tool timeout in milliseconds
  --output             Optional file path for saving the Frevana tool result
  -h, --help           Show this help message

Environment:
  FREVANA_PORT         Local daemon port, default 12306
  FREVANA_TIMEOUT      frevana call timeout in seconds, default 180
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

TOPIC=""
SORT=""
COUNT=""
FETCH_MODE="quick"
CURSOR=""
INCLUDE_REPLIES=""
INCLUDE_QUOTES=""
INCLUDE_MEDIA=""
MAX_SCROLL_ROUNDS=""
MIN_COUNT=""
TOOL_TIMEOUT=""
OUTPUT_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --topic|--query|--q)
      TOPIC="${2:-}"
      shift 2
      ;;
    --sort)
      SORT="${2:-}"
      shift 2
      ;;
    --count)
      COUNT="${2:-}"
      shift 2
      ;;
    --fetch-mode|--fetchMode)
      FETCH_MODE="${2:-}"
      shift 2
      ;;
    --cursor)
      CURSOR="${2:-}"
      shift 2
      ;;
    --include-replies|--includeReplies)
      INCLUDE_REPLIES="true"
      shift
      ;;
    --include-quotes|--includeQuotes)
      INCLUDE_QUOTES="true"
      shift
      ;;
    --include-media|--includeMedia)
      INCLUDE_MEDIA="true"
      shift
      ;;
    --max-scroll-rounds|--maxScrollRounds)
      MAX_SCROLL_ROUNDS="${2:-}"
      shift 2
      ;;
    --min-count|--minCount)
      MIN_COUNT="${2:-}"
      shift 2
      ;;
    --timeout)
      TOOL_TIMEOUT="${2:-}"
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

if [[ -z "$TOPIC" ]]; then
  echo "Missing required argument: --topic" >&2
  exit 1
fi

if [[ -n "$SORT" && "$SORT" != "top" && "$SORT" != "live" ]]; then
  echo "Invalid --sort value: $SORT. Allowed values: top, live" >&2
  exit 1
fi

if [[ -n "$FETCH_MODE" && "$FETCH_MODE" != "quick" && "$FETCH_MODE" != "full" ]]; then
  echo "Invalid --fetch-mode value: $FETCH_MODE. Allowed values: quick, full" >&2
  exit 1
fi

validate_int() {
  local name="$1"
  local value="$2"
  if ! [[ "$value" =~ ^[0-9]+$ ]]; then
    echo "Invalid $name value: $value. Expected a positive integer." >&2
    exit 1
  fi
}

if [[ -n "$COUNT" ]]; then
  validate_int "--count" "$COUNT"
  if (( COUNT < 1 || COUNT > 100 )); then
    echo "Invalid --count value: $COUNT. Expected an integer from 1 through 100." >&2
    exit 1
  fi
fi

if [[ -n "$MAX_SCROLL_ROUNDS" ]]; then
  validate_int "--max-scroll-rounds" "$MAX_SCROLL_ROUNDS"
fi

if [[ -n "$MIN_COUNT" ]]; then
  validate_int "--min-count" "$MIN_COUNT"
fi

if [[ -n "$TOOL_TIMEOUT" ]]; then
  validate_int "--timeout" "$TOOL_TIMEOUT"
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

export TOPIC SORT COUNT FETCH_MODE CURSOR INCLUDE_REPLIES INCLUDE_QUOTES INCLUDE_MEDIA MAX_SCROLL_ROUNDS MIN_COUNT TOOL_TIMEOUT

python3 - "$PAYLOAD_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path

payload_path = Path(sys.argv[1])

payload = {
    "topic": os.environ["TOPIC"],
}

string_fields = {
    "sort": os.environ.get("SORT"),
    "fetchMode": os.environ.get("FETCH_MODE"),
    "cursor": os.environ.get("CURSOR"),
}

for key, value in string_fields.items():
    if value:
        payload[key] = value

number_fields = {
    "count": os.environ.get("COUNT"),
    "maxScrollRounds": os.environ.get("MAX_SCROLL_ROUNDS"),
    "minCount": os.environ.get("MIN_COUNT"),
    "timeout": os.environ.get("TOOL_TIMEOUT"),
}

for key, value in number_fields.items():
    if value:
        payload[key] = int(value)

boolean_fields = {
    "includeReplies": os.environ.get("INCLUDE_REPLIES"),
    "includeQuotes": os.environ.get("INCLUDE_QUOTES"),
    "includeMedia": os.environ.get("INCLUDE_MEDIA"),
}

for key, value in boolean_fields.items():
    if value == "true":
        payload[key] = True

payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
PY

"$FREVANA_BIN" call frevana_x_search_topic "$(cat "$PAYLOAD_FILE")" \
  --port "$DAEMON_PORT" \
  --timeout "$TIMEOUT_MS" > "$RESULT_FILE"

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  cp "$RESULT_FILE" "$OUTPUT_PATH"
  echo "Saved X topic search output to $OUTPUT_PATH" >&2
fi

cat "$RESULT_FILE"
