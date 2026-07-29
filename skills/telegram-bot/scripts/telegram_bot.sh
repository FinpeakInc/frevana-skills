#!/usr/bin/env bash

set -euo pipefail

CONNECT_TIMEOUT="10"
MAX_TIME="180"
API_BASE="https://api.telegram.org"

usage() {
  cat <<'EOF'
Usage:
  telegram_bot.sh --action ACTION [options]

Read actions call Telegram immediately by default. Write actions dry-run by default.
Pass --execute to perform write actions.

Actions:
  getMe getMyCommands setMyCommands sendMessage sendPhoto sendDocument sendLocation
  getUpdates setWebhook getWebhookInfo deleteWebhook getChat getChatMemberCount
  getChatAdministrators banChatMember unbanChatMember editMessageText deleteMessage
  pinChatMessage forwardMessage answerCallbackQuery raw

Options:
  --action                  Telegram action/method alias
  --method                  Telegram method name for --action raw
  --payload-json            Complete payload JSON object
  --payload-file            File containing complete payload JSON object
  --chat-id                 Telegram chat ID or @channelname
  --text                    Message text
  --text-file               UTF-8 file containing message text
  --parse-mode              HTML, Markdown, or MarkdownV2
  --reply-markup-json       reply_markup JSON object
  --commands-json           Bot commands JSON array
  --photo                   Photo URL, file_id, or local file path
  --document                Document URL, file_id, or local file path
  --caption                 Media caption
  --latitude                Latitude for sendLocation
  --longitude               Longitude for sendLocation
  --offset                  getUpdates offset
  --timeout                 getUpdates timeout
  --limit                   getUpdates limit
  --url                     Webhook URL
  --allowed-updates-json    allowed_updates JSON array
  --message-id              Telegram message_id
  --user-id                 Telegram user_id
  --from-chat-id            Source chat for forwardMessage
  --callback-query-id       Callback query ID
  --show-alert              true or false for answerCallbackQuery
  --bot-token               Telegram bot token override for this run
  --save-bot-token          Save --bot-token for future runs
  --configure-bot-token     Prompt for a Telegram bot token and save it
  --clear-bot-token         Remove the locally saved Telegram bot token
  --output                  Optional path for saving dry-run metadata or response JSON
  --dry-run                 Preview request instead of calling Telegram
  --execute                 Execute write actions
  -h, --help                Show this help message

Environment:
  TELEGRAM_BOT_TOKEN        Telegram bot token used before the locally saved token
  TELEGRAM_BOT_CONFIG_DIR   Optional config directory override
EOF
}

config_dir() {
  if [[ -n "${TELEGRAM_BOT_CONFIG_DIR:-}" ]]; then
    printf '%s\n' "$TELEGRAM_BOT_CONFIG_DIR"
  else
    printf '%s\n' "${XDG_CONFIG_HOME:-$HOME/.config}/telegram-bot"
  fi
}

bot_token_file() {
  printf '%s/bot_token\n' "$(config_dir)"
}

load_saved_bot_token() {
  local path
  path="$(bot_token_file)"
  if [[ -r "$path" ]]; then
    IFS= read -r BOT_TOKEN < "$path" || true
    BOT_TOKEN="${BOT_TOKEN//$'\r'/}"
  fi
}

save_bot_token() {
  local token="$1"
  local dir path tmp
  dir="$(config_dir)"
  path="$(bot_token_file)"
  mkdir -p "$dir"
  chmod 700 "$dir" 2>/dev/null || true
  tmp="$(mktemp "$dir/bot_token.XXXXXX")"
  printf '%s\n' "$token" > "$tmp"
  chmod 600 "$tmp" 2>/dev/null || true
  mv "$tmp" "$path"
  chmod 600 "$path" 2>/dev/null || true
}

