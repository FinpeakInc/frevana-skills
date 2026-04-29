#!/usr/bin/env bash

set -euo pipefail

FIXED_PROVIDER="gemini"
FIXED_MODEL="gemini-3-pro-image-preview"
API_BASE_URL="https://ai-factory.frevana.com"
GEMINI_IMAGE_PATH="/gemini/image/generate"
CONNECT_TIMEOUT="10"
MAX_TIME="600"

usage() {
  cat <<'EOF'
Usage:
  generate_image.sh (--prompt "image prompt" | --contents "image contents") [gemini options] [--output /path/to/result.json] [--token "bearer token"]

Fixed backend:
  --provider gemini
  --model gemini-3-pro-image-preview

Gemini options:
  --seed                 Random seed
  --max-output-tokens    Maximum output tokens
  --response-modality    Requested response modality. Repeat to pass multiple values
  --aspect-ratio         GenerateContentConfig.imageConfig.aspectRatio
  --image-size           GenerateContentConfig.imageConfig.imageSize (1K, 2K, 4K; numeric and WxH inputs are normalized to the nearest tier, defaults to 1K)

Other:
  --output               Optional file path for saving returned JSON
  --token                Optional Bearer token override for this run
  -h, --help             Show this help message
EOF
}

is_number() {
  [[ "$1" =~ ^-?[0-9]+([.][0-9]+)?$ ]]
}

is_integer() {
  [[ "$1" =~ ^[0-9]+$ ]]
}

normalize_image_size() {
  local value="$1"
  local normalized=""
  local numeric_value=0
  local width=0
  local height=0

  normalized="$(printf '%s' "$value" | tr '[:lower:]' '[:upper:]' | tr -d '[:space:]')"

  case "$normalized" in
    1K|2K|4K)
      printf '%s\n' "$normalized"
      return 0
      ;;
  esac

  if [[ "$normalized" =~ ^([0-9]+)X([0-9]+)$ ]]; then
    width="${BASH_REMATCH[1]}"
    height="${BASH_REMATCH[2]}"
    numeric_value="$width"
    if (( height > numeric_value )); then
      numeric_value="$height"
    fi
  elif [[ "$normalized" =~ ^[0-9]+$ ]]; then
    numeric_value="$normalized"
  else
    return 1
  fi

  if (( numeric_value < 1 )); then
    return 1
  fi

  if (( numeric_value < 1536 )); then
      printf '%s\n' "1K"
    elif (( numeric_value < 3072 )); then
      printf '%s\n' "2K"
    else
      printf '%s\n' "4K"
    fi
}

PROMPT=""
SEED=""
MAX_OUTPUT_TOKENS=""
ASPECT_RATIO=""
IMAGE_SIZE=""
OUTPUT_PATH=""
TOKEN_OVERRIDE=""
RESPONSE_MODALITIES=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prompt|--contents)
      PROMPT="${2:-}"
      shift 2
      ;;
    --seed)
      SEED="${2:-}"
      shift 2
      ;;
    --max-output-tokens)
      MAX_OUTPUT_TOKENS="${2:-}"
      shift 2
      ;;
    --response-modality)
      RESPONSE_MODALITIES+=("${2:-}")
      shift 2
      ;;
    --aspect-ratio)
      ASPECT_RATIO="${2:-}"
      shift 2
      ;;
    --image-size)
      IMAGE_SIZE="${2:-}"
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

if [[ -n "$SEED" ]] && ! is_number "$SEED"; then
  echo "Invalid value for --seed: $SEED" >&2
  exit 1
fi

if [[ -n "$MAX_OUTPUT_TOKENS" ]] && ! is_integer "$MAX_OUTPUT_TOKENS"; then
  echo "Invalid value for --max-output-tokens: $MAX_OUTPUT_TOKENS" >&2
  exit 1
fi

