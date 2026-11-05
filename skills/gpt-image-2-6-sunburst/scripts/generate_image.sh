#!/usr/bin/env bash

set -euo pipefail

FIXED_PROVIDER="openai"
FIXED_MODEL="gpt-image-2.6-sunburst"
DEFAULT_API_BASE_URL="https://ai-factory.frevana.com"
API_BASE_URL="${FREVANA_API_BASE_URL:-$DEFAULT_API_BASE_URL}"
while [[ "$API_BASE_URL" == */ ]]; do API_BASE_URL="${API_BASE_URL%/}"; done; [[ "$API_BASE_URL" =~ ^https?://[^/?#]+(/[^?#]*)?$ ]] || { echo "Invalid API base URL after normalisation: ${API_BASE_URL:-<empty>}" >&2; exit 1; }
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

Fixed backend:
  Provider: openai
  Model: gpt-image-2.6-sunburst (not configurable)

OpenAI image options:
  --n                    Number of images (1-10)
  --size                 auto or positive WIDTHxHEIGHT dimensions divisible by 16
                         GIF defaults to auto; explicit values are per-frame sizes
  --quality              auto, low, medium, high, xhigh, or max
  --complexity           low, medium, or high (planning effort; upstream default high)
  --background           auto, opaque, or transparent
  --output-format        png, jpeg, webp, or gif (GIF is text-only generation)
  --frame-count          GIF frames (2-16; server default 9)
  --frame-duration-ms    GIF frame delay (20-2000; server default 200)
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

is_integer_in_range() {
  python3 - "$1" "$2" "$3" <<'PYINT'
import re, sys
value, lower, upper = sys.argv[1:]
valid = bool(re.fullmatch(r"[0-9]+", value)) and int(lower) <= int(value) <= int(upper)
raise SystemExit(0 if valid else 1)
PYINT
}
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

curl_file_form() {
  local field="$1" path="$2" mime="$3"
  # curl parses -F separately from the shell: quote the path and escape its
  # backslashes/quotes so commas and semicolons cannot select other files.
  path="${path//\\/\\\\}"
  path="${path//\"/\\\"}"
  printf '%s=@"%s";type=%s' "$field" "$path" "$mime"
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
suffix = path.rsplit(".", 1)[-1].lower()
if suffix == "png" and header[:8] == b"\x89PNG\r\n\x1a\n":
    raise SystemExit(0)
if suffix in {"jpg", "jpeg"} and header[:3] == b"\xff\xd8\xff":
    raise SystemExit(0)
if suffix == "webp" and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
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
  (( ${#COLLECTED_IMAGES[@]} <= MAX_IMAGE_COUNT )) || { echo "At most 16 reference images are allowed." >&2; exit 1; }
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

append_image_directory() {
  local directory="$1" found_image=0 path
  [[ -d "$directory" ]] || { echo "Image directory not found: $directory" >&2; exit 1; }
  while IFS= read -r -d '' path; do
    found_image=1
    append_image "$path"
  done < <(
    find "$directory" -type f \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.webp' \) -print0 | LC_ALL=C sort -z
  )
  (( found_image )) || { echo "No supported images found in directory: $directory" >&2; exit 1; }
}

validate_size() {
  python3 - "$1" "$OUTPUT_FORMAT" <<'PY'
import re, sys
value = sys.argv[1]
if value == "auto":
    raise SystemExit(0)
match = re.fullmatch(r"([0-9]+)x([0-9]+)", value)
if not match:
    raise SystemExit(1)
w, h = map(int, match.groups())
valid = (
    w > 0 and h > 0 and w % 16 == 0 and h % 16 == 0
    and w * h <= 9007199254740991
    and (sys.argv[2] == "gif" or max(w, h) <= 3 * min(w, h))
)
raise SystemExit(0 if valid else 1)
PY
}

PROMPT=""
MODEL="$FIXED_MODEL"
N=""
SIZE=""
QUALITY=""
COMPLEXITY=""
BACKGROUND=""
OUTPUT_FORMAT=""
FRAME_COUNT=""
FRAME_DURATION_MS=""
OUTPUT_COMPRESSION=""
MODERATION=""
INPUT_FIDELITY=""
OUTPUT_PATH=""
TOKEN_OVERRIDE=""
MASK_PATH=""
REFERENCE_INPUT_TYPES=()
REFERENCE_INPUT_VALUES=()
COLLECTED_IMAGES=()
DOWNLOAD_INDEX=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prompt|--contents|--n|--size|--quality|--complexity|--background|--output-format|--frame-count|--frame-duration-ms|--output-compression|--moderation|--input-fidelity|--image|--image-url|--image-dir|--mask|--output|--token)
      [[ $# -ge 2 && -n "$2" ]] || { echo "Missing or empty value for $1." >&2; exit 1; }
      ;;
  esac
  case "$1" in
    --prompt|--contents) PROMPT="${2:-}"; shift 2 ;;
    --n) N="${2:-}"; shift 2 ;;
    --size) SIZE="${2:-}"; shift 2 ;;
    --quality) QUALITY="${2:-}"; shift 2 ;;
    --complexity) COMPLEXITY="${2:-}"; shift 2 ;;
    --background) BACKGROUND="${2:-}"; shift 2 ;;
    --output-format) OUTPUT_FORMAT="${2:-}"; shift 2 ;;
    --frame-count) FRAME_COUNT="${2:-}"; shift 2 ;;
    --frame-duration-ms) FRAME_DURATION_MS="${2:-}"; shift 2 ;;
    --output-compression) OUTPUT_COMPRESSION="${2:-}"; shift 2 ;;
    --moderation) MODERATION="${2:-}"; shift 2 ;;
    --input-fidelity) INPUT_FIDELITY="${2:-}"; shift 2 ;;
    --image|--image-url|--image-dir)
      REFERENCE_INPUT_TYPES+=("$1")
      REFERENCE_INPUT_VALUES+=("$2")
      shift 2
      ;;
    --mask) MASK_PATH="${2:-}"; shift 2 ;;
    --output) OUTPUT_PATH="${2:-}"; shift 2 ;;
    --token) TOKEN_OVERRIDE="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    --model|--model=*) echo "This skill fixes --model=$FIXED_MODEL." >&2; exit 1 ;;
    --provider|--provider=*) echo "This skill fixes --provider=$FIXED_PROVIDER." >&2; exit 1 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done

