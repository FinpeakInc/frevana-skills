#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="https://ai-factory.frevana.com"
APPLE_SEARCH_PATH="/service/apple-app-store-search"
CONNECT_TIMEOUT="10"
MAX_TIME="600"

usage() {
  cat <<'EOF'
Usage:
  search_apple_app_store.sh --term "instagram" [--country us] [--lang en-us] [--num 10] [--page 0] [--disallow-explicit] [--property developer] [--category-id 6014] [--device desktop|tablet|mobile] [--serpapi-output json|html] [--no-cache] [--async] [--zero-trace] [--output /path/to/result.json] [--token "bearer token"]

Options:
  --term, --q, --query Search query term for the App Store (required)
  --country            Two-letter country code for the App Store region (default: us)
  --lang               Four-letter language code (default: en-us)
  --num                Number of results per page (1 to 200, default: 10)
  --page               Page number (0-indexed, default: 0)
  --disallow-explicit  Filter out explicit apps
  --property           Search by app property (e.g. 'developer' to search by developer name)
  --category-id        Filter results by category/genre ID (e.g. 6014 for Games)
  --device             Device type: desktop (default), tablet, or mobile
  --serpapi-output     SerpAPI output format: json or html
  --no-cache           Force SerpAPI to fetch fresh results instead of cache
  --async              Submit search asynchronously and retrieve it later
  --zero-trace         Enable SerpAPI ZeroTrace mode for Enterprise accounts
  --output             Optional file path for saving returned JSON. Defaults to ./out/apple-app-store-search-<timestamp>-<pid>.json
  --token              Optional Bearer token override for this run
  -h, --help           Show this help message
EOF
}

TERM=""
COUNTRY=""
LANG_CODE=""
NUM=""
PAGE=""
DISALLOW_EXPLICIT=""
PROPERTY=""
CATEGORY_ID=""
DEVICE=""
SERPAPI_OUTPUT=""
NO_CACHE=""
ASYNC_REQ=""
ZERO_TRACE=""
OUTPUT_PATH=""
TOKEN_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --term|--q|--query)
      TERM="${2:-}"
      shift 2
      ;;
    --country)
      COUNTRY="${2:-}"
      shift 2
      ;;
    --lang)
      LANG_CODE="${2:-}"
      shift 2
      ;;
    --num)
      NUM="${2:-}"
      shift 2
      ;;
    --page)
      PAGE="${2:-}"
      shift 2
      ;;
    --disallow-explicit)
      if [[ "${2:-}" == "true" || "${2:-}" == "false" ]]; then
        DISALLOW_EXPLICIT="$2"
        shift 2
      else
        DISALLOW_EXPLICIT="true"
        shift 1
      fi
      ;;
    --property)
      PROPERTY="${2:-}"
      shift 2
      ;;
    --category-id)
      CATEGORY_ID="${2:-}"
      shift 2
      ;;
    --device)
      DEVICE="${2:-}"
      shift 2
      ;;
    --serpapi-output)
      SERPAPI_OUTPUT="${2:-}"
      shift 2
      ;;
    --no-cache)
      if [[ "${2:-}" == "true" || "${2:-}" == "false" ]]; then
        NO_CACHE="$2"
        shift 2
      else
        NO_CACHE="true"
        shift 1
      fi
      ;;
    --async)
      if [[ "${2:-}" == "true" || "${2:-}" == "false" ]]; then
        ASYNC_REQ="$2"
        shift 2
      else
        ASYNC_REQ="true"
        shift 1
      fi
      ;;
    --zero-trace)
      if [[ "${2:-}" == "true" || "${2:-}" == "false" ]]; then
        ZERO_TRACE="$2"
        shift 2
      else
        ZERO_TRACE="true"
        shift 1
      fi
      ;;
    --output)
      OUTPUT_PATH="${2:-}"
      shift 2
      ;;
    --token)
      TOKEN_OVERRIDE="${2:-}"
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

if [[ -z "$TERM" ]]; then
  echo "Missing required argument: --term" >&2
  exit 1
fi

if [[ -n "$NUM" ]]; then
  if ! [[ "$NUM" =~ ^[0-9]+$ ]]; then
    echo "Invalid --num value: $NUM. Expected an integer from 1 through 200." >&2
    exit 1
  fi
  if (( NUM < 1 || NUM > 200 )); then
    echo "Invalid --num value: $NUM. Expected an integer from 1 through 200." >&2
    exit 1
  fi
fi

if [[ -n "$PAGE" ]]; then
  if ! [[ "$PAGE" =~ ^[0-9]+$ ]]; then
    echo "Invalid --page value: $PAGE. Expected an integer 0 or greater." >&2
    exit 1
  fi
fi

