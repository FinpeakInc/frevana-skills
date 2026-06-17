#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="https://api.instantly.ai"
CONFIG_NAME="instantly-send-email"
CONNECT_TIMEOUT="10"
MAX_TIME="120"
API_KEY_HELP_URL="https://developer.instantly.ai/getting-started/getting-started"

usage() {
  cat <<'EOF'
Usage:
  lead.sh list --email user@example.com [--limit 10] [global options]
  lead.sh create --email user@example.com --campaign-id UUID [lead fields] [--send] [global options]
  lead.sh move --email user@example.com (--to-campaign-id UUID | --to-list-id UUID) [--from-campaign-id UUID | --from-list-id UUID] [--send] [global options]

Read actions call the API immediately. Write actions dry-run by default; pass --send to execute.

Global options:
  --api-key KEY
  --save-api-key
  --configure-api-key
  --clear-api-key
  --output PATH

Lead fields for create:
  --first-name VALUE
  --last-name VALUE
  --company-name VALUE
  --job-title VALUE
  --website VALUE
  --phone VALUE
  --personalization VALUE
  --custom-variable KEY=VALUE
  --custom-variables-json JSON
  --skip-if-in-workspace
  --skip-if-in-campaign
  --skip-if-in-list
  --blocklist-id UUID
  --verify-leads-on-import
  --verify-leads-for-lead-finder
EOF
}

config_dir() {
  printf '%s\n' "${INSTANTLY_SEND_EMAIL_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/$CONFIG_NAME}"
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
  API_KEY="${API_KEY_OVERRIDE:-${INSTANTLY_API_KEY:-}}"
  if [[ -z "$API_KEY" && -r "$(api_key_file)" ]]; then
    IFS= read -r API_KEY < "$(api_key_file)" || true
    API_KEY="${API_KEY//$'\r'/}"
  fi
  if [[ -z "$API_KEY" ]]; then
    if [[ -t 0 ]]; then
      read -r -s -p "INSTANTLY_API_KEY not found. Please enter your Instantly API key: " API_KEY
      echo >&2
      [[ -n "$API_KEY" ]] && save_api_key "$API_KEY"
    else
      echo "INSTANTLY_API_KEY is not set and no saved Instantly API key was found." >&2
      echo "Set INSTANTLY_API_KEY, pass --api-key, or run --api-key <key> --save-api-key once." >&2
      echo "Refer to this article to create an Instantly API key: $API_KEY_HELP_URL" >&2
      exit 1
    fi
  fi
}

