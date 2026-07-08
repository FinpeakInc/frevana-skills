#!/usr/bin/env bash

set -euo pipefail

CONNECT_TIMEOUT="10"
MAX_TIME="600"
CONFIG_DOC_URL="https://frevana.gitbook.io/frevana-docs/email-integrations/sendgrid-integration"

usage() {
  cat <<'EOF'
Usage:
  get_email_log.sh --sg-message-id ID [options]
  get_email_log.sh --to EMAIL --sent-at ISO_TIME [--message-id ID] [--subject SUBJECT] [options]
  get_email_log.sh --query "query" [--message-id ID] [options]

Retrieve per-message Twilio SendGrid Email Logs activity with GET /v3/logs/{sg_message_id}.
When only the Mail Send x-message-id or no message ID is known, first search POST /v3/logs
to resolve the full sg_message_id, then retrieve the detailed log by ID.

Options:
  --sg-message-id     Full SendGrid Email Logs sg_message_id for direct by-ID lookup
  --to                Recipient email used to search POST /v3/logs when full sg_message_id is unknown
  --from              Optional sender email filter for POST /v3/logs search
  --sent-at           Sent/queued ISO time used as lower bound for POST /v3/logs search
  --message-id        Optional Mail Send x-message-id used for fuzzy matching after POST /v3/logs
  --subject           Optional exact subject filter for POST /v3/logs search
  --status            Optional status filter, repeatable or comma-separated
  --start-time        Optional lower bound ISO timestamp for POST /v3/logs search
  --end-time          Optional upper bound ISO timestamp for POST /v3/logs search
  --query             Raw SendGrid Email Logs query string. Overrides generated search filters
  --sent-at-lookback-seconds Seconds subtracted from --sent-at before querying. Default 5
  --limit             Number of /v3/logs search messages to inspect, 1-1000. Default 100
  --on-behalf-of      Optional SendGrid on-behalf-of header value for parent account calls
  --subuser           Optional numeric SendGrid subuser ID for POST /v3/logs search. Repeatable or comma-separated
  --region            SendGrid API region: global or eu. Default global
  --api-key           Optional SendGrid API key override for this run
  --save-api-key      Save --api-key for future runs
  --configure-api-key Prompt for a SendGrid API key and save it for future runs
  --clear-api-key     Remove the locally saved SendGrid API key
  --output            Optional path for saving returned JSON, summary JSON, or dry-run metadata
  --summary-only      Print only the computed event summary
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

SG_MESSAGE_ID=""
SEARCH_RAW_QUERY=""
SEARCH_TO_EMAIL=""
SEARCH_FROM_EMAIL=""
SEARCH_SENT_AT=""
SEARCH_MESSAGE_ID=""
SEARCH_SUBJECT=""
SEARCH_STATUSES=""
SEARCH_START_TIME=""
SEARCH_END_TIME=""
SEARCH_SENT_AT_LOOKBACK_SECONDS="5"
SEARCH_LIMIT="100"
ON_BEHALF_OF=""
SUBUSERS=""
REGION="global"
API_KEY_OVERRIDE=""
SAVE_API_KEY="false"
CONFIGURE_API_KEY="false"
CLEAR_API_KEY="false"
OUTPUT_PATH=""
SUMMARY_ONLY="false"
DRY_RUN="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --sg-message-id)
      SG_MESSAGE_ID="${2:-}"
      shift 2
      ;;
    --to)
      SEARCH_TO_EMAIL="${2:-}"
      shift 2
      ;;
    --from|--from-email)
      SEARCH_FROM_EMAIL="${2:-}"
      shift 2
      ;;
    --sent-at)
      SEARCH_SENT_AT="${2:-}"
      shift 2
      ;;
    --message-id)
      SEARCH_MESSAGE_ID="${2:-}"
      shift 2
      ;;
    --subject)
      SEARCH_SUBJECT="${2:-}"
      shift 2
      ;;
    --status)
      if [[ -z "$SEARCH_STATUSES" ]]; then
        SEARCH_STATUSES="${2:-}"
      else
        SEARCH_STATUSES="$SEARCH_STATUSES,${2:-}"
      fi
      shift 2
      ;;
    --start-time)
      SEARCH_START_TIME="${2:-}"
      shift 2
      ;;
    --end-time)
      SEARCH_END_TIME="${2:-}"
      shift 2
      ;;
    --query)
      SEARCH_RAW_QUERY="${2:-}"
      shift 2
      ;;
    --sent-at-lookback-seconds)
      SEARCH_SENT_AT_LOOKBACK_SECONDS="${2:-}"
      shift 2
      ;;
    --limit)
      SEARCH_LIMIT="${2:-}"
      shift 2
      ;;
    --on-behalf-of)
      ON_BEHALF_OF="${2:-}"
      shift 2
      ;;
    --subuser)
      if [[ -z "$SUBUSERS" ]]; then
        SUBUSERS="${2:-}"
      else
        SUBUSERS="$SUBUSERS,${2:-}"
      fi
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
    --summary-only)
      SUMMARY_ONLY="true"
      shift
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