if [[ -n "$CATEGORY_ID" ]]; then
  if ! [[ "$CATEGORY_ID" =~ ^[0-9]+$ ]]; then
    echo "Invalid --category-id value: $CATEGORY_ID. Expected an integer." >&2
    exit 1
  fi
fi

if [[ -n "$DEVICE" && "$DEVICE" != "desktop" && "$DEVICE" != "tablet" && "$DEVICE" != "mobile" ]]; then
  echo "Invalid --device value: $DEVICE. Allowed values: desktop, tablet, mobile" >&2
  exit 1
fi

if [[ -n "$SERPAPI_OUTPUT" && "$SERPAPI_OUTPUT" != "json" && "$SERPAPI_OUTPUT" != "html" ]]; then
  echo "Invalid --serpapi-output value: $SERPAPI_OUTPUT. Allowed values: json, html" >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required but was not found in PATH." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required but was not found in PATH." >&2
  exit 1
fi

TOKEN="${TOKEN_OVERRIDE:-${FREVANA_TOKEN:-}}"
if [[ -z "$TOKEN" ]]; then
  if [[ -t 0 ]]; then
    read -r -s -p "FREVANA_TOKEN not found. Please enter your Frevana Bearer token: " TOKEN
    echo >&2
  else
    echo "FREVANA_TOKEN is not set. In non-interactive runs, set FREVANA_TOKEN or pass --token explicitly." >&2
    exit 1
  fi
fi

if [[ -z "$TOKEN" ]]; then
  echo "Bearer token is required." >&2
  exit 1
fi

if [[ -z "$OUTPUT_PATH" ]]; then
  OUTPUT_PATH="out/apple-app-store-search-$(date -u +%Y%m%dT%H%M%SZ)-$$.json"
fi

PAYLOAD_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
RESULT_FILE="$(mktemp)"
cleanup() {
  rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE" "$RESULT_FILE"
}
trap cleanup EXIT

export TERM COUNTRY LANG_CODE NUM PAGE DISALLOW_EXPLICIT PROPERTY CATEGORY_ID DEVICE SERPAPI_OUTPUT NO_CACHE ASYNC_REQ ZERO_TRACE

python3 - "$PAYLOAD_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path

payload_path = Path(sys.argv[1])

payload = {
    "term": os.environ["TERM"],
}

string_fields = {
    "country": os.environ.get("COUNTRY"),
    "lang": os.environ.get("LANG_CODE"),
    "property": os.environ.get("PROPERTY"),
    "device": os.environ.get("DEVICE"),
    "output": os.environ.get("SERPAPI_OUTPUT"),
}

for key, value in string_fields.items():
    if value:
        payload[key] = value

number_fields = {
    "num": os.environ.get("NUM"),
    "page": os.environ.get("PAGE"),
    "category_id": os.environ.get("CATEGORY_ID"),
}

for key, value in number_fields.items():
    if value:
        payload[key] = int(value)

bool_fields = {
    "disallow_explicit": os.environ.get("DISALLOW_EXPLICIT"),
    "no_cache": os.environ.get("NO_CACHE"),
    "async": os.environ.get("ASYNC_REQ"),
    "zero_trace": os.environ.get("ZERO_TRACE"),
}

for key, value in bool_fields.items():
    if value:
        payload[key] = (value.lower() == "true")

payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
PY

HTTP_CODE="$(
  curl -sS \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -o "$RESPONSE_FILE" \
    -w "%{http_code}" \
    -X POST "$API_BASE_URL$APPLE_SEARCH_PATH" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    --data @"$PAYLOAD_FILE"
)"

if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "Apple App Store Search API request failed with HTTP $HTTP_CODE" >&2
  cat "$RESPONSE_FILE" >&2
  exit 1
fi

if [[ ! -s "$RESPONSE_FILE" ]]; then
  echo "Apple App Store Search API returned an empty response body." >&2
  exit 1
fi

python3 - "$RESPONSE_FILE" "$RESULT_FILE" <<'PY'
import json
import sys
from pathlib import Path

response_path = Path(sys.argv[1])
result_path = Path(sys.argv[2])
raw = response_path.read_text(encoding="utf-8")

try:
    json.loads(raw)
except json.JSONDecodeError as exc:
    print(f"Apple App Store Search API returned non-JSON response: {exc}", file=sys.stderr)
    print(raw, file=sys.stderr)
    sys.exit(1)

result_path.write_text(raw, encoding="utf-8")
PY

mkdir -p "$(dirname "$OUTPUT_PATH")"
cp "$RESULT_FILE" "$OUTPUT_PATH"
echo "Saved Apple App Store Search JSON to $OUTPUT_PATH" >&2

cat "$RESULT_FILE"
