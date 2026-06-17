#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="https://a.klaviyo.com/api"
CONFIG_NAME="klaviyo-send-email"
CONNECT_TIMEOUT="10"
MAX_TIME="120"
API_KEY_HELP_URL="https://developers.klaviyo.com/en/docs/getting-started#quick-start-guide"

usage() {
  cat <<'EOF'
Usage:
  lists.sh list [--filter FILTER] [--limit N] [--sort SORT] [global options]
  lists.sh get --list-id UUID [global options]
  lists.sh create --name NAME [--send] [global options]
  lists.sh update --list-id UUID --name NAME [--send] [global options]
  lists.sh delete --list-id UUID [--send] [global options]
  lists.sh get-profiles --list-id UUID [--limit N] [global options]
  lists.sh get-profile-ids --list-id UUID [global options]
  lists.sh add-profiles --list-id UUID --profile-ids JSON [--send] [global options]
  lists.sh remove-profiles --list-id UUID --profile-ids JSON [--send] [global options]

Read actions call the API immediately. Write actions dry-run by default; pass --send to execute.

--- Required Parameters ---
  --list-id        (get/update/delete/get-profiles/get-profile-ids/add-profiles/remove-profiles)
  --name           (create/update)           List name
  --profile-ids    (add-profiles/remove-profiles) JSON array of profile IDs, e.g. '["01ABCDEF","02GHIJKL"]'

--- Optional Parameters ---
  --filter         (list)     Filter string, e.g. 'equals(name,"Newsletter")'
  --limit N        (list/get-profiles)  Results per page (default 100)
  --sort SORT      (list)     Sort field, e.g. "-created", "name"

--- Global Options ---
  Environment variable: KLAVIVO_API_KEY  (falls back to saved key, overridden by --api-key)
  --api-key KEY                 Klaviyo API key (highest priority)
  --save-api-key                Save --api-key to ~/.config/klaviyo-send-email/api_key
  --configure-api-key           Prompt to save a new API key
  --clear-api-key               Remove the saved API key
  --output PATH                 Save response JSON to file (printed to stdout anyway)

Filter examples:
  --filter 'equals(name,"Newsletter")'

Sort options:
  created, -created, name, -name, updated, -updated
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
  local revision="${4:-2026-04-15}"
  local response_file http_code
  response_file="$(mktemp)"
  if [[ -n "$payload" ]]; then
    http_code="$(curl -sSg --connect-timeout "$CONNECT_TIMEOUT" --max-time "$MAX_TIME" -o "$response_file" -w "%{http_code}" -X "$method" "$url" \
      -H "Authorization: Klaviyo-API-Key $API_KEY" \
      -H "Content-Type: application/vnd.api+json" \
      -H "revision: $revision" \
      --data @"$payload")"
  else
    http_code="$(curl -sSg --connect-timeout "$CONNECT_TIMEOUT" --max-time "$MAX_TIME" -o "$response_file" -w "%{http_code}" -X "$method" "$url" \
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
FILTER=""
LIMIT="100"
SORT=""
LIST_ID=""
NAME=""
PROFILE_IDS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-key) API_KEY_OVERRIDE="${2:-}"; shift 2 ;;
    --save-api-key) SAVE_API_KEY="true"; shift ;;
    --configure-api-key) CONFIGURE_API_KEY="true"; shift ;;
    --clear-api-key) rm -f "$(api_key_file)"; echo "Removed saved Klaviyo API key." >&2; shift ;;
    --output) OUTPUT_PATH="${2:-}"; shift 2 ;;
    --send) DO_SEND="true"; shift ;;
    --filter) FILTER="${2:-}"; shift 2 ;;
    --limit) LIMIT="${2:-}"; shift 2 ;;
    --sort) SORT="${2:-}"; shift 2 ;;
    --list-id) LIST_ID="${2:-}"; shift 2 ;;
    --name) NAME="${2:-}"; shift 2 ;;
    --profile-ids) PROFILE_IDS="${2:-}"; shift 2 ;;
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
  list)
    load_api_key
    list_url="$API_BASE_URL/lists?page[size]=$LIMIT"
    [[ -n "$FILTER" ]] && list_url="$list_url&filter=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$FILTER'))")"
    [[ -n "$SORT" ]] && list_url="$list_url&sort=$SORT"
    result="$(curl_json GET "$list_url")"
    ;;
  get)
    [[ -n "$LIST_ID" ]] || { echo "--list-id is required for list get." >&2; exit 1; }
    load_api_key
    result="$(curl_json GET "$API_BASE_URL/lists/$LIST_ID")"
    ;;
  create)
    [[ -n "$NAME" ]] || { echo "--name is required for list create." >&2; exit 1; }
    export NAME
    python3 - "$PAYLOAD_FILE" <<'PY'
