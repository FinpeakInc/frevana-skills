#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="https://ai-factory.frevana.com"
AMAZON_SEARCH_PATH="/service/amazon-search"
CONNECT_TIMEOUT="10"
MAX_TIME="600"

usage() {
  cat <<'EOF'
Usage:
  search_amazon.sh (--query "wireless mouse" | --node 283155) [options]

Options:
  --query                Search keyword to send. Required unless --node is provided
  --node                 Amazon category node ID. Required unless --query is provided
  --amazon-domain        Optional Amazon domain, for example amazon.com
  --language             Optional Amazon language code
  --delivery-zip         Optional delivery ZIP code. Takes priority over --shipping-location
  --shipping-location    Optional shipping location string, for example "Seattle,Washington,United States"
  --sort-by              Optional sort key: review-rank | price-asc-rank | price-desc-rank | date-desc-rank | relevanceblender
  --rh                   Optional Amazon refinement hash
  --device               Optional device type: desktop | mobile
  --page                 Optional result page (default: 1)
  --no-cache             Optional boolean: true | false
  --async                Optional boolean: true | false
  --zero-trace           Optional boolean: true | false
  --output               Optional file path for saving returned JSON. Defaults to ./out/amazon-search-<timestamp>-<pid>.json
  --token                Optional Bearer token override for this run
  -h, --help             Show this help message
EOF
}

is_integer() {
  [[ "$1" =~ ^[0-9]+$ ]]
}

parse_boolean() {
  local value
  value="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  case "$value" in
    true|false)
      printf '%s\n' "$value"
      ;;
    *)
      return 1
      ;;
  esac
}

require_option_value() {
  local option="$1"
  local value="${2:-}"
  if [[ -z "$value" || "$value" == --* ]]; then
    echo "Missing value for $option" >&2
    exit 1
  fi
  printf '%s\n' "$value"
}

QUERY=""
NODE=""
AMAZON_DOMAIN=""
LANGUAGE=""
DELIVERY_ZIP=""
SHIPPING_LOCATION=""
SORT_BY=""
RH=""
DEVICE=""
PAGE="1"
NO_CACHE=""
ASYNC_REQUEST=""
ZERO_TRACE=""
OUTPUT_PATH=""
TOKEN_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --query)
      QUERY="$(require_option_value "$1" "${2:-}")"
      shift 2
      ;;
    --node)
      NODE="$(require_option_value "$1" "${2:-}")"
      shift 2
      ;;
    --amazon-domain)
      AMAZON_DOMAIN="$(require_option_value "$1" "${2:-}")"
      shift 2
      ;;
    --language)
      LANGUAGE="$(require_option_value "$1" "${2:-}")"
      shift 2
      ;;
    --delivery-zip)
      DELIVERY_ZIP="$(require_option_value "$1" "${2:-}")"
      shift 2
      ;;
    --shipping-location)
      SHIPPING_LOCATION="$(require_option_value "$1" "${2:-}")"
      shift 2
      ;;
    --sort-by)
      SORT_BY="$(require_option_value "$1" "${2:-}")"
      shift 2
      ;;
    --rh)
      RH="$(require_option_value "$1" "${2:-}")"
      shift 2
      ;;
    --device)
      DEVICE="$(require_option_value "$1" "${2:-}")"
      shift 2
      ;;
    --page)
      PAGE="$(require_option_value "$1" "${2:-}")"
      shift 2
      ;;
    --no-cache)
      NO_CACHE="$(require_option_value "$1" "${2:-}")"
      shift 2
      ;;
    --async)
      ASYNC_REQUEST="$(require_option_value "$1" "${2:-}")"
      shift 2
      ;;
    --zero-trace)
      ZERO_TRACE="$(require_option_value "$1" "${2:-}")"
      shift 2
      ;;
    --output)
      OUTPUT_PATH="$(require_option_value "$1" "${2:-}")"
      shift 2
      ;;
    --token)
      TOKEN_OVERRIDE="$(require_option_value "$1" "${2:-}")"
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

if [[ -n "$QUERY" && -n "$NODE" ]]; then
  echo "--query and --node cannot be used together." >&2
  exit 1
fi

if [[ -z "$QUERY" && -z "$NODE" ]]; then
  echo "Missing required argument: provide either --query or --node." >&2
  exit 1
fi

if ! is_integer "$PAGE" || (( PAGE < 1 )); then
  echo "Invalid value for --page: $PAGE" >&2
  echo "Allowed range: integers >= 1" >&2
  exit 1
fi

