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
  email.sh list --lead user@example.com [--limit 20] [--latest-of-thread] [global options]
  email.sh reply --eaccount sender@example.com --reply-to-uuid EMAIL_ID --subject "Re: ..." (--html HTML | --text TEXT) [--send] [global options]

List calls the API immediately. Reply dry-runs by default; pass --send to execute.

Global options:
  --api-key KEY
  --save-api-key
  --configure-api-key
  --clear-api-key
  --output PATH

Reply options:
  --additional-recipient EMAIL
  --cc EMAIL
  --bcc EMAIL
  --reminder-ts ISO_TIME
  --assigned-to USER_ID
EOF
}

config_dir() { printf '%s\n' "${INSTANTLY_SEND_EMAIL_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/$CONFIG_NAME}"; }
api_key_file() { printf '%s/api_key\n' "$(config_dir)"; }
save_api_key() { local dir path tmp; dir="$(config_dir)"; path="$(api_key_file)"; mkdir -p "$dir"; chmod 700 "$dir" 2>/dev/null || true; tmp="$(mktemp "$dir/api_key.XXXXXX")"; printf '%s\n' "$1" > "$tmp"; chmod 600 "$tmp" 2>/dev/null || true; mv "$tmp" "$path"; chmod 600 "$path" 2>/dev/null || true; }
load_api_key() {
  API_KEY="${API_KEY_OVERRIDE:-${INSTANTLY_API_KEY:-}}"
  if [[ -z "$API_KEY" && -r "$(api_key_file)" ]]; then IFS= read -r API_KEY < "$(api_key_file)" || true; API_KEY="${API_KEY//$'\r'/}"; fi
  if [[ -z "$API_KEY" ]]; then
    if [[ -t 0 ]]; then read -r -s -p "INSTANTLY_API_KEY not found. Please enter your Instantly API key: " API_KEY; echo >&2; [[ -n "$API_KEY" ]] && save_api_key "$API_KEY"; else echo "INSTANTLY_API_KEY is not set and no saved Instantly API key was found." >&2; echo "Set INSTANTLY_API_KEY, pass --api-key, or run --api-key <key> --save-api-key once." >&2; echo "Refer to this article to create an Instantly API key: $API_KEY_HELP_URL" >&2; exit 1; fi
  fi
}
curl_json() {
  local method="$1" url="$2" payload="${3:-}" response_file http_code
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
try: body = json.loads(raw) if raw.strip() else None
except json.JSONDecodeError: body = raw
out = {"status_code": code, "ok": 200 <= code < 300}
if body is not None: out["body"] = body
print(json.dumps(out, ensure_ascii=False, indent=2))
sys.exit(0 if 200 <= code < 300 else 1)
PY
  rm -f "$response_file"
}

ACTION="${1:-}"; [[ -n "$ACTION" ]] && shift || true
API_KEY_OVERRIDE=""; OUTPUT_PATH=""; DO_SEND="false"; LEAD=""; LIMIT="20"; LATEST_OF_THREAD="false"; EACCOUNT=""; REPLY_TO_UUID=""; SUBJECT=""; HTML=""; HTML_FILE=""; TEXT=""; TEXT_FILE=""; ADDITIONAL_RECIPIENTS=(); CC_VALUES=(); BCC_VALUES=(); REMINDER_TS=""; ASSIGNED_TO=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-key) API_KEY_OVERRIDE="${2:-}"; shift 2 ;;
    --save-api-key) SAVE_API_KEY="true"; shift ;;
    --configure-api-key) CONFIGURE_API_KEY="true"; shift ;;
    --clear-api-key) rm -f "$(api_key_file)"; echo "Removed saved Instantly API key." >&2; shift ;;
    --output) OUTPUT_PATH="${2:-}"; shift 2 ;;
    --send) DO_SEND="true"; shift ;;
    --lead) LEAD="${2:-}"; shift 2 ;;
    --limit) LIMIT="${2:-}"; shift 2 ;;
    --latest-of-thread) LATEST_OF_THREAD="true"; shift ;;
    --eaccount) EACCOUNT="${2:-}"; shift 2 ;;
    --reply-to-uuid) REPLY_TO_UUID="${2:-}"; shift 2 ;;
    --subject) SUBJECT="${2:-}"; shift 2 ;;
    --html) HTML="${2:-}"; shift 2 ;;
    --html-file) HTML_FILE="${2:-}"; shift 2 ;;
    --text) TEXT="${2:-}"; shift 2 ;;
    --text-file) TEXT_FILE="${2:-}"; shift 2 ;;
    --additional-recipient) ADDITIONAL_RECIPIENTS+=("${2:-}"); shift 2 ;;
    --cc) CC_VALUES+=("${2:-}"); shift 2 ;;
    --bcc) BCC_VALUES+=("${2:-}"); shift 2 ;;
    --reminder-ts) REMINDER_TS="${2:-}"; shift 2 ;;
    --assigned-to) ASSIGNED_TO="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done
