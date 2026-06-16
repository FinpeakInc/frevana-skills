#!/usr/bin/env bash

set -euo pipefail

CONNECT_TIMEOUT="10"
MAX_TIME="600"
CONFIG_DOC_URL="https://wenjun.gitbook.io/wenjun-docs/sendgrid-integration"

usage() {
  cat <<'EOF'
Usage:
  send_email.sh --from "verified@example.com" --to "recipient@example.com" [--subject "Subject"] (--text "Body" | --html "<p>Body</p>" | --template-id "d-...") [options]

By default this script prints the SendGrid Mail Send JSON payload and does not send.
Pass --send to call the SendGrid API.

Options:
  --from                         Sender email, optionally "Name <email@example.com>"
  --to                           Recipient email, repeatable or comma-separated
  --cc                           CC email, repeatable or comma-separated
  --bcc                          BCC email, repeatable or comma-separated
  --subject                      Email subject
  --text                         Plain text content
  --text-file                    UTF-8 file containing plain text content
  --html                         HTML content
  --html-file                    UTF-8 file containing HTML content
  --template-id                  SendGrid dynamic template ID
  --dynamic-template-data-json   JSON object for dynamic_template_data
  --reply-to                     Reply-to email, optionally "Name <email@example.com>"
  --attachment                   File path to attach, repeatable
  --business-id                  Optional business lookup ID. Auto-generated when omitted
  --category                     Category string, repeatable
  --custom-arg                   Custom arg as KEY=VALUE, repeatable
  --batch-id                     Optional SendGrid batch_id for scheduled/cancellable sends
  --send-at                      Unix timestamp in seconds for scheduled sends
  --sandbox                      Enable SendGrid sandbox mode; validates without delivery
  --private-recipients           Put each --to recipient in a separate personalization
  --region                       SendGrid API region: global or eu. Default global
  --api-key                      Optional SendGrid API key override for this run
  --save-api-key                 Save --api-key for future runs
  --configure-api-key            Prompt for a SendGrid API key and save it for future runs
  --clear-api-key                Remove the locally saved SendGrid API key
  --output                       Optional path for saving dry-run JSON or send metadata JSON
  --send                         Actually call POST /v3/mail/send
  -h, --help                     Show this help message

Environment:
  SENDGRID_API_KEY               SendGrid API key used before the locally saved key
  SENDGRID_SEND_EMAIL_CONFIG_DIR Optional config directory override

Setup guide:
  https://wenjun.gitbook.io/wenjun-docs/sendgrid-integration
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

FROM=""
TO_VALUES=()
CC_VALUES=()
BCC_VALUES=()
SUBJECT=""
TEXT=""
TEXT_FILE=""
HTML=""
HTML_FILE=""
TEMPLATE_ID=""
DYNAMIC_TEMPLATE_DATA_JSON=""
REPLY_TO=""
ATTACHMENTS=()
CATEGORIES=()
CUSTOM_ARGS=()
BUSINESS_ID=""
BATCH_ID=""
SEND_AT=""
SANDBOX="false"
PRIVATE_RECIPIENTS="false"
REGION="global"
API_KEY_OVERRIDE=""
SAVE_API_KEY="false"
CONFIGURE_API_KEY="false"
CLEAR_API_KEY="false"
OUTPUT_PATH=""
DO_SEND="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from)
      FROM="${2:-}"
      shift 2
      ;;
    --to)
      TO_VALUES+=("${2:-}")
      shift 2
      ;;
    --cc)
      CC_VALUES+=("${2:-}")
      shift 2
      ;;
    --bcc)
      BCC_VALUES+=("${2:-}")
      shift 2
      ;;
    --subject)
      SUBJECT="${2:-}"
      shift 2
      ;;
    --text)
      TEXT="${2:-}"
      shift 2
      ;;
    --text-file)
      TEXT_FILE="${2:-}"
      shift 2
      ;;
    --html)
      HTML="${2:-}"
      shift 2
      ;;
    --html-file)
      HTML_FILE="${2:-}"
      shift 2
      ;;
    --template-id)
      TEMPLATE_ID="${2:-}"
      shift 2
      ;;
    --dynamic-template-data-json)
      DYNAMIC_TEMPLATE_DATA_JSON="${2:-}"
      shift 2
      ;;
    --reply-to)
      REPLY_TO="${2:-}"
      shift 2
      ;;
    --attachment)
      ATTACHMENTS+=("${2:-}")
      shift 2
      ;;
    --business-id)
      BUSINESS_ID="${2:-}"
      shift 2
      ;;
    --category)
      CATEGORIES+=("${2:-}")
      shift 2
      ;;
    --custom-arg)
      CUSTOM_ARGS+=("${2:-}")
      shift 2
      ;;
    --batch-id)
      BATCH_ID="${2:-}"
      shift 2
      ;;
    --send-at)
      SEND_AT="${2:-}"
      shift 2
      ;;
    --sandbox)
      SANDBOX="true"
      shift
      ;;
    --private-recipients)
      PRIVATE_RECIPIENTS="true"
      shift
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
    --send)
      DO_SEND="true"
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

