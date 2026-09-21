#!/usr/bin/env bash

set -euo pipefail

FIXED_PROVIDER="openai"
DEFAULT_MODEL="gpt-image-2.5-flare"
SUNBURST_MODEL="gpt-image-2.5-sunburst"
DEFAULT_API_BASE_URL="https://ai-factory.frevana.com"
API_BASE_URL="${FREVANA_API_BASE_URL:-$DEFAULT_API_BASE_URL}"
while [[ "$API_BASE_URL" == */ ]]; do API_BASE_URL="${API_BASE_URL%/}"; done
OPENAI_IMAGE_PATH="/openai/image/generate"
CONNECT_TIMEOUT="10"
MAX_TIME="600"
MAX_IMAGE_COUNT="16"
MAX_IMAGE_SIZE_BYTES="$((50 * 1024 * 1024))"
MAX_MASK_SIZE_BYTES="$((4 * 1024 * 1024))"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

usage() {
  cat <<'EOF'
Usage:
  generate_image.sh (--prompt "image prompt" | --contents "image contents") [options]

Model:
  --model                gpt-image-2.5-flare (default) or gpt-image-2.5-sunburst

OpenAI image options:
  --n                    Number of images (1-10)
  --size                 auto or WIDTHxHEIGHT under GPT Image 2.5 constraints
  --quality              auto, low, medium, high, xhigh, or max
  --background           auto, opaque, or transparent
  --output-format        png, jpeg, or webp
  --output-compression   Compression for jpeg/webp (1-100)
  --moderation           auto or low (generation only)
  --input-fidelity       low or high (editing/reference images only)
  --image                Reference image path (repeatable, png/jpg/jpeg/webp, <50MB)
  --image-url            Reference HTTP(S) image URL (repeatable)
  --image-dir            Reference image directory (repeatable, recursive, 16 images total)
  --mask                 Optional PNG mask (<4MB, requires a reference image)

Other:
  --output               Optional path for returned JSON
  --token                Bearer token override for this run
  Env override           FREVANA_API_BASE_URL=http://127.0.0.1:3001
  -h, --help             Show help
EOF
}

is_allowed() {
  local value="$1"
  shift
  local allowed
  for allowed in "$@"; do
    [[ "$value" == "$allowed" ]] && return 0
  done
  return 1
}

is_integer() { [[ "$1" =~ ^[0-9]+$ ]]; }
is_http_url() { [[ "$1" =~ ^https?://[^[:space:]]+$ ]]; }
is_image_path() { [[ "$1" =~ \.(png|PNG|jpg|JPG|jpeg|JPEG|webp|WEBP)$ ]]; }

mime_for_path() {
  case "$1" in
    *.png|*.PNG) printf '%s' image/png ;;
    *.jpg|*.JPG|*.jpeg|*.JPEG) printf '%s' image/jpeg ;;
    *.webp|*.WEBP) printf '%s' image/webp ;;
    *) return 1 ;;
  esac
}

file_size() {
  python3 - "$1" <<'PY'
import os, sys
print(os.path.getsize(sys.argv[1]))
PY
}

verify_image_magic() {
  python3 - "$1" <<'PY'
import sys
path = sys.argv[1]
with open(path, "rb") as f:
    header = f.read(12)
if len(header) < 4:
    raise SystemExit(1)
if header[:8] == b"\x89PNG\r\n\x1a\n":
    raise SystemExit(0)
if header[:3] == b"\xff\xd8\xff":
    raise SystemExit(0)
if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
    raise SystemExit(0)
raise SystemExit(1)
PY
}

