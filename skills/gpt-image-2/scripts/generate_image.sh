#!/usr/bin/env bash

set -euo pipefail

FIXED_PROVIDER="openai"
FIXED_MODEL="gpt-image-2"
API_BASE_URL="https://ai-factory.frevana.com"
OPENAI_IMAGE_PATH="/openai/image/generate"
CONNECT_TIMEOUT="10"
MAX_TIME="600"

usage() {
  cat <<'EOF'
Usage:
  generate_image.sh (--prompt "image prompt" | --contents "image contents") [openai options] [--output /path/to/result.json] [--token "bearer token"]

Fixed backend:
  --provider openai
  --model gpt-image-2

OpenAI options:
  --n                    Number of images (1-10)
  --size                 Image size
  --quality              Image quality
  --background           Background behavior
  --output-format        Output format
  --output-compression   Output compression for jpeg/webp (1-100)

Other:
  --output               Optional file path for saving returned JSON
  --token                Optional Bearer token override for this run
  -h, --help             Show this help message
EOF
}

is_allowed_value() {
  local value="$1"
  shift
  local allowed
  for allowed in "$@"; do
    if [[ "$value" == "$allowed" ]]; then
      return 0
    fi
  done
  return 1
}

is_integer() {
  [[ "$1" =~ ^[0-9]+$ ]]
}

PROMPT=""
N=""
SIZE=""
QUALITY=""
BACKGROUND=""
OUTPUT_FORMAT=""
OUTPUT_COMPRESSION=""
OUTPUT_PATH=""
TOKEN_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prompt|--contents)
      PROMPT="${2:-}"
      shift 2
      ;;
    --n)
      N="${2:-}"
      shift 2
      ;;
    --size)
      SIZE="${2:-}"
      shift 2
      ;;
    --quality)
      QUALITY="${2:-}"
      shift 2
      ;;
    --background)
      BACKGROUND="${2:-}"
      shift 2
      ;;
    --output-format)
      OUTPUT_FORMAT="${2:-}"
      shift 2
      ;;
    --output-compression)
      OUTPUT_COMPRESSION="${2:-}"
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
    --provider|--provider=*|--model|--model=*)
      echo "This skill fixes --provider=$FIXED_PROVIDER and --model=$FIXED_MODEL. Do not pass --provider or --model." >&2
      exit 1
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$PROMPT" ]]; then
  echo "Missing required argument: --prompt or --contents" >&2
  exit 1
fi

OPENAI_QUALITIES=("standard" "hd" "low" "medium" "high" "auto")
OPENAI_SIZES=("auto" "1024x1024" "1536x1024" "1024x1536" "256x256" "512x512" "1792x1024" "1024x1792")
OPENAI_BACKGROUNDS=("transparent" "opaque" "auto")
OPENAI_OUTPUT_FORMATS=("png" "jpeg" "webp")

if [[ -n "$N" ]]; then
  if ! is_integer "$N" || (( N < 1 || N > 10 )); then
    echo "Invalid value for --n: $N" >&2
    echo "Allowed range: 1-10" >&2
    exit 1
  fi
fi

if [[ -n "$QUALITY" ]] && ! is_allowed_value "$QUALITY" "${OPENAI_QUALITIES[@]}"; then
  echo "Invalid quality: $QUALITY" >&2
  echo "Allowed qualities: ${OPENAI_QUALITIES[*]}" >&2
  exit 1
fi

if [[ -n "$SIZE" ]] && ! is_allowed_value "$SIZE" "${OPENAI_SIZES[@]}"; then
  echo "Invalid size: $SIZE" >&2
  echo "Allowed sizes: ${OPENAI_SIZES[*]}" >&2
  exit 1
fi

if [[ -n "$BACKGROUND" ]] && ! is_allowed_value "$BACKGROUND" "${OPENAI_BACKGROUNDS[@]}"; then
  echo "Invalid background: $BACKGROUND" >&2
  echo "Allowed backgrounds: ${OPENAI_BACKGROUNDS[*]}" >&2
  exit 1