HAS_SEND_OPERATION="false"
if [[ -n "$FROM" || "${#TO_VALUES[@]}" -gt 0 || -n "$SUBJECT" || -n "$TEXT" || -n "$TEXT_FILE" || -n "$HTML" || -n "$HTML_FILE" || -n "$TEMPLATE_ID" || -n "$OUTPUT_PATH" || "$DO_SEND" == "true" ]]; then
  HAS_SEND_OPERATION="true"
fi

if [[ "$CLEAR_API_KEY" == "true" ]]; then
  clear_saved_api_key
  echo "Removed locally saved SendGrid API key from $(api_key_file)" >&2
  if [[ "$HAS_SEND_OPERATION" != "true" && "$CONFIGURE_API_KEY" != "true" && -z "$API_KEY_OVERRIDE" ]]; then
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
  if [[ "$HAS_SEND_OPERATION" != "true" ]]; then
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
  if [[ "$HAS_SEND_OPERATION" != "true" ]]; then
    exit 0
  fi
fi

if [[ -z "$FROM" ]]; then
  echo "Missing required argument: --from" >&2
  echo "This address should be a verified sender in your Twilio SendGrid account." >&2
  exit 1
fi

if [[ "${#TO_VALUES[@]}" -eq 0 ]]; then
  echo "Missing required argument: --to" >&2
  exit 1
fi

if [[ -n "$TEXT" && -n "$TEXT_FILE" ]]; then
  echo "--text and --text-file are mutually exclusive." >&2
  exit 1
fi

if [[ -n "$HTML" && -n "$HTML_FILE" ]]; then
  echo "--html and --html-file are mutually exclusive." >&2
  exit 1
fi

if [[ -n "$TEXT_FILE" ]]; then
  if [[ ! -f "$TEXT_FILE" ]]; then
    echo "Invalid --text-file value: file not found: $TEXT_FILE" >&2
    exit 1
  fi
  TEXT="$(cat "$TEXT_FILE")"
fi

if [[ -n "$HTML_FILE" ]]; then
  if [[ ! -f "$HTML_FILE" ]]; then
    echo "Invalid --html-file value: file not found: $HTML_FILE" >&2
    exit 1
  fi
  HTML="$(cat "$HTML_FILE")"
fi

if [[ -z "$TEMPLATE_ID" && -z "$TEXT" && -z "$HTML" ]]; then
  echo "Missing message content: provide --text, --html, or --template-id." >&2
  exit 1
fi

if [[ -z "$TEMPLATE_ID" && -z "$SUBJECT" ]]; then
  echo "Missing required argument: --subject is required unless --template-id supplies the subject." >&2
  exit 1
fi

if [[ -n "$SEND_AT" && ! "$SEND_AT" =~ ^[0-9]+$ ]]; then
  echo "Invalid --send-at value: expected Unix timestamp in seconds." >&2
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

if [[ -z "$BUSINESS_ID" ]]; then
  BUSINESS_ID="$(
    python3 - <<'PY'
from datetime import datetime, timezone
import uuid

timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
print(f"sendgrid_email_{timestamp}_{uuid.uuid4().hex}")
PY
  )"
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required but was not found in PATH." >&2
  exit 1
fi

if [[ "${#ATTACHMENTS[@]}" -gt 0 ]]; then
  for attachment in "${ATTACHMENTS[@]}"; do
    if [[ ! -f "$attachment" ]]; then
      echo "Invalid --attachment value: file not found: $attachment" >&2
      exit 1
    fi
  done
fi

PAYLOAD_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
HEADER_FILE="$(mktemp)"
RESULT_FILE="$(mktemp)"
cleanup() {
  rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE" "$HEADER_FILE" "$RESULT_FILE"
}
trap cleanup EXIT

export FROM SUBJECT TEXT HTML TEMPLATE_ID DYNAMIC_TEMPLATE_DATA_JSON REPLY_TO BUSINESS_ID BATCH_ID SEND_AT SANDBOX PRIVATE_RECIPIENTS

PY_ARGS=("$PAYLOAD_FILE")
if [[ "${#TO_VALUES[@]}" -gt 0 ]]; then
  PY_ARGS+=("--to" "${TO_VALUES[@]}")
