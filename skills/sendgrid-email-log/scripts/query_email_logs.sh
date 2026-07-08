#!/usr/bin/env bash

set -euo pipefail

CONNECT_TIMEOUT="10"
MAX_TIME="600"
CONFIG_DOC_URL="https://frevana.gitbook.io/frevana-docs/email-integrations/sendgrid-integration"

usage() {
  cat <<'EOF'
Usage:
  query_email_logs.sh (--to EMAIL --sent-at ISO_TIME --message-id ID [--subject SUBJECT] | --query "query") [--limit 10] [options]

Query Twilio SendGrid Email Logs with POST /v3/logs.

Options:
  --query             Raw SendGrid Email Logs query string. Overrides generated filters
  --status            Status filter, repeatable. Example: delivered, processed, bounced
  --to                Optional recipient email filter
  --sent-at           Optional sent/queued time used as lower bound for sg_message_id_created_at
  --sent-at-lookback-seconds Seconds subtracted from --sent-at before querying. Default 5
  --message-id        Optional x-message-id from Mail Send response for fuzzy sg_message_id matching
  --subject           Optional exact subject filter to narrow Email Logs results
  --start-time        Optional lower bound ISO timestamp, e.g. 2026-06-15T00:00:00Z
  --end-time          Optional upper bound ISO timestamp, e.g. 2026-06-16T00:00:00Z
  --limit             Number of messages to return, 1-1000. Default 10
  --subuser           Optional subuser ID. May be passed once
  --region            SendGrid API region: global or eu. Default global
  --api-key           Optional SendGrid API key override for this run
  --save-api-key      Save --api-key for future runs
  --configure-api-key Prompt for a SendGrid API key and save it for future runs
  --clear-api-key     Remove the locally saved SendGrid API key
  --output            Optional path for saving returned JSON
  --dry-run           Print request payload without calling SendGrid
  -h, --help          Show this help message

Environment:
  SENDGRID_API_KEY    SendGrid API key used before the locally saved key
  SENDGRID_SEND_EMAIL_CONFIG_DIR Optional config directory override

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

RAW_QUERY=""
STATUSES=()
TO_EMAIL=""
SENT_AT=""
SENT_AT_LOOKBACK_SECONDS="5"
MESSAGE_ID=""
SUBJECT=""
START_TIME=""
END_TIME=""
LIMIT="10"
SUBUSER=""
REGION="global"
API_KEY_OVERRIDE=""
SAVE_API_KEY="false"
CONFIGURE_API_KEY="false"
CLEAR_API_KEY="false"
OUTPUT_PATH=""
DRY_RUN="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --query)
      RAW_QUERY="${2:-}"
      shift 2
      ;;
    --status)
      STATUSES+=("${2:-}")
      shift 2
      ;;
    --to)
      TO_EMAIL="${2:-}"
      shift 2
      ;;
    --sent-at)
      SENT_AT="${2:-}"
      shift 2
      ;;
    --sent-at-lookback-seconds)
      SENT_AT_LOOKBACK_SECONDS="${2:-}"
      shift 2
      ;;
    --message-id)
      MESSAGE_ID="${2:-}"
      shift 2
      ;;
    --subject)
      SUBJECT="${2:-}"
      shift 2
      ;;
    --start-time)
      START_TIME="${2:-}"
      shift 2
      ;;
    --end-time)
      END_TIME="${2:-}"
      shift 2
      ;;
    --limit)
      LIMIT="${2:-}"
      shift 2
      ;;
    --subuser)
      SUBUSER="${2:-}"
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

HAS_QUERY_OPERATION="false"
if [[ -n "$RAW_QUERY" || "${#STATUSES[@]}" -gt 0 || -n "$TO_EMAIL" || -n "$SUBJECT" || -n "$START_TIME" || -n "$END_TIME" || -n "$SENT_AT" || -n "$MESSAGE_ID" || -n "$OUTPUT_PATH" || "$DRY_RUN" == "true" ]]; then
  HAS_QUERY_OPERATION="true"
