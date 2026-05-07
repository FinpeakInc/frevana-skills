#!/usr/bin/env bash

set -euo pipefail

FIXED_PROVIDER="openai"
FIXED_MODEL="gpt-image-2"
DEFAULT_API_BASE_URL="https://ai-factory.frevana.com"
API_BASE_URL="${FREVANA_API_BASE_URL:-$DEFAULT_API_BASE_URL}"
OPENAI_IMAGE_PATH="/openai/image/generate"
CONNECT_TIMEOUT="10"
MAX_TIME="600"
MAX_IMAGE_COUNT="16"
MAX_IMAGE_SIZE_BYTES="$((50 * 1024 * 1024))"
MAX_MASK_SIZE_BYTES="$((4 * 1024 * 1024))"

usage() {
  cat <<'EOF'
Usage:
  generate_image.sh (--prompt "image prompt" | --contents "image contents") [openai options] [--image /path/to/ref.png ...] [--image-dir /path/to/images ...] [--mask /path/to/mask.png] [--output /path/to/result.json] [--token "bearer token"]

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
  --image                Reference image path for image-to-image (repeatable, png/jpg/jpeg/webp, <50MB each)
  --image-dir            Directory of reference images for image-to-image (repeatable, recursive, up to 16 images total)
  --mask                 Optional PNG mask image for image-to-image (<4MB)

Other:
  --output               Optional file path for saving returned JSON
  --token                Optional Bearer token override for this run
  Env override           FREVANA_API_BASE_URL=http://127.0.0.1:3001 for local testing
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

is_supported_image_path() {
  case "$1" in
    *.png|*.PNG|*.jpg|*.JPG|*.jpeg|*.JPEG|*.webp|*.WEBP)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

mime_type_for_path() {
  case "$1" in
    *.png|*.PNG)
      printf '%s' 'image/png'
      ;;
    *.jpg|*.JPG|*.jpeg|*.JPEG)
      printf '%s' 'image/jpeg'
      ;;
    *.webp|*.WEBP)
      printf '%s' 'image/webp'
      ;;
    *)
      return 1
      ;;
  esac
}

file_size_bytes() {
  python3 - "$1" <<'PY'
import os
import sys

print(os.path.getsize(sys.argv[1]))
PY
}

require_existing_file() {
  local path="$1"
  local flag_name="$2"

  if [[ -z "$path" ]]; then
    echo "Missing value for $flag_name" >&2
    exit 1
  fi
  if [[ ! -e "$path" ]]; then
    echo "File not found for $flag_name: $path" >&2
    exit 1
  fi
  if [[ ! -f "$path" ]]; then
    echo "Expected a file for $flag_name: $path" >&2
    exit 1
  fi
}

append_image_path() {
  local path="$1"
  local file_size

  require_existing_file "$path" "--image"
  if ! is_supported_image_path "$path"; then
    echo "Unsupported image type for --image: $path" >&2
    echo "Allowed image extensions: .png .jpg .jpeg .webp" >&2
    exit 1
  fi

  file_size="$(file_size_bytes "$path")"
  if (( file_size > MAX_IMAGE_SIZE_BYTES )); then
    echo "Each image must be less than 50MB: $path" >&2
    exit 1
  fi

  COLLECTED_IMAGES+=("$path")
}

collect_directory_images() {
  local dir_path="$1"
  local found_any=0
  local listing_file
  local path

  if [[ -z "$dir_path" ]]; then
    echo "Missing value for --image-dir" >&2
    exit 1
  fi
  if [[ ! -d "$dir_path" ]]; then
    echo "Image directory not found: $dir_path" >&2
    exit 1
  fi

  listing_file="$(mktemp)"
  python3 - "$dir_path" > "$listing_file" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
supported_suffixes = {".png", ".jpg", ".jpeg", ".webp"}

for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file() and candidate.suffix.lower() in supported_suffixes):
    print(path)
PY

  while IFS= read -r path; do
    [[ -z "$path" ]] && continue
    found_any=1
    append_image_path "$path"
  done < "$listing_file"

  rm -f "$listing_file"

  if (( ! found_any )); then
    echo "No supported images found in directory: $dir_path" >&2
    exit 1
  fi
}

