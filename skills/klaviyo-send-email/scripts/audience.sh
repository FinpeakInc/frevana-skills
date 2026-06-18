#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="https://a.klaviyo.com/api"
CONFIG_NAME="klaviyo-send-email"
CONNECT_TIMEOUT="10"
MAX_TIME="120"
API_KEY_HELP_URL="https://frevana.gitbook.io/frevana-docs/email-integrations/klaviyo-integration"
BETA_REVISION="2026-04-15.pre"

usage() {
  cat <<'EOF'
Usage:
  audience.sh get --audience-id UUID [global options]
  audience.sh create --campaign-id UUID --definition-json JSON [--send] [global options]
  audience.sh update --audience-id UUID --definition-json JSON [--send] [global options]

Read actions call the API immediately. Write actions dry-run by default; pass --send to execute.

--- Required Parameters ---
  --audience-id     (get/update)   Audience UUID
  --campaign-id     (create)       Campaign UUID to associate this audience with
  --definition-json (create/update) JSON audience definition (see below)

--- Optional Parameters ---
  --send       Execute the API call (dry-run by default). Pass when you approve.

--- Global Options ---
  Environment variable: KLAVIVO_API_KEY  (falls back to saved key, overridden by --api-key)
  --api-key KEY                 Klaviyo API key (highest priority)
  --save-api-key                Save --api-key to ~/.config/klaviyo-send-email/api_key
  --configure-api-key           Prompt to save a new API key
  --clear-api-key               Remove the saved API key
  --output PATH                 Save response JSON to file (printed to stdout anyway)

Definition JSON fields (all nullable):
  name      string   Audience name
  included  [string] List of included group/segment IDs
  excluded  [string] List of excluded group/segment IDs
  priority  integer  Audience priority

Example:
  {"name":"My Audience","included":["abc123"],"excluded":["def456"],"priority":1}
EOF
}

config_dir() {
  printf '%s\n' "${KLAVIVO_SEND_EMAIL_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/$CONFIG_NAME}"
}

api_key_file() {
  printf '%s/api_key\n' "$(config_dir)"
}

save_api_key() {
  local dir path tmp
  dir="$(config_dir)"
  path="$(api_key_file)"
  mkdir -p "$dir"
  chmod 700 "$dir" 2>/dev/null || true
  tmp="$(mktemp "$dir/api_key.XXXXXX")"
  printf '%s\n' "$1" > "$tmp"
  chmod 600 "$tmp" 2>/dev/null || true
  mv "$tmp" "$path"
  chmod 600 "$path" 2>/dev/null || true
}

load_api_key() {
  API_KEY="${API_KEY_OVERRIDE:-${KLAVIVO_API_KEY:-}}"
  if [[ -z "$API_KEY" && -r "$(api_key_file)" ]]; then
    IFS= read -r API_KEY < "$(api_key_file)" || true
    API_KEY="${API_KEY//$'\r'/}"
  fi
  if [[ -z "$API_KEY" ]]; then
    if [[ -t 0 ]]; then
      read -r -s -p "KLAVIVO_API_KEY not found. Please enter your Klaviyo API key: " API_KEY
      echo >&2
      [[ -n "$API_KEY" ]] && save_api_key "$API_KEY"
    else
      echo "KLAVIVO_API_KEY is not set and no saved Klaviyo API key was found." >&2
      echo "Set KLAVIVO_API_KEY, pass --api-key, or run --api-key <key> --save-api-key once." >&2
      echo "Refer to this guide to create a Klaviyo API key: $API_KEY_HELP_URL" >&2
      exit 1
    fi
  fi
}

curl_json() {
  local method="$1"
  local url="$2"
  local payload="${3:-}"
  local revision="${4:-$BETA_REVISION}"
  local response_file http_code
  response_file="$(mktemp)"
  if [[ -n "$payload" ]]; then
    http_code="$(curl -sS --connect-timeout "$CONNECT_TIMEOUT" --max-time "$MAX_TIME" -o "$response_file" -w "%{http_code}" -X "$method" "$url" \
      -H "Authorization: Klaviyo-API-Key $API_KEY" \
      -H "Content-Type: application/vnd.api+json" \
      -H "revision: $revision" \
      --data @"$payload")"
  else
    http_code="$(curl -sS --connect-timeout "$CONNECT_TIMEOUT" --max-time "$MAX_TIME" -o "$response_file" -w "%{http_code}" -X "$method" "$url" \
      -H "Authorization: Klaviyo-API-Key $API_KEY" \
      -H "revision: $revision")"
  fi
  python3 - "$http_code" "$response_file" <<'PY'
import json, sys
code = int(sys.argv[1])
raw = open(sys.argv[2], encoding="utf-8", errors="replace").read()
try:
    body = json.loads(raw) if raw.strip() else None
except json.JSONDecodeError:
    body = raw
out = {"status_code": code, "ok": 200 <= code < 300}
if body is not None:
    out["body"] = body
print(json.dumps(out, ensure_ascii=False, indent=2))
sys.exit(0 if 200 <= code < 300 else 1)
PY
  rm -f "$response_file"
}

