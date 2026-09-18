#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="${FREVANA_API_BASE_URL:-https://ai-factory.frevana.com}"
APPLE_PRODUCT_PATH="/service/apple-product"
CONNECT_TIMEOUT="10"
MAX_TIME="600"

usage() {
  cat <<'EOF'
Usage:
  get_apple_product.sh --product-id "6444058226" [--type app] [--country us] [--serpapi-output json|html] [--no-cache] [--async] [--zero-trace] [--output /path/to/result.json] [--token "bearer token"]

Options:
  --product-id, --id Unique product ID (required)
  --type             Type of Apple product (default: app)
  --country          Two-letter country code for the App Store region (default: us)
  --serpapi-output   SerpAPI output format: json or html
  --no-cache         Force SerpAPI to fetch fresh results instead of cache
  --async            Submit search asynchronously and retrieve it later
  --zero-trace       Enable SerpAPI ZeroTrace mode for Enterprise accounts
  --output           Optional file path for saving returned JSON. Defaults to ./out/apple-product-<timestamp>-<pid>.json
  --token            Optional Bearer token override for this run
  -h, --help         Show this help message
EOF
}

PRODUCT_ID=""
PRODUCT_TYPE=""
COUNTRY=""
SERPAPI_OUTPUT=""
NO_CACHE=""
ASYNC_REQ=""
ZERO_TRACE=""
OUTPUT_PATH=""
TOKEN_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --product-id|--id)
      PRODUCT_ID="${2:-}"
      shift 2
      ;;
    --type)
      PRODUCT_TYPE="${2:-}"
      shift 2
      ;;
    --country)
      COUNTRY="${2:-}"
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

if [[ -z "$PRODUCT_ID" ]]; then
  echo "Missing required argument: --product-id" >&2
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
  OUTPUT_PATH="out/apple-product-$(date -u +%Y%m%dT%H%M%SZ)-$$.json"
fi

PAYLOAD_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
RESULT_FILE="$(mktemp)"
cleanup() {
  rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE" "$RESULT_FILE"
}
trap cleanup EXIT

export PRODUCT_ID PRODUCT_TYPE COUNTRY SERPAPI_OUTPUT NO_CACHE ASYNC_REQ ZERO_TRACE

python3 - "$PAYLOAD_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path

payload_path = Path(sys.argv[1])

payload = {
    "product_id": os.environ["PRODUCT_ID"],
}

string_fields = {
    "type": os.environ.get("PRODUCT_TYPE"),
    "country": os.environ.get("COUNTRY"),
    "output": os.environ.get("SERPAPI_OUTPUT"),
}

for key, value in string_fields.items():
    if value:
        payload[key] = value

bool_fields = {
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
    -X POST "$API_BASE_URL$APPLE_PRODUCT_PATH" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    --data @"$PAYLOAD_FILE"
)"

if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "Apple Product API request failed with HTTP $HTTP_CODE" >&2
  cat "$RESPONSE_FILE" >&2
  exit 1
fi

if [[ ! -s "$RESPONSE_FILE" ]]; then
  echo "Apple Product API returned an empty response body." >&2
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
    print(f"Apple Product API returned non-JSON response: {exc}", file=sys.stderr)
    print(raw, file=sys.stderr)
    sys.exit(1)

result_path.write_text(raw, encoding="utf-8")
PY

mkdir -p "$(dirname "$OUTPUT_PATH")"
cp "$RESULT_FILE" "$OUTPUT_PATH"
echo "Saved Apple Product JSON to $OUTPUT_PATH" >&2

cat "$RESULT_FILE"
