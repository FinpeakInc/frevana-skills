#!/usr/bin/env bash

set -euo pipefail

FIXED_PROVIDER="gemini"
DEFAULT_MODEL="gemini-3.1-flash-image"
ALLOWED_MODEL="gemini-3.1-flash-image"
DEFAULT_API_BASE_URL="https://ai-factory.frevana.com"
API_BASE_URL="${FREVANA_API_BASE_URL:-$DEFAULT_API_BASE_URL}"
while [[ "$API_BASE_URL" == */ ]]; do API_BASE_URL="${API_BASE_URL%/}"; done; [[ "$API_BASE_URL" =~ ^https?://[^/?#]+ ]] || { echo "Invalid API base URL after normalisation: ${API_BASE_URL:-<empty>}" >&2; exit 1; }
GEMINI_IMAGE_PATH="/gemini/image/generate"
CONNECT_TIMEOUT="10"
MAX_TIME="600"
MAX_IMAGE_COUNT="14"
MAX_IMAGE_SIZE_BYTES="$((50 * 1024 * 1024))"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

usage() {
  cat <<'EOF'
Usage:
  generate_image.sh (--prompt "image prompt" | --contents "image contents") [options]

Model:
  --model                gemini-3.1-flash-image (default)

Gemini options:
  --job-id               Client UUID for asynchronous generation and 7-day deduplication
  --aspect-ratio         Aspect ratio: 1:1, 1:4, 1:8, 2:3, 3:2, 3:4, 4:1, 4:3, 4:5, 5:4, 8:1, 9:16, 16:9, 21:9
  --image-size           Image resolution: 1K, 2K, 4K (default: 1K)
  --candidate-count, --n Number of candidate images (1-8; image editing supports 1 only)
  --system-instruction   System instruction prompt
  --temperature          Randomness in token selection (0.0 - 2.0; text-to-image only)
  --top-p                Top-p sampling (0.0 - 1.0; text-to-image only)
  --top-k                Top-k sampling (>= 1; text-to-image only)
  --seed                 Random seed for reproducible results
  --image                Reference image path (repeatable, png/jpg/jpeg/webp, <50MB)
  --image-url            Reference HTTP(S) image URL (repeatable)
  --image-dir            Reference image directory (repeatable, recursive, max 14 images total)

Auth & Attribution:
  --api-key              Frevana API key (or FREVANA_API_KEY env)
  --token                Frevana Bearer token (or FREVANA_TOKEN env)
  --agent-app-instance-id Agent App instance/team ID (or FREVANA_AGENT_APP_INSTANCE_ID env)

Other:
  --output               Optional path for returned JSON
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
is_number() { [[ "$1" =~ ^-?[0-9]+([.][0-9]+)?$ ]]; }
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

normalize_image_size() {
  local value="$1"
  local upper
  upper="$(printf '%s' "$value" | tr '[:lower:]' '[:upper:]' | tr -d '[:space:]')"
  case "$upper" in
    1K|2K|4K) printf '%s' "$upper"; return 0 ;;
    *) return 1 ;;
  esac
}

PROMPT=""
MODEL="$DEFAULT_MODEL"
JOB_ID=""
ASPECT_RATIO=""
IMAGE_SIZE=""
CANDIDATE_COUNT=""
SYSTEM_INSTRUCTION=""
TEMPERATURE=""
TOP_P=""
TOP_K=""
SEED=""
API_KEY_OVERRIDE=""
TOKEN_OVERRIDE=""
AGENT_APP_INSTANCE_ID_OVERRIDE=""
OUTPUT_PATH=""
IMAGE_PATHS=()
IMAGE_URLS=()
IMAGE_DIRS=()
COLLECTED_IMAGES=()
DOWNLOAD_INDEX=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prompt|--contents) PROMPT="${2:-}"; shift 2 ;;
    --model) MODEL="${2:-}"; shift 2 ;;
    --job-id) JOB_ID="${2:-}"; shift 2 ;;
    --aspect-ratio) ASPECT_RATIO="${2:-}"; shift 2 ;;
    --image-size) IMAGE_SIZE="${2:-}"; shift 2 ;;
    --candidate-count|--n) CANDIDATE_COUNT="${2:-}"; shift 2 ;;
    --system-instruction) SYSTEM_INSTRUCTION="${2:-}"; shift 2 ;;
    --temperature) TEMPERATURE="${2:-}"; shift 2 ;;
    --top-p) TOP_P="${2:-}"; shift 2 ;;
    --top-k) TOP_K="${2:-}"; shift 2 ;;
    --seed) SEED="${2:-}"; shift 2 ;;
    --image) IMAGE_PATHS+=("${2:-}"); shift 2 ;;
    --image-url) IMAGE_URLS+=("${2:-}"); shift 2 ;;
    --image-dir) IMAGE_DIRS+=("${2:-}"); shift 2 ;;
    --api-key) API_KEY_OVERRIDE="${2:-}"; shift 2 ;;
    --token) TOKEN_OVERRIDE="${2:-}"; shift 2 ;;
    --agent-app-instance-id) AGENT_APP_INSTANCE_ID_OVERRIDE="${2:-}"; shift 2 ;;
    --output) OUTPUT_PATH="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    --provider|--provider=*) echo "This skill fixes --provider=$FIXED_PROVIDER." >&2; exit 1 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done