fi
if [[ "${#CC_VALUES[@]}" -gt 0 ]]; then
  PY_ARGS+=("--cc" "${CC_VALUES[@]}")
fi
if [[ "${#BCC_VALUES[@]}" -gt 0 ]]; then
  PY_ARGS+=("--bcc" "${BCC_VALUES[@]}")
fi
if [[ "${#ATTACHMENTS[@]}" -gt 0 ]]; then
  PY_ARGS+=("--attachment" "${ATTACHMENTS[@]}")
fi
if [[ "${#CATEGORIES[@]}" -gt 0 ]]; then
  PY_ARGS+=("--category" "${CATEGORIES[@]}")
fi
if [[ "${#CUSTOM_ARGS[@]}" -gt 0 ]]; then
  PY_ARGS+=("--custom-arg" "${CUSTOM_ARGS[@]}")
fi

python3 - "${PY_ARGS[@]}" <<'PY'
import argparse
import base64
import json
import mimetypes
import os
import re
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("payload_path")
parser.add_argument("--to", nargs="*", default=[])
parser.add_argument("--cc", nargs="*", default=[])
parser.add_argument("--bcc", nargs="*", default=[])
parser.add_argument("--attachment", nargs="*", default=[])
parser.add_argument("--category", nargs="*", default=[])
parser.add_argument("--custom-arg", nargs="*", default=[])
args = parser.parse_args()

EMAIL_RE = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")


def split_values(values):
    result = []
    for value in values:
        for part in value.split(","):
            item = part.strip()
            if item:
                result.append(item)
    return result


def email_object(value):
    value = value.strip()
    match = re.match(r"^(?P<name>.+?)\s*<(?P<email>[^<>]+)>$", value)
    if match:
        email = match.group("email").strip()
        name = match.group("name").strip().strip('"')
    else:
        email = value
        name = ""

    if not EMAIL_RE.match(email):
        print(f"Invalid email address: {value}", file=sys.stderr)
        sys.exit(1)

    obj = {"email": email}
    if name:
        obj["name"] = name
    return obj


to = [email_object(value) for value in split_values(args.to)]
cc = [email_object(value) for value in split_values(args.cc)]
bcc = [email_object(value) for value in split_values(args.bcc)]

if not to:
    print("At least one --to recipient is required.", file=sys.stderr)
    sys.exit(1)

from_obj = email_object(os.environ["FROM"])
payload = {
    "from": from_obj,
}

subject = os.environ.get("SUBJECT", "")
if subject:
    payload["subject"] = subject

template_id = os.environ.get("TEMPLATE_ID", "")
if template_id:
    payload["template_id"] = template_id

personalization_base = {}
if cc:
    personalization_base["cc"] = cc
if bcc:
    personalization_base["bcc"] = bcc

