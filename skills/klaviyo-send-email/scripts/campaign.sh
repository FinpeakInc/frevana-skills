#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="https://a.klaviyo.com/api"
CONFIG_NAME="klaviyo-send-email"
CONNECT_TIMEOUT="10"
MAX_TIME="120"
API_KEY_HELP_URL="https://frevana.gitbook.io/frevana-docs/email-integrations/klaviyo-integration"

usage() {
  cat <<'EOF'
Usage:
  campaign.sh list --filter CHANNEL [--limit N] [--sort SORT] [global options]
  campaign.sh get --campaign-id UUID [global options]
  campaign.sh create --name NAME --audience-json JSON --message-json JSON [--send] [global options]
  campaign.sh update --campaign-id UUID --name NAME [--audience-json JSON] [--send] [global options]
  campaign.sh delete --campaign-id UUID [--send] [global options]
  campaign.sh clone --campaign-id UUID [--send] [global options]
  campaign.sh send --campaign-id UUID [--send] [global options]
  campaign.sh send-status --send-job-id UUID [global options]
  campaign.sh cancel --send-job-id UUID [--send] [global options]
  campaign.sh assign-template --message-id UUID --template-id UUID [--send] [global options]
  campaign.sh list-messages --campaign-id UUID [global options]
  campaign.sh get-message --message-id UUID [global options]
  campaign.sh update-message --message-id UUID --message-json JSON [--send] [global options]
  campaign.sh refresh-estimation --campaign-id UUID [--send] [global options]
  campaign.sh get-estimation --campaign-id UUID [global options]
  campaign.sh get-estimation-job --estimation-job-id UUID [global options]

Read actions call the API immediately. Write actions dry-run by default; pass --send to execute.

--- Required Parameters (per action) ---
  --filter         (list)     Filter string, e.g. 'equals(messages.channel,"email")'
  --campaign-id    (get/update/delete/clone/send/list-messages/refresh-estimation/get-estimation)
  --name           (create/update)  Campaign name
  --audience-json  (create/update)        JSON: {"included":["seg_id"],"excluded":[]}
  --message-json   (create)       JSON: {"subject":"...","from_email":"...","from_label":"..."}
  --message-json   (update-message) JSON: {"definition":{"label":"...","content":{"subject":"..."}}}
  --send-job-id    (send-status/cancel)   Campaign send job UUID
  --message-id     (assign-template/get-message/update-message)  Campaign message UUID
  --template-id    (assign-template)      Reusable template UUID
  --estimation-job-id (get-estimation-job) Recipient estimation job UUID

--- Optional Parameters (what they do, when to fill) ---
  --limit N        (list)     Results per page (default 100). Use when you want more/fewer results.
  --sort SORT      (list)     Sort field, e.g. "-created_at", "name". Use when you need ordering.
  --audience-json  (update)   Update audience groups. Only pass when you need to change audiences.
  --send                       Execute the API call (dry-run by default). Pass when you approve.

--- Global Options (apply to all actions) ---
  Environment variable: KLAVIVO_API_KEY  (falls back to saved key, overridden by --api-key)
  --api-key KEY                 Klaviyo API key (highest priority)
  --save-api-key                Save --api-key to ~/.config/klaviyo-send-email/api_key
  --configure-api-key           Prompt to save a new API key
  --clear-api-key               Remove the saved API key
  --output PATH                 Save response JSON to file (printed to stdout anyway)

Filter examples:
  --filter 'equals(messages.channel,"email")'

Sort options:
  created_at, -created_at, name, -name, scheduled_at, -scheduled_at, updated_at, -updated_at
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
CAMPAIGN_ID=""
NAME=""
AUDIENCE_JSON=""
MESSAGE_JSON=""
SEND_JOB_ID=""
MESSAGE_ID=""
TEMPLATE_ID=""
ESTIMATION_JOB_ID=""

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
    --campaign-id) CAMPAIGN_ID="${2:-}"; shift 2 ;;
    --name) NAME="${2:-}"; shift 2 ;;
    --audience-json) AUDIENCE_JSON="${2:-}"; shift 2 ;;
    --message-json) MESSAGE_JSON="${2:-}"; shift 2 ;;
    --send-job-id) SEND_JOB_ID="${2:-}"; shift 2 ;;
    --message-id) MESSAGE_ID="${2:-}"; shift 2 ;;
    --template-id) TEMPLATE_ID="${2:-}"; shift 2 ;;
    --estimation-job-id) ESTIMATION_JOB_ID="${2:-}"; shift 2 ;;
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
    [[ -n "$FILTER" ]] || { echo "--filter is required for campaign list. Example: --filter 'equals(messages.channel,\"email\")'" >&2; exit 1; }
    load_api_key
    list_url="$API_BASE_URL/campaigns?filter=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$FILTER'))")&page[size]=$LIMIT"
    [[ -n "$SORT" ]] && list_url="$list_url&sort=$SORT"
    result="$(curl_json GET "$list_url")"
    ;;
  get)
    [[ -n "$CAMPAIGN_ID" ]] || { echo "--campaign-id is required for campaign get." >&2; exit 1; }
    load_api_key
    result="$(curl_json GET "$API_BASE_URL/campaigns/$CAMPAIGN_ID")"
    ;;
  create)
    [[ -n "$NAME" ]] || { echo "--name is required for campaign create." >&2; exit 1; }
    [[ -n "$AUDIENCE_JSON" ]] || { echo "--audience-json is required for campaign create. Example: '{\"included\":[\"Y6nRLr\"],\"excluded\":[]}'" >&2; exit 1; }
    [[ -n "$MESSAGE_JSON" ]] || { echo "--message-json is required for campaign create. Must contain at least subject/from_email/from_label." >&2; exit 1; }
    export NAME AUDIENCE_JSON MESSAGE_JSON
    python3 - "$PAYLOAD_FILE" <<'PY'