clear_saved_bot_token() {
  local path
  path="$(bot_token_file)"
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

validate_token() {
  local token="$1"
  if [[ ! "$token" =~ ^[0-9]+:[A-Za-z0-9_-]+$ ]]; then
    echo "Telegram bot token does not look like a BotFather token" >&2
    exit 1
  fi
}

ACTION=""
METHOD=""
PAYLOAD_JSON=""
PAYLOAD_FILE=""
CHAT_ID=""
TEXT=""
TEXT_FILE=""
PARSE_MODE=""
REPLY_MARKUP_JSON=""
COMMANDS_JSON=""
PHOTO=""
DOCUMENT=""
CAPTION=""
LATITUDE=""
LONGITUDE=""
OFFSET=""
TIMEOUT_VALUE=""
LIMIT_VALUE=""
WEBHOOK_URL=""
ALLOWED_UPDATES_JSON=""
MESSAGE_ID=""
USER_ID=""
FROM_CHAT_ID=""
CALLBACK_QUERY_ID=""
SHOW_ALERT=""
BOT_TOKEN_OVERRIDE=""
SAVE_BOT_TOKEN="false"
CONFIGURE_BOT_TOKEN="false"
CLEAR_BOT_TOKEN="false"
OUTPUT_PATH=""
DRY_RUN="false"
EXECUTE="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --action) ACTION="${2:-}"; shift 2 ;;
    --method) METHOD="${2:-}"; shift 2 ;;
    --payload-json) PAYLOAD_JSON="${2:-}"; shift 2 ;;
    --payload-file) PAYLOAD_FILE="${2:-}"; shift 2 ;;
    --chat-id) CHAT_ID="${2:-}"; shift 2 ;;
    --text) TEXT="${2:-}"; shift 2 ;;
    --text-file) TEXT_FILE="${2:-}"; shift 2 ;;
    --parse-mode) PARSE_MODE="${2:-}"; shift 2 ;;
    --reply-markup-json) REPLY_MARKUP_JSON="${2:-}"; shift 2 ;;
    --commands-json) COMMANDS_JSON="${2:-}"; shift 2 ;;
    --photo) PHOTO="${2:-}"; shift 2 ;;
    --document) DOCUMENT="${2:-}"; shift 2 ;;
    --caption) CAPTION="${2:-}"; shift 2 ;;
    --latitude) LATITUDE="${2:-}"; shift 2 ;;
    --longitude) LONGITUDE="${2:-}"; shift 2 ;;
    --offset) OFFSET="${2:-}"; shift 2 ;;
    --timeout) TIMEOUT_VALUE="${2:-}"; shift 2 ;;
    --limit) LIMIT_VALUE="${2:-}"; shift 2 ;;
    --url) WEBHOOK_URL="${2:-}"; shift 2 ;;
    --allowed-updates-json) ALLOWED_UPDATES_JSON="${2:-}"; shift 2 ;;
    --message-id) MESSAGE_ID="${2:-}"; shift 2 ;;
    --user-id) USER_ID="${2:-}"; shift 2 ;;
    --from-chat-id) FROM_CHAT_ID="${2:-}"; shift 2 ;;
    --callback-query-id) CALLBACK_QUERY_ID="${2:-}"; shift 2 ;;
    --show-alert) SHOW_ALERT="${2:-}"; shift 2 ;;
    --bot-token) BOT_TOKEN_OVERRIDE="${2:-}"; shift 2 ;;
    --save-bot-token) SAVE_BOT_TOKEN="true"; shift ;;
    --configure-bot-token) CONFIGURE_BOT_TOKEN="true"; shift ;;
    --clear-bot-token) CLEAR_BOT_TOKEN="true"; shift ;;
    --output) OUTPUT_PATH="${2:-}"; shift 2 ;;
    --dry-run) DRY_RUN="true"; shift ;;
    --execute) EXECUTE="true"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done

HAS_OPERATION="false"
if [[ -n "$ACTION" || -n "$METHOD" || -n "$PAYLOAD_JSON" || -n "$PAYLOAD_FILE" || -n "$OUTPUT_PATH" || "$DRY_RUN" == "true" || "$EXECUTE" == "true" ]]; then
  HAS_OPERATION="true"
fi

if [[ "$CLEAR_BOT_TOKEN" == "true" ]]; then
  clear_saved_bot_token
  echo "Removed locally saved Telegram bot token from $(bot_token_file)" >&2
  if [[ "$HAS_OPERATION" != "true" && "$CONFIGURE_BOT_TOKEN" != "true" && -z "$BOT_TOKEN_OVERRIDE" ]]; then
    exit 0
  fi
fi

BOT_TOKEN=""
if [[ -n "$BOT_TOKEN_OVERRIDE" ]]; then
  validate_token "$BOT_TOKEN_OVERRIDE"
  BOT_TOKEN="$BOT_TOKEN_OVERRIDE"
elif [[ -n "${TELEGRAM_BOT_TOKEN:-}" ]]; then
  validate_token "$TELEGRAM_BOT_TOKEN"
  BOT_TOKEN="$TELEGRAM_BOT_TOKEN"
else
  load_saved_bot_token
  if [[ -n "$BOT_TOKEN" ]]; then
    validate_token "$BOT_TOKEN"
  fi
fi

