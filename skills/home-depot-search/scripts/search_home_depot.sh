#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="https://ai-factory.frevana.com"
HOME_DEPOT_SEARCH_PATH="/service/home-depot-search"
CONNECT_TIMEOUT="10"
MAX_TIME="600"

usage() {
  cat <<'EOF'
Usage:
  search_home_depot.sh --q "patio chairs" [--country us|ca] [--store 121] [--delivery-zip 10001] [--page 1] [--page-size 40] [--output /path/to/result.json] [--token "bearer token"]

Options:
  --q                 Search query keyword to send
  --query             Alias for --q
  --country           Optional country code: us or ca
  --store             Optional Home Depot store id
  --delivery-zip      Optional delivery ZIP or postal code
  --page              Optional page number. Must be an integer >= 1.
  --page-size         Optional page size. Must be an integer from 1 to 40.
  --output            Optional file path for saving returned JSON. Defaults to ./out/home-depot-search-<timestamp>-<pid>.json
  --token             Optional Bearer token override for this run
  -h, --help          Show this help message
EOF
}

is_integer() {
  [[ "$1" =~ ^[0-9]+$ ]]
}

Q=""
COUNTRY=""
STORE=""
DELIVERY_ZIP=""
PAGE=""
PAGE_SIZE=""
OUTPUT_PATH=""
TOKEN_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --q|--query)
      Q="${2:-}"
      shift 2
      ;;
    --country)
      COUNTRY="${2:-}"
      shift 2
      ;;
    --store)
      STORE="${2:-}"
      shift 2
      ;;
    --delivery-zip|--delivery_zip)
      DELIVERY_ZIP="${2:-}"
      shift 2
      ;;
    --page)
      PAGE="${2:-}"
      shift 2
      ;;
    --page-size|--page_size)
      PAGE_SIZE="${2:-}"
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

if [[ -z "$Q" ]]; then
  echo "Missing required argument: --q" >&2
  exit 1
fi

COUNTRY_LOWER="$(printf '%s' "$COUNTRY" | tr '[:upper:]' '[:lower:]')"
case "$COUNTRY_LOWER" in
  ""|us|ca)
    ;;
  *)
    echo "Invalid value for --country: $COUNTRY" >&2
    echo "Allowed values: us, ca" >&2
    exit 1
    ;;
esac

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

if [[ -n "$PAGE_SIZE" ]] && ! is_integer "$PAGE_SIZE"; then
  echo "Invalid value for --page-size: $PAGE_SIZE" >&2
  echo "Allowed range: integers from 1 to 40" >&2
  exit 1
fi

if [[ -n "$PAGE_SIZE" && ( "$PAGE_SIZE" -lt 1 || "$PAGE_SIZE" -gt 40 ) ]]; then
  echo "Invalid value for --page-size: $PAGE_SIZE" >&2
  echo "Allowed range: integers from 1 to 40" >&2
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
  OUTPUT_PATH="out/home-depot-search-$(date -u +%Y%m%dT%H%M%SZ)-$$.json"
fi

PAYLOAD_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
RESULT_FILE="$(mktemp)"
cleanup() {
  rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE" "$RESULT_FILE"
}
trap cleanup EXIT

export Q COUNTRY_LOWER STORE DELIVERY_ZIP PAGE PAGE_SIZE

python3 - "$PAYLOAD_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path

payload_path = Path(sys.argv[1])

payload = {
    "q": os.environ["Q"],
}

optional_fields = {
    "country": os.environ.get("COUNTRY_LOWER"),
    "store": os.environ.get("STORE"),
    "delivery_zip": os.environ.get("DELIVERY_ZIP"),
}

for key, value in optional_fields.items():
    if value:
        payload[key] = value

if os.environ.get("PAGE"):
    payload["page"] = int(os.environ["PAGE"])

if os.environ.get("PAGE_SIZE"):
    payload["page_size"] = int(os.environ["PAGE_SIZE"])

payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
PY

HTTP_CODE="$(
  curl -sS \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -o "$RESPONSE_FILE" \
    -w "%{http_code}" \
    -X POST "$API_BASE_URL$HOME_DEPOT_SEARCH_PATH" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    --data @"$PAYLOAD_FILE"
)"

if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "Home Depot search API request failed with HTTP $HTTP_CODE" >&2
  cat "$RESPONSE_FILE" >&2
  exit 1
fi

if [[ ! -s "$RESPONSE_FILE" ]]; then
  echo "Home Depot search API returned an empty response body." >&2
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
    print(f"Home Depot search API returned non-JSON response: {exc}", file=sys.stderr)
    print(raw, file=sys.stderr)
    sys.exit(1)

result_path.write_text(raw, encoding="utf-8")
PY

mkdir -p "$(dirname "$OUTPUT_PATH")"
cp "$RESULT_FILE" "$OUTPUT_PATH"
echo "Saved Home Depot search JSON to $OUTPUT_PATH" >&2

cat "$RESULT_FILE"
