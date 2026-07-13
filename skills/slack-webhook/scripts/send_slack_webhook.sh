#!/usr/bin/env bash

set -euo pipefail

CONNECT_TIMEOUT="10"
MAX_TIME="120"

usage() {
  cat <<'EOF'
Usage:
  send_slack_webhook.sh (--text "Message" | --payload-json JSON | --payload-file PATH) [options]

By default this script prints the Slack webhook JSON payload and does not send.
Pass --send to call the Slack incoming webhook URL.

Options:
  --text                   Message text and fallback
  --text-file              UTF-8 file containing message text
  --payload-json           Complete Slack webhook payload JSON object
  --payload-file           File containing complete Slack webhook payload JSON object
  --blocks-json            Block Kit blocks JSON array
  --attachments-json       Slack attachments JSON array
  --thread-ts              Slack thread timestamp for a thread reply
  --unfurl-links           true or false
  --unfurl-media           true or false
  --webhook-url-stdin      Read Slack incoming webhook URL from stdin for this run
  --save-webhook-url       Save the resolved webhook URL for future runs
  --configure-webhook-url  Prompt for a Slack webhook URL and save it
  --clear-webhook-url      Remove the locally saved Slack webhook URL
  --output                 Optional path for saving dry-run payload or send metadata JSON
  --send                   Actually call the Slack incoming webhook
  -h, --help               Show this help message

Environment:
  SLACK_WEBHOOK_URL        Slack incoming webhook URL used before stdin and the locally saved URL
  SLACK_WEBHOOK_CONFIG_DIR Optional config directory override
EOF
}

config_dir() {
  if [[ -n "${SLACK_WEBHOOK_CONFIG_DIR:-}" ]]; then
    printf '%s\n' "$SLACK_WEBHOOK_CONFIG_DIR"
  else
    printf '%s\n' "${XDG_CONFIG_HOME:-$HOME/.config}/slack-webhook"
  fi
}

webhook_url_file() {
  printf '%s/webhook_url\n' "$(config_dir)"
}

load_saved_webhook_url() {
  local path
  path="$(webhook_url_file)"
  if [[ -r "$path" ]]; then
    IFS= read -r WEBHOOK_URL < "$path" || true
    WEBHOOK_URL="${WEBHOOK_URL//$'\r'/}"
  fi
}

save_webhook_url() {
  local url="$1"
  local dir path tmp
  dir="$(config_dir)"
  path="$(webhook_url_file)"
  mkdir -p "$dir"
  chmod 700 "$dir" 2>/dev/null || true
  tmp="$(mktemp "$dir/webhook_url.XXXXXX")"
  printf '%s\n' "$url" > "$tmp"
  chmod 600 "$tmp" 2>/dev/null || true
  mv "$tmp" "$path"
  chmod 600 "$path" 2>/dev/null || true
}

clear_saved_webhook_url() {
  local path
  path="$(webhook_url_file)"
  if [[ -f "$path" ]]; then
    rm -f "$path"
  fi
}

validate_bool() {
  local value="$1"
  local name="$2"
  case "$value" in
    true|false) ;;
    *)
      echo "$name must be true or false" >&2
      exit 1
      ;;
  esac
}