SAVE_API_KEY="${SAVE_API_KEY:-false}"; CONFIGURE_API_KEY="${CONFIGURE_API_KEY:-false}"
if [[ "$SAVE_API_KEY" == "true" ]]; then [[ -n "$API_KEY_OVERRIDE" ]] || { echo "--save-api-key requires --api-key." >&2; exit 1; }; save_api_key "$API_KEY_OVERRIDE"; [[ -n "$ACTION" ]] || exit 0; fi
if [[ "$CONFIGURE_API_KEY" == "true" ]]; then if [[ -n "$API_KEY_OVERRIDE" ]]; then save_api_key "$API_KEY_OVERRIDE"; elif [[ -t 0 ]]; then read -r -s -p "Enter Instantly API key: " key; echo >&2; save_api_key "$key"; else echo "Cannot prompt in non-interactive shell." >&2; echo "Refer to this article to create an Instantly API key: $API_KEY_HELP_URL" >&2; exit 1; fi; [[ -n "$ACTION" ]] || exit 0; fi

PAYLOAD_FILE="$(mktemp)"; trap 'rm -f "$PAYLOAD_FILE"' EXIT
case "$ACTION" in
  list)
    [[ -n "$LEAD" ]] || { echo "--lead is required for email list." >&2; exit 1; }
    load_api_key
    URL="$(python3 - "$API_BASE_URL/api/v2/emails" "$LEAD" "$LIMIT" "$LATEST_OF_THREAD" <<'PY'
from urllib.parse import urlencode
import sys
base, lead, limit, latest = sys.argv[1:]
params = {"lead": lead, "limit": limit, "sort_order": "desc"}
if latest == "true":
    params["latest_of_thread"] = "true"
print(base + "?" + urlencode(params))
PY
)"
    result="$(curl_json GET "$URL")"
    ;;
  reply)
    [[ -n "$EACCOUNT" ]] || { echo "--eaccount is required for reply." >&2; exit 1; }
    [[ -n "$REPLY_TO_UUID" ]] || { echo "--reply-to-uuid is required for reply. Use email.sh list first and let the user choose an email id." >&2; exit 1; }
    [[ -n "$SUBJECT" ]] || { echo "--subject is required for reply." >&2; exit 1; }
    if [[ -n "$HTML_FILE" ]]; then [[ -f "$HTML_FILE" ]] || { echo "Missing --html-file: $HTML_FILE" >&2; exit 1; }; HTML="$(<"$HTML_FILE")"; fi
    if [[ -n "$TEXT_FILE" ]]; then [[ -f "$TEXT_FILE" ]] || { echo "Missing --text-file: $TEXT_FILE" >&2; exit 1; }; TEXT="$(<"$TEXT_FILE")"; fi
    [[ -n "$HTML" || -n "$TEXT" ]] || { echo "--html or --text is required for reply." >&2; exit 1; }
    export EACCOUNT REPLY_TO_UUID SUBJECT HTML TEXT REMINDER_TS ASSIGNED_TO
    PY_ARGS=("$PAYLOAD_FILE" "--additional")
    [[ "${#ADDITIONAL_RECIPIENTS[@]}" -gt 0 ]] && PY_ARGS+=("${ADDITIONAL_RECIPIENTS[@]}")
    PY_ARGS+=("--cc")
    [[ "${#CC_VALUES[@]}" -gt 0 ]] && PY_ARGS+=("${CC_VALUES[@]}")
    PY_ARGS+=("--bcc")
    [[ "${#BCC_VALUES[@]}" -gt 0 ]] && PY_ARGS+=("${BCC_VALUES[@]}")
    python3 - "${PY_ARGS[@]}" <<'PY'
import json, os, sys
args = sys.argv[1:]
path = args.pop(0)
add_i = args.index("--additional")
cc_i = args.index("--cc")
bcc_i = args.index("--bcc")
additional = args[add_i + 1:cc_i]
cc = args[cc_i + 1:bcc_i]
bcc = args[bcc_i + 1:]
def split(values):
    out = []
    for value in values:
        out += [part.strip() for part in value.split(",") if part.strip()]
    return out
payload = {"eaccount": os.environ["EACCOUNT"], "reply_to_uuid": os.environ["REPLY_TO_UUID"], "subject": os.environ["SUBJECT"], "body": {}}
if os.environ.get("HTML"): payload["body"]["html"] = os.environ["HTML"]
if os.environ.get("TEXT"): payload["body"]["text"] = os.environ["TEXT"]
if split(additional): payload["additional_recipients"] = split(additional)
if split(cc): payload["cc_address_email_list"] = ",".join(split(cc))
if split(bcc): payload["bcc_address_email_list"] = ",".join(split(bcc))
if os.environ.get("REMINDER_TS"): payload["reminder_ts"] = os.environ["REMINDER_TS"]
if os.environ.get("ASSIGNED_TO"): payload["assigned_to"] = os.environ["ASSIGNED_TO"]
open(path, "w", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False, indent=2))
PY
    if [[ "$DO_SEND" != "true" ]]; then result="$(cat "$PAYLOAD_FILE")"; else load_api_key; result="$(curl_json POST "$API_BASE_URL/api/v2/emails/reply" "$PAYLOAD_FILE")"; fi
    ;;
  *) echo "Action is required: list or reply." >&2; usage >&2; exit 1 ;;
esac
if [[ -n "$OUTPUT_PATH" ]]; then mkdir -p "$(dirname "$OUTPUT_PATH")"; printf '%s\n' "$result" > "$OUTPUT_PATH"; fi
printf '%s\n' "$result"
