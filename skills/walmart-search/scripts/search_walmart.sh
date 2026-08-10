#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="${FREVANA_API_BASE_URL:-https://ai-factory.frevana.com}"
WALMART_SEARCH_PATH="/service/walmart-search"
CONNECT_TIMEOUT="10"
MAX_TIME="600"

usage() {
  cat <<'EOF'
Usage:
  search_walmart.sh --query "coffee maker" [--device desktop|mobile|tablet] [--cat-id 4044] [--page 1] [--sort price_low|price_high|best_seller|best_match|rating_high|new] [--facet "brand:Sony"] [--min-price 25] [--max-price 100] [--output /path/to/result.json] [--token "bearer token"]

Options:
  --query        Search query keyword to send
  --q            Alias for --query
  --device       Optional device type: desktop, mobile, or tablet
  --cat-id       Optional Walmart category id
  --page         Optional page number. Must be an integer from 1 to 100.
  --sort         Optional sort: price_low, price_high, best_seller, best_match, rating_high, or new
  --facet        Optional facet filter string
  --min-price    Optional minimum price
  --max-price    Optional maximum price
  --output       Optional file path for saving returned JSON. Defaults to ./out/walmart-search-<timestamp>-<pid>.json
  --token        Optional Bearer token override for this run
  -h, --help     Show this help message
EOF
}

is_integer() {
  [[ "$1" =~ ^[0-9]+$ ]]
}

is_number() {
  [[ "$1" =~ ^[0-9]+([.][0-9]+)?$ ]]
}

QUERY=""
DEVICE=""
CAT_ID=""
PAGE=""
SORT=""
FACET=""
MIN_PRICE=""
MAX_PRICE=""
OUTPUT_PATH=""
TOKEN_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --query|--q)
      QUERY="${2:-}"
      shift 2
      ;;
    --device)
      DEVICE="${2:-}"
      shift 2
      ;;
    --cat-id|--cat_id)
      CAT_ID="${2:-}"
      shift 2
      ;;
    --page)
      PAGE="${2:-}"
      shift 2
      ;;
    --sort)
      SORT="${2:-}"
      shift 2
      ;;
    --facet)
      FACET="${2:-}"
      shift 2
      ;;
    --min-price|--min_price)
      MIN_PRICE="${2:-}"
      shift 2
      ;;
    --max-price|--max_price)
      MAX_PRICE="${2:-}"
      shift 2
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

if [[ -z "$QUERY" ]]; then
  echo "Missing required argument: --query" >&2
  exit 1
fi

DEVICE_LOWER="$(printf '%s' "$DEVICE" | tr '[:upper:]' '[:lower:]')"
case "$DEVICE_LOWER" in
  ""|desktop|mobile|tablet)
    ;;
  *)
    echo "Invalid value for --device: $DEVICE" >&2
    echo "Allowed values: desktop, mobile, tablet" >&2
    exit 1
    ;;
esac

if [[ -n "$PAGE" ]] && ! is_integer "$PAGE"; then
  echo "Invalid value for --page: $PAGE" >&2
  echo "Allowed range: integers from 1 to 100" >&2
  exit 1
fi

if [[ -n "$PAGE" && ( "$PAGE" -lt 1 || "$PAGE" -gt 100 ) ]]; then
  echo "Invalid value for --page: $PAGE" >&2
  echo "Allowed range: integers from 1 to 100" >&2
  exit 1
fi

case "$SORT" in
  ""|price_low|price_high|best_seller|best_match|rating_high|new)
    ;;
  *)
    echo "Invalid value for --sort: $SORT" >&2
    echo "Allowed values: price_low, price_high, best_seller, best_match, rating_high, new" >&2
    exit 1
    ;;
esac

if [[ -n "$MIN_PRICE" ]] && ! is_number "$MIN_PRICE"; then
  echo "Invalid value for --min-price: $MIN_PRICE" >&2
  echo "Allowed value: a non-negative number" >&2
  exit 1
fi

if [[ -n "$MAX_PRICE" ]] && ! is_number "$MAX_PRICE"; then
  echo "Invalid value for --max-price: $MAX_PRICE" >&2
  echo "Allowed value: a non-negative number" >&2
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
  OUTPUT_PATH="out/walmart-search-$(date -u +%Y%m%dT%H%M%SZ)-$$.json"
fi

PAYLOAD_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
RESULT_FILE="$(mktemp)"
cleanup() {
  rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE" "$RESULT_FILE"
}
trap cleanup EXIT

export QUERY DEVICE_LOWER CAT_ID PAGE SORT FACET MIN_PRICE MAX_PRICE

python3 - "$PAYLOAD_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path

payload_path = Path(sys.argv[1])

payload = {
    "query": os.environ["QUERY"],
}

optional_fields = {
    "device": os.environ.get("DEVICE_LOWER"),
    "cat_id": os.environ.get("CAT_ID"),
    "sort": os.environ.get("SORT"),
    "facet": os.environ.get("FACET"),
}

for key, value in optional_fields.items():
    if value:
        payload[key] = value

if os.environ.get("PAGE"):
    payload["page"] = int(os.environ["PAGE"])

if os.environ.get("MIN_PRICE"):
    payload["min_price"] = float(os.environ["MIN_PRICE"])

if os.environ.get("MAX_PRICE"):
    payload["max_price"] = float(os.environ["MAX_PRICE"])

payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
PY

HTTP_CODE="$(
  curl -sS \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -o "$RESPONSE_FILE" \
    -w "%{http_code}" \
    -X POST "$API_BASE_URL$WALMART_SEARCH_PATH" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    --data @"$PAYLOAD_FILE"
)"

if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "Walmart search API request failed with HTTP $HTTP_CODE" >&2
  cat "$RESPONSE_FILE" >&2
  exit 1
fi

if [[ ! -s "$RESPONSE_FILE" ]]; then
  echo "Walmart search API returned an empty response body." >&2
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
    print(f"Walmart search API returned non-JSON response: {exc}", file=sys.stderr)
    print(raw, file=sys.stderr)
    sys.exit(1)

result_path.write_text(raw, encoding="utf-8")
PY

mkdir -p "$(dirname "$OUTPUT_PATH")"
cp "$RESULT_FILE" "$OUTPUT_PATH"
echo "Saved Walmart search JSON to $OUTPUT_PATH" >&2

cat "$RESULT_FILE"