ACTION="${1:-}"
[[ -n "$ACTION" ]] && shift || true

API_KEY_OVERRIDE=""
OUTPUT_PATH=""
DO_SEND="false"
CAMPAIGN_ID=""
AUDIENCE_ID=""
DEFINITION_JSON=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-key) API_KEY_OVERRIDE="${2:-}"; shift 2 ;;
    --save-api-key) SAVE_API_KEY="true"; shift ;;
    --configure-api-key) CONFIGURE_API_KEY="true"; shift ;;
    --clear-api-key) rm -f "$(api_key_file)"; echo "Removed saved Klaviyo API key." >&2; shift ;;
    --output) OUTPUT_PATH="${2:-}"; shift 2 ;;
    --send) DO_SEND="true"; shift ;;
    --campaign-id) CAMPAIGN_ID="${2:-}"; shift 2 ;;
    --audience-id) AUDIENCE_ID="${2:-}"; shift 2 ;;
    --definition-json) DEFINITION_JSON="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done

SAVE_API_KEY="${SAVE_API_KEY:-false}"
CONFIGURE_API_KEY="${CONFIGURE_API_KEY:-false}"
if [[ "$SAVE_API_KEY" == "true" ]]; then
  [[ -n "$API_KEY_OVERRIDE" ]] || { echo "--save-api-key requires --api-key." >&2; exit 1; }
  save_api_key "$API_KEY_OVERRIDE"
  echo "Saved Klaviyo API key to $(api_key_file)" >&2
  [[ -n "$ACTION" ]] || exit 0
fi
if [[ "$CONFIGURE_API_KEY" == "true" ]]; then
  if [[ -n "$API_KEY_OVERRIDE" ]]; then
    save_api_key "$API_KEY_OVERRIDE"
  elif [[ -t 0 ]]; then
    read -r -s -p "Enter Klaviyo API key to save locally: " key
    echo >&2
    save_api_key "$key"
  else
    echo "Cannot prompt in a non-interactive shell. Pass --api-key <key> --save-api-key." >&2
    echo "Refer to this guide to create a Klaviyo API key: $API_KEY_HELP_URL" >&2
    exit 1
  fi
  [[ -n "$ACTION" ]] || exit 0
fi

PAYLOAD_FILE="$(mktemp)"
trap 'rm -f "$PAYLOAD_FILE"' EXIT

case "$ACTION" in
  get)
    [[ -n "$AUDIENCE_ID" ]] || { echo "--audience-id is required for audience get." >&2; exit 1; }
    load_api_key
    result="$(curl_json GET "$API_BASE_URL/campaign-audiences/$AUDIENCE_ID")"
    ;;
  create)
    [[ -n "$CAMPAIGN_ID" ]] || { echo "--campaign-id is required for audience create." >&2; exit 1; }
    [[ -n "$DEFINITION_JSON" ]] || { echo "--definition-json is required for audience create." >&2; exit 1; }
    export CAMPAIGN_ID DEFINITION_JSON
    python3 - "$PAYLOAD_FILE" <<'PY'
import json, os, sys
definition = json.loads(os.environ["DEFINITION_JSON"])
payload = {
    "data": {
        "type": "campaign-audience",
        "attributes": {
            "definition": definition
        },
        "relationships": {
            "campaign": {
                "data": {
                    "type": "campaign",
                    "id": os.environ["CAMPAIGN_ID"]
                }
            }
        }
    }
}
open(sys.argv[1], "w", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False, indent=2))
PY
    if [[ "$DO_SEND" != "true" ]]; then
      result="$(cat "$PAYLOAD_FILE")"
    else
      load_api_key
      result="$(curl_json POST "$API_BASE_URL/campaign-audiences" "$PAYLOAD_FILE")"
    fi
    ;;
  update)
    [[ -n "$AUDIENCE_ID" ]] || { echo "--audience-id is required for audience update." >&2; exit 1; }
    [[ -n "$DEFINITION_JSON" ]] || { echo "--definition-json is required for audience update." >&2; exit 1; }
    export AUDIENCE_ID DEFINITION_JSON
    python3 - "$PAYLOAD_FILE" <<'PY'
import json, os, sys
definition = json.loads(os.environ["DEFINITION_JSON"])
payload = {
    "data": {
        "type": "campaign-audience",
        "id": os.environ["AUDIENCE_ID"],
        "attributes": {
            "definition": definition
        }
    }
}
open(sys.argv[1], "w", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False, indent=2))
PY
    if [[ "$DO_SEND" != "true" ]]; then
      result="$(cat "$PAYLOAD_FILE")"
    else
      load_api_key
      result="$(curl_json PATCH "$API_BASE_URL/campaign-audiences/$AUDIENCE_ID" "$PAYLOAD_FILE")"
    fi
    ;;
  *)
    echo "Action is required: get, create, or update." >&2
    usage >&2
    exit 1
    ;;
esac

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  printf '%s\n' "$result" > "$OUTPUT_PATH"
fi
printf '%s\n' "$result"
