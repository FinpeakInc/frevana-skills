#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="https://ai-factory.frevana.com"
AMAZON_SEARCH_VOLUME_PATH="/dataforseo/amazon-keywords-search-volume"
CONNECT_TIMEOUT="10"
MAX_TIME="600"

usage() {
  cat <<'EOF'
Usage:
  get_search_volume.sh --keywords "wireless earbuds,gaming headset" [--location-name "United States"] [--location-code 2840] [--language-name "English"] [--language-code en] [--output /path/to/result.json] [--token "bearer token"]

Options:
  --keywords        Comma-separated keyword list
  --location-name   Marketplace name
  --location-code   Marketplace location code
  --language-name   Language name
  --language-code   Language code
  --output          Optional file path for saving returned JSON
  --token           Optional Bearer token override for this run
  -h, --help        Show this help message
EOF
}

set_marketplace_by_name() {
  case "$1" in
    Australia)
      LOCATION_CODE="2036"; LOCATION_NAME="Australia"; LANGUAGE_CODE="en"; LANGUAGE_NAME="English"
      ;;
    Austria)
      LOCATION_CODE="2040"; LOCATION_NAME="Austria"; LANGUAGE_CODE="de"; LANGUAGE_NAME="German"
      ;;
    Canada)
      LOCATION_CODE="2124"; LOCATION_NAME="Canada"; LANGUAGE_CODE="en"; LANGUAGE_NAME="English"
      ;;
    Egypt)
      LOCATION_CODE="2818"; LOCATION_NAME="Egypt"; LANGUAGE_CODE="ar"; LANGUAGE_NAME="Arabic"
      ;;
    France)
      LOCATION_CODE="2250"; LOCATION_NAME="France"; LANGUAGE_CODE="fr"; LANGUAGE_NAME="French"
      ;;
    Germany)
      LOCATION_CODE="2276"; LOCATION_NAME="Germany"; LANGUAGE_CODE="de"; LANGUAGE_NAME="German"
      ;;
    India)
      LOCATION_CODE="2356"; LOCATION_NAME="India"; LANGUAGE_CODE="en"; LANGUAGE_NAME="English"
      ;;
    Italy)
      LOCATION_CODE="2380"; LOCATION_NAME="Italy"; LANGUAGE_CODE="it"; LANGUAGE_NAME="Italian"
      ;;
    Mexico)
      LOCATION_CODE="2484"; LOCATION_NAME="Mexico"; LANGUAGE_CODE="es"; LANGUAGE_NAME="Spanish"
      ;;
    Netherlands)
      LOCATION_CODE="2528"; LOCATION_NAME="Netherlands"; LANGUAGE_CODE="nl"; LANGUAGE_NAME="Dutch"
      ;;
    "Saudi Arabia")
      LOCATION_CODE="2682"; LOCATION_NAME="Saudi Arabia"; LANGUAGE_CODE="ar"; LANGUAGE_NAME="Arabic"
      ;;
    Singapore)
      LOCATION_CODE="2702"; LOCATION_NAME="Singapore"; LANGUAGE_CODE="en"; LANGUAGE_NAME="English"
      ;;
    Spain)
      LOCATION_CODE="2724"; LOCATION_NAME="Spain"; LANGUAGE_CODE="es"; LANGUAGE_NAME="Spanish"
      ;;
    "United Arab Emirates")
      LOCATION_CODE="2784"; LOCATION_NAME="United Arab Emirates"; LANGUAGE_CODE="ar"; LANGUAGE_NAME="Arabic"
      ;;
    "United Kingdom")
      LOCATION_CODE="2826"; LOCATION_NAME="United Kingdom"; LANGUAGE_CODE="en"; LANGUAGE_NAME="English"
      ;;
    "United States")
      LOCATION_CODE="2840"; LOCATION_NAME="United States"; LANGUAGE_CODE="en"; LANGUAGE_NAME="English"
      ;;
    *)
      return 1
      ;;
  esac
}

