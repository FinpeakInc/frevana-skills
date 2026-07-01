#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="${FREVANA_API_BASE_URL:-https://ai-factory.frevana.com}"
GOOGLE_ADS_KEYWORDS_SEARCH_VOLUME_PATH="/service/google-ads-search-volume"
CONNECT_TIMEOUT="10"
MAX_TIME="600"

usage() {
  cat <<'EOF'
Usage:
  search_google_ads_keywords_search_volume.sh --keywords "wireless earbuds,gaming headset" [--search-partners true|false] [--output /path/to/result.json] [--token "bearer token"]

Options:
  --keywords           Comma-separated keyword list
  --search-partners    Whether to include search partners. Defaults to true
  --search_partners    Alias for --search-partners
  --output             Optional file path for saving returned JSON. Defaults to ./out/google-ads-keywords-search-volume-<timestamp>-<pid>.json
  --token              Optional Bearer token override for this run
  -h, --help           Show this help message
EOF
}

fail() {
  echo "$1" >&2
  exit 1
}

KEYWORDS=""
SEARCH_PARTNERS="true"
OUTPUT_PATH=""
TOKEN_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --keywords)
      KEYWORDS="${2:-}"
      shift 2
      ;;
    --search-partners|--search_partners)
      SEARCH_PARTNERS="${2:-}"
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

[[ -n "$KEYWORDS" ]] || fail "Missing required argument: --keywords"

command -v curl >/dev/null 2>&1 || fail "curl is required but was not found in PATH."
command -v python3 >/dev/null 2>&1 || fail "python3 is required but was not found in PATH."

TOKEN="${TOKEN_OVERRIDE:-${FREVANA_TOKEN:-}}"
if [[ -z "$TOKEN" && -t 0 ]]; then
  read -r -s -p "FREVANA_TOKEN not found. Please enter your Frevana Bearer token: " TOKEN
  echo >&2
fi
[[ -n "$TOKEN" ]] || fail "FREVANA_TOKEN is not set. In non-interactive runs, set FREVANA_TOKEN or pass --token explicitly."

if [[ -z "$OUTPUT_PATH" ]]; then
  OUTPUT_PATH="out/google-ads-keywords-search-volume-$(date -u +%Y%m%dT%H%M%SZ)-$$.json"
fi

PAYLOAD_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
RESULT_FILE="$(mktemp)"
cleanup() {
  rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE" "$RESULT_FILE"
}
trap cleanup EXIT

export KEYWORDS SEARCH_PARTNERS

python3 - "$PAYLOAD_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path

payload_path = Path(sys.argv[1])

keywords = [
    item.strip()
    for item in os.environ["KEYWORDS"].split(",")
    if item.strip()
]

if not keywords:
    print("At least one non-empty keyword is required.", file=sys.stderr)
    sys.exit(1)

raw_search_partners = os.environ["SEARCH_PARTNERS"].strip().lower()
if raw_search_partners in {"1", "true", "yes", "on"}:
    search_partners = True
elif raw_search_partners in {"0", "false", "no", "off"}:
    search_partners = False
else:
    print("Invalid --search-partners value: expected true or false.", file=sys.stderr)
    sys.exit(1)

payload = {
    "keywords": keywords,
    "search_partners": search_partners,
}

payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
PY

HTTP_CODE="$(
  curl -sS \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -o "$RESPONSE_FILE" \
    -w "%{http_code}" \
    -X POST "$API_BASE_URL$GOOGLE_ADS_KEYWORDS_SEARCH_VOLUME_PATH" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    --data @"$PAYLOAD_FILE"
)"

if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "Google Ads keywords search volume API request failed with HTTP $HTTP_CODE" >&2
  cat "$RESPONSE_FILE" >&2
  exit 1
fi

[[ -s "$RESPONSE_FILE" ]] || fail "Google Ads keywords search volume API returned an empty response body."

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
    print(f"Google Ads keywords search volume API returned non-JSON response: {exc}", file=sys.stderr)
    print(raw, file=sys.stderr)
    sys.exit(1)

result_path.write_text(raw, encoding="utf-8")
PY

mkdir -p "$(dirname "$OUTPUT_PATH")"
cp "$RESULT_FILE" "$OUTPUT_PATH"
echo "Saved Google Ads keywords search volume JSON to $OUTPUT_PATH" >&2

cat "$RESULT_FILE"