append_image() {
  local path="$1"
  [[ -n "$path" ]] || { echo "Reference image path must not be empty." >&2; exit 1; }
  [[ -f "$path" ]] || { echo "Reference image not found: $path" >&2; exit 1; }
  is_image_path "$path" || { echo "Unsupported reference image type: $path" >&2; exit 1; }
  verify_image_magic "$path" || { echo "File does not match its declared image format (bad magic bytes): $path" >&2; exit 1; }
  (( $(file_size "$path") < MAX_IMAGE_SIZE_BYTES )) || { echo "Each reference image must be less than 50MB: $path" >&2; exit 1; }
  COLLECTED_IMAGES+=("$path")
}

download_image() {
  local url="$1"
  local headers="$TEMP_DIR/headers-$DOWNLOAD_INDEX"
  local body="$TEMP_DIR/download-$DOWNLOAD_INDEX"
  local content_type extension
  DOWNLOAD_INDEX=$((DOWNLOAD_INDEX + 1))
  is_http_url "$url" || { echo "Invalid --image-url: $url" >&2; exit 1; }
  curl -fsSL --connect-timeout "$CONNECT_TIMEOUT" --max-time "$MAX_TIME" --max-filesize "$MAX_IMAGE_SIZE_BYTES" -D "$headers" -o "$body" "$url" || {
    echo "Failed to download --image-url (may exceed 50MB): $url" >&2
    exit 1
  }
  [[ -s "$body" ]] || { echo "Downloaded image is empty: $url" >&2; exit 1; }
  content_type="$(python3 - "$headers" <<'PY'
import sys
value = ""
for line in open(sys.argv[1], encoding="utf-8", errors="ignore"):
    if line.lower().startswith("content-type:"):
        value = line.split(":", 1)[1].strip().split(";", 1)[0].lower()
print(value)
PY
)"
  case "$content_type" in
    image/png) extension=.png ;;
    image/jpeg|image/jpg) extension=.jpg ;;
    image/webp) extension=.webp ;;
    *)
      extension="$(python3 - "$url" <<'PY'
import sys
from pathlib import PurePosixPath
from urllib.parse import urlparse
suffix = PurePosixPath(urlparse(sys.argv[1]).path).suffix.lower()
print(suffix if suffix in {".png", ".jpg", ".jpeg", ".webp"} else "")
PY
)"
      ;;
  esac
  [[ -n "$extension" ]] || { echo "Unsupported remote image type: $url" >&2; exit 1; }
  mv "$body" "$body$extension"
  append_image "$body$extension"
}

validate_size() {
  python3 - "$1" <<'PY'
import re, sys
value = sys.argv[1]
if value == "auto":
    raise SystemExit(0)
match = re.fullmatch(r"([0-9]+)x([0-9]+)", value)
if not match:
    raise SystemExit(1)
w, h = map(int, match.groups())
valid = (
    w <= 3840 and h <= 3840 and w % 16 == 0 and h % 16 == 0
    and max(w, h) <= 3 * min(w, h)
    and 655360 <= w * h <= 8294400
)
raise SystemExit(0 if valid else 1)
PY
}

PROMPT=""
MODEL="$DEFAULT_MODEL"
N=""
SIZE=""
QUALITY=""
BACKGROUND=""
OUTPUT_FORMAT=""
OUTPUT_COMPRESSION=""
MODERATION=""
INPUT_FIDELITY=""
OUTPUT_PATH=""
TOKEN_OVERRIDE=""
MASK_PATH=""
IMAGE_PATHS=()
IMAGE_URLS=()
IMAGE_DIRS=()
COLLECTED_IMAGES=()
DOWNLOAD_INDEX=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prompt|--contents) PROMPT="${2:-}"; shift 2 ;;
    --model) MODEL="${2:-}"; shift 2 ;;
    --n) N="${2:-}"; shift 2 ;;
    --size) SIZE="${2:-}"; shift 2 ;;
    --quality) QUALITY="${2:-}"; shift 2 ;;
    --background) BACKGROUND="${2:-}"; shift 2 ;;
    --output-format) OUTPUT_FORMAT="${2:-}"; shift 2 ;;
    --output-compression) OUTPUT_COMPRESSION="${2:-}"; shift 2 ;;
    --moderation) MODERATION="${2:-}"; shift 2 ;;
    --input-fidelity) INPUT_FIDELITY="${2:-}"; shift 2 ;;
    --image) IMAGE_PATHS+=("${2:-}"); shift 2 ;;
    --image-url) IMAGE_URLS+=("${2:-}"); shift 2 ;;
    --image-dir) IMAGE_DIRS+=("${2:-}"); shift 2 ;;
    --mask) MASK_PATH="${2:-}"; shift 2 ;;
    --output) OUTPUT_PATH="${2:-}"; shift 2 ;;
    --token) TOKEN_OVERRIDE="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    --provider|--provider=*) echo "This skill fixes --provider=$FIXED_PROVIDER." >&2; exit 1 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done