curl_json() {
  local method="$1"
  local url="$2"
  local payload="${3:-}"
  local response_file http_code
  response_file="$(mktemp)"
  if [[ -n "$payload" ]]; then
    http_code="$(curl -sS --connect-timeout "$CONNECT_TIMEOUT" --max-time "$MAX_TIME" -o "$response_file" -w "%{http_code}" -X "$method" "$url" -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" --data @"$payload")"
  else
    http_code="$(curl -sS --connect-timeout "$CONNECT_TIMEOUT" --max-time "$MAX_TIME" -o "$response_file" -w "%{http_code}" -X "$method" "$url" -H "Authorization: Bearer $API_KEY")"
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
EMAIL=""
LIMIT="10"
CAMPAIGN_ID=""
FROM_CAMPAIGN_ID=""
FROM_LIST_ID=""
TO_CAMPAIGN_ID=""
TO_LIST_ID=""
FIRST_NAME=""
LAST_NAME=""
COMPANY_NAME=""
JOB_TITLE=""
WEBSITE=""
PHONE=""
PERSONALIZATION=""
CUSTOM_VARIABLES=()
CUSTOM_VARIABLES_JSON=""
SKIP_IF_IN_WORKSPACE="false"
SKIP_IF_IN_CAMPAIGN="false"
SKIP_IF_IN_LIST="false"
BLOCKLIST_ID=""
VERIFY_LEADS_ON_IMPORT="false"
VERIFY_LEADS_FOR_LEAD_FINDER="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-key) API_KEY_OVERRIDE="${2:-}"; shift 2 ;;
    --save-api-key) SAVE_API_KEY="true"; shift ;;
    --configure-api-key) CONFIGURE_API_KEY="true"; shift ;;
    --clear-api-key) rm -f "$(api_key_file)"; echo "Removed saved Instantly API key." >&2; shift ;;
    --output) OUTPUT_PATH="${2:-}"; shift 2 ;;
    --send) DO_SEND="true"; shift ;;
    --email) EMAIL="${2:-}"; shift 2 ;;
    --limit) LIMIT="${2:-}"; shift 2 ;;
    --campaign-id) CAMPAIGN_ID="${2:-}"; shift 2 ;;
    --from-campaign-id) FROM_CAMPAIGN_ID="${2:-}"; shift 2 ;;
    --from-list-id) FROM_LIST_ID="${2:-}"; shift 2 ;;
    --to-campaign-id) TO_CAMPAIGN_ID="${2:-}"; shift 2 ;;
    --to-list-id) TO_LIST_ID="${2:-}"; shift 2 ;;
    --first-name) FIRST_NAME="${2:-}"; shift 2 ;;
    --last-name) LAST_NAME="${2:-}"; shift 2 ;;
    --company-name) COMPANY_NAME="${2:-}"; shift 2 ;;
    --job-title) JOB_TITLE="${2:-}"; shift 2 ;;
    --website) WEBSITE="${2:-}"; shift 2 ;;
    --phone) PHONE="${2:-}"; shift 2 ;;
    --personalization) PERSONALIZATION="${2:-}"; shift 2 ;;
    --custom-variable) CUSTOM_VARIABLES+=("${2:-}"); shift 2 ;;
    --custom-variables-json) CUSTOM_VARIABLES_JSON="${2:-}"; shift 2 ;;
    --skip-if-in-workspace) SKIP_IF_IN_WORKSPACE="true"; shift ;;
    --skip-if-in-campaign) SKIP_IF_IN_CAMPAIGN="true"; shift ;;
    --skip-if-in-list) SKIP_IF_IN_LIST="true"; shift ;;
    --blocklist-id) BLOCKLIST_ID="${2:-}"; shift 2 ;;
    --verify-leads-on-import) VERIFY_LEADS_ON_IMPORT="true"; shift ;;
    --verify-leads-for-lead-finder) VERIFY_LEADS_FOR_LEAD_FINDER="true"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done

SAVE_API_KEY="${SAVE_API_KEY:-false}"
CONFIGURE_API_KEY="${CONFIGURE_API_KEY:-false}"
if [[ "$SAVE_API_KEY" == "true" ]]; then
  [[ -n "$API_KEY_OVERRIDE" ]] || { echo "--save-api-key requires --api-key." >&2; exit 1; }
  save_api_key "$API_KEY_OVERRIDE"
  echo "Saved Instantly API key to $(api_key_file)" >&2
  [[ -n "$ACTION" ]] || exit 0
fi
if [[ "$CONFIGURE_API_KEY" == "true" ]]; then
  if [[ -n "$API_KEY_OVERRIDE" ]]; then
    save_api_key "$API_KEY_OVERRIDE"
  elif [[ -t 0 ]]; then
    read -r -s -p "Enter Instantly API key to save locally: " key
    echo >&2
    save_api_key "$key"
  else
    echo "Cannot prompt in a non-interactive shell. Pass --api-key <key> --save-api-key." >&2
    echo "Refer to this article to create an Instantly API key: $API_KEY_HELP_URL" >&2
    exit 1
  fi
  [[ -n "$ACTION" ]] || exit 0
fi

PAYLOAD_FILE="$(mktemp)"
trap 'rm -f "$PAYLOAD_FILE"' EXIT

case "$ACTION" in
  list)
    [[ -n "$EMAIL" ]] || { echo "--email is required for lead list." >&2; exit 1; }
    python3 - "$PAYLOAD_FILE" "$EMAIL" "$LIMIT" <<'PY'