validate_webhook_url() {
  local url="$1"
  if [[ ! "$url" =~ ^https://hooks\.slack\.com/services/ ]]; then
    echo "Slack webhook URL must start with https://hooks.slack.com/services/" >&2
    exit 1
  fi
}

read_webhook_url_from_stdin() {
  if [[ -t 0 ]]; then
    echo "--webhook-url-stdin expects the webhook URL on stdin" >&2
    exit 1
  fi
  IFS= read -r WEBHOOK_URL || true
  WEBHOOK_URL="${WEBHOOK_URL//$'\r'/}"
  [[ -n "$WEBHOOK_URL" ]] || {
    echo "No Slack webhook URL received on stdin" >&2
    exit 1
  }
  validate_webhook_url "$WEBHOOK_URL"
}

prompt_for_webhook_url() {
  if [[ ! -t 0 ]]; then
    echo "No Slack webhook URL is configured. Set SLACK_WEBHOOK_URL, pipe it with --webhook-url-stdin, or use --configure-webhook-url in an interactive terminal. See https://frevana.gitbook.io/frevana-docs/connect-chat-apps/slack-webhook-integration for setup instructions." >&2
    exit 1
  fi
  read -r -s -p "Slack webhook URL: " WEBHOOK_URL
  printf '\n' >&2
  [[ -n "$WEBHOOK_URL" ]] || {
    echo "No Slack webhook URL entered" >&2
    exit 1
  }
  validate_webhook_url "$WEBHOOK_URL"
}

TEXT=""
TEXT_FILE=""
PAYLOAD_JSON=""
PAYLOAD_FILE=""
BLOCKS_JSON=""
ATTACHMENTS_JSON=""
THREAD_TS=""
UNFURL_LINKS=""
UNFURL_MEDIA=""
READ_WEBHOOK_URL_FROM_STDIN="false"
SAVE_WEBHOOK_URL="false"
CONFIGURE_WEBHOOK_URL="false"
CLEAR_WEBHOOK_URL="false"
OUTPUT_PATH=""
DO_SEND="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --text)
      TEXT="${2:-}"
      shift 2
      ;;
    --text-file)
      TEXT_FILE="${2:-}"
      shift 2
      ;;
    --payload-json)
      PAYLOAD_JSON="${2:-}"
      shift 2
      ;;
    --payload-file)
      PAYLOAD_FILE="${2:-}"
      shift 2
      ;;
    --blocks-json)
      BLOCKS_JSON="${2:-}"
      shift 2
      ;;
    --attachments-json)
      ATTACHMENTS_JSON="${2:-}"
      shift 2
      ;;
    --thread-ts)
      THREAD_TS="${2:-}"
      shift 2
      ;;
    --unfurl-links)
      UNFURL_LINKS="${2:-}"
      shift 2
      ;;
    --unfurl-media)
      UNFURL_MEDIA="${2:-}"
      shift 2
      ;;
    --webhook-url-stdin)
      READ_WEBHOOK_URL_FROM_STDIN="true"
      shift
      ;;
    --save-webhook-url)
      SAVE_WEBHOOK_URL="true"
      shift
      ;;
    --configure-webhook-url)
      CONFIGURE_WEBHOOK_URL="true"
      shift
      ;;
    --clear-webhook-url)
      CLEAR_WEBHOOK_URL="true"
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

HAS_MESSAGE_OPERATION="false"
if [[ -n "$TEXT" || -n "$TEXT_FILE" || -n "$PAYLOAD_JSON" || -n "$PAYLOAD_FILE" || -n "$BLOCKS_JSON" || -n "$ATTACHMENTS_JSON" || -n "$THREAD_TS" || -n "$OUTPUT_PATH" || "$DO_SEND" == "true" ]]; then
  HAS_MESSAGE_OPERATION="true"
fi

if [[ "$CLEAR_WEBHOOK_URL" == "true" ]]; then
  clear_saved_webhook_url
  echo "Removed locally saved Slack webhook URL from $(webhook_url_file)" >&2
  if [[ "$HAS_MESSAGE_OPERATION" != "true" && "$CONFIGURE_WEBHOOK_URL" != "true" && "$READ_WEBHOOK_URL_FROM_STDIN" != "true" && "$SAVE_WEBHOOK_URL" != "true" && -z "${SLACK_WEBHOOK_URL:-}" ]]; then
    exit 0
  fi
fi

WEBHOOK_URL=""
if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
  validate_webhook_url "$SLACK_WEBHOOK_URL"
  WEBHOOK_URL="$SLACK_WEBHOOK_URL"
elif [[ "$READ_WEBHOOK_URL_FROM_STDIN" == "true" ]]; then
  read_webhook_url_from_stdin
else
  load_saved_webhook_url
  if [[ -n "$WEBHOOK_URL" ]]; then
    validate_webhook_url "$WEBHOOK_URL"
  fi
fi

if [[ "$CONFIGURE_WEBHOOK_URL" == "true" ]]; then
  prompt_for_webhook_url
  save_webhook_url "$WEBHOOK_URL"
  echo "Saved Slack webhook URL to $(webhook_url_file)" >&2
  if [[ "$HAS_MESSAGE_OPERATION" != "true" ]]; then
    exit 0
  fi
fi

if [[ -z "$WEBHOOK_URL" && "$DO_SEND" == "true" && -t 0 ]]; then
  echo "No Slack webhook URL is configured yet. Paste one now to send this message." >&2
  prompt_for_webhook_url
  if [[ "$SAVE_WEBHOOK_URL" != "true" ]]; then
    read -r -p "Save this webhook URL for future runs? [y/N] " SAVE_REPLY
    if [[ "$SAVE_REPLY" =~ ^[Yy]$ ]]; then
      SAVE_WEBHOOK_URL="true"
    fi
  fi
fi

if [[ "$SAVE_WEBHOOK_URL" == "true" ]]; then
  if [[ -z "$WEBHOOK_URL" ]]; then
    echo "--save-webhook-url requires SLACK_WEBHOOK_URL, --webhook-url-stdin, or interactive input" >&2
    exit 1
  fi
  save_webhook_url "$WEBHOOK_URL"
  echo "Saved Slack webhook URL to $(webhook_url_file)" >&2
  if [[ "$HAS_MESSAGE_OPERATION" != "true" && "$CONFIGURE_WEBHOOK_URL" != "true" ]]; then
    exit 0
  fi
