#!/usr/bin/env bash

set -euo pipefail

CONNECT_TIMEOUT="10"
MAX_TIME="600"
CONFIG_DOC_URL="https://frevana.gitbook.io/frevana-docs/email-integrations/sendgrid-integration"

usage() {
  cat <<'EOF'
Usage:
  retrieve_global_email_stats.sh --start-date YYYY-MM-DD [options]

Retrieve Twilio SendGrid global email statistics with GET /v3/stats.

Options:
  --start-date        Required start date, format YYYY-MM-DD
  --end-date          Optional end date, format YYYY-MM-DD. SendGrid defaults to today when omitted
  --aggregated-by     Optional grouping: day, week, or month
  --limit             Optional number of results to return
  --offset            Optional zero-based offset
  --on-behalf-of      Optional SendGrid on-behalf-of header value for parent account calls
  --region            SendGrid API region: global or eu. Default global
  --api-key           Optional SendGrid API key override for this run
  --save-api-key      Save --api-key for future runs
  --configure-api-key Prompt for a SendGrid API key and save it for future runs
  --clear-api-key     Remove the locally saved SendGrid API key
  --output            Optional path for saving returned JSON or dry-run metadata
  --dry-run           Print request metadata without calling SendGrid
  -h, --help          Show this help message

Environment:
  SENDGRID_API_KEY    SendGrid API key used before the locally saved key
  SENDGRID_SEND_EMAIL_CONFIG_DIR Optional config directory override shared with sendgrid-send-email

Setup guide:
  https://frevana.gitbook.io/frevana-docs/email-integrations/sendgrid-integration
EOF
}

config_dir() {
  if [[ -n "${SENDGRID_SEND_EMAIL_CONFIG_DIR:-}" ]]; then
    printf '%s\n' "$SENDGRID_SEND_EMAIL_CONFIG_DIR"
  else
    printf '%s\n' "${XDG_CONFIG_HOME:-$HOME/.config}/sendgrid-send-email"
  fi
}

api_key_file() {
  printf '%s/api_key\n' "$(config_dir)"
}

load_saved_api_key() {
  local path
  path="$(api_key_file)"
  if [[ -r "$path" ]]; then
    IFS= read -r API_KEY < "$path" || true
    API_KEY="${API_KEY//$'\r'/}"
  fi
}

save_api_key() {
  local key="$1"
  local dir path tmp
  dir="$(config_dir)"
  path="$(api_key_file)"
  mkdir -p "$dir"
  chmod 700 "$dir" 2>/dev/null || true
  tmp="$(mktemp "$dir/api_key.XXXXXX")"
  printf '%s\n' "$key" > "$tmp"
  chmod 600 "$tmp" 2>/dev/null || true
  mv "$tmp" "$path"
  chmod 600 "$path" 2>/dev/null || true
}

clear_saved_api_key() {
  local path
  path="$(api_key_file)"
  if [[ -f "$path" ]]; then
    rm -f "$path"
  fi
}

START_DATE=""
END_DATE=""
AGGREGATED_BY=""
LIMIT=""
OFFSET=""
ON_BEHALF_OF=""
REGION="global"
API_KEY_OVERRIDE=""
SAVE_API_KEY="false"
CONFIGURE_API_KEY="false"
CLEAR_API_KEY="false"
OUTPUT_PATH=""
DRY_RUN="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --start-date)
      START_DATE="${2:-}"
      shift 2
      ;;
    --end-date)
      END_DATE="${2:-}"
      shift 2
      ;;
    --aggregated-by)
      AGGREGATED_BY="${2:-}"
      shift 2
      ;;
    --limit)
      LIMIT="${2:-}"
      shift 2
      ;;
    --offset)
      OFFSET="${2:-}"
      shift 2
      ;;
    --on-behalf-of)
      ON_BEHALF_OF="${2:-}"
      shift 2
      ;;
    --region)
      REGION="${2:-}"
      shift 2
      ;;
    --api-key)
      API_KEY_OVERRIDE="${2:-}"
      shift 2
      ;;
    --save-api-key)
      SAVE_API_KEY="true"
      shift
      ;;
    --configure-api-key)
      CONFIGURE_API_KEY="true"
      shift
      ;;
    --clear-api-key)
      CLEAR_API_KEY="true"
      shift
      ;;
    --output)
      OUTPUT_PATH="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN="true"
      shift
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

