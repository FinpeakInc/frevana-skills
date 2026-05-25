#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="https://ai-factory.frevana.com"
WALMART_PRODUCT_REVIEWS_PATH="/service/serpapi/walmart-product-reviews"
CONNECT_TIMEOUT="10"
MAX_TIME="600"

usage() {
  cat <<'EOF'
Usage:
  search_walmart_product_reviews.sh --product-id 5689919121 [--page 1] [--sort relevancy|helpful|submission-desc|submission-asc|rating-desc|rating-asc] [--rating 1|2|3|4|5] [--output /path/to/result.json] [--token "bearer token"]

Options:
  --product-id   Walmart product id / us_item_id to fetch reviews for
  --product_id   Alias for --product-id
  --us-item-id   Alias for --product-id
  --us_item_id   Alias for --product-id
  --page         Optional page number. Must be an integer >= 1.
  --sort         Optional review sort: relevancy, helpful, submission-desc, submission-asc, rating-desc, or rating-asc
  --rating       Optional rating filter. Must be an integer from 1 to 5.
  --output       Optional file path for saving returned JSON. Defaults to ./out/walmart-product-reviews-<timestamp>-<pid>.json
  --token        Optional Bearer token override for this run
  -h, --help     Show this help message
EOF
}

is_integer() {
  [[ "$1" =~ ^[0-9]+$ ]]
}

PRODUCT_ID=""
PAGE=""
SORT=""
RATING=""
OUTPUT_PATH=""
TOKEN_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --product-id|--product_id|--us-item-id|--us_item_id)
      PRODUCT_ID="${2:-}"
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
    --rating)
      RATING="${2:-}"
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

if [[ -z "$PRODUCT_ID" ]]; then
  echo "Missing required argument: --product-id" >&2
  exit 1
fi

if [[ -n "$PAGE" ]] && ! is_integer "$PAGE"; then
  echo "Invalid value for --page: $PAGE" >&2
  echo "Allowed range: integers >= 1" >&2
  exit 1
fi

if [[ -n "$PAGE" && "$PAGE" -lt 1 ]]; then
  echo "Invalid value for --page: $PAGE" >&2
  echo "Allowed range: integers >= 1" >&2
  exit 1
fi

case "$SORT" in
  ""|relevancy|helpful|submission-desc|submission-asc|rating-desc|rating-asc)
    ;;
  *)
    echo "Invalid value for --sort: $SORT" >&2
    echo "Allowed values: relevancy, helpful, submission-desc, submission-asc, rating-desc, rating-asc" >&2
    exit 1
    ;;
esac

if [[ -n "$RATING" ]] && ! is_integer "$RATING"; then
  echo "Invalid value for --rating: $RATING" >&2
  echo "Allowed values: integers from 1 to 5" >&2
  exit 1
fi

if [[ -n "$RATING" && ( "$RATING" -lt 1 || "$RATING" -gt 5 ) ]]; then
  echo "Invalid value for --rating: $RATING" >&2
  echo "Allowed values: integers from 1 to 5" >&2
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
  OUTPUT_PATH="out/walmart-product-reviews-$(date -u +%Y%m%dT%H%M%SZ)-$$.json"
fi

PAYLOAD_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
RESULT_FILE="$(mktemp)"
cleanup() {
  rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE" "$RESULT_FILE"
}
trap cleanup EXIT

export PRODUCT_ID PAGE SORT RATING

python3 - "$PAYLOAD_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path

payload_path = Path(sys.argv[1])

payload = {
    "product_id": os.environ["PRODUCT_ID"],
}

sort = os.environ.get("SORT")
if sort:
    payload["sort"] = sort

if os.environ.get("PAGE"):
    payload["page"] = int(os.environ["PAGE"])

if os.environ.get("RATING"):
    payload["rating"] = int(os.environ["RATING"])

payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
PY

HTTP_CODE="$(
  curl -sS \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -o "$RESPONSE_FILE" \
    -w "%{http_code}" \
    -X POST "$API_BASE_URL$WALMART_PRODUCT_REVIEWS_PATH" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    --data @"$PAYLOAD_FILE"
)"

if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "Walmart product reviews API request failed with HTTP $HTTP_CODE" >&2
  cat "$RESPONSE_FILE" >&2
  exit 1
fi

if [[ ! -s "$RESPONSE_FILE" ]]; then
  echo "Walmart product reviews API returned an empty response body." >&2
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
    print(f"Walmart product reviews API returned non-JSON response: {exc}", file=sys.stderr)
    print(raw, file=sys.stderr)
    sys.exit(1)

result_path.write_text(raw, encoding="utf-8")
PY

mkdir -p "$(dirname "$OUTPUT_PATH")"
cp "$RESULT_FILE" "$OUTPUT_PATH"
echo "Saved Walmart product reviews JSON to $OUTPUT_PATH" >&2

cat "$RESULT_FILE"
