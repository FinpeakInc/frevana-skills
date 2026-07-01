#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="${FREVANA_API_BASE_URL:-https://ai-factory.frevana.com}"
API_PATH="/service/google-ads-keywords-for-keywords"
CONNECT_TIMEOUT="10"
MAX_TIME="600"

usage() {
  cat <<'EOF'
Usage:
  search_google_ads_keywords_for_keywords.sh --keywords "phone,cellphone" [options]

Options:
  --keywords                 Comma-separated seed keyword list
  --location-name            Full Google Ads location name
  --location-code            Google Ads location code
  --location-coordinate      GPS coordinates in latitude,longitude format
  --language-name            Full Google Ads language name
  --language-code            Google Ads language code
  --search-partners          Whether to include Google search partners. Defaults to false
  --search_partners          Alias for --search-partners
  --date-from                Historical data start date in yyyy-mm-dd format
  --date-to                  Historical data end date in yyyy-mm-dd format
  --sort-by                  Sort by relevance, search_volume, competition_index, low_top_of_page_bid, or high_top_of_page_bid
  --include-adult-keywords   Whether to include adult keywords. Defaults to false
  --include_adult_keywords   Alias for --include-adult-keywords
  --tag                      User-defined task identifier
  --output                   Optional file path for saving returned JSON. Defaults to ./out/google-ads-keywords-for-keywords-<timestamp>-<pid>.json
  --token                    Optional Bearer token override for this run
  -h, --help                 Show this help message
EOF
}

fail() {
  echo "$1" >&2
  exit 1
}

KEYWORDS=""
LOCATION_NAME=""
LOCATION_CODE=""
LOCATION_COORDINATE=""
LANGUAGE_NAME=""
LANGUAGE_CODE=""
SEARCH_PARTNERS="false"
DATE_FROM=""
DATE_TO=""
SORT_BY=""
INCLUDE_ADULT_KEYWORDS="false"
TAG=""
OUTPUT_PATH=""
TOKEN_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --keywords)
      KEYWORDS="${2:-}"
      shift 2
      ;;
    --location-name|--location_name)
      LOCATION_NAME="${2:-}"
      shift 2
      ;;
    --location-code|--location_code)
      LOCATION_CODE="${2:-}"
      shift 2
      ;;
    --location-coordinate|--location_coordinate)
      LOCATION_COORDINATE="${2:-}"
      shift 2
      ;;
    --language-name|--language_name)
      LANGUAGE_NAME="${2:-}"
      shift 2
      ;;
    --language-code|--language_code)
      LANGUAGE_CODE="${2:-}"
      shift 2
      ;;
    --search-partners|--search_partners)
      SEARCH_PARTNERS="${2:-}"
      shift 2
      ;;
    --date-from|--date_from)
      DATE_FROM="${2:-}"
      shift 2
      ;;
    --date-to|--date_to)
      DATE_TO="${2:-}"
      shift 2
      ;;
    --sort-by|--sort_by)
      SORT_BY="${2:-}"
      shift 2
      ;;
    --include-adult-keywords|--include_adult_keywords)
      INCLUDE_ADULT_KEYWORDS="${2:-}"
      shift 2
      ;;
    --tag)
      TAG="${2:-}"
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
  OUTPUT_PATH="out/google-ads-keywords-for-keywords-$(date -u +%Y%m%dT%H%M%SZ)-$$.json"
fi

PAYLOAD_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
RESULT_FILE="$(mktemp)"
cleanup() {
  rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE" "$RESULT_FILE"
}
trap cleanup EXIT

export KEYWORDS LOCATION_NAME LOCATION_CODE LOCATION_COORDINATE
export LANGUAGE_NAME LANGUAGE_CODE SEARCH_PARTNERS DATE_FROM DATE_TO SORT_BY
export INCLUDE_ADULT_KEYWORDS TAG

python3 - "$PAYLOAD_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path

payload_path = Path(sys.argv[1])

def env(name):
    return os.environ.get(name, "").strip()

def parse_bool(name, label):
    raw = env(name).lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    print(f"Invalid {label} value: expected true or false.", file=sys.stderr)
    sys.exit(1)

keywords = [item.strip() for item in env("KEYWORDS").split(",") if item.strip()]
if not keywords:
    print("At least one non-empty keyword is required.", file=sys.stderr)
    sys.exit(1)
if len(keywords) > 20:
    print("--keywords accepts at most 20 seed keywords.", file=sys.stderr)
    sys.exit(1)

location_values = [env("LOCATION_NAME"), env("LOCATION_CODE"), env("LOCATION_COORDINATE")]
if sum(1 for value in location_values if value) > 1:
    print("Use only one of --location-name, --location-code, or --location-coordinate.", file=sys.stderr)
    sys.exit(1)

if env("LANGUAGE_NAME") and env("LANGUAGE_CODE"):
    print("Use only one of --language-name or --language-code.", file=sys.stderr)
    sys.exit(1)

sort_by = env("SORT_BY")
allowed_sort = {
    "relevance",
    "search_volume",
    "competition_index",
    "low_top_of_page_bid",
    "high_top_of_page_bid",
}
if sort_by and sort_by not in allowed_sort:
    print("--sort-by must be one of: relevance, search_volume, competition_index, low_top_of_page_bid, high_top_of_page_bid.", file=sys.stderr)
    sys.exit(1)

payload = {
    "keywords": keywords,
    "search_partners": parse_bool("SEARCH_PARTNERS", "--search-partners"),
    "include_adult_keywords": parse_bool("INCLUDE_ADULT_KEYWORDS", "--include-adult-keywords"),
}

if env("LOCATION_NAME"):
    payload["location_name"] = env("LOCATION_NAME")
if env("LOCATION_CODE"):
    try:
        payload["location_code"] = int(env("LOCATION_CODE"))
    except ValueError:
        print("--location-code must be an integer.", file=sys.stderr)
        sys.exit(1)
if env("LOCATION_COORDINATE"):
    payload["location_coordinate"] = env("LOCATION_COORDINATE")
if env("LANGUAGE_NAME"):
    payload["language_name"] = env("LANGUAGE_NAME")
if env("LANGUAGE_CODE"):
    payload["language_code"] = env("LANGUAGE_CODE")
if env("DATE_FROM"):
    payload["date_from"] = env("DATE_FROM")
if env("DATE_TO"):
    payload["date_to"] = env("DATE_TO")
if sort_by:
    payload["sort_by"] = sort_by
if env("TAG"):
    payload["tag"] = env("TAG")

payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
PY

HTTP_CODE="$(
  curl -sS \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -o "$RESPONSE_FILE" \
    -w "%{http_code}" \
    -X POST "$API_BASE_URL$API_PATH" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    --data @"$PAYLOAD_FILE"
)"

if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "Google Ads keywords for keywords API request failed with HTTP $HTTP_CODE" >&2
  cat "$RESPONSE_FILE" >&2
  exit 1
fi

[[ -s "$RESPONSE_FILE" ]] || fail "Google Ads keywords for keywords API returned an empty response body."

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
    print(f"Google Ads keywords for keywords API returned non-JSON response: {exc}", file=sys.stderr)
    print(raw, file=sys.stderr)
    sys.exit(1)

result_path.write_text(raw, encoding="utf-8")
PY

mkdir -p "$(dirname "$OUTPUT_PATH")"
cp "$RESULT_FILE" "$OUTPUT_PATH"
echo "Saved Google Ads keywords for keywords JSON to $OUTPUT_PATH" >&2

cat "$RESULT_FILE"
