#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="https://ai-factory.frevana.com"
GOOGLE_PATENTS_PATH="/service/serpapi/google-patents"
CONNECT_TIMEOUT="10"
MAX_TIME="600"

usage() {
  cat <<'EOF'
Usage:
  search_google_patents.sh --q "(Coffee)" [--page 0] [--num 10] [--language en] [--status GRANT|APPLICATION] [--output /path/to/result.json] [--token "bearer token"]

Options:
  --q           Search query to send
  --query       Alias for --q
  --page        Optional page number, 0 or greater
  --num         Optional results per page, 10 through 100
  --language    Optional patents language filter
  --status      Optional patent status: GRANT or APPLICATION
  --output      Optional file path for saving returned JSON. Defaults to ./out/google-patents-search-<timestamp>-<pid>.json
  --token       Optional Bearer token override for this run
  -h, --help    Show this help message
EOF
}

Q=""
PAGE=""
NUM=""
LANGUAGE=""
STATUS=""
OUTPUT_PATH=""
TOKEN_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --q|--query)
      Q="${2:-}"
      shift 2
      ;;
    --page)
      PAGE="${2:-}"
      shift 2
      ;;
    --num)
      NUM="${2:-}"
      shift 2
      ;;
    --language)
      LANGUAGE="${2:-}"
      shift 2
      ;;
    --status)
      STATUS="${2:-}"
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

if [[ -n "$PAGE" ]]; then
  if ! [[ "$PAGE" =~ ^[0-9]+$ ]]; then
    echo "Invalid --page value: $PAGE. Expected an integer 0 or greater." >&2
    exit 1
  fi
fi

if [[ -n "$NUM" ]]; then
  if ! [[ "$NUM" =~ ^[0-9]+$ ]]; then
    echo "Invalid --num value: $NUM. Expected an integer from 10 through 100." >&2
    exit 1
  fi
  if (( NUM < 10 || NUM > 100 )); then
    echo "Invalid --num value: $NUM. Expected an integer from 10 through 100." >&2
    exit 1
  fi
fi

if [[ -n "$STATUS" && "$STATUS" != "GRANT" && "$STATUS" != "APPLICATION" ]]; then
  echo "Invalid --status value: $STATUS. Allowed values: GRANT, APPLICATION" >&2
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
  OUTPUT_PATH="out/google-patents-search-$(date -u +%Y%m%dT%H%M%SZ)-$$.json"
fi

PAYLOAD_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
RESULT_FILE="$(mktemp)"
cleanup() {
  rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE" "$RESULT_FILE"
}
trap cleanup EXIT

export Q PAGE NUM LANGUAGE STATUS

python3 - "$PAYLOAD_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path

payload_path = Path(sys.argv[1])

payload = {
    "q": os.environ["Q"],
}

string_fields = {
    "language": os.environ.get("LANGUAGE"),
    "status": os.environ.get("STATUS"),
}

for key, value in string_fields.items():
    if value:
        payload[key] = value

number_fields = {
    "page": os.environ.get("PAGE"),
    "num": os.environ.get("NUM"),
}

for key, value in number_fields.items():
    if value:
        payload[key] = int(value)

payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
PY

HTTP_CODE="$(
  curl -sS \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -o "$RESPONSE_FILE" \
    -w "%{http_code}" \
    -X POST "$API_BASE_URL$GOOGLE_PATENTS_PATH" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    --data @"$PAYLOAD_FILE"
)"

if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "Google Patents API request failed with HTTP $HTTP_CODE" >&2
  cat "$RESPONSE_FILE" >&2
  exit 1
fi

if [[ ! -s "$RESPONSE_FILE" ]]; then
  echo "Google Patents API returned an empty response body." >&2
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
    print(f"Google Patents API returned non-JSON response: {exc}", file=sys.stderr)
    print(raw, file=sys.stderr)
    sys.exit(1)

result_path.write_text(raw, encoding="utf-8")
PY

mkdir -p "$(dirname "$OUTPUT_PATH")"
cp "$RESULT_FILE" "$OUTPUT_PATH"
echo "Saved Google Patents JSON to $OUTPUT_PATH" >&2

cat "$RESULT_FILE"