HAS_ACTIVITY_OPERATION="false"
if [[ -n "$SG_MESSAGE_ID" || -n "$SEARCH_RAW_QUERY" || -n "$SEARCH_TO_EMAIL" || -n "$SEARCH_FROM_EMAIL" || -n "$SEARCH_SENT_AT" || -n "$SEARCH_MESSAGE_ID" || -n "$SEARCH_SUBJECT" || -n "$SEARCH_STATUSES" || -n "$SEARCH_START_TIME" || -n "$SEARCH_END_TIME" || -n "$ON_BEHALF_OF" || -n "$OUTPUT_PATH" || "$SUMMARY_ONLY" == "true" || "$DRY_RUN" == "true" ]]; then
  HAS_ACTIVITY_OPERATION="true"
fi

if [[ "$CLEAR_API_KEY" == "true" ]]; then
  clear_saved_api_key
  echo "Removed locally saved SendGrid API key from $(api_key_file)" >&2
  if [[ "$HAS_ACTIVITY_OPERATION" != "true" && "$CONFIGURE_API_KEY" != "true" && -z "$API_KEY_OVERRIDE" ]]; then
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
  API_KEY_OVERRIDE="$API_KEY_TO_SAVE"
  echo "Saved SendGrid API key for future runs to $(api_key_file)" >&2
  if [[ "$HAS_ACTIVITY_OPERATION" != "true" ]]; then
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
  if [[ "$HAS_ACTIVITY_OPERATION" != "true" ]]; then
    exit 0
  fi
fi

RESOLVE_SG_MESSAGE_ID="false"
if [[ -z "$SG_MESSAGE_ID" ]]; then
  RESOLVE_SG_MESSAGE_ID="true"
fi

if [[ "$RESOLVE_SG_MESSAGE_ID" == "true" && -z "$SEARCH_RAW_QUERY" && -z "$SEARCH_TO_EMAIL" && -z "$SEARCH_FROM_EMAIL" && -z "$SEARCH_SENT_AT" && -z "$SEARCH_SUBJECT" && -z "$SEARCH_STATUSES" && -z "$SEARCH_START_TIME" && -z "$SEARCH_END_TIME" ]]; then
  echo "Pass --sg-message-id for direct lookup, pass --query, or pass one or more search filters such as --to, --from, --sent-at, --subject, --status, --start-time, or --end-time." >&2
  usage >&2
  exit 1
fi

if [[ -n "$SG_MESSAGE_ID" && ( "$SG_MESSAGE_ID" == "." || "$SG_MESSAGE_ID" == ".." ) ]]; then
  echo "Invalid --sg-message-id value." >&2
  exit 1
fi

if [[ ! "$SEARCH_SENT_AT_LOOKBACK_SECONDS" =~ ^[0-9]+$ ]] || (( SEARCH_SENT_AT_LOOKBACK_SECONDS > 300 )); then
  echo "Invalid --sent-at-lookback-seconds value: $SEARCH_SENT_AT_LOOKBACK_SECONDS. Expected integer 0-300." >&2
  exit 1