import json, os, sys
audiences = json.loads(os.environ["AUDIENCE_JSON"])
message = json.loads(os.environ["MESSAGE_JSON"])
payload = {
    "data": {
        "type": "campaign",
        "attributes": {
            "name": os.environ["NAME"],
            "audiences": audiences,
            "campaign-messages": {
                "data": [
                    {
                        "type": "campaign-message",
                        "attributes": {
                            "definition": {
                                "channel": "email",
                                "label": message.get("label", "Email Message"),
                                "content": {
                                    "subject": message["subject"],
                                    "preview_text": message.get("preview_text", ""),
                                    "from_email": message["from_email"],
                                    "from_label": message["from_label"]
                                }
                            }
                        }
                    }
                ]
            }
        }
    }
}
content = payload["data"]["attributes"]["campaign-messages"]["data"][0]["attributes"]["definition"]["content"]
if message.get("reply_to_email"):
    content["reply_to_email"] = message["reply_to_email"]
if message.get("cc_email"):
    content["cc_email"] = message["cc_email"]
if message.get("bcc_email"):
    content["bcc_email"] = message["bcc_email"]
if "send_options" in message:
    payload["data"]["attributes"]["send_options"] = message["send_options"]
if "tracking_options" in message:
    payload["data"]["attributes"]["tracking_options"] = message["tracking_options"]
if "send_strategy" in message:
    payload["data"]["attributes"]["send_strategy"] = message["send_strategy"]
open(sys.argv[1], "w", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False, indent=2))
PY
    if [[ "$DO_SEND" != "true" ]]; then
      result="$(cat "$PAYLOAD_FILE")"
    else
      load_api_key
      result="$(curl_json POST "$API_BASE_URL/campaigns" "$PAYLOAD_FILE")"
    fi
    ;;
  update)
    [[ -n "$CAMPAIGN_ID" ]] || { echo "--campaign-id is required for campaign update." >&2; exit 1; }
    [[ -n "$NAME" ]] || { echo "--name is required for campaign update." >&2; exit 1; }
    export CAMPAIGN_ID NAME AUDIENCE_JSON
    python3 - "$PAYLOAD_FILE" <<'PY'
