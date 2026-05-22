#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="https://ai-factory.frevana.com"
GOOGLE_TRENDS_PATH="/service/serpapi/google-trends"
CONNECT_TIMEOUT="10"
MAX_TIME="600"

usage() {
  cat <<'EOF'
Usage:
  search_google_trends.sh --q "home treadmill" [--geo US] [--cat 18] [--date "today 12-m"] [--gprop images|news|youtube|froogle] [--hl en] [--tz 420] [--output /path/to/result.json] [--token "bearer token"]

Options:
  --q                 Search query keyword to send
  --query             Alias for --q
  --geo               Optional country/region code for trends
  --cat               Optional category id
  --date              Optional date range
  --gprop             Optional Google property
  --hl                Optional language code
  --tz                Optional timezone offset in minutes
  --output            Optional file path for saving returned JSON. Defaults to ./out/google-trends-<timestamp>-<pid>.json
  --token             Optional Bearer token override for this run
  -h, --help          Show this help message
EOF
}

Q=""
GEO=""
CAT=""
DATE_RANGE=""
GPROP=""
HL=""
TZ=""
OUTPUT_PATH=""
TOKEN_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --q|--query)
      Q="${2:-}"
      shift 2
      ;;
    --geo)
      GEO="${2:-}"
      shift 2
      ;;
    --cat)
      CAT="${2:-}"
      shift 2
      ;;
    --date)
      DATE_RANGE="${2:-}"
      shift 2
      ;;
    --gprop)
      GPROP="${2:-}"
      shift 2
      ;;
    --hl)
      HL="${2:-}"
      shift 2
      ;;
    --tz)
      TZ="${2:-}"
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
  OUTPUT_PATH="out/google-trends-$(date -u +%Y%m%dT%H%M%SZ)-$$.json"
fi

PAYLOAD_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
RESULT_FILE="$(mktemp)"
cleanup() {
  rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE" "$RESULT_FILE"
}
trap cleanup EXIT

export Q GEO CAT DATE_RANGE GPROP HL TZ

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
    "geo": os.environ.get("GEO"),
    "cat": os.environ.get("CAT"),
    "date": os.environ.get("DATE_RANGE"),
    "gprop": os.environ.get("GPROP"),
    "hl": os.environ.get("HL"),
    "tz": os.environ.get("TZ"),
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
    -X POST "$API_BASE_URL$GOOGLE_TRENDS_PATH" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    --data @"$PAYLOAD_FILE"
)"

if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "Google Trends API request failed with HTTP $HTTP_CODE" >&2
  cat "$RESPONSE_FILE" >&2
  exit 1
fi

if [[ ! -s "$RESPONSE_FILE" ]]; then
  echo "Google Trends API returned an empty response body." >&2
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
    print(f"Google Trends API returned non-JSON response: {exc}", file=sys.stderr)
    print(raw, file=sys.stderr)
    sys.exit(1)

result_path.write_text(raw, encoding="utf-8")
PY

mkdir -p "$(dirname "$OUTPUT_PATH")"
cp "$RESULT_FILE" "$OUTPUT_PATH"
echo "Saved Google Trends JSON to $OUTPUT_PATH" >&2

cat "$RESULT_FILE"