[[ -n "$PROMPT" ]] || { echo "Missing required argument: --prompt or --contents" >&2; exit 1; }
is_allowed "$MODEL" "$DEFAULT_MODEL" "$SUNBURST_MODEL" || { echo "Invalid model: $MODEL" >&2; echo "Allowed models: $DEFAULT_MODEL $SUNBURST_MODEL" >&2; exit 1; }

if [[ -n "$N" ]] && { ! is_integer "$N" || (( N < 1 || N > 10 )); }; then
  echo "Invalid --n: $N (allowed: 1-10)" >&2; exit 1
fi
if [[ -n "$SIZE" ]] && ! validate_size "$SIZE"; then
  echo "Invalid --size: $SIZE" >&2
  echo "Use auto or WIDTHxHEIGHT: edges <=3840 and divisible by 16, ratio <=3:1, total pixels 655360-8294400." >&2
  exit 1
fi
if [[ -n "$QUALITY" ]] && ! is_allowed "$QUALITY" auto low medium high xhigh max; then
  echo "Invalid --quality: $QUALITY" >&2; exit 1
fi
if [[ -n "$BACKGROUND" ]] && ! is_allowed "$BACKGROUND" auto opaque transparent; then
  echo "Invalid --background: $BACKGROUND" >&2; exit 1
fi
if [[ -n "$OUTPUT_FORMAT" ]] && ! is_allowed "$OUTPUT_FORMAT" png jpeg webp; then
  echo "Invalid --output-format: $OUTPUT_FORMAT" >&2; exit 1
fi
if [[ -n "$OUTPUT_COMPRESSION" ]] && { ! is_integer "$OUTPUT_COMPRESSION" || (( OUTPUT_COMPRESSION < 1 || OUTPUT_COMPRESSION > 100 )); }; then
  echo "Invalid --output-compression: $OUTPUT_COMPRESSION (allowed: 1-100)" >&2; exit 1
fi
if [[ -n "$MODERATION" ]] && ! is_allowed "$MODERATION" auto low; then
  echo "Invalid --moderation: $MODERATION" >&2; exit 1
fi
if [[ -n "$INPUT_FIDELITY" ]] && ! is_allowed "$INPUT_FIDELITY" low high; then
  echo "Invalid --input-fidelity: $INPUT_FIDELITY" >&2; exit 1
fi
if [[ "$BACKGROUND" == transparent && "$OUTPUT_FORMAT" == jpeg ]]; then
  echo "Transparent backgrounds require png or webp output." >&2; exit 1
fi
if [[ -n "$OUTPUT_COMPRESSION" && "$OUTPUT_FORMAT" != jpeg && "$OUTPUT_FORMAT" != webp ]]; then
  echo "--output-compression requires --output-format jpeg or webp." >&2; exit 1
fi