if [[ -n "$NODE" ]] && ! is_integer "$NODE"; then
  echo "Invalid value for --node: $NODE" >&2
  echo "Allowed range: integers >= 1" >&2
  exit 1
fi

if [[ -n "$DEVICE" ]]; then
  DEVICE="$(printf '%s' "$DEVICE" | tr '[:upper:]' '[:lower:]')"
  case "$DEVICE" in
    desktop|mobile)
      ;;
    *)
      echo "Invalid value for --device: $DEVICE" >&2
      echo "Allowed values: desktop, mobile" >&2
      exit 1
      ;;
  esac
fi

if [[ -n "$SORT_BY" ]]; then
  case "$SORT_BY" in
    review-rank|price-asc-rank|price-desc-rank|date-desc-rank|relevanceblender)
      ;;
    *)
      echo "Invalid value for --sort-by: $SORT_BY" >&2
      echo "Allowed values: review-rank, price-asc-rank, price-desc-rank, date-desc-rank, relevanceblender" >&2
      exit 1
      ;;
  esac
fi

if [[ -n "$NO_CACHE" ]]; then
  raw_no_cache="$NO_CACHE"
  if ! NO_CACHE="$(parse_boolean "$raw_no_cache")"; then
    echo "Invalid value for --no-cache: $raw_no_cache" >&2
    echo "Allowed values: true, false" >&2
    exit 1
  fi
fi

if [[ -n "$ASYNC_REQUEST" ]]; then
  raw_async="$ASYNC_REQUEST"
  if ! ASYNC_REQUEST="$(parse_boolean "$raw_async")"; then
    echo "Invalid value for --async: $raw_async" >&2
    echo "Allowed values: true, false" >&2
    exit 1
  fi
fi

if [[ -n "$ZERO_TRACE" ]]; then
  raw_zero_trace="$ZERO_TRACE"
  if ! ZERO_TRACE="$(parse_boolean "$raw_zero_trace")"; then
    echo "Invalid value for --zero-trace: $raw_zero_trace" >&2
    echo "Allowed values: true, false" >&2
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
  OUTPUT_PATH="out/amazon-search-$(date -u +%Y%m%dT%H%M%SZ)-$$.json"
fi

PAYLOAD_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
RESULT_FILE="$(mktemp)"
cleanup() {
  rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE" "$RESULT_FILE"
}
trap cleanup EXIT

export QUERY NODE AMAZON_DOMAIN LANGUAGE DELIVERY_ZIP SHIPPING_LOCATION SORT_BY RH DEVICE PAGE NO_CACHE ASYNC_REQUEST ZERO_TRACE

python3 - "$PAYLOAD_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path

payload_path = Path(sys.argv[1])

payload = {"page": int(os.environ["PAGE"])}

optional_fields = {
    "query": os.environ.get("QUERY", ""),
    "node": os.environ.get("NODE", ""),
    "amazon_domain": os.environ.get("AMAZON_DOMAIN", ""),
    "language": os.environ.get("LANGUAGE", ""),
    "delivery_zip": os.environ.get("DELIVERY_ZIP", ""),
    "shipping_location": os.environ.get("SHIPPING_LOCATION", ""),
    "sort_by": os.environ.get("SORT_BY", ""),
    "rh": os.environ.get("RH", ""),
    "device": os.environ.get("DEVICE", ""),
}

for key, value in optional_fields.items():
    if value:
        payload[key] = value

for key, env_name in {
    "no_cache": "NO_CACHE",
    "async": "ASYNC_REQUEST",
    "zero_trace": "ZERO_TRACE",
}.items():
    value = os.environ.get(env_name, "")
    if value:
        payload[key] = value == "true"

payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
PY

HTTP_CODE="$(
  curl -sS \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -o "$RESPONSE_FILE" \
    -w "%{http_code}" \
    -X POST "$API_BASE_URL$AMAZON_SEARCH_PATH" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    --data @"$PAYLOAD_FILE"
)"

if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "Amazon search API request failed with HTTP $HTTP_CODE" >&2
  cat "$RESPONSE_FILE" >&2
  exit 1
fi

if [[ ! -s "$RESPONSE_FILE" ]]; then
  echo "Amazon search API returned an empty response body." >&2
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
    print(f"Amazon search API returned non-JSON response: {exc}", file=sys.stderr)
    print(raw, file=sys.stderr)
    sys.exit(1)

result_path.write_text(raw, encoding="utf-8")
PY

mkdir -p "$(dirname "$OUTPUT_PATH")"
cp "$RESULT_FILE" "$OUTPUT_PATH"
echo "Saved Amazon Search response to $OUTPUT_PATH" >&2

cat "$RESULT_FILE"
