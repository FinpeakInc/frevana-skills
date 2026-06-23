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
  search_meta_ads.sh --keyword "nike" [--country ALL|US] [--active-status active|inactive|all] [--date-from YYYY-MM-DD] [--date-to YYYY-MM-DD] [--max-results 20] [--timeout MS] [--output /path/to/result.json]

Options:
  --keyword            Keyword, advertiser, or brand text to search in Meta Ads Library
  --query              Alias for --keyword
  --q                  Alias for --keyword
  --text               Alias for --keyword
  --country            Country filter: ALL by default, or an ISO 3166-1 alpha-2 code
  --active-status      Ad status: active by default; inactive or all when specified
  --active_status      Alias for --active-status
  --date-from          Optional inclusive start date in YYYY-MM-DD format
  --date_from          Alias for --date-from
  --date-to            Optional inclusive end date in YYYY-MM-DD format
  --date_to            Alias for --date-to
  --max-results        Maximum number of ads to return, defaults to 20 (1 through 500)
  --maxResults         Alias for --max-results
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

validate_int() {
  local name="$1"
  local value="$2"

  if ! [[ "$value" =~ ^[0-9]+$ ]]; then
    echo "Invalid $name value: $value. Expected a positive integer." >&2
    exit 1
  fi
}

validate_date() {
  local name="$1"
  local value="$2"

  if ! [[ "$value" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    echo "Invalid $name value: $value. Expected YYYY-MM-DD." >&2
    exit 1
  fi
}

KEYWORD=""
COUNTRY="ALL"
ACTIVE_STATUS="active"
DATE_FROM=""
DATE_TO=""
MAX_RESULTS="20"
TOOL_TIMEOUT=""
OUTPUT_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --keyword|--query|--q|--text)
      KEYWORD="${2:-}"
      shift 2
      ;;
    --country)
      COUNTRY="${2:-}"
      shift 2
      ;;
    --active-status|--active_status)
      ACTIVE_STATUS="${2:-}"
      shift 2
      ;;
    --date-from|--date_from)
      DATE_FROM="${2:-}"
      shift 2
      ;;
    --date-to|--date_to)
      DATE_TO="${2:-}"
      shift 2
      ;;
    --max-results|--maxResults)
      MAX_RESULTS="${2:-}"
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

if [[ -z "$KEYWORD" ]]; then
  echo "Missing required argument: --keyword" >&2
  exit 1
fi

if [[ -n "$COUNTRY" ]]; then
  if [[ "$COUNTRY" != "ALL" && ! "$COUNTRY" =~ ^[A-Z]{2}$ ]]; then
    echo "Invalid --country value: $COUNTRY. Expected ALL or a two-letter uppercase country code." >&2
    exit 1
  fi
fi

if [[ -n "$ACTIVE_STATUS" && "$ACTIVE_STATUS" != "active" && "$ACTIVE_STATUS" != "inactive" && "$ACTIVE_STATUS" != "all" ]]; then
  echo "Invalid --active-status value: $ACTIVE_STATUS. Allowed values: active, inactive, all" >&2
  exit 1
fi

if [[ -n "$DATE_FROM" ]]; then
  validate_date "--date-from" "$DATE_FROM"
fi

if [[ -n "$DATE_TO" ]]; then
  validate_date "--date-to" "$DATE_TO"
fi

if [[ -n "$MAX_RESULTS" ]]; then
  validate_int "--max-results" "$MAX_RESULTS"
  if (( MAX_RESULTS < 1 || MAX_RESULTS > 500 )); then
    echo "Invalid --max-results value: $MAX_RESULTS. Expected an integer from 1 through 500." >&2
    exit 1
  fi
fi

if [[ -n "$TOOL_TIMEOUT" ]]; then
  validate_int "--timeout" "$TOOL_TIMEOUT"
  if (( TOOL_TIMEOUT < 1 )); then
    echo "Invalid --timeout value: $TOOL_TIMEOUT. Expected a positive integer." >&2
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

export KEYWORD COUNTRY ACTIVE_STATUS DATE_FROM DATE_TO MAX_RESULTS TOOL_TIMEOUT

python3 - "$PAYLOAD_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path

payload_path = Path(sys.argv[1])

payload = {
    "keyword": os.environ["KEYWORD"],
}

string_fields = {
    "country": os.environ.get("COUNTRY"),
    "active_status": os.environ.get("ACTIVE_STATUS"),
    "date_from": os.environ.get("DATE_FROM"),
    "date_to": os.environ.get("DATE_TO"),
}

for key, value in string_fields.items():
    if value:
        payload[key] = value

max_results = os.environ.get("MAX_RESULTS")
if max_results:
    payload["maxResults"] = int(max_results)

tool_timeout = os.environ.get("TOOL_TIMEOUT")
if tool_timeout:
    payload["timeout"] = int(tool_timeout)

payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
PY

"$FREVANA_BIN" call frevana_meta_ads_search "$(cat "$PAYLOAD_FILE")" \
  --port "$DAEMON_PORT" \
  --timeout "$TIMEOUT_MS" > "$RESULT_FILE"

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  cp "$RESULT_FILE" "$OUTPUT_PATH"
  echo "Saved Meta Ads search output to $OUTPUT_PATH" >&2
fi

cat "$RESULT_FILE"