HAS_STATS_OPERATION="false"
if [[ -n "$START_DATE" || -n "$END_DATE" || -n "$AGGREGATED_BY" || -n "$LIMIT" || -n "$OFFSET" || -n "$ON_BEHALF_OF" || -n "$OUTPUT_PATH" || "$DRY_RUN" == "true" ]]; then
  HAS_STATS_OPERATION="true"
fi

if [[ "$CLEAR_API_KEY" == "true" ]]; then
  clear_saved_api_key
  echo "Removed locally saved SendGrid API key from $(api_key_file)" >&2
  if [[ "$HAS_STATS_OPERATION" != "true" && "$CONFIGURE_API_KEY" != "true" && -z "$API_KEY_OVERRIDE" ]]; then
    exit 0
  fi
fi

if [[ "$CONFIGURE_API_KEY" == "true" ]]; then
  API_KEY_TO_SAVE="$API_KEY_OVERRIDE"
  if [[ -z "$API_KEY_TO_SAVE" ]]; then
    if [[ -t 0 ]]; then
      read -r -s -p "Enter SendGrid API key to save locally: " API_KEY_TO_SAVE
      echo >&2
    else
      echo "--configure-api-key requires an interactive terminal or --api-key in non-interactive runs." >&2
      echo "Read the SendGrid integration guide to get the required configuration: $CONFIG_DOC_URL" >&2
      exit 1
    fi
  fi
  if [[ -z "$API_KEY_TO_SAVE" ]]; then
    echo "SendGrid API key is required." >&2
    exit 1
  fi
  save_api_key "$API_KEY_TO_SAVE"
  echo "Saved SendGrid API key for future runs to $(api_key_file)" >&2
  if [[ "$HAS_STATS_OPERATION" != "true" ]]; then
    exit 0
  fi
fi

if [[ "$SAVE_API_KEY" == "true" ]]; then
  if [[ -z "$API_KEY_OVERRIDE" ]]; then
    echo "--save-api-key requires --api-key." >&2
    exit 1
  fi
  save_api_key "$API_KEY_OVERRIDE"
  echo "Saved SendGrid API key for future runs to $(api_key_file)" >&2
  if [[ "$HAS_STATS_OPERATION" != "true" ]]; then
    exit 0
  fi
fi

if [[ -z "$START_DATE" ]]; then
  echo "--start-date is required for SendGrid global email statistics." >&2
  usage >&2
  exit 1
fi