[[ -n "$PROMPT" ]] || { echo "Missing required argument: --prompt or --contents" >&2; exit 1; }

if [[ "$MODEL" != "$ALLOWED_MODEL" ]]; then
  echo "Invalid model: $MODEL" >&2
  echo "Allowed model for this skill: $ALLOWED_MODEL (use skills/gemini-3-pro-image for gemini-3-pro-image)" >&2
  exit 1
fi

if [[ -n "$ASPECT_RATIO" ]] && ! is_allowed "$ASPECT_RATIO" 1:1 1:4 1:8 2:3 3:2 3:4 4:1 4:3 4:5 5:4 8:1 9:16 16:9 21:9; then
  echo "Invalid --aspect-ratio: $ASPECT_RATIO" >&2
  echo "Allowed aspect ratios: 1:1, 1:4, 1:8, 2:3, 3:2, 3:4, 4:1, 4:3, 4:5, 5:4, 8:1, 9:16, 16:9, 21:9" >&2
  exit 1
fi

if [[ -n "$IMAGE_SIZE" ]]; then
  if ! NORMALIZED_SIZE="$(normalize_image_size "$IMAGE_SIZE")"; then
    echo "Invalid --image-size: $IMAGE_SIZE" >&2
    echo "Allowed image sizes: 1K, 2K, 4K" >&2
    exit 1
  fi
  IMAGE_SIZE="$NORMALIZED_SIZE"
fi

if [[ -n "$CANDIDATE_COUNT" ]] && { ! is_integer "$CANDIDATE_COUNT" || (( CANDIDATE_COUNT < 1 || CANDIDATE_COUNT > 8 )); }; then
  echo "Invalid --candidate-count: $CANDIDATE_COUNT (allowed: 1-8)" >&2
  exit 1
fi

if [[ -n "$TEMPERATURE" ]]; then
  if ! is_number "$TEMPERATURE" || ! python3 -c 'import sys; v = float(sys.argv[1]); sys.exit(0 if 0.0 <= v <= 2.0 else 1)' "$TEMPERATURE" 2>/dev/null; then
    echo "Invalid --temperature: $TEMPERATURE (allowed: 0.0 - 2.0)" >&2
    exit 1
  fi
fi

if [[ -n "$TOP_P" ]]; then
  if ! is_number "$TOP_P" || ! python3 -c 'import sys; v = float(sys.argv[1]); sys.exit(0 if 0.0 <= v <= 1.0 else 1)' "$TOP_P" 2>/dev/null; then
    echo "Invalid --top-p: $TOP_P (allowed: 0.0 - 1.0)" >&2
    exit 1
  fi
fi

if [[ -n "$TOP_K" ]] && { ! is_integer "$TOP_K" || (( TOP_K < 1 )); }; then
  echo "Invalid --top-k: $TOP_K (allowed: integer >= 1)" >&2
  exit 1
fi

if [[ -n "$SEED" ]] && ! is_integer "$SEED"; then
  echo "Invalid --seed: $SEED (allowed: integer)" >&2
  exit 1
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

IMAGE_COUNT="${#COLLECTED_IMAGES[@]}"
(( IMAGE_COUNT <= MAX_IMAGE_COUNT )) || { echo "At most $MAX_IMAGE_COUNT reference images are allowed; received $IMAGE_COUNT." >&2; exit 1; }

if (( IMAGE_COUNT > 0 )); then
  if [[ -n "$CANDIDATE_COUNT" && "$CANDIDATE_COUNT" -gt 1 ]]; then
    echo "Gemini image editing supports candidate_count=1 only." >&2
    exit 1
  fi
  if [[ -n "$TEMPERATURE" ]]; then
    echo "--temperature is supported only for text-to-image generation (no reference images)." >&2
    exit 1
  fi
  if [[ -n "$TOP_P" ]]; then
    echo "--top-p is supported only for text-to-image generation (no reference images)." >&2
    exit 1
  fi
  if [[ -n "$TOP_K" ]]; then
    echo "--top-k is supported only for text-to-image generation (no reference images)." >&2
    exit 1
  fi
fi