validate_mask_path() {
  local file_size

  if [[ -z "$MASK_PATH" ]]; then
    return 0
  fi

  require_existing_file "$MASK_PATH" "--mask"
  case "$MASK_PATH" in
    *.png|*.PNG)
      ;;
    *)
      echo "Mask must be a PNG file: $MASK_PATH" >&2
      exit 1
      ;;
  esac

  file_size="$(file_size_bytes "$MASK_PATH")"
  if (( file_size > MAX_MASK_SIZE_BYTES )); then
    echo "Mask must be less than 4MB: $MASK_PATH" >&2
    exit 1
  fi
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
MASK_PATH=""
IMAGE_PATHS=()
IMAGE_DIRS=()
COLLECTED_IMAGES=()

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
    --image)
      IMAGE_PATHS+=("${2:-}")
      shift 2
      ;;
    --image-dir)
      IMAGE_DIRS+=("${2:-}")
      shift 2
      ;;
    --mask)
      MASK_PATH="${2:-}"
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

if [[ -n "${IMAGE_PATHS[*]-}" ]]; then
  for image_path in "${IMAGE_PATHS[@]}"; do
    append_image_path "$image_path"
  done
fi

if [[ -n "${IMAGE_DIRS[*]-}" ]]; then
  for image_dir in "${IMAGE_DIRS[@]}"; do
    collect_directory_images "$image_dir"
  done
fi

COLLECTED_IMAGE_COUNT=0
if [[ -n "${COLLECTED_IMAGES[*]-}" ]]; then
  COLLECTED_IMAGE_COUNT="${#COLLECTED_IMAGES[@]}"
fi

if (( COLLECTED_IMAGE_COUNT > MAX_IMAGE_COUNT )); then
  echo "You can upload up to 16 images total. Received: $COLLECTED_IMAGE_COUNT" >&2
  exit 1
fi

validate_mask_path

USE_MULTIPART=0
if (( COLLECTED_IMAGE_COUNT > 0 )) || [[ -n "$MASK_PATH" ]]; then
  USE_MULTIPART=1
fi

if (( USE_MULTIPART )) && (( COLLECTED_IMAGE_COUNT == 0 )); then
  echo "At least one image file is required when using image-to-image options." >&2
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

if (( ! USE_MULTIPART )); then
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
fi

CURL_ARGS=(
  -sS
  --connect-timeout "$CONNECT_TIMEOUT"
  --max-time "$MAX_TIME"
  -o "$RESPONSE_FILE"
  -w "%{http_code}"
  -X POST "$API_BASE_URL$OPENAI_IMAGE_PATH"
  -H "Authorization: Bearer $TOKEN"
)

if (( USE_MULTIPART )); then
  CURL_ARGS+=(--form-string "prompt=$PROMPT")
  CURL_ARGS+=(--form-string "model=$FIXED_MODEL")

  if [[ -n "$N" ]]; then
    CURL_ARGS+=(--form-string "n=$N")
  fi
  if [[ -n "$SIZE" ]]; then
    CURL_ARGS+=(--form-string "size=$SIZE")
  fi
  if [[ -n "$QUALITY" ]]; then
    CURL_ARGS+=(--form-string "quality=$QUALITY")
  fi
  if [[ -n "$BACKGROUND" ]]; then
    CURL_ARGS+=(--form-string "background=$BACKGROUND")
  fi
  if [[ -n "$OUTPUT_FORMAT" ]]; then
    CURL_ARGS+=(--form-string "output_format=$OUTPUT_FORMAT")
  fi
  if [[ -n "$OUTPUT_COMPRESSION" ]]; then
    CURL_ARGS+=(--form-string "output_compression=$OUTPUT_COMPRESSION")
  fi

  if (( COLLECTED_IMAGE_COUNT > 0 )); then
    for image_path in "${COLLECTED_IMAGES[@]}"; do
      CURL_ARGS+=(-F "image=@$image_path;type=$(mime_type_for_path "$image_path")")
    done
  fi

  if [[ -n "$MASK_PATH" ]]; then
    CURL_ARGS+=(-F "mask=@$MASK_PATH;type=image/png")
  fi
else
  CURL_ARGS+=(-H "Content-Type: application/json")
  CURL_ARGS+=(--data @"$PAYLOAD_FILE")
fi

HTTP_CODE="$(curl "${CURL_ARGS[@]}")"

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