set_marketplace_by_code() {
  case "$1" in
    2036) set_marketplace_by_name "Australia" ;;
    2040) set_marketplace_by_name "Austria" ;;
    2124) set_marketplace_by_name "Canada" ;;
    2250) set_marketplace_by_name "France" ;;
    2276) set_marketplace_by_name "Germany" ;;
    2356) set_marketplace_by_name "India" ;;
    2380) set_marketplace_by_name "Italy" ;;
    2484) set_marketplace_by_name "Mexico" ;;
    2528) set_marketplace_by_name "Netherlands" ;;
    2682) set_marketplace_by_name "Saudi Arabia" ;;
    2702) set_marketplace_by_name "Singapore" ;;
    2724) set_marketplace_by_name "Spain" ;;
    2784) set_marketplace_by_name "United Arab Emirates" ;;
    2818) set_marketplace_by_name "Egypt" ;;
    2826) set_marketplace_by_name "United Kingdom" ;;
    2840) set_marketplace_by_name "United States" ;;
    *)
      return 1
      ;;
  esac
}

KEYWORDS=""
LOCATION_CODE=""
LOCATION_NAME=""
LANGUAGE_CODE=""
LANGUAGE_NAME=""
OUTPUT_PATH=""
TOKEN_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --keywords)
      KEYWORDS="${2:-}"
      shift 2
      ;;
    --location-code)
      LOCATION_CODE="${2:-}"
      shift 2
      ;;
    --location-name)
      LOCATION_NAME="${2:-}"
      shift 2
      ;;
    --language-code)
      LANGUAGE_CODE="${2:-}"
      shift 2
      ;;
    --language-name)
      LANGUAGE_NAME="${2:-}"
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

if [[ -z "$KEYWORDS" ]]; then
  echo "Missing required argument: --keywords" >&2
  exit 1
fi

if [[ -z "$LOCATION_CODE" && -z "$LOCATION_NAME" && -z "$LANGUAGE_CODE" && -z "$LANGUAGE_NAME" ]]; then
  set_marketplace_by_name "United States"
elif [[ -n "$LOCATION_NAME" ]]; then
  if ! set_marketplace_by_name "$LOCATION_NAME"; then
    echo "Unsupported marketplace: $LOCATION_NAME" >&2
    exit 1
  fi
elif [[ -n "$LOCATION_CODE" ]]; then
  if ! set_marketplace_by_code "$LOCATION_CODE"; then
    echo "Unsupported location code: $LOCATION_CODE" >&2
    exit 1
  fi
fi

if [[ -z "$LOCATION_CODE" || -z "$LOCATION_NAME" || -z "$LANGUAGE_CODE" || -z "$LANGUAGE_NAME" ]]; then
  echo "Location and language must resolve to a supported marketplace." >&2
  echo "Provide no location inputs for the default, or provide a supported --location-name/--location-code." >&2
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

export KEYWORDS LOCATION_CODE LOCATION_NAME LANGUAGE_CODE LANGUAGE_NAME

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

payload = {
    "keywords": keywords,
    "location_code": int(os.environ["LOCATION_CODE"]),
    "location_name": os.environ["LOCATION_NAME"],
    "language_code": os.environ["LANGUAGE_CODE"],
    "language_name": os.environ["LANGUAGE_NAME"],
}

payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
PY

HTTP_CODE="$(
  curl -sS \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -o "$RESPONSE_FILE" \
    -w "%{http_code}" \
    -X POST "$API_BASE_URL$AMAZON_SEARCH_VOLUME_PATH" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    --data @"$PAYLOAD_FILE"
)"

if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "Amazon keyword search volume API request failed with HTTP $HTTP_CODE" >&2
  cat "$RESPONSE_FILE" >&2
  exit 1
fi

if [[ ! -s "$RESPONSE_FILE" ]]; then
  echo "Amazon keyword search volume API returned an empty response body." >&2
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
    print(f"Amazon keyword search volume API returned non-JSON response: {exc}", file=sys.stderr)
    print(raw, file=sys.stderr)
    sys.exit(1)

result_path.write_text(raw, encoding="utf-8")
PY

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  cp "$RESULT_FILE" "$OUTPUT_PATH"
fi

cat "$RESULT_FILE"