fi

if [[ "$CLEAR_API_KEY" == "true" ]]; then
  clear_saved_api_key
  echo "Removed locally saved SendGrid API key from $(api_key_file)" >&2
  if [[ "$HAS_QUERY_OPERATION" != "true" && "$CONFIGURE_API_KEY" != "true" && -z "$API_KEY_OVERRIDE" ]]; then
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
  if [[ "$HAS_QUERY_OPERATION" != "true" ]]; then
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
  if [[ "$HAS_QUERY_OPERATION" != "true" ]]; then
    exit 0
  fi
fi

if [[ -z "$RAW_QUERY" && "${#STATUSES[@]}" -eq 0 && -z "$TO_EMAIL" && -z "$SUBJECT" && -z "$START_TIME" && -z "$END_TIME" && -z "$SENT_AT" && -z "$MESSAGE_ID" ]]; then
  echo "Missing query criteria: pass --to with --sent-at and --message-id; --query; or another supported Email Logs filter." >&2
  exit 1
fi

if [[ -n "$MESSAGE_ID" && ( -z "$TO_EMAIL" || -z "$SENT_AT" ) ]]; then
  echo "--message-id fuzzy matching requires --to and --sent-at so Email Logs can be narrowed before filtering." >&2
  exit 1
fi

if [[ -n "$SENT_AT" && -z "$TO_EMAIL" ]]; then
  echo "--sent-at requires --to so Email Logs can be narrowed safely." >&2
  exit 1
fi

if [[ ! "$LIMIT" =~ ^[0-9]+$ ]] || (( LIMIT < 1 || LIMIT > 1000 )); then
  echo "Invalid --limit value: $LIMIT. Expected integer 1-1000." >&2
  exit 1
fi

if [[ ! "$SENT_AT_LOOKBACK_SECONDS" =~ ^[0-9]+$ ]] || (( SENT_AT_LOOKBACK_SECONDS > 300 )); then
  echo "Invalid --sent-at-lookback-seconds value: $SENT_AT_LOOKBACK_SECONDS. Expected integer 0-300." >&2
  exit 1
fi

if [[ -n "$SUBUSER" && ! "$SUBUSER" =~ ^[0-9]+$ ]]; then
  echo "Invalid --subuser value: $SUBUSER. Expected numeric subuser ID." >&2
  exit 1
fi

if [[ "$REGION" != "global" && "$REGION" != "eu" ]]; then
  echo "Invalid --region value: $REGION. Allowed values: global, eu" >&2
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

PAYLOAD_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
RESULT_FILE="$(mktemp)"
cleanup() {
  rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE" "$RESULT_FILE"
}
trap cleanup EXIT

export RAW_QUERY TO_EMAIL SENT_AT SENT_AT_LOOKBACK_SECONDS MESSAGE_ID SUBJECT START_TIME END_TIME LIMIT SUBUSER

PY_ARGS=("$PAYLOAD_FILE")
if [[ "${#STATUSES[@]}" -gt 0 ]]; then
  PY_ARGS+=("--status" "${STATUSES[@]}")
fi

python3 - "${PY_ARGS[@]}" <<'PY'
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("payload_path")
parser.add_argument("--status", nargs="*", default=[])
args = parser.parse_args()


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


conditions = []
raw_query = os.environ.get("RAW_QUERY", "")

if raw_query:
    query = raw_query