fi

if [[ -n "$OUTPUT_FORMAT" ]] && ! is_allowed_value "$OUTPUT_FORMAT" "${OPENAI_OUTPUT_FORMATS[@]}"; then
  echo "Invalid output format: $OUTPUT_FORMAT" >&2
  echo "Allowed output formats: ${OPENAI_OUTPUT_FORMATS[*]}" >&2
  exit 1
fi

if [[ -n "$OUTPUT_COMPRESSION" ]]; then
  if ! is_integer "$OUTPUT_COMPRESSION" || (( OUTPUT_COMPRESSION < 1 || OUTPUT_COMPRESSION > 100 )); then
    echo "Invalid value for --output-compression: $OUTPUT_COMPRESSION" >&2
    echo "Allowed range: 1-100" >&2
    exit 1
  fi
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

export PROMPT N SIZE QUALITY BACKGROUND OUTPUT_FORMAT OUTPUT_COMPRESSION FIXED_MODEL

python3 - "$PAYLOAD_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path

payload_path = Path(sys.argv[1])

payload = {
    "prompt": os.environ["PROMPT"],
    "model": os.environ["FIXED_MODEL"],
}

if os.environ.get("N"):
    payload["n"] = int(os.environ["N"])
if os.environ.get("SIZE"):
    payload["size"] = os.environ["SIZE"]
if os.environ.get("QUALITY"):
    payload["quality"] = os.environ["QUALITY"]
if os.environ.get("BACKGROUND"):
    payload["background"] = os.environ["BACKGROUND"]
if os.environ.get("OUTPUT_FORMAT"):
    payload["output_format"] = os.environ["OUTPUT_FORMAT"]
if os.environ.get("OUTPUT_COMPRESSION"):
    payload["output_compression"] = int(os.environ["OUTPUT_COMPRESSION"])

payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
PY

HTTP_CODE="$(
  curl -sS \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -o "$RESPONSE_FILE" \
    -w "%{http_code}" \
    -X POST "$API_BASE_URL$OPENAI_IMAGE_PATH" \
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

python3 - "$RESPONSE_FILE" "$RESULT_FILE" <<'PY'
import json
import sys
from pathlib import Path

response_path = Path(sys.argv[1])
result_path = Path(sys.argv[2])
raw = response_path.read_text(encoding="utf-8")


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    print(raw, file=sys.stderr)
    sys.exit(1)


try:
    payload = json.loads(raw)
except json.JSONDecodeError as exc:
    fail(f"Frevana API returned non-JSON response: {exc}")

if not isinstance(payload, dict):
    fail("Frevana API returned JSON, but not an object.")

for field in ("created", "data", "credits_consumed"):
    if field not in payload:
        fail(f"Frevana OpenAI response JSON is missing the '{field}' field.")

if not isinstance(payload["created"], (int, float)):
    fail("Frevana OpenAI response field 'created' must be numeric.")

if not isinstance(payload["credits_consumed"], (int, float)):
    fail("Frevana OpenAI response field 'credits_consumed' must be numeric.")

if not isinstance(payload["data"], list) or not payload["data"]:
    fail("Frevana OpenAI response field 'data' must be a non-empty array.")

for index, item in enumerate(payload["data"]):
    if not isinstance(item, dict):
        fail(f"Frevana OpenAI response data item {index} must be an object.")
    image_url = item.get("image_url")
    if not isinstance(image_url, str) or not image_url:
        fail(f"Frevana OpenAI response data item {index} is missing a non-empty 'image_url'.")
    if "revised_prompt" in item and not isinstance(item["revised_prompt"], str):
        fail(f"Frevana OpenAI response data item {index} field 'revised_prompt' must be a string when present.")

for optional_field in ("background", "output_format", "quality", "size"):
    if optional_field in payload and not isinstance(payload[optional_field], str):
        fail(f"Frevana OpenAI response field '{optional_field}' must be a string when present.")

result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  cp "$RESULT_FILE" "$OUTPUT_PATH"
fi

cat "$RESULT_FILE"