fi

save_output_copy() {
  local src="$1"
  local label="$2"
  [[ -n "$OUTPUT_PATH" ]] || return 0
  if mkdir -p "$(dirname "$OUTPUT_PATH")" && cp "$src" "$OUTPUT_PATH"; then
    echo "Saved $label to $OUTPUT_PATH" >&2
  else
    echo "Warning: failed to save $label to $OUTPUT_PATH" >&2
  fi
}

if [[ -n "$TEXT_FILE" ]]; then
  if [[ ! -r "$TEXT_FILE" ]]; then
    echo "Text file is not readable: $TEXT_FILE" >&2
    exit 1
  fi
  TEXT="$(python3 - "$TEXT_FILE" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).read_text(encoding="utf-8"), end="")
PY
)"
fi

if [[ -n "$PAYLOAD_FILE" ]]; then
  if [[ ! -r "$PAYLOAD_FILE" ]]; then
    echo "Payload file is not readable: $PAYLOAD_FILE" >&2
    exit 1
  fi
fi

if [[ -n "$UNFURL_LINKS" ]]; then
  validate_bool "$UNFURL_LINKS" "--unfurl-links"
fi

if [[ -n "$UNFURL_MEDIA" ]]; then
  validate_bool "$UNFURL_MEDIA" "--unfurl-media"
fi

if [[ -n "$PAYLOAD_JSON" && -n "$PAYLOAD_FILE" ]]; then
  echo "Use only one of --payload-json or --payload-file" >&2
  exit 1
fi

if [[ -n "$PAYLOAD_JSON" || -n "$PAYLOAD_FILE" ]]; then
  if [[ -n "$TEXT" || -n "$BLOCKS_JSON" || -n "$ATTACHMENTS_JSON" || -n "$THREAD_TS" || -n "$UNFURL_LINKS" || -n "$UNFURL_MEDIA" ]]; then
    echo "Do not combine --payload-json/--payload-file with constructed payload options" >&2
    exit 1
  fi
else
  if [[ -z "$TEXT" ]]; then
    echo "Missing required message text. Provide --text, --text-file, --payload-json, or --payload-file." >&2
    exit 1
  fi
fi

PAYLOAD_PATH="$(mktemp "${TMPDIR:-/tmp}/slack-webhook-payload.XXXXXX")"
RESPONSE_PATH=""
CURL_CONFIG_PATH=""
cleanup() {
  rm -f "$PAYLOAD_PATH"
  if [[ -n "$RESPONSE_PATH" ]]; then
    rm -f "$RESPONSE_PATH"
  fi
  if [[ -n "$CURL_CONFIG_PATH" ]]; then
    rm -f "$CURL_CONFIG_PATH"
  fi
}
trap cleanup EXIT

PAYLOAD_JSON_ENV="$PAYLOAD_JSON" \
PAYLOAD_FILE_ENV="$PAYLOAD_FILE" \
TEXT_ENV="$TEXT" \
BLOCKS_JSON_ENV="$BLOCKS_JSON" \
ATTACHMENTS_JSON_ENV="$ATTACHMENTS_JSON" \
THREAD_TS_ENV="$THREAD_TS" \
UNFURL_LINKS_ENV="$UNFURL_LINKS" \
UNFURL_MEDIA_ENV="$UNFURL_MEDIA" \
python3 - "$PAYLOAD_PATH" <<'PY'
import json
import os
import sys
from pathlib import Path

MESSAGE_BLOCK_TYPES = {
    "actions",
    "card",
    "carousel",
    "container",
    "context",
    "context_actions",
    "data_table",
    "data_visualization",
    "divider",
    "file",
    "header",
    "image",
    "markdown",
    "plan",
    "rich_text",
    "section",
    "table",
    "task_card",
    "video",
}

payload_json = os.environ.get("PAYLOAD_JSON_ENV", "")
payload_file = os.environ.get("PAYLOAD_FILE_ENV", "")