dynamic_template_data_json = os.environ.get("DYNAMIC_TEMPLATE_DATA_JSON", "")
if dynamic_template_data_json:
    try:
        dynamic_template_data = json.loads(dynamic_template_data_json)
    except json.JSONDecodeError as exc:
        print(f"Invalid --dynamic-template-data-json: {exc}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(dynamic_template_data, dict):
        print("--dynamic-template-data-json must be a JSON object.", file=sys.stderr)
        sys.exit(1)
    personalization_base["dynamic_template_data"] = dynamic_template_data

if os.environ.get("PRIVATE_RECIPIENTS") == "true":
    payload["personalizations"] = [
        {"to": [recipient], **personalization_base}
        for recipient in to
    ]
else:
    payload["personalizations"] = [{"to": to, **personalization_base}]

reply_to = os.environ.get("REPLY_TO", "")
if reply_to:
    payload["reply_to"] = email_object(reply_to)

content = []
text = os.environ.get("TEXT", "")
html = os.environ.get("HTML", "")
if text:
    content.append({"type": "text/plain", "value": text})
if html:
    content.append({"type": "text/html", "value": html})
if content:
    payload["content"] = content

attachments = []
for attachment_path in args.attachment:
    path = Path(attachment_path)
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    attachments.append({
        "content": base64.b64encode(path.read_bytes()).decode("ascii"),
        "filename": path.name,
        "type": content_type,
        "disposition": "attachment",
    })
if attachments:
    payload["attachments"] = attachments

categories = split_values(args.category)
if categories:
    payload["categories"] = categories

custom_args = {}
for item in args.custom_arg:
    if "=" not in item:
        print(f"Invalid --custom-arg value: {item}. Expected KEY=VALUE.", file=sys.stderr)
        sys.exit(1)
    key, value = item.split("=", 1)
    key = key.strip()
    if not key:
        print(f"Invalid --custom-arg value: {item}. Key must not be empty.", file=sys.stderr)
        sys.exit(1)
    if key == "business_id":
        print("Do not pass --custom-arg business_id=...; use --business-id instead.", file=sys.stderr)
        sys.exit(1)
    custom_args[key] = value

business_id = os.environ.get("BUSINESS_ID", "")
if business_id:
    custom_args["business_id"] = business_id
payload["custom_args"] = custom_args

batch_id = os.environ.get("BATCH_ID", "")
if batch_id:
    payload["batch_id"] = batch_id

send_at = os.environ.get("SEND_AT", "")
if send_at:
    payload["send_at"] = int(send_at)

if os.environ.get("SANDBOX") == "true":
    payload["mail_settings"] = {"sandbox_mode": {"enable": True}}

Path(args.payload_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
PY

if [[ "$DO_SEND" != "true" ]]; then
  if [[ -n "$OUTPUT_PATH" ]]; then
    mkdir -p "$(dirname "$OUTPUT_PATH")"
    cp "$PAYLOAD_FILE" "$OUTPUT_PATH"
    echo "Saved SendGrid dry-run payload to $OUTPUT_PATH" >&2
  fi
  echo "Dry run only. Pass --send to call SendGrid." >&2
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
    -D "$HEADER_FILE" \
    -o "$RESPONSE_FILE" \
    -w "%{http_code}" \
    -X POST "$API_BASE_URL/v3/mail/send" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $API_KEY" \
    --data @"$PAYLOAD_FILE"
)"

python3 - "$HTTP_CODE" "$HEADER_FILE" "$RESPONSE_FILE" "$RESULT_FILE" "$PAYLOAD_FILE" <<'PY'
from datetime import datetime, timezone
import json
import os
import sys
from pathlib import Path

http_code = int(sys.argv[1])
header_path = Path(sys.argv[2])
response_path = Path(sys.argv[3])
result_path = Path(sys.argv[4])
payload_path = Path(sys.argv[5])

headers = {}
for line in header_path.read_text(encoding="utf-8", errors="replace").splitlines():
    if ":" in line:
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()

raw_body = response_path.read_text(encoding="utf-8", errors="replace")
body = None
if raw_body.strip():
    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError:
        body = raw_body

result = {
    "status_code": http_code,
    "queued": http_code == 202,
    "sandbox_validated": http_code == 200,
    "message_id": headers.get("x-message-id"),
}
try:
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    business_id = payload.get("custom_args", {}).get("business_id")
except json.JSONDecodeError:
    payload = {}
    business_id = None
if business_id:
    result["business_id"] = business_id
if body is not None:
    result["body"] = body

message_id = result.get("message_id")
if 200 <= http_code < 300 and message_id:
    sent_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    subject = payload.get("subject", "")
    template_id = payload.get("template_id", "")
    to_emails = []
    for personalization in payload.get("personalizations", []):
        for recipient in personalization.get("to", []):
            email = recipient.get("email")
            if email and email not in to_emails:
                to_emails.append(email)

    if to_emails:
        example_to = to_emails[0]
        query_params = {
            "to": example_to,
            "sent_at": sent_at,
            "message_id": message_id,
        }
        prompt_items = [
            f"to={example_to}",
            f"sent_at={sent_at}",
            f"message_id={message_id}",
        ]
        if subject and not template_id:
            query_params["subject"] = subject
            prompt_items.append(f"subject={subject}")
        result["status_query"] = {
            "available": True,
            "example_to": example_to,
            "sent_at": sent_at,
            "query_params": query_params,
            "manual_review_url": "https://app.sendgrid.com/email_logs",
            "note": "Delivery is asynchronous. Ask the agent to query status after a short delay, changing the recipient if you want to check another recipient.",
            "prompt_example": "Check the status of this SendGrid email",
        }
        if template_id:
            result["status_query"]["template_subject_ignored"] = True
            result["status_query"]["note"] += " This was a template send, so subject is omitted because the template may override the request subject."

result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
PY

if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "SendGrid Mail Send API request failed with HTTP $HTTP_CODE" >&2
  cat "$RESULT_FILE" >&2
  exit 1
fi

if [[ "$HTTP_CODE" -ne 202 && "$SANDBOX" != "true" ]]; then
  echo "SendGrid returned HTTP $HTTP_CODE. Non-sandbox sends usually return 202 Accepted when queued." >&2
fi

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  cp "$RESULT_FILE" "$OUTPUT_PATH"
  echo "Saved SendGrid send metadata to $OUTPUT_PATH" >&2
fi

cat "$RESULT_FILE"