else:
    statuses = []
    for status in args.status:
        for part in status.split(","):
            item = part.strip()
            if item:
                statuses.append(item)
    if statuses:
        values = ", ".join(sql_quote(status) for status in statuses)
        conditions.append(f"status IN ({values})")

    to_email = os.environ.get("TO_EMAIL", "")
    if to_email:
        conditions.append(f"to_email = {sql_quote(to_email)}")

    sent_at = os.environ.get("SENT_AT", "")
    if sent_at:
        parsed_sent_at = parse_iso_datetime(sent_at)
        lookback_seconds = int(os.environ.get("SENT_AT_LOOKBACK_SECONDS", "5"))
        query_start = parsed_sent_at - timedelta(seconds=lookback_seconds)
        conditions.append(f"sg_message_id_created_at >= {timestamp_literal(iso_z(query_start))}")

    subject = os.environ.get("SUBJECT", "")
    if subject:
        conditions.append(f"subject = {sql_quote(subject)}")

    start_time = os.environ.get("START_TIME", "")
    if start_time:
        conditions.append(f"sg_message_id_created_at >= {timestamp_literal(start_time)}")

    end_time = os.environ.get("END_TIME", "")
    if end_time:
        conditions.append(f"sg_message_id_created_at <= {timestamp_literal(end_time)}")

    query = " AND ".join(conditions)

payload = {
    "query": query,
    "limit": int(os.environ["LIMIT"]),
}

subuser = os.environ.get("SUBUSER", "")
if subuser:
    payload["subusers"] = [subuser]

Path(args.payload_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
PY

if [[ "$DRY_RUN" == "true" ]]; then
  if [[ -n "$OUTPUT_PATH" ]]; then
    mkdir -p "$(dirname "$OUTPUT_PATH")"
    cp "$PAYLOAD_FILE" "$OUTPUT_PATH"
    echo "Saved SendGrid Email Logs dry-run payload to $OUTPUT_PATH" >&2
  fi
  cat "$PAYLOAD_FILE"
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

API_BASE_URL="https://api.sendgrid.com"
if [[ "$REGION" == "eu" ]]; then
  API_BASE_URL="https://api.eu.sendgrid.com"
fi

HTTP_CODE="$(
  curl -sS \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -o "$RESPONSE_FILE" \
    -w "%{http_code}" \
    -X POST "$API_BASE_URL/v3/logs" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $API_KEY" \
    --data @"$PAYLOAD_FILE"
)"

if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "SendGrid Email Logs API request failed with HTTP $HTTP_CODE" >&2
  cat "$RESPONSE_FILE" >&2
  exit 1
fi

if [[ ! -s "$RESPONSE_FILE" ]]; then
  echo "SendGrid Email Logs API returned an empty response body." >&2
  exit 1
fi

python3 - "$RESPONSE_FILE" "$RESULT_FILE" "$MESSAGE_ID" <<'PY'
import json
import re
import sys
from pathlib import Path

response_path = Path(sys.argv[1])
result_path = Path(sys.argv[2])
message_id = sys.argv[3]
raw = response_path.read_text(encoding="utf-8")

try:
    parsed = json.loads(raw)
except json.JSONDecodeError as exc:
    print(f"SendGrid Email Logs API returned non-JSON response: {exc}", file=sys.stderr)
    print(raw, file=sys.stderr)
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


if message_id:
    messages = parsed.get("messages", []) if isinstance(parsed, dict) else []
    matched_messages = []
    for message in messages:
        sg_message_id = message.get("sg_message_id", "")
        match_reason = message_id_match(message_id, sg_message_id)
        if match_reason:
            matched = dict(message)
            matched["_match_reason"] = match_reason
            matched_messages.append(matched)

    if isinstance(parsed, dict):
        parsed["message_id_filter"] = message_id
        parsed["matched_count"] = len(matched_messages)
        parsed["matched_messages"] = matched_messages
        if not matched_messages:
            parsed["manual_review_url"] = "https://app.sendgrid.com/email_logs"
            parsed["manual_review_message"] = "No matching sg_message_id was found. Ask the user to review SendGrid Email Logs manually."
elif isinstance(parsed, dict) and not parsed.get("messages"):
    parsed["manual_review_url"] = "https://app.sendgrid.com/email_logs"
    parsed["manual_review_message"] = "No Email Logs messages were returned. Ask the user to review SendGrid Email Logs manually."

result_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
PY

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  cp "$RESULT_FILE" "$OUTPUT_PATH"
  echo "Saved SendGrid Email Logs JSON to $OUTPUT_PATH" >&2
fi

cat "$RESULT_FILE"
