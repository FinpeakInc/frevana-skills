#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="${FREVANA_API_BASE_URL:-https://ai-factory.frevana.com}"
API_PATH="/service/google-ads-ad-traffic-by-keywords"
CONNECT_TIMEOUT="10"
MAX_TIME="600"

usage() {
  cat <<'EOF'
Usage:
  search_google_ads_ad_traffic_by_keywords.sh --keywords "seo marketing" --bid 999 --match exact [options]

Options:
  --keywords              Comma-separated keyword list
  --bid                   Maximum custom bid
  --match                 Keyword match type: exact, broad, or phrase
  --location-name         Full Google Ads location name
  --location-code         Google Ads location code
  --location-coordinate   GPS coordinates in latitude,longitude format
  --language-name         Full Google Ads language name
  --language-code         Google Ads language code
  --date-from             Forecast start date in yyyy-mm-dd format
  --date-to               Forecast end date in yyyy-mm-dd format
  --date-interval         Forecast interval: next_week, next_month, or next_quarter
  --sort-by               Sort by relevance, impressions, ctr, average_cpc, cost, or clicks
  --tag                   User-defined task identifier
  --output                Optional file path for saving returned JSON. Defaults to ./out/google-ads-ad-traffic-by-keywords-<timestamp>-<pid>.json
  --token                 Optional Bearer token override for this run
  -h, --help              Show this help message
EOF
}

fail() {
  echo "$1" >&2
  exit 1
}

KEYWORDS=""
BID=""
MATCH=""
LOCATION_NAME=""
LOCATION_CODE=""
LOCATION_COORDINATE=""
LANGUAGE_NAME=""
LANGUAGE_CODE=""
DATE_FROM=""
DATE_TO=""
DATE_INTERVAL=""
SORT_BY=""
TAG=""
OUTPUT_PATH=""
TOKEN_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --keywords)
      KEYWORDS="${2:-}"
      shift 2
      ;;
    --bid)
      BID="${2:-}"
      shift 2
      ;;
    --match)
      MATCH="${2:-}"
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
    --date-from|--date_from)
      DATE_FROM="${2:-}"
      shift 2
      ;;
    --date-to|--date_to)
      DATE_TO="${2:-}"
      shift 2
      ;;
    --date-interval|--date_interval)
      DATE_INTERVAL="${2:-}"
      shift 2
      ;;
    --sort-by|--sort_by)
      SORT_BY="${2:-}"
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
[[ -n "$BID" ]] || fail "Missing required argument: --bid"
[[ -n "$MATCH" ]] || fail "Missing required argument: --match"

command -v curl >/dev/null 2>&1 || fail "curl is required but was not found in PATH."
command -v python3 >/dev/null 2>&1 || fail "python3 is required but was not found in PATH."

TOKEN="${TOKEN_OVERRIDE:-${FREVANA_TOKEN:-}}"
if [[ -z "$TOKEN" && -t 0 ]]; then
  read -r -s -p "FREVANA_TOKEN not found. Please enter your Frevana Bearer token: " TOKEN
  echo >&2
fi
[[ -n "$TOKEN" ]] || fail "FREVANA_TOKEN is not set. In non-interactive runs, set FREVANA_TOKEN or pass --token explicitly."

if [[ -z "$OUTPUT_PATH" ]]; then
  OUTPUT_PATH="out/google-ads-ad-traffic-by-keywords-$(date -u +%Y%m%dT%H%M%SZ)-$$.json"
fi

PAYLOAD_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
RESULT_FILE="$(mktemp)"
cleanup() {
  rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE" "$RESULT_FILE"
}
trap cleanup EXIT

export KEYWORDS BID MATCH LOCATION_NAME LOCATION_CODE LOCATION_COORDINATE
export LANGUAGE_NAME LANGUAGE_CODE DATE_FROM DATE_TO DATE_INTERVAL SORT_BY TAG

python3 - "$PAYLOAD_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path

payload_path = Path(sys.argv[1])

def env(name):
    return os.environ.get(name, "").strip()

keywords = [item.strip() for item in env("KEYWORDS").split(",") if item.strip()]
if not keywords:
    print("At least one non-empty keyword is required.", file=sys.stderr)
    sys.exit(1)

try:
    bid = int(env("BID"))
except ValueError:
    print("--bid must be a positive integer.", file=sys.stderr)
    sys.exit(1)
if bid < 1:
    print("--bid must be a positive integer.", file=sys.stderr)
    sys.exit(1)

match = env("MATCH").lower()
if match not in {"exact", "broad", "phrase"}:
    print("--match must be one of: exact, broad, phrase.", file=sys.stderr)
    sys.exit(1)

location_values = [env("LOCATION_NAME"), env("LOCATION_CODE"), env("LOCATION_COORDINATE")]
if sum(1 for value in location_values if value) > 1:
    print("Use only one of --location-name, --location-code, or --location-coordinate.", file=sys.stderr)
    sys.exit(1)

if env("LANGUAGE_NAME") and env("LANGUAGE_CODE"):
    print("Use only one of --language-name or --language-code.", file=sys.stderr)
    sys.exit(1)

if env("DATE_INTERVAL") and (env("DATE_FROM") or env("DATE_TO")):
    print("--date-interval cannot be combined with --date-from or --date-to.", file=sys.stderr)
    sys.exit(1)

if bool(env("DATE_FROM")) != bool(env("DATE_TO")):
    print("--date-from and --date-to must be provided together.", file=sys.stderr)
    sys.exit(1)

date_interval = env("DATE_INTERVAL")
if date_interval and date_interval not in {"next_week", "next_month", "next_quarter"}:
    print("--date-interval must be one of: next_week, next_month, next_quarter.", file=sys.stderr)
    sys.exit(1)

sort_by = env("SORT_BY")
if sort_by and sort_by not in {"relevance", "impressions", "ctr", "average_cpc", "cost", "clicks"}:
    print("--sort-by must be one of: relevance, impressions, ctr, average_cpc, cost, clicks.", file=sys.stderr)
    sys.exit(1)

payload = {
    "keywords": keywords,
    "bid": bid,
    "match": match,
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
if date_interval:
    payload["date_interval"] = date_interval
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
  echo "Google Ads ad traffic by keywords API request failed with HTTP $HTTP_CODE" >&2
  cat "$RESPONSE_FILE" >&2
  exit 1
fi

[[ -s "$RESPONSE_FILE" ]] || fail "Google Ads ad traffic by keywords API returned an empty response body."

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
    print(f"Google Ads ad traffic by keywords API returned non-JSON response: {exc}", file=sys.stderr)
    print(raw, file=sys.stderr)
    sys.exit(1)

result_path.write_text(raw, encoding="utf-8")
PY

mkdir -p "$(dirname "$OUTPUT_PATH")"
cp "$RESULT_FILE" "$OUTPUT_PATH"
echo "Saved Google Ads ad traffic by keywords JSON to $OUTPUT_PATH" >&2

cat "$RESULT_FILE"
