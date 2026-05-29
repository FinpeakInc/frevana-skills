#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="https://ai-factory.frevana.com"
EBAY_SEARCH_PATH="/service/ebay-search"
CONNECT_TIMEOUT="10"
MAX_TIME="600"

usage() {
  cat <<'EOF'
Usage:
  search_ebay.sh [--query "vintage watch"] [--category-id 31387] [--ebay-domain ebay.com] [--page 1] [--results-per-page 50] [--output /path/to/result.json] [--token "bearer token"]

Options:
  --query              Optional search query keyword to send. Required unless --category-id is provided.
  --category-id        Optional eBay category id. Required unless --query is provided.
  --ebay-domain        Optional eBay domain, e.g. ebay.com
  --page               Optional page number. Must be an integer >= 1.
  --results-per-page   Optional results per page. Must be an integer from 1 to 240.
  --output             Optional file path for saving returned JSON. Defaults to ./out/ebay-search-<timestamp>-<pid>.json
  --token              Optional Bearer token override for this run
  -h, --help           Show this help message
EOF
}

is_integer() {
  [[ "$1" =~ ^[0-9]+$ ]]
}

QUERY=""
CATEGORY_ID=""
EBAY_DOMAIN=""
PAGE=""
RESULTS_PER_PAGE=""
OUTPUT_PATH=""
TOKEN_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --query|--q)
      QUERY="${2:-}"
      shift 2
      ;;
    --category-id|--category_id)
      CATEGORY_ID="${2:-}"
      shift 2
      ;;
    --ebay-domain|--ebay_domain)
      EBAY_DOMAIN="${2:-}"
      shift 2
      ;;
    --page)
      PAGE="${2:-}"
      shift 2
      ;;
    --results-per-page|--results_per_page)
      RESULTS_PER_PAGE="${2:-}"
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

if [[ -z "$QUERY" && -z "$CATEGORY_ID" ]]; then
  echo "Missing required argument: provide --query or --category-id" >&2
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

if [[ -n "$RESULTS_PER_PAGE" ]] && ! is_integer "$RESULTS_PER_PAGE"; then
  echo "Invalid value for --results-per-page: $RESULTS_PER_PAGE" >&2
  echo "Allowed range: integers from 1 to 240" >&2
  exit 1
fi

if [[ -n "$RESULTS_PER_PAGE" && ( "$RESULTS_PER_PAGE" -lt 1 || "$RESULTS_PER_PAGE" -gt 240 ) ]]; then
  echo "Invalid value for --results-per-page: $RESULTS_PER_PAGE" >&2
  echo "Allowed range: integers from 1 to 240" >&2
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
  OUTPUT_PATH="out/ebay-search-$(date -u +%Y%m%dT%H%M%SZ)-$$.json"
fi

PAYLOAD_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
RESULT_FILE="$(mktemp)"
cleanup() {
  rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE" "$RESULT_FILE"
}
trap cleanup EXIT

export QUERY CATEGORY_ID EBAY_DOMAIN PAGE RESULTS_PER_PAGE

python3 - "$PAYLOAD_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path

payload_path = Path(sys.argv[1])

payload = {}

if os.environ.get("QUERY"):
    payload["query"] = os.environ["QUERY"]

optional_fields = {
    "category_id": os.environ.get("CATEGORY_ID"),
    "ebay_domain": os.environ.get("EBAY_DOMAIN"),
}

for key, value in optional_fields.items():
    if value:
        payload[key] = value

if os.environ.get("PAGE"):
    payload["page"] = int(os.environ["PAGE"])

if os.environ.get("RESULTS_PER_PAGE"):
    payload["results_per_page"] = int(os.environ["RESULTS_PER_PAGE"])

payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
PY

HTTP_CODE="$(
  curl -sS \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -o "$RESPONSE_FILE" \
    -w "%{http_code}" \
    -X POST "$API_BASE_URL$EBAY_SEARCH_PATH" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    --data @"$PAYLOAD_FILE"
)"

if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "eBay search API request failed with HTTP $HTTP_CODE" >&2
  cat "$RESPONSE_FILE" >&2
  exit 1
fi

if [[ ! -s "$RESPONSE_FILE" ]]; then
  echo "eBay search API returned an empty response body." >&2
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
    print(f"eBay search API returned non-JSON response: {exc}", file=sys.stderr)
    print(raw, file=sys.stderr)
    sys.exit(1)

result_path.write_text(raw, encoding="utf-8")
PY

mkdir -p "$(dirname "$OUTPUT_PATH")"
cp "$RESULT_FILE" "$OUTPUT_PATH"
echo "Saved eBay search JSON to $OUTPUT_PATH" >&2

cat "$RESULT_FILE"