import json, os, sys
payload = {
    "data": {
        "type": "campaign",
        "id": os.environ["CAMPAIGN_ID"],
        "attributes": {
            "name": os.environ["NAME"]
        }
    }
}
if os.environ.get("AUDIENCE_JSON"):
    payload["data"]["attributes"]["audiences"] = json.loads(os.environ["AUDIENCE_JSON"])
open(sys.argv[1], "w", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False, indent=2))
PY
    if [[ "$DO_SEND" != "true" ]]; then
      result="$(cat "$PAYLOAD_FILE")"
    else
      load_api_key
      result="$(curl_json PATCH "$API_BASE_URL/campaigns/$CAMPAIGN_ID" "$PAYLOAD_FILE")"
    fi
    ;;
  delete)
    [[ -n "$CAMPAIGN_ID" ]] || { echo "--campaign-id is required for campaign delete." >&2; exit 1; }
    if [[ "$DO_SEND" != "true" ]]; then
      echo "Dry-run: DELETE $API_BASE_URL/campaigns/$CAMPAIGN_ID" >&2
      echo '{"status_code":204,"ok":true,"body":"Would delete campaign. Pass --send to execute."}'
    else
      load_api_key
      result="$(curl_json DELETE "$API_BASE_URL/campaigns/$CAMPAIGN_ID")"
    fi
    ;;
  clone)
    [[ -n "$CAMPAIGN_ID" ]] || { echo "--campaign-id is required for campaign clone." >&2; exit 1; }
    export CAMPAIGN_ID
    python3 - "$PAYLOAD_FILE" <<'PY'
import json, os, sys
payload = {
    "data": {
        "type": "campaign",
        "id": os.environ["CAMPAIGN_ID"]
    }
}
open(sys.argv[1], "w", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False, indent=2))
PY
    if [[ "$DO_SEND" != "true" ]]; then
      result="$(cat "$PAYLOAD_FILE")"
    else
      load_api_key
      result="$(curl_json POST "$API_BASE_URL/campaign-clone" "$PAYLOAD_FILE")"
    fi
    ;;
  send)
    [[ -n "$CAMPAIGN_ID" ]] || { echo "--campaign-id is required for campaign send." >&2; exit 1; }
    export CAMPAIGN_ID
    python3 - "$PAYLOAD_FILE" <<'PY'
import json, os, sys
payload = {
    "data": {
        "type": "campaign-send-job",
        "id": os.environ["CAMPAIGN_ID"],
        "attributes": {}
    }
}
open(sys.argv[1], "w", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False, indent=2))
PY
    if [[ "$DO_SEND" != "true" ]]; then
      result="$(cat "$PAYLOAD_FILE")"
    else
      load_api_key
      result="$(curl_json POST "$API_BASE_URL/campaign-send-jobs" "$PAYLOAD_FILE")"
    fi
    ;;
  send-status)
    [[ -n "$SEND_JOB_ID" ]] || { echo "--send-job-id is required for campaign send-status." >&2; exit 1; }
    load_api_key
    result="$(curl_json GET "$API_BASE_URL/campaign-send-jobs/$SEND_JOB_ID")"
    ;;
  cancel)
    [[ -n "$SEND_JOB_ID" ]] || { echo "--send-job-id is required for campaign cancel." >&2; exit 1; }
    export SEND_JOB_ID
    python3 - "$PAYLOAD_FILE" <<'PY'
import json, os, sys
payload = {
    "data": {
        "type": "campaign-send-job",
        "id": os.environ["SEND_JOB_ID"],
        "attributes": {
            "status": "cancelled"
        }
    }
}
open(sys.argv[1], "w", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False, indent=2))
PY
    if [[ "$DO_SEND" != "true" ]]; then
      result="$(cat "$PAYLOAD_FILE")"
    else
      load_api_key
      result="$(curl_json PATCH "$API_BASE_URL/campaign-send-jobs/$SEND_JOB_ID" "$PAYLOAD_FILE")"
    fi
    ;;
  assign-template)
    [[ -n "$MESSAGE_ID" ]] || { echo "--message-id is required for campaign assign-template." >&2; exit 1; }
    [[ -n "$TEMPLATE_ID" ]] || { echo "--template-id is required for campaign assign-template." >&2; exit 1; }
    export MESSAGE_ID TEMPLATE_ID
    python3 - "$PAYLOAD_FILE" <<'PY'
