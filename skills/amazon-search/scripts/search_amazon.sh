#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="https://ai-factory.frevana.com"
AMAZON_SEARCH_PATH="/service/serpapi/amazon-search"
CONNECT_TIMEOUT="10"
MAX_TIME="600"

usage() {
  cat <<'EOF'
Usage:
  search_amazon.sh --query "wireless mouse" [--delivery-zip 10001] [--page 1] [--output /path/to/result.json] [--token "bearer token"]

Options:
  --query          Search keyword to send
  --delivery-zip   Optional delivery ZIP code
  --page           Optional result page (default: 1)
  --output         Optional file path for saving returned JSON
  --token          Optional Bearer token override for this run
  -h, --help       Show this help message
EOF
}

is_integer() {
  [[ "$1" =~ ^[0-9]+$ ]]
}

QUERY=""
DELIVERY_ZIP=""
PAGE="1"
OUTPUT_PATH=""
TOKEN_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --query)
      QUERY="${2:-}"
      shift 2
      ;;
    --delivery-zip)
      DELIVERY_ZIP="${2:-}"
      shift 2
      ;;
    --page)
      PAGE="${2:-}"
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

if ! is_integer "$PAGE" || (( PAGE < 1 )); then
  echo "Invalid value for --page: $PAGE" >&2
  echo "Allowed range: integers >= 1" >&2
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

PAYLOAD_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
RESULT_FILE="$(mktemp)"
cleanup() {
  rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE" "$RESULT_FILE"
}
trap cleanup EXIT

export QUERY DELIVERY_ZIP PAGE

python3 - "$PAYLOAD_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path

payload_path = Path(sys.argv[1])

payload = {
    "query": os.environ["QUERY"],
    "page": int(os.environ["PAGE"]),
}

if os.environ.get("DELIVERY_ZIP"):
    payload["delivery_zip"] = os.environ["DELIVERY_ZIP"]

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

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  cp "$RESULT_FILE" "$OUTPUT_PATH"
fi

cat "$RESULT_FILE"
