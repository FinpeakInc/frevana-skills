#!/usr/bin/env bash

set -euo pipefail

DEFAULT_API_BASE_URL="https://ai-factory.frevana.com"
API_BASE_URL="${FREVANA_API_BASE_URL:-$DEFAULT_API_BASE_URL}"
GOOGLE_MAPS_SEARCH_PATH="/service/google-maps"
CONNECT_TIMEOUT="10"
MAX_TIME="600"

usage() {
  cat <<'EOF'
Usage:
  search_google_maps.sh [--q QUERY] [--type search|place] [map and filter options] [--output PATH] [--token TOKEN]

Request options:
  --q QUERY                 Google Maps search query
  --ll VALUE                Google Maps coordinates and zoom value
  --location VALUE          Search origin location name (requires --z or --m)
  --lat NUMBER              Search-origin latitude (requires --lon and --z or --m)
  --lon NUMBER              Search-origin longitude (requires --lat and --z or --m)
  --z NUMBER                Map zoom level (3-30)
  --m NUMBER                Map height in meters (1-15028132), alternative to --z
  --nearby VALUE            Nearby location used to bias results
  --type VALUE              search or place; required unless --place-id or --data-cid is supplied
  --data VALUE              Google Maps data parameter; required for --type place
  --place-id VALUE          Google Maps place ID; cannot be used with --data-cid
  --data-cid VALUE          Google customer ID; cannot be used with --place-id
  --google-domain VALUE     Google domain
  --hl VALUE                Language code
  --gl VALUE                Country code
  --min-price NUMBER        Minimum price level (1-4)
  --max-price NUMBER        Maximum price level (1-4)
  --min-rating NUMBER       Minimum rating (2, 2.5, 3, 3.5, 4, 4.5)
  --open-state VALUE        now or 24h; cannot be used with --open-on-day/--open-at-hour
  --open-on-day VALUE       mon, tue, wed, thu, fri, sat, or sun
  --open-at-hour NUMBER     Hour 0-23; requires --open-on-day
  --start NUMBER            Pagination offset (minimum 0)
  --output PATH             Save returned JSON to this path
  --token TOKEN             Bearer token override for this run
  -h, --help                Show this help message
EOF
}

Q=""; LL=""; LOCATION=""; LAT=""; LON=""; Z=""; M=""; NEARBY=""; TYPE=""; DATA=""; PLACE_ID=""; DATA_CID=""; GOOGLE_DOMAIN=""; HL=""; GL=""; MIN_PRICE=""; MAX_PRICE=""; MIN_RATING=""; OPEN_STATE=""; OPEN_ON_DAY=""; OPEN_AT_HOUR=""; START=""; OUTPUT_PATH=""; TOKEN_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --q|--query) Q="${2:-}"; shift 2 ;;
    --ll) LL="${2:-}"; shift 2 ;;
    --location) LOCATION="${2:-}"; shift 2 ;;
    --lat) LAT="${2:-}"; shift 2 ;;
    --lon) LON="${2:-}"; shift 2 ;;
    --z) Z="${2:-}"; shift 2 ;;
    --m) M="${2:-}"; shift 2 ;;
    --nearby) NEARBY="${2:-}"; shift 2 ;;
    --type) TYPE="${2:-}"; shift 2 ;;
    --data) DATA="${2:-}"; shift 2 ;;
    --place-id|--place_id) PLACE_ID="${2:-}"; shift 2 ;;
    --data-cid|--data_cid) DATA_CID="${2:-}"; shift 2 ;;
    --google-domain|--google_domain) GOOGLE_DOMAIN="${2:-}"; shift 2 ;;
    --hl) HL="${2:-}"; shift 2 ;;
    --gl) GL="${2:-}"; shift 2 ;;
    --min-price|--min_price) MIN_PRICE="${2:-}"; shift 2 ;;
    --max-price|--max_price) MAX_PRICE="${2:-}"; shift 2 ;;
    --min-rating|--min_rating) MIN_RATING="${2:-}"; shift 2 ;;
    --open-state|--open_state) OPEN_STATE="${2:-}"; shift 2 ;;
    --open-on-day|--open_on_day) OPEN_ON_DAY="${2:-}"; shift 2 ;;
    --open-at-hour|--open_at_hour) OPEN_AT_HOUR="${2:-}"; shift 2 ;;
    --start) START="${2:-}"; shift 2 ;;
    --output) OUTPUT_PATH="${2:-}"; shift 2 ;;
    --token) TOKEN_OVERRIDE="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done

fail() { echo "$1" >&2; exit 1; }
is_number() { [[ "$1" =~ ^[0-9]+([.][0-9]+)?$ ]]; }
is_int() { [[ "$1" =~ ^[0-9]+$ ]]; }

[[ -n "$PLACE_ID" && -n "$DATA_CID" ]] && fail "--place-id and --data-cid cannot be used together."
[[ -z "$TYPE" && -z "$PLACE_ID" && -z "$DATA_CID" ]] && fail "--type is required unless --place-id or --data-cid is supplied."
[[ -n "$TYPE" && "$TYPE" != "search" && "$TYPE" != "place" ]] && fail "--type must be search or place."
[[ "$TYPE" == "search" && -z "$Q" ]] && fail "--q is required when --type is search."
[[ "$TYPE" == "place" && -z "$DATA" ]] && fail "--data is required when --type is place."
[[ -n "$LAT" && -z "$LON" || -z "$LAT" && -n "$LON" ]] && fail "--lat and --lon must be supplied together."
[[ -n "$LOCATION" || -n "$LAT" ]] && [[ -z "$Z" && -z "$M" ]] && fail "--location or --lat/--lon requires --z or --m."
[[ -n "$Z" && -n "$M" ]] && fail "Use either --z or --m, not both."
[[ -n "$OPEN_STATE" && ( -n "$OPEN_ON_DAY" || -n "$OPEN_AT_HOUR" ) ]] && fail "--open-state cannot be used with --open-on-day or --open-at-hour."
[[ -n "$OPEN_AT_HOUR" && -z "$OPEN_ON_DAY" ]] && fail "--open-at-hour requires --open-on-day."