try:
    if payload_file:
        payload = json.loads(Path(payload_file).read_text(encoding="utf-8"))
    elif payload_json:
        payload = json.loads(payload_json)
    else:
        payload = {"text": os.environ.get("TEXT_ENV", "")}
        blocks_json = os.environ.get("BLOCKS_JSON_ENV", "")
        attachments_json = os.environ.get("ATTACHMENTS_JSON_ENV", "")
        thread_ts = os.environ.get("THREAD_TS_ENV", "")
        unfurl_links = os.environ.get("UNFURL_LINKS_ENV", "")
        unfurl_media = os.environ.get("UNFURL_MEDIA_ENV", "")

        if blocks_json:
            payload["blocks"] = json.loads(blocks_json)
        if attachments_json:
            payload["attachments"] = json.loads(attachments_json)
        if thread_ts:
            payload["thread_ts"] = thread_ts
        if unfurl_links:
            payload["unfurl_links"] = unfurl_links == "true"
        if unfurl_media:
            payload["unfurl_media"] = unfurl_media == "true"
except json.JSONDecodeError as exc:
    raise SystemExit(f"Invalid JSON: {exc.msg} at line {exc.lineno} column {exc.colno}")

if not isinstance(payload, dict):
    raise SystemExit("Slack webhook payload must be a JSON object")
if "text" not in payload and "blocks" not in payload and "attachments" not in payload:
    raise SystemExit("Slack webhook payload should include text, blocks, or attachments")
if "blocks" in payload and not isinstance(payload["blocks"], list):
    raise SystemExit("Slack blocks must be a JSON array")
if "attachments" in payload and not isinstance(payload["attachments"], list):
    raise SystemExit("Slack attachments must be a JSON array")
if "blocks" in payload:
    if len(payload["blocks"]) > 50:
        raise SystemExit("Slack incoming webhook messages support up to 50 blocks")
    for idx, block in enumerate(payload["blocks"]):
        if not isinstance(block, dict):
            raise SystemExit(f"Slack block at index {idx} must be a JSON object")
        block_type = block.get("type")
        if not isinstance(block_type, str) or not block_type:
            raise SystemExit(f"Slack block at index {idx} must include a string type")
        if block_type not in MESSAGE_BLOCK_TYPES:
            allowed = ", ".join(sorted(MESSAGE_BLOCK_TYPES))
            raise SystemExit(
                f"Unsupported Slack message block type '{block_type}' at index {idx}. "
                f"Supported message block types: {allowed}"
            )

Path(sys.argv[1]).write_text(
    json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY

if [[ "$DO_SEND" != "true" ]]; then
  save_output_copy "$PAYLOAD_PATH" "Slack webhook dry-run payload"
  cat "$PAYLOAD_PATH"
  exit 0
fi

if [[ -z "$WEBHOOK_URL" ]]; then
  echo "Missing Slack webhook URL. Set SLACK_WEBHOOK_URL, pipe it with --webhook-url-stdin, or save one with --save-webhook-url. See https://frevana.gitbook.io/frevana-docs/connect-chat-apps/slack-webhook-integration for setup instructions." >&2
  exit 1
fi

RESPONSE_PATH="$(mktemp "${TMPDIR:-/tmp}/slack-webhook-response.XXXXXX")"
CURL_CONFIG_PATH="$(mktemp "${TMPDIR:-/tmp}/slack-webhook-curl.XXXXXX")"
python3 - "$CURL_CONFIG_PATH" "$WEBHOOK_URL" "$PAYLOAD_PATH" <<'PY'
import json
import sys
from pathlib import Path

Path(sys.argv[1]).write_text("\n".join([
    f"url = {json.dumps(sys.argv[2])}",
    'request = "POST"',
    'header = "Content-Type: application/json"',
    f"data-binary = {json.dumps('@' + sys.argv[3])}",
]) + "\n", encoding="utf-8")
PY
HTTP_STATUS="$(
  curl -sS \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -o "$RESPONSE_PATH" \
    -w '%{http_code}' \
    --config "$CURL_CONFIG_PATH"
)"

RESPONSE_BODY="$(cat "$RESPONSE_PATH")"

METADATA_PATH="$(mktemp "${TMPDIR:-/tmp}/slack-webhook-metadata.XXXXXX")"
HTTP_STATUS_ENV="$HTTP_STATUS" \
RESPONSE_BODY_ENV="$RESPONSE_BODY" \
python3 - "$METADATA_PATH" <<'PY'
import json
import os
import sys
from pathlib import Path

body = os.environ.get("RESPONSE_BODY_ENV", "")
metadata = {
    "http_status": int(os.environ["HTTP_STATUS_ENV"]),
    "ok": os.environ["HTTP_STATUS_ENV"] == "200" and body.strip() == "ok",
    "response_body": body,
}
Path(sys.argv[1]).write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

save_output_copy "$METADATA_PATH" "Slack webhook send metadata"

cat "$METADATA_PATH"
rm -f "$METADATA_PATH"

if [[ "$HTTP_STATUS" != "200" || "$RESPONSE_BODY" != "ok" ]]; then
  exit 1
fi