if [[ "$CONFIGURE_BOT_TOKEN" == "true" ]]; then
  if [[ ! -t 0 ]]; then
    echo "--configure-bot-token requires an interactive terminal. Use --bot-token with --save-bot-token instead." >&2
    exit 1
  fi
  read -r -s -p "Telegram bot token: " BOT_TOKEN
  printf '\n' >&2
  validate_token "$BOT_TOKEN"
  save_bot_token "$BOT_TOKEN"
  echo "Saved Telegram bot token to $(bot_token_file)" >&2
  if [[ "$HAS_OPERATION" != "true" ]]; then
    exit 0
  fi
fi

if [[ "$SAVE_BOT_TOKEN" == "true" ]]; then
  if [[ -z "$BOT_TOKEN_OVERRIDE" ]]; then
    echo "--save-bot-token requires --bot-token so the saved value is explicit" >&2
    exit 1
  fi
  save_bot_token "$BOT_TOKEN_OVERRIDE"
  echo "Saved Telegram bot token to $(bot_token_file)" >&2
fi

if [[ -z "$ACTION" ]]; then
  echo "Missing required --action" >&2
  usage >&2
  exit 1
fi

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

if [[ -n "$PAYLOAD_FILE" && ! -r "$PAYLOAD_FILE" ]]; then
  echo "Payload file is not readable: $PAYLOAD_FILE" >&2
  exit 1
fi

if [[ -n "$SHOW_ALERT" ]]; then
  validate_bool "$SHOW_ALERT" "--show-alert"
fi

PAYLOAD_PATH="$(mktemp "${TMPDIR:-/tmp}/telegram-bot-payload.XXXXXX")"
META_PATH="$(mktemp "${TMPDIR:-/tmp}/telegram-bot-meta.XXXXXX")"
RESPONSE_PATH=""
cleanup() {
  rm -f "$PAYLOAD_PATH" "$META_PATH"
  if [[ -n "$RESPONSE_PATH" ]]; then
    rm -f "$RESPONSE_PATH"
  fi
}
trap cleanup EXIT

ACTION_ENV="$ACTION" METHOD_ENV="$METHOD" PAYLOAD_JSON_ENV="$PAYLOAD_JSON" PAYLOAD_FILE_ENV="$PAYLOAD_FILE" \
CHAT_ID_ENV="$CHAT_ID" TEXT_ENV="$TEXT" PARSE_MODE_ENV="$PARSE_MODE" REPLY_MARKUP_JSON_ENV="$REPLY_MARKUP_JSON" \
COMMANDS_JSON_ENV="$COMMANDS_JSON" PHOTO_ENV="$PHOTO" DOCUMENT_ENV="$DOCUMENT" CAPTION_ENV="$CAPTION" \
LATITUDE_ENV="$LATITUDE" LONGITUDE_ENV="$LONGITUDE" OFFSET_ENV="$OFFSET" TIMEOUT_ENV="$TIMEOUT_VALUE" LIMIT_ENV="$LIMIT_VALUE" \
WEBHOOK_URL_ENV="$WEBHOOK_URL" ALLOWED_UPDATES_JSON_ENV="$ALLOWED_UPDATES_JSON" MESSAGE_ID_ENV="$MESSAGE_ID" \
USER_ID_ENV="$USER_ID" FROM_CHAT_ID_ENV="$FROM_CHAT_ID" CALLBACK_QUERY_ID_ENV="$CALLBACK_QUERY_ID" SHOW_ALERT_ENV="$SHOW_ALERT" \
python3 - "$PAYLOAD_PATH" "$META_PATH" <<'PY'
import json
import os
import sys
from pathlib import Path

payload_path = Path(sys.argv[1])
meta_path = Path(sys.argv[2])
action = os.environ["ACTION_ENV"]
method_env = os.environ.get("METHOD_ENV", "")
method = method_env or action

read_actions = {
    "getMe", "getMyCommands", "getUpdates", "getWebhookInfo",
    "getChat", "getChatMemberCount", "getChatAdministrators",
}
write_actions = {
    "setMyCommands", "sendMessage", "sendPhoto", "sendDocument", "sendLocation",
    "setWebhook", "deleteWebhook", "banChatMember", "unbanChatMember",
    "editMessageText", "deleteMessage", "pinChatMessage", "forwardMessage",
    "answerCallbackQuery",
}

aliases = {
    "getChatMemberCount": "getChatMemberCount",
}

if action == "raw":
    if not method_env:
        raise SystemExit("--method is required for --action raw")
    method = method_env