fi

if [[ ! "$SEARCH_LIMIT" =~ ^[0-9]+$ ]] || (( SEARCH_LIMIT < 1 || SEARCH_LIMIT > 1000 )); then
  echo "Invalid --limit value: $SEARCH_LIMIT. Expected integer 1-1000." >&2
  exit 1
fi

if [[ -n "$SUBUSERS" ]]; then
  IFS=',' read -r -a SUBUSER_VALUES <<< "$SUBUSERS"
  for subuser in "${SUBUSER_VALUES[@]}"; do
    subuser="${subuser//[[:space:]]/}"
    if [[ -z "$subuser" || ! "$subuser" =~ ^[0-9]+$ ]]; then
      echo "Invalid --subuser value: $subuser. Expected numeric subuser ID." >&2
      exit 1
    fi
  done
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

REQUEST_FILE="$(mktemp)"
SEARCH_PAYLOAD_FILE="$(mktemp)"
SEARCH_RESPONSE_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
RESULT_FILE="$(mktemp)"
cleanup() {
  rm -f "$REQUEST_FILE" "$SEARCH_PAYLOAD_FILE" "$SEARCH_RESPONSE_FILE" "$RESPONSE_FILE" "$RESULT_FILE"
}
trap cleanup EXIT

API_BASE_URL="https://api.sendgrid.com"
if [[ "$REGION" == "eu" ]]; then
  API_BASE_URL="https://api.eu.sendgrid.com"
fi

export API_BASE_URL SG_MESSAGE_ID SEARCH_RAW_QUERY SEARCH_TO_EMAIL SEARCH_FROM_EMAIL SEARCH_SENT_AT SEARCH_MESSAGE_ID SEARCH_SUBJECT SEARCH_STATUSES SEARCH_START_TIME SEARCH_END_TIME SEARCH_SENT_AT_LOOKBACK_SECONDS SEARCH_LIMIT ON_BEHALF_OF SUBUSERS REGION RESOLVE_SG_MESSAGE_ID

REQUEST_URL="$(python3 - "$REQUEST_FILE" <<'PY'
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

base = os.environ["API_BASE_URL"].rstrip("/") + "/v3/logs/"
metadata = {
    "region": os.environ["REGION"],
}
message_id = os.environ.get("SG_MESSAGE_ID", "")
if message_id:
    url = base + quote(message_id, safe="")
    metadata.update({
        "method": "GET",
        "url": url,
        "sg_message_id": message_id,
    })
else:
    url = base + "{resolved_sg_message_id}"
    metadata.update({
        "method": "POST_THEN_GET",
        "search_url": os.environ["API_BASE_URL"].rstrip("/") + "/v3/logs",
        "detail_url_template": url,
    })
on_behalf_of = os.environ.get("ON_BEHALF_OF", "")
if on_behalf_of:
    metadata["headers"] = {"on-behalf-of": on_behalf_of}

Path(sys.argv[1]).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
print(url)
PY
)"