import json, os, sys
payload = {
    "data": {
        "type": "list",
        "attributes": {
            "name": os.environ["NAME"]
        }
    }
}
open(sys.argv[1], "w", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False, indent=2))
PY
    if [[ "$DO_SEND" != "true" ]]; then
      result="$(cat "$PAYLOAD_FILE")"
    else
      load_api_key
      result="$(curl_json POST "$API_BASE_URL/lists" "$PAYLOAD_FILE")"
    fi
    ;;
  update)
    [[ -n "$LIST_ID" ]] || { echo "--list-id is required for list update." >&2; exit 1; }
    [[ -n "$NAME" ]] || { echo "--name is required for list update." >&2; exit 1; }
    export LIST_ID NAME
    python3 - "$PAYLOAD_FILE" <<'PY'
import json, os, sys
payload = {
    "data": {
        "type": "list",
        "id": os.environ["LIST_ID"],
        "attributes": {
            "name": os.environ["NAME"]
        }
    }
}
open(sys.argv[1], "w", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False, indent=2))
PY
    if [[ "$DO_SEND" != "true" ]]; then
      result="$(cat "$PAYLOAD_FILE")"
    else
      load_api_key
      result="$(curl_json PATCH "$API_BASE_URL/lists/$LIST_ID" "$PAYLOAD_FILE")"
    fi
    ;;
  delete)
    [[ -n "$LIST_ID" ]] || { echo "--list-id is required for list delete." >&2; exit 1; }
    if [[ "$DO_SEND" != "true" ]]; then
      echo "Dry-run: DELETE $API_BASE_URL/lists/$LIST_ID" >&2
      echo '{"status_code":204,"ok":true,"body":"Would delete list. Pass --send to execute."}'
    else
      load_api_key
      result="$(curl_json DELETE "$API_BASE_URL/lists/$LIST_ID")"
    fi
    ;;
  get-profiles)
    [[ -n "$LIST_ID" ]] || { echo "--list-id is required for list get-profiles." >&2; exit 1; }
    load_api_key
    result="$(curl_json GET "$API_BASE_URL/lists/$LIST_ID/profiles?page[size]=$LIMIT")"
    ;;
  get-profile-ids)
    [[ -n "$LIST_ID" ]] || { echo "--list-id is required for list get-profile-ids." >&2; exit 1; }
    load_api_key
    result="$(curl_json GET "$API_BASE_URL/lists/$LIST_ID/relationships/profiles")"
    ;;
  add-profiles)
    [[ -n "$LIST_ID" ]] || { echo "--list-id is required for list add-profiles." >&2; exit 1; }
    [[ -n "$PROFILE_IDS" ]] || { echo "--profile-ids is required for list add-profiles." >&2; exit 1; }
    export LIST_ID PROFILE_IDS
    python3 - "$PAYLOAD_FILE" <<'PY'
import json, os, sys
profile_ids = json.loads(os.environ["PROFILE_IDS"])
payload = {
    "data": [
        {"type": "profile", "id": pid} for pid in profile_ids
    ]
}
open(sys.argv[1], "w", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False, indent=2))
PY
    if [[ "$DO_SEND" != "true" ]]; then
      result="$(cat "$PAYLOAD_FILE")"
    else
      load_api_key
      result="$(curl_json POST "$API_BASE_URL/lists/$LIST_ID/relationships/profiles" "$PAYLOAD_FILE")"
    fi
    ;;
  remove-profiles)
    [[ -n "$LIST_ID" ]] || { echo "--list-id is required for list remove-profiles." >&2; exit 1; }
    [[ -n "$PROFILE_IDS" ]] || { echo "--profile-ids is required for list remove-profiles." >&2; exit 1; }
    export LIST_ID PROFILE_IDS
    python3 - "$PAYLOAD_FILE" <<'PY'
import json, os, sys
profile_ids = json.loads(os.environ["PROFILE_IDS"])
payload = {
    "data": [
        {"type": "profile", "id": pid} for pid in profile_ids
    ]
}
open(sys.argv[1], "w", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False, indent=2))
PY
    if [[ "$DO_SEND" != "true" ]]; then
      result="$(cat "$PAYLOAD_FILE")"
    else
      load_api_key
      result="$(curl_json DELETE "$API_BASE_URL/lists/$LIST_ID/relationships/profiles" "$PAYLOAD_FILE")"
    fi
    ;;
  *)
    echo "Action is required: list, get, create, update, delete, get-profiles, get-profile-ids, add-profiles, or remove-profiles." >&2
    usage >&2
    exit 1
    ;;
esac

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  printf '%s\n' "$result" > "$OUTPUT_PATH"
fi
printf '%s\n' "$result"