command -v curl >/dev/null 2>&1 || { echo "curl is required." >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is required." >&2; exit 1; }

if (( ${#IMAGE_PATHS[@]} > 0 )); then
  for path in "${IMAGE_PATHS[@]}"; do append_image "$path"; done
fi
if (( ${#IMAGE_URLS[@]} > 0 )); then
  for url in "${IMAGE_URLS[@]}"; do download_image "$url"; done
fi
if (( ${#IMAGE_DIRS[@]} > 0 )); then
  for directory in "${IMAGE_DIRS[@]}"; do
    found_image=0
    [[ -d "$directory" ]] || { echo "Image directory not found: $directory" >&2; exit 1; }
    while IFS= read -r -d '' path; do
      found_image=1
      append_image "$path"
    done < <(
      find "$directory" -type f \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.webp' \) -print0 | sort -z
    )
    (( found_image )) || { echo "No supported images found in directory: $directory" >&2; exit 1; }
  done
fi

IMAGE_COUNT=0
if (( ${#COLLECTED_IMAGES[@]} > 0 )); then
  IMAGE_COUNT="${#COLLECTED_IMAGES[@]}"
fi
(( IMAGE_COUNT <= MAX_IMAGE_COUNT )) || { echo "At most 16 reference images are allowed; received $IMAGE_COUNT." >&2; exit 1; }
if [[ -n "$MASK_PATH" ]]; then
  [[ -f "$MASK_PATH" && "$MASK_PATH" =~ \.(png|PNG)$ ]] || { echo "--mask must be an existing PNG file." >&2; exit 1; }
  (( $(file_size "$MASK_PATH") < MAX_MASK_SIZE_BYTES )) || { echo "Mask must be less than 4MB." >&2; exit 1; }
  (( IMAGE_COUNT > 0 )) || { echo "--mask requires at least one reference image." >&2; exit 1; }
fi
if [[ -n "$INPUT_FIDELITY" ]] && (( IMAGE_COUNT == 0 )); then
  echo "--input-fidelity requires at least one reference image." >&2; exit 1
fi
if [[ -n "$MODERATION" ]] && (( IMAGE_COUNT > 0 )); then
  echo "--moderation is supported only for generation without reference images." >&2; exit 1
fi

TOKEN="${TOKEN_OVERRIDE:-${FREVANA_TOKEN:-}}"
if [[ -z "$TOKEN" ]]; then
  if [[ -t 0 ]]; then
    read -r -s -p "FREVANA_TOKEN not found. Enter Frevana Bearer token: " TOKEN
    echo >&2
  else
    echo "FREVANA_TOKEN is not set. Set it or pass --token explicitly." >&2
    exit 1
  fi
fi
[[ -n "$TOKEN" ]] || { echo "Bearer token is required." >&2; exit 1; }

PAYLOAD_FILE="$TEMP_DIR/payload.json"
RESPONSE_FILE="$TEMP_DIR/response.json"
RESULT_FILE="$TEMP_DIR/result.json"

if (( IMAGE_COUNT == 0 )); then
  export PROMPT MODEL N SIZE QUALITY BACKGROUND OUTPUT_FORMAT OUTPUT_COMPRESSION MODERATION
  python3 - "$PAYLOAD_FILE" <<'PY'
import json, os, sys
payload = {"prompt": os.environ["PROMPT"], "model": os.environ["MODEL"]}
for env, key in (
    ("SIZE", "size"), ("QUALITY", "quality"), ("BACKGROUND", "background"),
    ("OUTPUT_FORMAT", "output_format"), ("MODERATION", "moderation"),
):
    if os.environ.get(env): payload[key] = os.environ[env]
for env, key in (("N", "n"), ("OUTPUT_COMPRESSION", "output_compression")):
    if os.environ.get(env): payload[key] = int(os.environ[env])
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False)
PY
fi

CURL_ARGS=(-sS --connect-timeout "$CONNECT_TIMEOUT" --max-time "$MAX_TIME" -o "$RESPONSE_FILE" -w '%{http_code}' -X POST "$API_BASE_URL$OPENAI_IMAGE_PATH" -H "Authorization: Bearer $TOKEN")
if [[ -n "${FREVANA_AGENT_APP_INSTANCE_ID:-}" ]]; then
  CURL_ARGS+=(-H "x-frevana-agent-app-instance-id: $FREVANA_AGENT_APP_INSTANCE_ID")
fi
if (( IMAGE_COUNT > 0 )); then
  CURL_ARGS+=(--form-string "prompt=$PROMPT" --form-string "model=$MODEL")
  [[ -n "$N" ]] && CURL_ARGS+=(--form-string "n=$N")
  [[ -n "$SIZE" ]] && CURL_ARGS+=(--form-string "size=$SIZE")
  [[ -n "$QUALITY" ]] && CURL_ARGS+=(--form-string "quality=$QUALITY")
  [[ -n "$BACKGROUND" ]] && CURL_ARGS+=(--form-string "background=$BACKGROUND")
  [[ -n "$OUTPUT_FORMAT" ]] && CURL_ARGS+=(--form-string "output_format=$OUTPUT_FORMAT")
  [[ -n "$OUTPUT_COMPRESSION" ]] && CURL_ARGS+=(--form-string "output_compression=$OUTPUT_COMPRESSION")
  [[ -n "$INPUT_FIDELITY" ]] && CURL_ARGS+=(--form-string "input_fidelity=$INPUT_FIDELITY")
  if (( ${#COLLECTED_IMAGES[@]} > 0 )); then
    for path in "${COLLECTED_IMAGES[@]}"; do CURL_ARGS+=(-F "image=@$path;type=$(mime_for_path "$path")"); done
  fi
  [[ -n "$MASK_PATH" ]] && CURL_ARGS+=(-F "mask=@$MASK_PATH;type=image/png")
else
  CURL_ARGS+=(-H 'Content-Type: application/json' --data "@$PAYLOAD_FILE")
fi

HTTP_CODE="$(curl "${CURL_ARGS[@]}")"
if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "Frevana API request failed with HTTP $HTTP_CODE" >&2
  cat "$RESPONSE_FILE" >&2
  exit 1
fi
[[ -s "$RESPONSE_FILE" ]] || { echo "Frevana API returned an empty response body." >&2; exit 1; }

python3 - "$RESPONSE_FILE" "$RESULT_FILE" <<'PY'
import json, sys
raw = open(sys.argv[1], encoding="utf-8").read()
def fail(message):
    print(message, file=sys.stderr); print(raw, file=sys.stderr); raise SystemExit(1)
try: payload = json.loads(raw)
except json.JSONDecodeError as exc: fail(f"Frevana API returned non-JSON: {exc}")
if not isinstance(payload, dict): fail("Frevana API returned JSON, but not an object.")
for field in ("created", "data", "credits_consumed"):
    if field not in payload: fail(f"Frevana OpenAI response is missing '{field}'.")
if not isinstance(payload["created"], (int, float)): fail("Response 'created' must be numeric.")
if not isinstance(payload["credits_consumed"], (int, float)): fail("Response 'credits_consumed' must be numeric.")
if not isinstance(payload["data"], list) or not payload["data"]: fail("Response 'data' must be a non-empty array.")
for index, item in enumerate(payload["data"]):
    if not isinstance(item, dict): fail(f"Response data item {index} must be an object.")
    if not isinstance(item.get("image_url"), str) or not item["image_url"]: fail(f"Response data item {index} is missing 'image_url'.")
    if "revised_prompt" in item and item["revised_prompt"] is not None and not isinstance(item["revised_prompt"], str):
        fail(f"Response data item {index} 'revised_prompt' must be a string or null.")
for field in ("background", "output_format", "quality", "size"):
    if field in payload and not isinstance(payload[field], str): fail(f"Response '{field}' must be a string when present.")
with open(sys.argv[2], "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2); f.write("\n")
PY

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  cp "$RESULT_FILE" "$OUTPUT_PATH"
fi
cat "$RESULT_FILE"