if [[ "$RESOLVE_SG_MESSAGE_ID" == "true" ]]; then
  python3 - "$REQUEST_FILE" "$SEARCH_PAYLOAD_FILE" <<'PY'
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def sql_quote(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def timestamp_literal(value: str) -> str:
    return f'TIMESTAMP "{value}"'


def parse_iso_datetime(value: str) -> datetime:
    normalized = value
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        print(f"Invalid --sent-at value: {value}. Expected ISO timestamp like 2026-06-15T10:00:00Z.", file=sys.stderr)
        sys.exit(1)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


raw_query = os.environ.get("SEARCH_RAW_QUERY", "")
if raw_query:
    query = raw_query
else:
    conditions = []

    to_email = os.environ.get("SEARCH_TO_EMAIL", "")
    if to_email:
        conditions.append(f"to_email = {sql_quote(to_email)}")

    from_email = os.environ.get("SEARCH_FROM_EMAIL", "")
    if from_email:
        conditions.append(f"from_email = {sql_quote(from_email)}")

    sent_at = os.environ.get("SEARCH_SENT_AT", "")
    if sent_at:
        parsed_sent_at = parse_iso_datetime(sent_at)
        query_start = parsed_sent_at - timedelta(seconds=int(os.environ["SEARCH_SENT_AT_LOOKBACK_SECONDS"]))
        conditions.append(f"sg_message_id_created_at >= {timestamp_literal(iso_z(query_start))}")

    start_time = os.environ.get("SEARCH_START_TIME", "")
    if start_time:
        conditions.append(f"sg_message_id_created_at >= {timestamp_literal(start_time)}")

    end_time = os.environ.get("SEARCH_END_TIME", "")
    if end_time:
        conditions.append(f"sg_message_id_created_at <= {timestamp_literal(end_time)}")

    subject = os.environ.get("SEARCH_SUBJECT", "")
    if subject:
        conditions.append(f"subject = {sql_quote(subject)}")

    statuses = []
    for status in os.environ.get("SEARCH_STATUSES", "").split(","):
        item = status.strip()
        if item:
            statuses.append(item)
    if statuses:
        values = ", ".join(sql_quote(status) for status in statuses)
        conditions.append(f"status IN ({values})")

    query = " AND ".join(conditions)

payload = {
    "query": query,
    "limit": int(os.environ["SEARCH_LIMIT"]),
}
subusers = []
for subuser in os.environ.get("SUBUSERS", "").split(","):
    item = subuser.strip()
    if item:
        subusers.append(item)
if subusers:
    payload["subusers"] = subusers
Path(sys.argv[2]).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

metadata = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
metadata["search_payload"] = payload
if os.environ.get("SEARCH_MESSAGE_ID"):
    metadata["mail_send_message_id_filter"] = os.environ["SEARCH_MESSAGE_ID"]
metadata["resolution"] = "POST /v3/logs will run first to resolve the full sg_message_id; then GET /v3/logs/{sg_message_id} will retrieve details."
Path(sys.argv[1]).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
PY
fi

if [[ "$DRY_RUN" == "true" ]]; then
  if [[ -n "$OUTPUT_PATH" ]]; then
    mkdir -p "$(dirname "$OUTPUT_PATH")"
    cp "$REQUEST_FILE" "$OUTPUT_PATH"
    echo "Saved SendGrid email log dry-run metadata to $OUTPUT_PATH" >&2
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

if [[ "$RESOLVE_SG_MESSAGE_ID" == "true" ]]; then
  SEARCH_CURL_ARGS=(
    -sS
    --connect-timeout "$CONNECT_TIMEOUT"
    --max-time "$MAX_TIME"
    -o "$SEARCH_RESPONSE_FILE"
    -w "%{http_code}"
    -X POST "$API_BASE_URL/v3/logs"
    -H "Content-Type: application/json"
    -H "Authorization: Bearer $API_KEY"
    --data @"$SEARCH_PAYLOAD_FILE"
  )

  if [[ -n "$ON_BEHALF_OF" ]]; then
    SEARCH_CURL_ARGS+=(-H "on-behalf-of: $ON_BEHALF_OF")
  fi

  SEARCH_HTTP_CODE="$(
    curl "${SEARCH_CURL_ARGS[@]}"
  )"

  if [[ "$SEARCH_HTTP_CODE" -lt 200 || "$SEARCH_HTTP_CODE" -ge 300 ]]; then
    echo "SendGrid Email Logs search API request failed with HTTP $SEARCH_HTTP_CODE" >&2
    cat "$SEARCH_RESPONSE_FILE" >&2
    exit 1
  fi

  if [[ ! -s "$SEARCH_RESPONSE_FILE" ]]; then
    echo "SendGrid Email Logs search API returned an empty response body." >&2
    exit 1
  fi

  SG_MESSAGE_ID="$(python3 - "$SEARCH_RESPONSE_FILE" "$SEARCH_MESSAGE_ID" <<'PY'
