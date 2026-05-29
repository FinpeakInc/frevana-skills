#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="https://ai-factory.frevana.com"
GOOGLE_NEWS_SEARCH_PATH="/service/google-news"
CONNECT_TIMEOUT="10"
MAX_TIME="600"

usage() {
  cat <<'EOF'
Usage:
  search_google_news.sh --q "artificial intelligence" [--gl US] [--hl en] [--topic-token TOKEN] [--publication-token TOKEN] [--section-token TOKEN] [--story-token TOKEN] [--output /path/to/result.json] [--token "bearer token"]

Options:
  --q                  Search query keyword to send
  --query              Alias for --q
  --gl                 Optional country/region code
  --hl                 Optional language code
  --topic-token        Optional Google News topic token
  --publication-token  Optional Google News publication token
  --section-token      Optional Google News section token
  --story-token        Optional Google News story token
  --output             Optional file path for saving returned JSON
  --token              Optional Bearer token override for this run
  -h, --help           Show this help message
EOF
}

Q=""
GL=""
HL=""
TOPIC_TOKEN=""
PUBLICATION_TOKEN=""
SECTION_TOKEN=""
STORY_TOKEN=""
OUTPUT_PATH=""
TOKEN_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --q|--query)
      Q="${2:-}"
      shift 2
      ;;
    --gl)
      GL="${2:-}"
      shift 2
      ;;
    --hl)
      HL="${2:-}"
      shift 2
      ;;
    --topic-token)
      TOPIC_TOKEN="${2:-}"
      shift 2
      ;;
    --publication-token)
      PUBLICATION_TOKEN="${2:-}"
      shift 2
      ;;
    --section-token)
      SECTION_TOKEN="${2:-}"
      shift 2
      ;;
    --story-token)
      STORY_TOKEN="${2:-}"
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

if [[ -z "$Q" ]]; then
  echo "Missing required argument: --q" >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required but was not found in PATH." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required but was not found in PATH." >&2
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
RESULT_FILE="$(mktemp)"
cleanup() {
  rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE" "$RESULT_FILE"
}
trap cleanup EXIT

export Q GL HL TOPIC_TOKEN PUBLICATION_TOKEN SECTION_TOKEN STORY_TOKEN

python3 - "$PAYLOAD_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path

payload_path = Path(sys.argv[1])

payload = {
    "q": os.environ["Q"],
}

optional_fields = {
    "gl": os.environ.get("GL"),
    "hl": os.environ.get("HL"),
    "topic_token": os.environ.get("TOPIC_TOKEN"),
    "publication_token": os.environ.get("PUBLICATION_TOKEN"),
    "section_token": os.environ.get("SECTION_TOKEN"),
    "story_token": os.environ.get("STORY_TOKEN"),
}

for key, value in optional_fields.items():
    if value:
        payload[key] = value

payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
PY

HTTP_CODE="$(
  curl -sS \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -o "$RESPONSE_FILE" \
    -w "%{http_code}" \
    -X POST "$API_BASE_URL$GOOGLE_NEWS_SEARCH_PATH" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    --data @"$PAYLOAD_FILE"
)"

if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "Google News search API request failed with HTTP $HTTP_CODE" >&2
  cat "$RESPONSE_FILE" >&2
  exit 1
fi

if [[ ! -s "$RESPONSE_FILE" ]]; then
  echo "Google News search API returned an empty response body." >&2
  exit 1
fi

python3 - "$RESPONSE_FILE" "$RESULT_FILE" <<'PY'
import json
import sys
from pathlib import Path

response_path = Path(sys.argv[1])
result_path = Path(sys.argv[2])
raw = response_path.read_text(encoding="utf-8")

try:
    json.loads(raw)
except json.JSONDecodeError as exc:
    print(f"Google News search API returned non-JSON response: {exc}", file=sys.stderr)
    print(raw, file=sys.stderr)
    sys.exit(1)

result_path.write_text(raw, encoding="utf-8")
PY

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  cp "$RESULT_FILE" "$OUTPUT_PATH"
fi

cat "$RESULT_FILE"