import json, os, sys
payload = {
    "data": {
        "type": "campaign-message",
        "id": os.environ["MESSAGE_ID"],
        "relationships": {
            "template": {
                "data": {
                    "type": "template",
                    "id": os.environ["TEMPLATE_ID"]
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
      result="$(curl_json POST "$API_BASE_URL/campaign-message-assign-template" "$PAYLOAD_FILE")"
    fi
    ;;
  list-messages)
    [[ -n "$CAMPAIGN_ID" ]] || { echo "--campaign-id is required for campaign list-messages." >&2; exit 1; }
    load_api_key
    result="$(curl_json GET "$API_BASE_URL/campaigns/$CAMPAIGN_ID/campaign-messages")"
    ;;
  get-message)
    [[ -n "$MESSAGE_ID" ]] || { echo "--message-id is required for campaign get-message." >&2; exit 1; }
    load_api_key
    result="$(curl_json GET "$API_BASE_URL/campaign-messages/$MESSAGE_ID")"
    ;;
  update-message)
    [[ -n "$MESSAGE_ID" ]] || { echo "--message-id is required for campaign update-message." >&2; exit 1; }
    [[ -n "$MESSAGE_JSON" ]] || { echo "--message-json is required for campaign update-message." >&2; exit 1; }
    export MESSAGE_ID MESSAGE_JSON
    python3 - "$PAYLOAD_FILE" <<'PY'
import json, os, sys
message = json.loads(os.environ["MESSAGE_JSON"])
definition = message.get("definition", {})
if "channel" not in definition:
    definition["channel"] = "email"
payload = {
    "data": {
        "type": "campaign-message",
        "id": os.environ["MESSAGE_ID"],
        "attributes": {
            "definition": definition,
        }
    }
}
open(sys.argv[1], "w", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False, indent=2))
PY
    if [[ "$DO_SEND" != "true" ]]; then
      result="$(cat "$PAYLOAD_FILE")"
    else
      load_api_key
      result="$(curl_json PATCH "$API_BASE_URL/campaign-messages/$MESSAGE_ID" "$PAYLOAD_FILE")"
    fi
    ;;
  refresh-estimation)
    [[ -n "$CAMPAIGN_ID" ]] || { echo "--campaign-id is required for campaign refresh-estimation." >&2; exit 1; }
    export CAMPAIGN_ID
    python3 - "$PAYLOAD_FILE" <<'PY'
import json, os, sys
payload = {
    "data": {
        "type": "campaign-recipient-estimation-job",
        "id": os.environ["CAMPAIGN_ID"],
        "attributes": {}
    }
}
open(sys.argv[1], "w", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False, indent=2))
PY
    if [[ "$DO_SEND" != "true" ]]; then
      result="$(cat "$PAYLOAD_FILE")"
    else
      load_api_key
      result="$(curl_json POST "$API_BASE_URL/campaign-recipient-estimation-jobs" "$PAYLOAD_FILE")"
    fi
    ;;
  get-estimation)
    [[ -n "$CAMPAIGN_ID" ]] || { echo "--campaign-id is required for campaign get-estimation." >&2; exit 1; }
    load_api_key
    result="$(curl_json GET "$API_BASE_URL/campaign-recipient-estimations/$CAMPAIGN_ID")"
    ;;
  get-estimation-job)
    [[ -n "$ESTIMATION_JOB_ID" ]] || { echo "--estimation-job-id is required for campaign get-estimation-job." >&2; exit 1; }
    load_api_key
    result="$(curl_json GET "$API_BASE_URL/campaign-recipient-estimation-jobs/$ESTIMATION_JOB_ID")"
    ;;
  *)
    echo "Action is required: list, get, create, update, delete, clone, send, send-status, cancel, assign-template, list-messages, get-message, update-message, refresh-estimation, get-estimation, or get-estimation-job." >&2
    usage >&2
    exit 1
    ;;
esac

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  printf '%s\n' "$result" > "$OUTPUT_PATH"
fi
printf '%s\n' "$result"