import json
import re
import sys
from pathlib import Path

response_path = Path(sys.argv[1])
message_id = sys.argv[2]

try:
    parsed = json.loads(response_path.read_text(encoding="utf-8"))
except json.JSONDecodeError as exc:
    print(f"SendGrid Email Logs search API returned non-JSON response: {exc}", file=sys.stderr)
    sys.exit(1)


def normalize(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def strip_angle_brackets(value):
    value = str(value).strip()
    if value.startswith("<") and value.endswith(">"):
        return value[1:-1].strip()
    return value


def strip_sendgrid_suffix(value):
    value = strip_angle_brackets(value)
    if ".recvd-" in value:
        return value.split(".recvd-", 1)[0]
    return value


def message_id_match(user_message_id, sg_message_id):
    user_raw = strip_angle_brackets(user_message_id)
    sg_raw = strip_angle_brackets(sg_message_id)
    if not user_raw or not sg_raw:
        return None

    user_lower = user_raw.lower()
    sg_lower = sg_raw.lower()
    if user_lower == sg_lower:
        return "exact"
    if ".recvd-" in sg_lower and sg_lower.startswith(user_lower):
        return "sg_message_id_starts_with_user_message_id_before_recvd_suffix"
    if sg_lower.startswith(user_lower):
        return "sg_message_id_starts_with_user_message_id"

    sg_without_suffix = strip_sendgrid_suffix(sg_raw).lower()
    if user_lower == sg_without_suffix:
        return "matches_sg_message_id_without_suffix"
    if sg_without_suffix.startswith(user_lower):
        return "sg_message_id_without_suffix_starts_with_user_message_id"

    normalized_user = normalize(user_raw)
    normalized_sg = normalize(sg_raw)
    normalized_sg_without_suffix = normalize(sg_without_suffix)
    if normalized_user and normalized_sg:
        if normalized_user == normalized_sg:
            return "normalized_exact"
        if normalized_sg.startswith(normalized_user):
            return "normalized_sg_message_id_starts_with_user_message_id"
        if normalized_user in normalized_sg:
            return "normalized_user_message_id_inside_sg_message_id"
        if normalized_sg in normalized_user:
            return "normalized_sg_message_id_inside_user_message_id"
    if normalized_user and normalized_sg_without_suffix:
        if normalized_user == normalized_sg_without_suffix:
            return "normalized_matches_sg_message_id_without_suffix"
        if normalized_sg_without_suffix.startswith(normalized_user):
            return "normalized_sg_message_id_without_suffix_starts_with_user_message_id"
    return None


messages = parsed.get("messages", []) if isinstance(parsed, dict) else []
if not messages:
    print("No Email Logs messages were returned. Review https://app.sendgrid.com/email_logs manually.", file=sys.stderr)
    sys.exit(2)

selected = None
if message_id:
    for message in messages:
        sg_message_id = message.get("sg_message_id", "")
        if message_id_match(message_id, sg_message_id):
            selected = message
            break
    if selected is None:
        print("No matching sg_message_id was found from POST /v3/logs. Review https://app.sendgrid.com/email_logs manually.", file=sys.stderr)
        sys.exit(2)
else:
    selected = messages[0]

sg_message_id = selected.get("sg_message_id")
if not sg_message_id:
    print("Selected Email Logs message did not include sg_message_id.", file=sys.stderr)
    sys.exit(2)

print(sg_message_id)
PY
  )"

  if [[ -z "$SG_MESSAGE_ID" ]]; then
    echo "Could not resolve a full sg_message_id from POST /v3/logs." >&2
    exit 1
  fi

  REQUEST_URL="$(python3 - "$REQUEST_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path
from urllib.parse import quote

metadata = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
sg_message_id = os.environ["SG_MESSAGE_ID"]
url = os.environ["API_BASE_URL"].rstrip("/") + "/v3/logs/" + quote(sg_message_id, safe="")
metadata["resolved_sg_message_id"] = sg_message_id
metadata["detail_url"] = url
Path(sys.argv[1]).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
print(url)
PY
  )"
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
  echo "SendGrid email log API request failed with HTTP $HTTP_CODE" >&2
  cat "$RESPONSE_FILE" >&2
  exit 1
