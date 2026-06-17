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
  campaign.sh list [--limit 100] [global options]
  campaign.sh create --name "Campaign Name" --schedule-json JSON [--send] [global options]
  campaign.sh create --campaign-json JSON [--send] [global options]
  campaign.sh sending-status --campaign-id UUID [global options]

Read actions call the API immediately. Create dry-runs by default; pass --send to execute.

Global options:
  --api-key KEY
  --save-api-key
  --configure-api-key
  --clear-api-key
  --output PATH
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
API_KEY_OVERRIDE=""; OUTPUT_PATH=""; DO_SEND="false"; NAME=""; LIMIT="100"; CAMPAIGN_ID=""; SCHEDULE_JSON=""; CAMPAIGN_JSON=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-key) API_KEY_OVERRIDE="${2:-}"; shift 2 ;;
    --save-api-key) SAVE_API_KEY="true"; shift ;;
    --configure-api-key) CONFIGURE_API_KEY="true"; shift ;;
    --clear-api-key) rm -f "$(api_key_file)"; echo "Removed saved Instantly API key." >&2; shift ;;
    --output) OUTPUT_PATH="${2:-}"; shift 2 ;;
    --send) DO_SEND="true"; shift ;;
    --name) NAME="${2:-}"; shift 2 ;;
    --limit) LIMIT="${2:-}"; shift 2 ;;
    --campaign-id) CAMPAIGN_ID="${2:-}"; shift 2 ;;
    --schedule-json) SCHEDULE_JSON="${2:-}"; shift 2 ;;
    --campaign-json) CAMPAIGN_JSON="${2:-}"; shift 2 ;;
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
    load_api_key
    result="$(curl_json GET "$API_BASE_URL/api/v2/campaigns?limit=$LIMIT")"
    ;;
  create)
    if [[ -n "$CAMPAIGN_JSON" ]]; then
      printf '%s\n' "$CAMPAIGN_JSON" > "$PAYLOAD_FILE"
    else
      [[ -n "$NAME" ]] || { echo "--name is required for campaign create unless --campaign-json is provided." >&2; exit 1; }
      [[ -n "$SCHEDULE_JSON" ]] || { echo "--schedule-json is required for campaign create unless --campaign-json is provided. Instantly requires campaign_schedule." >&2; exit 1; }
      python3 - "$PAYLOAD_FILE" "$NAME" "$SCHEDULE_JSON" <<'PY'
import json, sys
payload = {"name": sys.argv[2]}
payload["campaign_schedule"] = json.loads(sys.argv[3])
open(sys.argv[1], "w", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False, indent=2))
PY
    fi
    if [[ "$DO_SEND" != "true" ]]; then result="$(cat "$PAYLOAD_FILE")"; else load_api_key; result="$(curl_json POST "$API_BASE_URL/api/v2/campaigns" "$PAYLOAD_FILE")"; fi
    ;;
  sending-status)
    [[ -n "$CAMPAIGN_ID" ]] || { echo "--campaign-id is required for sending-status." >&2; exit 1; }
    load_api_key
    result="$(curl_json GET "$API_BASE_URL/api/v2/campaigns/$CAMPAIGN_ID/sending-status")"
    ;;
  *) echo "Action is required: list, create, or sending-status." >&2; usage >&2; exit 1 ;;
esac
if [[ -n "$OUTPUT_PATH" ]]; then mkdir -p "$(dirname "$OUTPUT_PATH")"; printf '%s\n' "$result" > "$OUTPUT_PATH"; fi
printf '%s\n' "$result"