elif action not in read_actions and action not in write_actions:
    raise SystemExit(f"Unsupported action: {action}")

payload_json = os.environ.get("PAYLOAD_JSON_ENV", "")
payload_file = os.environ.get("PAYLOAD_FILE_ENV", "")

try:
    if payload_file:
        payload = json.loads(Path(payload_file).read_text(encoding="utf-8"))
    elif payload_json:
        payload = json.loads(payload_json)
    else:
        payload = {}
except json.JSONDecodeError as exc:
    raise SystemExit(f"Invalid JSON: {exc.msg} at line {exc.lineno} column {exc.colno}")

def put(name, value):
    if value != "":
        payload[name] = value

def put_int(name, value):
    if value != "":
        try:
            payload[name] = int(value)
        except ValueError:
            payload[name] = value

def put_float(name, value):
    if value != "":
        payload[name] = float(value)

def put_json(name, value):
    if value:
        try:
            payload[name] = json.loads(value)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON for {name}: {exc.msg} at line {exc.lineno} column {exc.colno}")

chat_id = os.environ.get("CHAT_ID_ENV", "")
text = os.environ.get("TEXT_ENV", "")
caption = os.environ.get("CAPTION_ENV", "")

if action in {"sendMessage", "sendPhoto", "sendDocument", "sendLocation", "getChat", "getChatMemberCount", "getChatAdministrators", "banChatMember", "unbanChatMember", "deleteMessage", "pinChatMessage", "forwardMessage"}:
    put("chat_id", chat_id)
if action in {"sendMessage", "editMessageText", "answerCallbackQuery"}:
    put("text", text)
if action in {"sendMessage", "editMessageText"}:
    put("parse_mode", os.environ.get("PARSE_MODE_ENV", ""))
    put_json("reply_markup", os.environ.get("REPLY_MARKUP_JSON_ENV", ""))
if action == "setMyCommands":
    put_json("commands", os.environ.get("COMMANDS_JSON_ENV", ""))
if action == "sendPhoto":
    put("photo", os.environ.get("PHOTO_ENV", ""))
    put("caption", caption)
    put("parse_mode", os.environ.get("PARSE_MODE_ENV", ""))
if action == "sendDocument":
    put("document", os.environ.get("DOCUMENT_ENV", ""))
    put("caption", caption)
    put("parse_mode", os.environ.get("PARSE_MODE_ENV", ""))
if action == "sendLocation":
    put_float("latitude", os.environ.get("LATITUDE_ENV", ""))
    put_float("longitude", os.environ.get("LONGITUDE_ENV", ""))
if action == "getUpdates":
    put_int("offset", os.environ.get("OFFSET_ENV", ""))
    put_int("timeout", os.environ.get("TIMEOUT_ENV", ""))
    put_int("limit", os.environ.get("LIMIT_ENV", ""))
if action == "setWebhook":
    put("url", os.environ.get("WEBHOOK_URL_ENV", ""))
    put_json("allowed_updates", os.environ.get("ALLOWED_UPDATES_JSON_ENV", ""))
if action in {"editMessageText", "deleteMessage", "pinChatMessage", "forwardMessage"}:
    put_int("message_id", os.environ.get("MESSAGE_ID_ENV", ""))
if action in {"banChatMember", "unbanChatMember"}:
    put_int("user_id", os.environ.get("USER_ID_ENV", ""))
if action == "unbanChatMember":
    payload.setdefault("only_if_banned", True)
if action == "forwardMessage":
    put("from_chat_id", os.environ.get("FROM_CHAT_ID_ENV", ""))
if action == "answerCallbackQuery":
    put("callback_query_id", os.environ.get("CALLBACK_QUERY_ID_ENV", ""))
    show_alert = os.environ.get("SHOW_ALERT_ENV", "")
    if show_alert:
        payload["show_alert"] = show_alert == "true"

required = {
    "sendMessage": ["chat_id", "text"],
    "sendPhoto": ["chat_id", "photo"],
    "sendDocument": ["chat_id", "document"],
    "sendLocation": ["chat_id", "latitude", "longitude"],
    "setWebhook": ["url"],
    "setMyCommands": ["commands"],
    "getChat": ["chat_id"],
    "getChatMemberCount": ["chat_id"],
    "getChatAdministrators": ["chat_id"],
    "banChatMember": ["chat_id", "user_id"],
    "unbanChatMember": ["chat_id", "user_id"],
    "editMessageText": ["chat_id", "message_id", "text"],
    "deleteMessage": ["chat_id", "message_id"],
    "pinChatMessage": ["chat_id", "message_id"],
    "forwardMessage": ["chat_id", "from_chat_id", "message_id"],
    "answerCallbackQuery": ["callback_query_id"],
}
missing = [key for key in required.get(action, []) if key not in payload or payload[key] in ("", None)]
if missing:
    raise SystemExit("Missing required field(s): " + ", ".join(missing))

payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
meta_path.write_text(json.dumps({
    "action": action,
    "method": method,
    "read_action": action in read_actions,
    "write_action": action in write_actions or action == "raw",
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

METHOD="$(python3 - "$META_PATH" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))["method"])
PY
)"
READ_ACTION="$(python3 - "$META_PATH" <<'PY'
import json, sys
print("true" if json.load(open(sys.argv[1]))["read_action"] else "false")
PY
)"

if [[ "$DRY_RUN" == "true" || ( "$READ_ACTION" != "true" && "$EXECUTE" != "true" ) ]]; then
  REDACTED_URL="$API_BASE/bot<TELEGRAM_BOT_TOKEN>/$METHOD"
  python3 - "$METHOD" "$REDACTED_URL" "$PAYLOAD_PATH" <<'PY'
import json
import sys
from pathlib import Path
method, url, payload_path = sys.argv[1:4]
payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))
print(json.dumps({
    "dry_run": True,
    "method": method,
    "url": url,
    "payload": payload,
}, ensure_ascii=False, indent=2, sort_keys=True))
PY
  if [[ -n "$OUTPUT_PATH" ]]; then
    mkdir -p "$(dirname "$OUTPUT_PATH")"
    python3 - "$METHOD" "$REDACTED_URL" "$PAYLOAD_PATH" "$OUTPUT_PATH" <<'PY'
import json
import sys
from pathlib import Path
method, url, payload_path, output_path = sys.argv[1:5]
payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))
Path(output_path).write_text(json.dumps({
    "dry_run": True,
    "method": method,
    "url": url,
    "payload": payload,
}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
    echo "Saved Telegram Bot API dry-run metadata to $OUTPUT_PATH" >&2
  fi
  exit 0
fi

if [[ -z "$BOT_TOKEN" ]]; then
  echo "Missing Telegram bot token. Set TELEGRAM_BOT_TOKEN, pass --bot-token, or save one with --save-bot-token." >&2
  exit 1
fi

REQUEST_URL="$API_BASE/bot$BOT_TOKEN/$METHOD"
RESPONSE_PATH="$(mktemp "${TMPDIR:-/tmp}/telegram-bot-response.XXXXXX")"

USE_MULTIPART="false"
if [[ "$ACTION" == "sendPhoto" && -n "$PHOTO" && -f "$PHOTO" ]]; then
  USE_MULTIPART="true"
fi
if [[ "$ACTION" == "sendDocument" && -n "$DOCUMENT" && -f "$DOCUMENT" ]]; then
  USE_MULTIPART="true"
fi

if [[ "$USE_MULTIPART" == "true" ]]; then
  curl_args=(
    -sS
    --connect-timeout "$CONNECT_TIMEOUT"
    --max-time "$MAX_TIME"
    -o "$RESPONSE_PATH"
    -w '%{http_code}'
    -X POST "$REQUEST_URL"
    -F "chat_id=$CHAT_ID"
  )
  if [[ -n "$CAPTION" ]]; then
    curl_args+=(-F "caption=$CAPTION")
  fi
  if [[ -n "$PARSE_MODE" ]]; then
    curl_args+=(-F "parse_mode=$PARSE_MODE")
  fi
  if [[ "$ACTION" == "sendPhoto" ]]; then
    curl_args+=(-F "photo=@$PHOTO")
  else
    curl_args+=(-F "document=@$DOCUMENT")
  fi
  HTTP_STATUS="$(curl "${curl_args[@]}")"
else
  HTTP_STATUS="$(
    curl -sS --connect-timeout "$CONNECT_TIMEOUT" --max-time "$MAX_TIME" \
      -o "$RESPONSE_PATH" -w '%{http_code}' \
      -X POST "$REQUEST_URL" \
      -H 'Content-Type: application/json' \
      --data-binary "@$PAYLOAD_PATH"
  )"
fi

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  cp "$RESPONSE_PATH" "$OUTPUT_PATH"
  echo "Saved Telegram Bot API response to $OUTPUT_PATH" >&2
fi

cat "$RESPONSE_PATH"
printf '\n'

if [[ "$HTTP_STATUS" -lt 200 || "$HTTP_STATUS" -ge 300 ]]; then
  exit 1
fi
