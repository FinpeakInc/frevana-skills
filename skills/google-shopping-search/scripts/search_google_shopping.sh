#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="${FREVANA_API_BASE_URL:-https://ai-factory.frevana.com}"
GOOGLE_SHOPPING_SEARCH_PATH="/service/google-shopping-search"
CONNECT_TIMEOUT="10"
MAX_TIME="600"

usage() {
  cat <<'EOF'
Usage:
  search_google_shopping.sh --q "wireless earbuds" [--google-domain google.com] [--gl US] [--hl en] [--start 0] [--device desktop|mobile|tablet] [--sort-by 1|2] [--output /path/to/result.json] [--token "bearer token"]

Options:
  --q                 Search query keyword to send
  --query             Alias for --q
  --google-domain     Optional Google domain
  --gl                Optional country code
  --hl                Optional language code
  --start             Optional start offset for pagination
  --device            Optional device type: desktop, mobile, or tablet
  --sort-by           Optional Google Shopping sort order: 1 price low to high, 2 price high to low
  --output            Optional file path for saving returned JSON. Defaults to ./out/google-shopping-search-<timestamp>-<pid>.json
  --token             Optional Bearer token override for this run
  -h, --help          Show this help message
EOF
}

is_integer() {
  [[ "$1" =~ ^[0-9]+$ ]]
}

Q=""
GOOGLE_DOMAIN=""
GL=""
HL=""
START=""
DEVICE=""
SORT_BY=""
OUTPUT_PATH=""
TOKEN_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --q|--query)
      Q="${2:-}"
      shift 2
      ;;
    --google-domain|--google_domain)
      GOOGLE_DOMAIN="${2:-}"
      shift 2
      ;;
    --gl)
      GL="${2:-}"
      shift 2
      ;;
    --hl)
      HL="${2:-}"
      shift 2
      ;;
    --start)
      START="${2:-}"
      shift 2
      ;;
    --device)
      DEVICE="${2:-}"
      shift 2
      ;;
    --sort-by|--sort_by)
      SORT_BY="${2:-}"
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

if [[ -n "$START" ]] && ! is_integer "$START"; then
  echo "Invalid value for --start: $START" >&2
  echo "Allowed range: integers >= 0" >&2
  exit 1
fi

case "$DEVICE" in
  ""|desktop|mobile|tablet)
    ;;
  *)
    echo "Invalid value for --device: $DEVICE" >&2
    echo "Allowed values: desktop, mobile, tablet" >&2
    exit 1
    ;;
esac

case "$SORT_BY" in
  ""|1|2)
    ;;
  *)
    echo "Invalid value for --sort-by: $SORT_BY" >&2
    echo "Allowed values: 1 (price low to high), 2 (price high to low)" >&2
    exit 1
    ;;
esac

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
  OUTPUT_PATH="out/google-shopping-search-$(date -u +%Y%m%dT%H%M%SZ)-$$.json"
fi

PAYLOAD_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
RESULT_FILE="$(mktemp)"
cleanup() {
  rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE" "$RESULT_FILE"
}
trap cleanup EXIT

export Q GOOGLE_DOMAIN GL HL START DEVICE SORT_BY

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
    "google_domain": os.environ.get("GOOGLE_DOMAIN"),
    "gl": os.environ.get("GL"),
    "hl": os.environ.get("HL"),
    "device": os.environ.get("DEVICE"),
    "sort_by": os.environ.get("SORT_BY"),
}

for key, value in optional_fields.items():
    if value:
        payload[key] = value

if os.environ.get("START"):
    payload["start"] = int(os.environ["START"])

payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
PY

HTTP_CODE="$(
  curl -sS \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -o "$RESPONSE_FILE" \
    -w "%{http_code}" \
    -X POST "$API_BASE_URL$GOOGLE_SHOPPING_SEARCH_PATH" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    --data @"$PAYLOAD_FILE"
)"

if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "Google Shopping search API request failed with HTTP $HTTP_CODE" >&2
  cat "$RESPONSE_FILE" >&2
  exit 1
fi

if [[ ! -s "$RESPONSE_FILE" ]]; then
  echo "Google Shopping search API returned an empty response body." >&2
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
    print(f"Google Shopping search API returned non-JSON response: {exc}", file=sys.stderr)
    print(raw, file=sys.stderr)
    sys.exit(1)

result_path.write_text(raw, encoding="utf-8")
PY

mkdir -p "$(dirname "$OUTPUT_PATH")"
cp "$RESULT_FILE" "$OUTPUT_PATH"
echo "Saved Google Shopping search JSON to $OUTPUT_PATH" >&2

cat "$RESULT_FILE"
