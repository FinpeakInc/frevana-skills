#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="https://ai-factory.frevana.com"
GOOGLE_ADS_TRANSPARENCY_CENTER_PATH="/service/google-ads-transparency-center"
CONNECT_TIMEOUT="10"
MAX_TIME="600"

usage() {
  cat <<'EOF'
Usage:
  search_google_ads_transparency_center.sh [--advertiser-id AR...] [--text "apple.com"] [--platform PLAY|MAPS|SEARCH|SHOPPING|YOUTUBE] [--region 2840] [--next-page-token TOKEN] [--output /path/to/result.json] [--token "bearer token"]

Options:
  --advertiser-id       Optional Google advertiser ID. Can be a single ID or comma-separated IDs.
  --advertiser_id       Alias for --advertiser-id
  --text                Optional domain or free text to search ads by
  --q                   Alias for --text
  --query               Alias for --text
  --platform            Optional target platform: PLAY, MAPS, SEARCH, SHOPPING, or YOUTUBE
  --region              Optional Google Ads Transparency Center region numeric ID
  --next-page-token     Optional pagination token from serpapi_pagination.next_page_token
  --next_page_token     Alias for --next-page-token
  --output              Optional file path for saving returned JSON. Defaults to ./out/google-ads-transparency-center-<timestamp>-<pid>.json
  --token               Optional Bearer token override for this run
  -h, --help            Show this help message
EOF
}

ADVERTISER_ID=""
TEXT=""
PLATFORM=""
REGION=""
NEXT_PAGE_TOKEN=""
OUTPUT_PATH=""
TOKEN_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --advertiser-id|--advertiser_id)
      ADVERTISER_ID="${2:-}"
      shift 2
      ;;
    --text|--q|--query)
      TEXT="${2:-}"
      shift 2
      ;;
    --platform)
      PLATFORM="${2:-}"
      shift 2
      ;;
    --region)
      REGION="${2:-}"
      shift 2
      ;;
    --next-page-token|--next_page_token)
      NEXT_PAGE_TOKEN="${2:-}"
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

if [[ -z "$ADVERTISER_ID" && -z "$TEXT" && -z "$NEXT_PAGE_TOKEN" ]]; then
  echo "Missing required input: provide --advertiser-id, --text, or --next-page-token." >&2
  exit 1
fi

case "$PLATFORM" in
  ""|PLAY|MAPS|SEARCH|SHOPPING|YOUTUBE)
    ;;
  *)
    echo "Invalid value for --platform: $PLATFORM" >&2
    echo "Allowed values: PLAY, MAPS, SEARCH, SHOPPING, YOUTUBE" >&2
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
  OUTPUT_PATH="out/google-ads-transparency-center-$(date -u +%Y%m%dT%H%M%SZ)-$$.json"
fi

PAYLOAD_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
RESULT_FILE="$(mktemp)"
cleanup() {
  rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE" "$RESULT_FILE"
}
trap cleanup EXIT

export ADVERTISER_ID TEXT PLATFORM REGION NEXT_PAGE_TOKEN

python3 - "$PAYLOAD_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path

payload_path = Path(sys.argv[1])
payload = {}

optional_fields = {
    "advertiser_id": os.environ.get("ADVERTISER_ID"),
    "text": os.environ.get("TEXT"),
    "platform": os.environ.get("PLATFORM"),
    "region": os.environ.get("REGION"),
    "next_page_token": os.environ.get("NEXT_PAGE_TOKEN"),
}

for key, value in optional_fields.items():
    if value:
        payload[key] = value

payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
PY

HTTP_CODE="$(
  curl -sS \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -o "$RESPONSE_FILE" \
    -w "%{http_code}" \
    -X POST "$API_BASE_URL$GOOGLE_ADS_TRANSPARENCY_CENTER_PATH" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    --data @"$PAYLOAD_FILE"
)"

if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "Google Ads Transparency Center API request failed with HTTP $HTTP_CODE" >&2
  cat "$RESPONSE_FILE" >&2
  exit 1
fi

if [[ ! -s "$RESPONSE_FILE" ]]; then
  echo "Google Ads Transparency Center API returned an empty response body." >&2
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
    print(f"Google Ads Transparency Center API returned non-JSON response: {exc}", file=sys.stderr)
    print(raw, file=sys.stderr)
    sys.exit(1)

result_path.write_text(raw, encoding="utf-8")
PY

mkdir -p "$(dirname "$OUTPUT_PATH")"
cp "$RESULT_FILE" "$OUTPUT_PATH"
echo "Saved Google Ads Transparency Center JSON to $OUTPUT_PATH" >&2

cat "$RESULT_FILE"