if [[ -n "$IMAGE_SIZE" ]]; then
  RAW_IMAGE_SIZE="$IMAGE_SIZE"
  if ! IMAGE_SIZE="$(normalize_image_size "$RAW_IMAGE_SIZE")"; then
    echo "Invalid value for --image-size: $RAW_IMAGE_SIZE" >&2
    echo "Use 1K, 2K, or 4K. Numeric values and WxH forms like 1024x1024 are normalized to the nearest supported tier." >&2
    echo "For WxH inputs, the larger edge is used to choose the nearest tier." >&2
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
RESPONSE_MODALITIES_FILE="$(mktemp)"
cleanup() {
  rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE" "$RESULT_FILE" "$RESPONSE_MODALITIES_FILE"
}
trap cleanup EXIT

if [[ "${#RESPONSE_MODALITIES[@]}" -gt 0 ]]; then
  printf '%s\n' "${RESPONSE_MODALITIES[@]}" > "$RESPONSE_MODALITIES_FILE"
fi

export PROMPT SEED MAX_OUTPUT_TOKENS ASPECT_RATIO IMAGE_SIZE FIXED_MODEL

python3 - "$PAYLOAD_FILE" "$RESPONSE_MODALITIES_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path

payload_path = Path(sys.argv[1])
modalities_path = Path(sys.argv[2])


def parse_number(value: str):
    if "." in value:
        return float(value)
    return int(value)


payload = {
    "model": os.environ["FIXED_MODEL"],
    "contents": os.environ["PROMPT"],
}

config = {}
if os.environ.get("SEED"):
    config["seed"] = parse_number(os.environ["SEED"])
if os.environ.get("MAX_OUTPUT_TOKENS"):
    config["maxOutputTokens"] = int(os.environ["MAX_OUTPUT_TOKENS"])

response_modalities = [
    line.strip()
    for line in modalities_path.read_text(encoding="utf-8").splitlines()
    if line.strip()
]
if response_modalities:
    config["responseModalities"] = response_modalities

image_config = {}
if os.environ.get("ASPECT_RATIO"):
    image_config["aspectRatio"] = os.environ["ASPECT_RATIO"]
if os.environ.get("IMAGE_SIZE"):
    image_config["imageSize"] = os.environ["IMAGE_SIZE"]
if image_config:
    config["imageConfig"] = image_config

if config:
    payload["config"] = config

payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
PY

HTTP_CODE="$(
  curl -sS \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -o "$RESPONSE_FILE" \
    -w "%{http_code}" \
    -X POST "$API_BASE_URL$GEMINI_IMAGE_PATH" \
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

for field in ("generated_images", "credits_consumed"):
    if field not in payload:
        fail(f"Frevana Gemini response JSON is missing the '{field}' field.")

if not isinstance(payload["credits_consumed"], (int, float)):
    fail("Frevana Gemini response field 'credits_consumed' must be numeric.")

if not isinstance(payload["generated_images"], list) or not payload["generated_images"]:
    fail("Frevana Gemini response field 'generated_images' must be a non-empty array.")

if "positive_prompt_safety_attributes" in payload and not isinstance(payload["positive_prompt_safety_attributes"], dict):
    fail("Frevana Gemini response field 'positive_prompt_safety_attributes' must be an object when present.")

for index, item in enumerate(payload["generated_images"]):
    if not isinstance(item, dict):
        fail(f"Frevana Gemini response generated_images item {index} must be an object.")
    image_url = item.get("image_url")
    if not isinstance(image_url, str) or not image_url:
        fail(f"Frevana Gemini response generated_images item {index} is missing a non-empty 'image_url'.")
    for optional_field in ("enhanced_prompt", "rai_filtered_reason", "mime_type"):
        if optional_field in item and not isinstance(item[optional_field], str):
            fail(
                f"Frevana Gemini response generated_images item {index} field '{optional_field}' must be a string when present."
            )

result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  cp "$RESULT_FILE" "$OUTPUT_PATH"
fi

cat "$RESULT_FILE"
