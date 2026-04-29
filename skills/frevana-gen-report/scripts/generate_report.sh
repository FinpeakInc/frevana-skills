#!/usr/bin/env bash

set -euo pipefail

API_URL="https://ai-factory.frevana.com/report/generate"
TARGET_PLATFORM="generate_auto_formating_content"
CONNECT_TIMEOUT="10"
MAX_TIME="600"

json_escape() {
  local s="$1"
  s=${s//\\/\\\\}
  s=${s//\"/\\\"}
  s=${s//$'\n'/\\n}
  s=${s//$'\r'/\\r}
  s=${s//$'\t'/\\t}
  s=${s//$'\f'/\\f}
  s=${s//$'\b'/\\b}
  printf '%s' "$s"
}

usage() {
  cat <<'EOF'
Usage:
  generate_report.sh (--content "report content" | --content-file /path/to/content.txt) --template-id "template id" [--output /path/to/report.html] [--token "bearer token"]

Options:
  --content        Report content to send
  --content-file   Read report content from a file
  --template-id    Frevana report template ID
  --output         Optional file path for saving returned HTML
  --token          Optional Bearer token override for this run
  -h, --help       Show this help message
EOF
}

CONTENT=""
CONTENT_FILE=""
TEMPLATE_ID=""
OUTPUT_PATH=""
TOKEN_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --content)
      CONTENT="${2:-}"
      shift 2
      ;;
    --content-file)
      CONTENT_FILE="${2:-}"
      shift 2
      ;;
    --template-id)
      TEMPLATE_ID="${2:-}"
      shift 2
      ;;
    --output)
      OUTPUT_PATH="${2:-}"
      shift 2
      ;;
    --token)
      TOKEN_OVERRIDE="${2:-}"
      shift 2
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

if [[ -n "$CONTENT" && -n "$CONTENT_FILE" ]]; then
  echo "Provide exactly one of --content or --content-file, not both." >&2
  exit 1
fi

if [[ -z "$CONTENT" && -z "$CONTENT_FILE" ]]; then
  echo "Missing required content input. Provide --content or --content-file." >&2
  exit 1
fi

if [[ -n "$CONTENT_FILE" ]]; then
  if [[ ! -f "$CONTENT_FILE" ]]; then
    echo "Content file not found: $CONTENT_FILE" >&2
    exit 1
  fi
  CONTENT="$(<"$CONTENT_FILE")"
fi

if [[ -z "$TEMPLATE_ID" ]]; then
  echo "Missing required argument: --template-id" >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required but was not found in PATH." >&2
  exit 1
fi

TOKEN="${TOKEN_OVERRIDE:-${FREVANA_TOKEN:-}}"
if [[ -z "$TOKEN" ]]; then
  if [[ -t 0 ]]; then
    read -r -s -p "FREVANA_TOKEN not found. Please enter your Frevana Bearer token: " TOKEN
    echo >&2
  else
    echo "FREVANA_TOKEN is not set. In non-interactive runs, set FREVANA_TOKEN or pass --token explicitly." >&2
    exit 1
  fi
fi

if [[ -z "$TOKEN" ]]; then
  echo "Bearer token is required." >&2
  exit 1
fi

PAYLOAD_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
HTML_FILE="$(mktemp)"
cleanup() {
  rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE" "$HTML_FILE"
}
trap cleanup EXIT

printf '{"content":"%s","template_id":"%s","target_platform":"%s"}' \
  "$(json_escape "$CONTENT")" \
  "$(json_escape "$TEMPLATE_ID")" \
  "$(json_escape "$TARGET_PLATFORM")" \
  > "$PAYLOAD_FILE"

HTTP_CODE="$(
  curl -sS \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -o "$RESPONSE_FILE" \
    -w "%{http_code}" \
    -X POST "$API_URL" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    --data @"$PAYLOAD_FILE"
)"

if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "Frevana API request failed with HTTP $HTTP_CODE" >&2
  cat "$RESPONSE_FILE" >&2
  exit 1
fi

if [[ ! -s "$RESPONSE_FILE" ]]; then
  echo "Frevana API returned an empty response body." >&2
  exit 1
fi

python3 - "$RESPONSE_FILE" "$HTML_FILE" <<'PY'
import json
import sys
from pathlib import Path

response_path = Path(sys.argv[1])
html_path = Path(sys.argv[2])
raw = response_path.read_text(encoding='utf-8')

try:
    payload = json.loads(raw)
except json.JSONDecodeError as exc:
    print(f"Frevana API returned non-JSON response: {exc}", file=sys.stderr)
    print(raw, file=sys.stderr)
    sys.exit(1)

if not isinstance(payload, dict):
    print("Frevana API returned JSON, but not an object.", file=sys.stderr)
    print(raw, file=sys.stderr)
    sys.exit(1)

if "content" not in payload:
    print("Frevana API response JSON is missing the 'content' field.", file=sys.stderr)
    print(raw, file=sys.stderr)
    sys.exit(1)

content = payload["content"]
if not isinstance(content, str):
    print("Frevana API response field 'content' must be a string.", file=sys.stderr)
    print(raw, file=sys.stderr)
    sys.exit(1)

if not content:
    print("Frevana API response field 'content' is empty.", file=sys.stderr)
    sys.exit(1)

html_path.write_text(content, encoding='utf-8')
PY

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  cp "$HTML_FILE" "$OUTPUT_PATH"
fi

cat "$HTML_FILE"