if [[ ! "$START_DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
  echo "Invalid --start-date value: $START_DATE. Expected YYYY-MM-DD." >&2
  exit 1
fi

if [[ -n "$END_DATE" && ! "$END_DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
  echo "Invalid --end-date value: $END_DATE. Expected YYYY-MM-DD." >&2
  exit 1
fi

if [[ -n "$AGGREGATED_BY" && "$AGGREGATED_BY" != "day" && "$AGGREGATED_BY" != "week" && "$AGGREGATED_BY" != "month" ]]; then
  echo "Invalid --aggregated-by value: $AGGREGATED_BY. Allowed values: day, week, month." >&2
  exit 1
fi

if [[ -n "$LIMIT" && (! "$LIMIT" =~ ^[0-9]+$ || "$LIMIT" == "0") ]]; then
  echo "Invalid --limit value: $LIMIT. Expected a positive integer." >&2
  exit 1
fi

if [[ -n "$OFFSET" && ! "$OFFSET" =~ ^[0-9]+$ ]]; then
  echo "Invalid --offset value: $OFFSET. Expected a non-negative integer." >&2
  exit 1
fi

if [[ "$REGION" != "global" && "$REGION" != "eu" ]]; then
  echo "Invalid --region value: $REGION. Allowed values: global, eu." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required but was not found in PATH." >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required but was not found in PATH." >&2
  exit 1
fi

export START_DATE END_DATE
python3 - <<'PY'
from datetime import date
import os
import sys

try:
    start = date.fromisoformat(os.environ["START_DATE"])
except ValueError:
    print(f"Invalid --start-date value: {os.environ['START_DATE']}. Expected a real date in YYYY-MM-DD format.", file=sys.stderr)
    sys.exit(1)

end_value = os.environ.get("END_DATE", "")
if end_value:
    try:
        end = date.fromisoformat(end_value)
    except ValueError:
        print(f"Invalid --end-date value: {end_value}. Expected a real date in YYYY-MM-DD format.", file=sys.stderr)
        sys.exit(1)
    if end < start:
        print("--end-date must be greater than or equal to --start-date.", file=sys.stderr)
        sys.exit(1)
PY

REQUEST_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
cleanup() {
  rm -f "$REQUEST_FILE" "$RESPONSE_FILE"
}
trap cleanup EXIT

API_BASE_URL="https://api.sendgrid.com"
if [[ "$REGION" == "eu" ]]; then
  API_BASE_URL="https://api.eu.sendgrid.com"
fi

export API_BASE_URL AGGREGATED_BY LIMIT OFFSET ON_BEHALF_OF REGION

REQUEST_URL="$(python3 - "$REQUEST_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlencode

params = {"start_date": os.environ["START_DATE"]}
optional = {
    "end_date": os.environ.get("END_DATE", ""),
    "aggregated_by": os.environ.get("AGGREGATED_BY", ""),
    "limit": os.environ.get("LIMIT", ""),
    "offset": os.environ.get("OFFSET", ""),
}
for key, value in optional.items():
    if value:
        params[key] = value

base = os.environ["API_BASE_URL"].rstrip("/") + "/v3/stats"
url = base + "?" + urlencode(params)
metadata = {
    "method": "GET",
    "url": url,
    "region": os.environ["REGION"],
    "query": params,
}
on_behalf_of = os.environ.get("ON_BEHALF_OF", "")
if on_behalf_of:
    metadata["headers"] = {"on-behalf-of": on_behalf_of}

Path(sys.argv[1]).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
print(url)
PY
)"

if [[ "$DRY_RUN" == "true" ]]; then
  if [[ -n "$OUTPUT_PATH" ]]; then
    mkdir -p "$(dirname "$OUTPUT_PATH")"
    cp "$REQUEST_FILE" "$OUTPUT_PATH"
    echo "Saved SendGrid global email stats dry-run metadata to $OUTPUT_PATH" >&2
  fi
  cat "$REQUEST_FILE"
  exit 0
fi

API_KEY="${API_KEY_OVERRIDE:-${SENDGRID_API_KEY:-}}"
if [[ -z "$API_KEY" ]]; then
  load_saved_api_key
fi
if [[ -z "$API_KEY" ]]; then
  if [[ -t 0 ]]; then
    read -r -s -p "SENDGRID_API_KEY not found. Please enter your SendGrid API key: " API_KEY
    echo >&2
    if [[ -n "$API_KEY" ]]; then
      save_api_key "$API_KEY"
      echo "Saved SendGrid API key for future runs to $(api_key_file)" >&2
    fi
  else
    echo "SENDGRID_API_KEY is not set and no saved SendGrid API key was found." >&2
    echo "In non-interactive runs, set SENDGRID_API_KEY, pass --api-key, or run --api-key <key> --save-api-key once." >&2
    echo "Read the SendGrid integration guide to get the required configuration: $CONFIG_DOC_URL" >&2
    exit 1
  fi
fi

if [[ -z "$API_KEY" ]]; then
  echo "SendGrid API key is required." >&2
  echo "Read the SendGrid integration guide to get the required configuration: $CONFIG_DOC_URL" >&2
  exit 1
fi

CURL_ARGS=(
  -sS
  --connect-timeout "$CONNECT_TIMEOUT"
  --max-time "$MAX_TIME"
  -o "$RESPONSE_FILE"
  -w "%{http_code}"
  -X GET "$REQUEST_URL"
  -H "Authorization: Bearer $API_KEY"
)

if [[ -n "$ON_BEHALF_OF" ]]; then
  CURL_ARGS+=(-H "on-behalf-of: $ON_BEHALF_OF")
fi

HTTP_CODE="$(curl "${CURL_ARGS[@]}")"

if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "SendGrid global email stats API request failed with HTTP $HTTP_CODE" >&2
  cat "$RESPONSE_FILE" >&2
  exit 1
fi

if [[ ! -s "$RESPONSE_FILE" ]]; then
  echo "SendGrid global email stats API returned an empty response body." >&2
  exit 1
fi

python3 - "$RESPONSE_FILE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    parsed = json.loads(path.read_text(encoding="utf-8"))
except json.JSONDecodeError as exc:
    print(f"SendGrid global email stats API returned non-JSON response: {exc}", file=sys.stderr)
    sys.exit(1)

path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  cp "$RESPONSE_FILE" "$OUTPUT_PATH"
  echo "Saved SendGrid global email stats JSON to $OUTPUT_PATH" >&2
fi

cat "$RESPONSE_FILE"