import json, sys
payload = {"contacts": [sys.argv[2]], "limit": int(sys.argv[3])}
open(sys.argv[1], "w", encoding="utf-8").write(json.dumps(payload, indent=2))
PY
    load_api_key
    result="$(curl_json POST "$API_BASE_URL/api/v2/leads/list" "$PAYLOAD_FILE")"
    ;;
  create)
    [[ -n "$EMAIL" ]] || { echo "--email is required for lead create." >&2; exit 1; }
    [[ -n "$CAMPAIGN_ID" ]] || { echo "--campaign-id is required for lead create in the Instantly send-email workflow." >&2; exit 1; }
    export EMAIL CAMPAIGN_ID FIRST_NAME LAST_NAME COMPANY_NAME JOB_TITLE WEBSITE PHONE PERSONALIZATION CUSTOM_VARIABLES_JSON SKIP_IF_IN_WORKSPACE SKIP_IF_IN_CAMPAIGN SKIP_IF_IN_LIST BLOCKLIST_ID VERIFY_LEADS_ON_IMPORT VERIFY_LEADS_FOR_LEAD_FINDER
    PY_ARGS=("$PAYLOAD_FILE")
    [[ "${#CUSTOM_VARIABLES[@]}" -gt 0 ]] && PY_ARGS+=("${CUSTOM_VARIABLES[@]}")
    python3 - "${PY_ARGS[@]}" <<'PY'
import json, os, sys
path = sys.argv[1]
payload = {"email": os.environ["EMAIL"]}
for env, key in {
    "CAMPAIGN_ID": "campaign", "FIRST_NAME": "first_name", "LAST_NAME": "last_name",
    "COMPANY_NAME": "company_name", "JOB_TITLE": "job_title", "WEBSITE": "website",
    "PHONE": "phone", "PERSONALIZATION": "personalization", "BLOCKLIST_ID": "blocklist_id",
}.items():
    if os.environ.get(env):
        payload[key] = os.environ[env]
for env, key in {
    "SKIP_IF_IN_WORKSPACE": "skip_if_in_workspace", "SKIP_IF_IN_CAMPAIGN": "skip_if_in_campaign",
    "SKIP_IF_IN_LIST": "skip_if_in_list", "VERIFY_LEADS_ON_IMPORT": "verify_leads_on_import",
    "VERIFY_LEADS_FOR_LEAD_FINDER": "verify_leads_for_lead_finder",
}.items():
    if os.environ.get(env) == "true":
        payload[key] = True
custom = {}
if os.environ.get("CUSTOM_VARIABLES_JSON"):
    custom.update(json.loads(os.environ["CUSTOM_VARIABLES_JSON"]))
for item in sys.argv[2:]:
    key, value = item.split("=", 1)
    custom[key] = value
if custom:
    payload["custom_variables"] = custom
open(path, "w", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False, indent=2))
PY
    if [[ "$DO_SEND" != "true" ]]; then
      result="$(cat "$PAYLOAD_FILE")"
    else
      load_api_key
      result="$(curl_json POST "$API_BASE_URL/api/v2/leads" "$PAYLOAD_FILE")"
    fi
    ;;
  move)
    [[ -n "$EMAIL" ]] || { echo "--email is required for lead move." >&2; exit 1; }
    [[ -n "$TO_CAMPAIGN_ID" || -n "$TO_LIST_ID" ]] || { echo "--to-campaign-id or --to-list-id is required for lead move." >&2; exit 1; }
    export EMAIL FROM_CAMPAIGN_ID FROM_LIST_ID TO_CAMPAIGN_ID TO_LIST_ID
    python3 - "$PAYLOAD_FILE" <<'PY'
import json, os, sys
payload = {"contacts": [os.environ["EMAIL"]]}
for env, key in {
    "FROM_CAMPAIGN_ID": "campaign", "FROM_LIST_ID": "list_id",
    "TO_CAMPAIGN_ID": "to_campaign_id", "TO_LIST_ID": "to_list_id",
}.items():
    if os.environ.get(env):
        payload[key] = os.environ[env]
open(sys.argv[1], "w", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False, indent=2))
PY
    if [[ "$DO_SEND" != "true" ]]; then
      result="$(cat "$PAYLOAD_FILE")"
    else
      load_api_key
      result="$(curl_json POST "$API_BASE_URL/api/v2/leads/move" "$PAYLOAD_FILE")"
    fi
    ;;
  *)
    echo "Action is required: list, create, or move." >&2
    usage >&2
    exit 1
    ;;
esac

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  printf '%s\n' "$result" > "$OUTPUT_PATH"
fi
printf '%s\n' "$result"
