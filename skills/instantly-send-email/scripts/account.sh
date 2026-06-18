#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="https://api.instantly.ai"
CONFIG_NAME="instantly-send-email"
CONNECT_TIMEOUT="10"
MAX_TIME="120"
API_KEY_HELP_URL="https://frevana.gitbook.io/frevana-docs/email-integrations/instantly-integration"

usage() {
  cat <<'EOF'
Usage:
  account.sh list [--limit 100] [global options]

Read actions call the API immediately.

Global options:
  --api-key KEY
  --save-api-key
  --configure-api-key
  --clear-api-key
  --output PATH
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
LIMIT="100"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-key) API_KEY_OVERRIDE="${2:-}"; shift 2 ;;
    --save-api-key) SAVE_API_KEY="true"; shift ;;
    --configure-api-key) CONFIGURE_API_KEY="true"; shift ;;
    --clear-api-key) rm -f "$(api_key_file)"; echo "Removed saved Instantly API key." >&2; shift ;;
    --output) OUTPUT_PATH="${2:-}"; shift 2 ;;
    --limit) LIMIT="${2:-}"; shift 2 ;;
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

case "$ACTION" in
  list)
    load_api_key
    result="$(curl_json GET "$API_BASE_URL/api/v2/accounts?limit=$LIMIT")"
    if echo "$result" | python3 -c "import sys,json; data=json.load(sys.stdin); sys.exit(0 if len(data.get('body',{}).get('items',[]))==0 else 1)" 2>/dev/null; then
      echo "No sender accounts found. Please add one at: https://app.instantly.ai/app/accounts" >&2
    fi
    ;;
  *)
    echo "Action is required: list." >&2
    usage >&2
    exit 1
    ;;
esac

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  printf '%s\n' "$result" > "$OUTPUT_PATH"
fi
printf '%s\n' "$result"