if [[ -n "$Z" ]] && (! is_int "$Z" || (( Z < 3 || Z > 30 ))); then fail "--z must be an integer from 3 to 30."; fi
if [[ -n "$M" ]] && (! is_int "$M" || (( M < 1 || M > 15028132 ))); then fail "--m must be an integer from 1 to 15028132."; fi
for field in MIN_PRICE MAX_PRICE; do value="${!field}"; [[ -z "$value" ]] || (is_int "$value" && (( value >= 1 && value <= 4 ))) || fail "--${field,,} must be an integer from 1 to 4."; done
[[ -z "$MIN_RATING" || "$MIN_RATING" =~ ^(2|2[.]5|3|3[.]5|4|4[.]5)$ ]] || fail "--min-rating must be 2, 2.5, 3, 3.5, 4, or 4.5."
[[ -z "$OPEN_STATE" || "$OPEN_STATE" == "now" || "$OPEN_STATE" == "24h" ]] || fail "--open-state must be now or 24h."
[[ -z "$OPEN_ON_DAY" || "$OPEN_ON_DAY" =~ ^(mon|tue|wed|thu|fri|sat|sun)$ ]] || fail "--open-on-day must be mon through sun."
if [[ -n "$OPEN_AT_HOUR" ]] && (! is_int "$OPEN_AT_HOUR" || (( OPEN_AT_HOUR > 23 ))); then fail "--open-at-hour must be an integer from 0 to 23."; fi
if [[ -n "$START" ]] && (! is_int "$START"); then fail "--start must be a non-negative integer."; fi
for value in "$LAT" "$LON"; do [[ -z "$value" ]] || is_number "$value" || fail "--lat and --lon must be numbers."; done

command -v curl >/dev/null 2>&1 || fail "curl is required but was not found in PATH."
command -v python3 >/dev/null 2>&1 || fail "python3 is required but was not found in PATH."
TOKEN="${TOKEN_OVERRIDE:-${FREVANA_TOKEN:-}}"
if [[ -z "$TOKEN" && -t 0 ]]; then read -r -s -p "FREVANA_TOKEN not found. Please enter your Frevana Bearer token: " TOKEN; echo >&2; fi
[[ -n "$TOKEN" ]] || fail "FREVANA_TOKEN is not set. In non-interactive runs, set FREVANA_TOKEN or pass --token explicitly."

PAYLOAD_FILE="$(mktemp)"; RESPONSE_FILE="$(mktemp)"; RESULT_FILE="$(mktemp)"
cleanup() { rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE" "$RESULT_FILE"; }
trap cleanup EXIT
export Q LL LOCATION LAT LON Z M NEARBY TYPE DATA PLACE_ID DATA_CID GOOGLE_DOMAIN HL GL MIN_PRICE MAX_PRICE MIN_RATING OPEN_STATE OPEN_ON_DAY OPEN_AT_HOUR START
python3 - "$PAYLOAD_FILE" <<'PY'
import json, os, sys
from pathlib import Path
fields = {"q":"Q", "ll":"LL", "location":"LOCATION", "lat":"LAT", "lon":"LON", "z":"Z", "m":"M", "nearby":"NEARBY", "type":"TYPE", "data":"DATA", "place_id":"PLACE_ID", "data_cid":"DATA_CID", "google_domain":"GOOGLE_DOMAIN", "hl":"HL", "gl":"GL", "min_price":"MIN_PRICE", "max_price":"MAX_PRICE", "min_rating":"MIN_RATING", "open_state":"OPEN_STATE", "open_on_day":"OPEN_ON_DAY", "open_at_hour":"OPEN_AT_HOUR", "start":"START"}
numeric = {"lat": float, "lon": float, "z": int, "m": int, "min_price": int, "max_price": int, "min_rating": float, "open_at_hour": int, "start": int}
payload = {key: numeric.get(key, str)(os.environ[name]) for key, name in fields.items() if os.environ.get(name)}
Path(sys.argv[1]).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
PY

HTTP_CODE="$(curl -sS --connect-timeout "$CONNECT_TIMEOUT" --max-time "$MAX_TIME" -o "$RESPONSE_FILE" -w "%{http_code}" -X POST "$API_BASE_URL$GOOGLE_MAPS_SEARCH_PATH" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" --data @"$PAYLOAD_FILE")"
if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then echo "Google Maps search API request failed with HTTP $HTTP_CODE" >&2; cat "$RESPONSE_FILE" >&2; exit 1; fi
[[ -s "$RESPONSE_FILE" ]] || fail "Google Maps search API returned an empty response body."
python3 - "$RESPONSE_FILE" "$RESULT_FILE" <<'PY'
import json, sys
from pathlib import Path
raw = Path(sys.argv[1]).read_text(encoding="utf-8")
try: json.loads(raw)
except json.JSONDecodeError as exc: print(f"Google Maps search API returned non-JSON response: {exc}", file=sys.stderr); print(raw, file=sys.stderr); sys.exit(1)
Path(sys.argv[2]).write_text(raw, encoding="utf-8")
PY
if [[ -n "$OUTPUT_PATH" ]]; then mkdir -p "$(dirname "$OUTPUT_PATH")"; cp "$RESULT_FILE" "$OUTPUT_PATH"; fi
cat "$RESULT_FILE"
