#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="https://ai-factory.frevana.com"
AMAZON_PRODUCT_PATH="/service/serpapi/amazon-product"
CONNECT_TIMEOUT="10"
MAX_TIME="600"

usage() {
  cat <<'EOF'
Usage:
  fetch_product.sh --asin B0BDJ49KVD [--amazon-domain amazon.com] [--gl US] [--hl en] [--customer-zipcode 10001] [--force-refresh true|false] [--output /path/to/result.json] [--token "bearer token"]

Options:
  --asin               Amazon ASIN to fetch
  --amazon-domain      Amazon domain to query (default: amazon.com)
  --gl                 Country code (default: US)
  --hl                 Language code (default: en)
  --customer-zipcode   Optional customer ZIP code
  --force-refresh      Force refresh flag: true or false (default: false)
  --output             Optional file path for saving returned JSON
  --token              Optional Bearer token override for this run
  -h, --help           Show this help message
EOF
}

ASIN=""
AMAZON_DOMAIN="amazon.com"
GL="US"
HL="en"
CUSTOMER_ZIPCODE=""
FORCE_REFRESH="false"
OUTPUT_PATH=""
TOKEN_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --asin)
      ASIN="${2:-}"
      shift 2
      ;;
    --amazon-domain)
      AMAZON_DOMAIN="${2:-}"
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
    --customer-zipcode)
      CUSTOMER_ZIPCODE="${2:-}"
      shift 2
      ;;
    --force-refresh)
      if [[ $# -gt 1 && "${2:-}" != --* ]]; then
        FORCE_REFRESH="${2:-}"
        shift 2
      else
        FORCE_REFRESH="true"
        shift
      fi
      ;;
    --no-force-refresh)
      FORCE_REFRESH="false"
      shift
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

if [[ -z "$ASIN" ]]; then
  echo "Missing required argument: --asin" >&2
  exit 1
fi

case "$FORCE_REFRESH" in
  true|false)
    ;;
  *)
    echo "Invalid value for --force-refresh: $FORCE_REFRESH" >&2
    echo "Allowed values: true, false" >&2
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

PAYLOAD_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
RESULT_FILE="$(mktemp)"
cleanup() {
  rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE" "$RESULT_FILE"
}
trap cleanup EXIT

export ASIN AMAZON_DOMAIN GL HL CUSTOMER_ZIPCODE FORCE_REFRESH

python3 - "$PAYLOAD_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path

payload_path = Path(sys.argv[1])

payload = {
    "asin": os.environ["ASIN"],
    "amazon_domain": os.environ["AMAZON_DOMAIN"],
    "gl": os.environ["GL"],
    "hl": os.environ["HL"],
    "force_refresh": os.environ["FORCE_REFRESH"] == "true",
}

if os.environ.get("CUSTOMER_ZIPCODE"):
    payload["customer_zipcode"] = os.environ["CUSTOMER_ZIPCODE"]

payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
PY

HTTP_CODE="$(
  curl -sS \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -o "$RESPONSE_FILE" \
    -w "%{http_code}" \
    -X POST "$API_BASE_URL$AMAZON_PRODUCT_PATH" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    --data @"$PAYLOAD_FILE"
)"

if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "Amazon product API request failed with HTTP $HTTP_CODE" >&2
  cat "$RESPONSE_FILE" >&2
  exit 1
fi

if [[ ! -s "$RESPONSE_FILE" ]]; then
  echo "Amazon product API returned an empty response body." >&2
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
    print(f"Amazon product API returned non-JSON response: {exc}", file=sys.stderr)
    print(raw, file=sys.stderr)
    sys.exit(1)

result_path.write_text(raw, encoding="utf-8")
PY

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  cp "$RESULT_FILE" "$OUTPUT_PATH"
fi

cat "$RESULT_FILE"