API_KEY="${API_KEY_OVERRIDE:-${FREVANA_API_KEY:-}}"
TOKEN="${TOKEN_OVERRIDE:-${FREVANA_TOKEN:-}}"
AGENT_APP_INSTANCE_ID="${AGENT_APP_INSTANCE_ID_OVERRIDE:-${FREVANA_AGENT_APP_INSTANCE_ID:-${X_FREVANA_AGENT_APP_INSTANCE_ID:-}}}"

if [[ -z "$API_KEY" && -z "$TOKEN" ]]; then
  if [[ -t 0 ]]; then
    read -r -s -p "Authentication required. Enter Frevana Bearer token or API key: " TOKEN
    echo >&2
  else
    echo "Authentication required: set FREVANA_API_KEY or FREVANA_TOKEN, or pass --api-key / --token explicitly." >&2
    exit 1
  fi
fi

RESPONSE_FILE="$TEMP_DIR/response.json"
RESULT_FILE="$TEMP_DIR/result.json"

REQUEST_URL="$API_BASE_URL$GEMINI_IMAGE_PATH"
if [[ -n "$JOB_ID" ]]; then
  ENCODED_JOB_ID="$(python3 -c 'import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1]))' "$JOB_ID")"
  REQUEST_URL="$REQUEST_URL?job_id=$ENCODED_JOB_ID"
fi

CURL_ARGS=(
  -sS
  --connect-timeout "$CONNECT_TIMEOUT"
  --max-time "$MAX_TIME"
  -o "$RESPONSE_FILE"
  -w '%{http_code}'
  -X POST "$REQUEST_URL"
)

if [[ -n "$API_KEY" ]]; then
  CURL_ARGS+=(-H "X-API-Key: $API_KEY")
fi
if [[ -n "$TOKEN" ]]; then
  CURL_ARGS+=(-H "Authorization: Bearer $TOKEN")
fi
if [[ -n "$AGENT_APP_INSTANCE_ID" ]]; then
  CURL_ARGS+=(-H "x-frevana-agent-app-instance-id: $AGENT_APP_INSTANCE_ID")
fi

CURL_ARGS+=(--form-string "prompt=$PROMPT" --form-string "model=$MODEL")
[[ -n "$ASPECT_RATIO" ]] && CURL_ARGS+=(--form-string "aspect_ratio=$ASPECT_RATIO")
[[ -n "$IMAGE_SIZE" ]] && CURL_ARGS+=(--form-string "image_size=$IMAGE_SIZE")
[[ -n "$CANDIDATE_COUNT" ]] && CURL_ARGS+=(--form-string "candidate_count=$CANDIDATE_COUNT")
[[ -n "$SYSTEM_INSTRUCTION" ]] && CURL_ARGS+=(--form-string "system_instruction=$SYSTEM_INSTRUCTION")
[[ -n "$TEMPERATURE" ]] && CURL_ARGS+=(--form-string "temperature=$TEMPERATURE")
[[ -n "$TOP_P" ]] && CURL_ARGS+=(--form-string "top_p=$TOP_P")
[[ -n "$TOP_K" ]] && CURL_ARGS+=(--form-string "top_k=$TOP_K")
[[ -n "$SEED" ]] && CURL_ARGS+=(--form-string "seed=$SEED")

if (( IMAGE_COUNT > 0 )); then
  for path in "${COLLECTED_IMAGES[@]}"; do
    CURL_ARGS+=(-F "image=@$path;type=$(mime_for_path "$path")")
  done
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
try:
    payload = json.loads(raw)
except json.JSONDecodeError as exc:
    fail(f"Frevana API returned non-JSON: {exc}")
if not isinstance(payload, dict):
    fail("Frevana API returned JSON, but not an object.")

# Check for synchronous generated images (either generated_images or data) or async response
if "generated_images" in payload:
    if not isinstance(payload["generated_images"], list) or not payload["generated_images"]:
        fail("Response field 'generated_images' must be a non-empty array.")
    for index, item in enumerate(payload["generated_images"]):
        if not isinstance(item, dict):
            fail(f"Response generated_images item {index} must be an object.")
        if not isinstance(item.get("image_url"), str) or not item["image_url"]:
            fail(f"Response generated_images item {index} is missing 'image_url'.")
elif "data" in payload:
    if not isinstance(payload["data"], list) or not payload["data"]:
        fail("Response field 'data' must be a non-empty array.")
    for index, item in enumerate(payload["data"]):
        if not isinstance(item, dict):
            fail(f"Response data item {index} must be an object.")
        if not isinstance(item.get("image_url"), str) or not item["image_url"]:
            fail(f"Response data item {index} is missing 'image_url'.")
elif "job_id" in payload or "task_id" in payload or "status" in payload:
    pass
else:
    fail("Response JSON must contain 'generated_images', 'data', or async job status.")

with open(sys.argv[2], "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)
    f.write("\n")
PY

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  cp "$RESULT_FILE" "$OUTPUT_PATH"
fi
cat "$RESULT_FILE"