[[ -n "$PROMPT" ]] || { echo "Missing required argument: --prompt or --contents" >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "curl is required." >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is required." >&2; exit 1; }

if [[ -n "$N" ]] && ! is_integer_in_range "$N" 1 10; then
  echo "Invalid --n: $N (allowed: 1-10)" >&2; exit 1
fi
if [[ -n "$SIZE" ]] && ! validate_size "$SIZE"; then
  echo "Invalid --size: $SIZE" >&2
  echo "Use auto or positive WIDTHxHEIGHT dimensions divisible by 16 (static aspect ratio <=3:1). Provider pixel/edge limits still apply." >&2
  exit 1
fi
if [[ -n "$QUALITY" ]] && ! is_allowed "$QUALITY" auto low medium high xhigh max; then
  echo "Invalid --quality: $QUALITY" >&2; exit 1
fi
if [[ -n "$COMPLEXITY" ]] && ! is_allowed "$COMPLEXITY" low medium high; then
  echo "Invalid --complexity: $COMPLEXITY" >&2; exit 1
fi
if [[ -n "$BACKGROUND" ]] && ! is_allowed "$BACKGROUND" auto opaque transparent; then
  echo "Invalid --background: $BACKGROUND" >&2; exit 1
fi
if [[ -n "$OUTPUT_FORMAT" ]] && ! is_allowed "$OUTPUT_FORMAT" png jpeg webp gif; then
  echo "Invalid --output-format: $OUTPUT_FORMAT" >&2; exit 1
fi
if [[ -n "$OUTPUT_COMPRESSION" ]] && ! is_integer_in_range "$OUTPUT_COMPRESSION" 1 100; then
  echo "Invalid --output-compression: $OUTPUT_COMPRESSION (allowed: 1-100)" >&2; exit 1
fi
if [[ -n "$MODERATION" ]] && ! is_allowed "$MODERATION" auto low; then
  echo "Invalid --moderation: $MODERATION" >&2; exit 1
fi
if [[ -n "$INPUT_FIDELITY" ]] && ! is_allowed "$INPUT_FIDELITY" low high; then
  echo "Invalid --input-fidelity: $INPUT_FIDELITY" >&2; exit 1
fi
if [[ -n "$FRAME_COUNT" ]] && ! is_integer_in_range "$FRAME_COUNT" 2 16; then
  echo "Invalid --frame-count: $FRAME_COUNT (allowed: 2-16)" >&2; exit 1
fi
if [[ -n "$FRAME_DURATION_MS" ]] && ! is_integer_in_range "$FRAME_DURATION_MS" 20 2000; then
  echo "Invalid --frame-duration-ms: $FRAME_DURATION_MS (allowed: 20-2000)" >&2; exit 1
fi
if [[ "$OUTPUT_FORMAT" != gif && ( -n "$FRAME_COUNT" || -n "$FRAME_DURATION_MS" ) ]]; then
  echo "--frame-count and --frame-duration-ms require --output-format gif." >&2; exit 1
fi
if [[ "$OUTPUT_FORMAT" == gif ]] && { (( ${#REFERENCE_INPUT_TYPES[@]} > 0 )) || [[ -n "$MASK_PATH" || -n "$INPUT_FIDELITY" ]]; }; then
  echo "GIF output supports text-only generation; reference images, masks and input fidelity are not supported." >&2; exit 1
fi
if [[ "$BACKGROUND" == transparent && ( "$OUTPUT_FORMAT" == jpeg || "$OUTPUT_FORMAT" == gif ) ]]; then
  echo "Transparent backgrounds require png or webp output." >&2; exit 1
fi
if [[ -n "$OUTPUT_COMPRESSION" && "$OUTPUT_FORMAT" != jpeg && "$OUTPUT_FORMAT" != webp ]]; then
  echo "--output-compression requires --output-format jpeg or webp." >&2; exit 1
fi

if [[ "$BACKGROUND" == transparent && -z "$OUTPUT_FORMAT" ]]; then
  OUTPUT_FORMAT=png
fi
if [[ "$OUTPUT_FORMAT" == gif && -z "$SIZE" ]]; then
  SIZE=auto
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

# Preserve input order: the upstream mask applies to the first reference.
if (( ${#REFERENCE_INPUT_TYPES[@]} > 0 )); then
  for reference_index in "${!REFERENCE_INPUT_TYPES[@]}"; do
    case "${REFERENCE_INPUT_TYPES[$reference_index]}" in
      --image) append_image "${REFERENCE_INPUT_VALUES[$reference_index]}" ;;
      --image-url) download_image "${REFERENCE_INPUT_VALUES[$reference_index]}" ;;
      --image-dir) append_image_directory "${REFERENCE_INPUT_VALUES[$reference_index]}" ;;
    esac
  done
fi

IMAGE_COUNT=0
if (( ${#COLLECTED_IMAGES[@]} > 0 )); then
  IMAGE_COUNT="${#COLLECTED_IMAGES[@]}"
fi
(( IMAGE_COUNT <= MAX_IMAGE_COUNT )) || { echo "At most 16 reference images are allowed; received $IMAGE_COUNT." >&2; exit 1; }
if [[ -n "$MASK_PATH" ]]; then
  [[ -f "$MASK_PATH" && "$MASK_PATH" =~ \.(png|PNG)$ ]] || { echo "--mask must be an existing PNG file." >&2; exit 1; }
  verify_image_magic "$MASK_PATH" || { echo "Mask must contain PNG image data." >&2; exit 1; }
  (( $(file_size "$MASK_PATH") < MAX_MASK_SIZE_BYTES )) || { echo "Mask must be less than 4MB." >&2; exit 1; }
  (( IMAGE_COUNT > 0 )) || { echo "--mask requires at least one reference image." >&2; exit 1; }
fi
if [[ -n "$INPUT_FIDELITY" ]] && (( IMAGE_COUNT == 0 )); then
  echo "--input-fidelity requires at least one reference image." >&2; exit 1
fi
if [[ -n "$MODERATION" ]] && (( IMAGE_COUNT > 0 )); then
  echo "--moderation is supported only for generation without reference images." >&2; exit 1
fi

PAYLOAD_FILE="$TEMP_DIR/payload.json"
RESPONSE_FILE="$TEMP_DIR/response.json"
RESULT_FILE="$TEMP_DIR/result.json"

if (( IMAGE_COUNT == 0 )); then
  export PROMPT MODEL N SIZE QUALITY COMPLEXITY BACKGROUND OUTPUT_FORMAT OUTPUT_COMPRESSION MODERATION FRAME_COUNT FRAME_DURATION_MS
  python3 - "$PAYLOAD_FILE" <<'PY'
import json, os, sys
payload = {"prompt": os.environ["PROMPT"], "model": os.environ["MODEL"]}
for env, key in (
    ("SIZE", "size"), ("QUALITY", "quality"), ("COMPLEXITY", "complexity"), ("BACKGROUND", "background"),
    ("OUTPUT_FORMAT", "output_format"), ("MODERATION", "moderation"),
):
    if os.environ.get(env): payload[key] = os.environ[env]
for env, key in (
    ("N", "n"), ("OUTPUT_COMPRESSION", "output_compression"),
    ("FRAME_COUNT", "frame_count"), ("FRAME_DURATION_MS", "frame_duration_ms"),
):
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
  [[ -n "$COMPLEXITY" ]] && CURL_ARGS+=(--form-string "complexity=$COMPLEXITY")
  [[ -n "$BACKGROUND" ]] && CURL_ARGS+=(--form-string "background=$BACKGROUND")
  [[ -n "$OUTPUT_FORMAT" ]] && CURL_ARGS+=(--form-string "output_format=$OUTPUT_FORMAT")
  [[ -n "$OUTPUT_COMPRESSION" ]] && CURL_ARGS+=(--form-string "output_compression=$OUTPUT_COMPRESSION")
  [[ -n "$INPUT_FIDELITY" ]] && CURL_ARGS+=(--form-string "input_fidelity=$INPUT_FIDELITY")
  if (( ${#COLLECTED_IMAGES[@]} > 0 )); then
    for path in "${COLLECTED_IMAGES[@]}"; do
      CURL_ARGS+=(-F "$(curl_file_form image "$path" "$(mime_for_path "$path")")")
    done
  fi
  [[ -n "$MASK_PATH" ]] && CURL_ARGS+=(-F "$(curl_file_form mask "$MASK_PATH" image/png)")
else
  CURL_ARGS+=(-H 'Content-Type: application/json' --data "@$PAYLOAD_FILE")
fi

if ! HTTP_CODE="$(curl "${CURL_ARGS[@]}")"; then
  echo "Frevana request failed during transport; the generation outcome may be unknown. Do not automatically retry." >&2
  [[ ! -s "$RESPONSE_FILE" ]] || cat "$RESPONSE_FILE" >&2
  exit 1
fi
if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "Frevana API request failed with HTTP $HTTP_CODE" >&2
  cat "$RESPONSE_FILE" >&2
  if [[ "$OUTPUT_FORMAT" == gif && "$HTTP_CODE" == 400 ]]; then
    python3 - "$RESPONSE_FILE" "$SIZE" <<'PYGIF' >&2
import json, sys
try:
    payload = json.loads(open(sys.argv[1], encoding="utf-8").read())
except (OSError, ValueError):
    raise SystemExit(0)
if not isinstance(payload, dict) or payload.get("code") != "invalid_value":
    raise SystemExit(0)
message = payload.get("message")
if not isinstance(message, str) or "no supported sheet fits" not in message.lower():
    raise SystemExit(0)
print("\nOpenAI rejected its internal GIF sheet layout. Fewer frames do not guarantee a supported size.")
if sys.argv[2] == "auto":
    print("GIF size=auto was also rejected. Stop and preserve the original error for provider investigation.")
else:
    print("For a new request, use --size auto if adaptive frame dimensions meet the user's requirements; preserve the desired frame count and timing.")
    print("Do not promise native 1024x1024 output or silently change an explicitly required native size.")
print("No retry was made. Do not guess progressively smaller frame counts or automatically resubmit.")
PYGIF
  fi
  exit 1
fi
[[ -s "$RESPONSE_FILE" ]] || { echo "Frevana API returned an empty response body." >&2; exit 1; }

python3 - "$RESPONSE_FILE" "$RESULT_FILE" <<'PY'
import json, math, sys
raw = open(sys.argv[1], encoding="utf-8").read()
def fail(message):
    print(message, file=sys.stderr); print(raw, file=sys.stderr); raise SystemExit(1)
try: payload = json.loads(raw)
except json.JSONDecodeError as exc: fail(f"Frevana API returned non-JSON: {exc}")
if not isinstance(payload, dict): fail("Frevana API returned JSON, but not an object.")
for field in ("created", "data", "credits_consumed"):
    if field not in payload: fail(f"Frevana OpenAI response is missing '{field}'.")
for field in ("created", "credits_consumed"):
    value = payload[field]
    if type(value) not in (int, float) or not math.isfinite(value):
        fail(f"Response '{field}' must be finite and numeric.")
if not isinstance(payload["data"], list) or not payload["data"]: fail("Response 'data' must be a non-empty array.")
for index, item in enumerate(payload["data"]):
    if not isinstance(item, dict): fail(f"Response data item {index} must be an object.")
    if not isinstance(item.get("image_url"), str) or not item["image_url"]: fail(f"Response data item {index} is missing 'image_url'.")
    if "revised_prompt" in item and item["revised_prompt"] is not None and not isinstance(item["revised_prompt"], str):
        fail(f"Response data item {index} 'revised_prompt' must be a string or null.")
for field in ("background", "output_format", "quality", "size"):
    if field in payload and not isinstance(payload[field], str): fail(f"Response '{field}' must be a string when present.")
with open(sys.argv[2], "w", encoding="utf-8") as f:
    f.write(raw)
PY

if [[ -n "$OUTPUT_PATH" ]]; then
  if ! { mkdir -p "$(dirname "$OUTPUT_PATH")" && cp "$RESULT_FILE" "$OUTPUT_PATH"; }; then
    echo "Generation completed, but JSON could not be saved to $OUTPUT_PATH. Recover the result from stdout; do not regenerate." >&2
    cat "$RESULT_FILE"
    exit 1
  fi
fi
cat "$RESULT_FILE"