fi

if [[ ! -s "$RESPONSE_FILE" ]]; then
  echo "SendGrid email log API returned an empty response body." >&2
  exit 1
fi

python3 - "$RESPONSE_FILE" "$RESULT_FILE" "$SUMMARY_ONLY" "$RESOLVE_SG_MESSAGE_ID" "$REQUEST_FILE" "$SEARCH_RESPONSE_FILE" <<'PY'
import json
import sys
from pathlib import Path

response_path = Path(sys.argv[1])
result_path = Path(sys.argv[2])
summary_only = sys.argv[3] == "true"
resolved_by_search = sys.argv[4] == "true"
request_path = Path(sys.argv[5])
search_response_path = Path(sys.argv[6])

try:
    parsed = json.loads(response_path.read_text(encoding="utf-8"))
except json.JSONDecodeError as exc:
    print(f"SendGrid email log API returned non-JSON response: {exc}", file=sys.stderr)
    sys.exit(1)

events = []


def collect_events(value):
    if isinstance(value, dict):
        event_name = value.get("event_name") or value.get("event") or value.get("type")
        if isinstance(event_name, str):
            events.append(value)
        for child in value.values():
            collect_events(child)
    elif isinstance(value, list):
        for child in value:
            collect_events(child)


collect_events(parsed)
event_names = []
for event in events:
    name = event.get("event_name") or event.get("event") or event.get("type")
    if isinstance(name, str):
        normalized = name.strip().lower()
        if normalized:
            event_names.append(normalized)

counts = {}
for name in event_names:
    counts[name] = counts.get(name, 0) + 1


def has_any(*names):
    return any(counts.get(name, 0) > 0 for name in names)


summary = {
    "event_count": len(event_names),
    "event_counts": counts,
    "delivered": has_any("delivered", "delivery"),
    "opened": has_any("open", "opened"),
    "clicked": has_any("click", "clicked"),
    "bounced": has_any("bounce", "bounced"),
    "deferred": has_any("deferred"),
    "dropped": has_any("dropped", "drop"),
    "processed": has_any("processed", "process"),
    "spam_reported": has_any("spamreport", "spam_report", "spam report"),
    "unsubscribed": has_any("unsubscribe", "unsubscribed", "group_unsubscribe", "group unsubscribe"),
}

if isinstance(parsed, dict):
    message = parsed.get("message") if isinstance(parsed.get("message"), dict) else parsed
    for key in ("sg_message_id", "msg_id", "message_id", "to_email", "from_email", "subject", "status"):
        value = message.get(key)
        if value is not None:
            summary[key] = value

if resolved_by_search:
    try:
        metadata = json.loads(request_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        metadata = {}
    if metadata.get("resolved_sg_message_id"):
        summary["resolved_sg_message_id"] = metadata["resolved_sg_message_id"]

if summary_only:
    output = summary
elif isinstance(parsed, dict):
    parsed["event_summary"] = summary
    if resolved_by_search:
        resolution = {}
        try:
            metadata = json.loads(request_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            metadata = {}
        for key in ("resolved_sg_message_id", "search_payload", "mail_send_message_id_filter"):
            if key in metadata:
                resolution[key] = metadata[key]
        try:
            search_response = json.loads(search_response_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            search_response = {}
        if isinstance(search_response, dict):
            messages = search_response.get("messages")
            if isinstance(messages, list):
                resolution["search_message_count"] = len(messages)
        if resolution:
            parsed["log_resolution"] = resolution
    output = parsed
else:
    output = {
        "data": parsed,
        "event_summary": summary,
    }

result_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  cp "$RESULT_FILE" "$OUTPUT_PATH"
  echo "Saved SendGrid email log JSON to $OUTPUT_PATH" >&2
fi

cat "$RESULT_FILE"
