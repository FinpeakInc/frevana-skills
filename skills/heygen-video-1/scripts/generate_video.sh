#!/usr/bin/env bash

set -euo pipefail

DEFAULT_MODEL="heygen/heygen-video-1"
ALLOWED_MODELS=("heygen/heygen-video-1")
ALLOWED_RESOLUTIONS=("480p" "768p" "1080p" "2K")
ALLOWED_ASPECT_RATIOS=("16:9" "4:3" "1:1" "3:4" "9:16" "21:9")
ALLOWED_DURATIONS=("5" "6" "7" "8" "9" "10" "11" "12" "13" "14" "15" "16" "17" "18" "19" "20" "21" "22" "23" "24" "25" "26" "27" "28" "29" "30")
SUPPORTED_FRAME_IMAGES=("first_frame")
SUPPORTED_INPUT_REFERENCES=("image_url" "audio_url" "video_url")

DEFAULT_RESOLUTION="768p"
DEFAULT_ASPECT_RATIO="16:9"
DEFAULT_DURATION="5"

DEFAULT_API_BASE_URL="https://ai-factory.frevana.com"
API_BASE_URL="${FREVANA_API_BASE_URL:-$DEFAULT_API_BASE_URL}"
while [[ "$API_BASE_URL" == */ ]]; do API_BASE_URL="${API_BASE_URL%/}"; done; [[ "$API_BASE_URL" =~ ^https?://[^/?#]+(/[^?#]*)?$ ]] || { echo "Invalid API base URL after normalisation: ${API_BASE_URL:-<empty>}" >&2; exit 1; }
VIDEOS_PATH="/openrouter/v1/videos"
CONNECT_TIMEOUT="15"
MAX_TIME="600"

TEMP_DIR="$(mktemp -d)"
DOWNLOAD_TEMP=""
trap 'rm -rf "$TEMP_DIR"; [[ -z "$DOWNLOAD_TEMP" ]] || rm -f "$DOWNLOAD_TEMP"' EXIT

usage() {
  cat <<EOF
Usage:
  $(basename "$0") [create|status|wait] [options]

Commands:
  create                 Submit a video generation job (default when --prompt is given)
  status                 Check the status of an existing video job
  wait                   Wait for an existing video job to complete

Options:
  -p, --prompt TEXT      Text prompt describing the video
  --prompt-file PATH     Path to file containing the prompt
  --model MODEL          Model slug (default: $DEFAULT_MODEL, allowed: ${ALLOWED_MODELS[*]})
  --duration SEC         Duration in seconds (allowed: 5-30, default: $DEFAULT_DURATION)
  --aspect-ratio RATIO   Aspect ratio (allowed: ${ALLOWED_ASPECT_RATIOS[*]}, default: $DEFAULT_ASPECT_RATIO)
  --resolution RES       Resolution (allowed: ${ALLOWED_RESOLUTIONS[*]}, default: $DEFAULT_RESOLUTION)
  --size WIDTHxHEIGHT    Exact output dimensions; overrides resolution and aspect ratio
  --first-frame PATH/URL Image path or URL for the first frame
  --image PATH/URL       Alias for --first-frame
  --reference-image PATH/URL
                         Add a reference image (repeatable)
  --reference-audio URL  Add a reference audio URL (repeatable)
  --reference-video URL  Add a reference video URL (repeatable)
  --seed INT             Unsigned 32-bit seed (0-4294967295)
  --prompt-enhancement MODE
                         turbo, quality (default), ultraquality, disabled
  --job-id ID            Job ID for status or wait commands
  --wait                 Wait for job completion (default in direct CLI usage)
  --no-wait              Submit job and return immediately without waiting
  --poll-interval SEC    Seconds between status checks (default: 10)
  --max-wait SEC         Maximum seconds to wait before timeout (default: 600)
  --download-dir DIR     Directory to download the completed video
  --output, -o FILE      Path to save output JSON or MP4 file
  -t, --text-only        Output only the video URL or downloaded file path
  --dry-run              Print payload JSON and exit without making network requests

Auth & Headers:
  --token TOKEN          Frevana JWT Bearer token (or FREVANA_TOKEN env)
  --agent-app-instance-id ID
                         Agent App instance/team ID (or FREVANA_AGENT_APP_INSTANCE_ID env)
  --api-base-url URL     API base URL override
  -h, --help             Show this help message
EOF
}

is_allowed() {
  local value="$1"
  shift
  local item
  for item in "$@"; do
    [[ "$value" == "$item" ]] && return 0
  done
  return 1
}

COMMAND=""
if [[ $# -gt 0 ]]; then
  case "$1" in
    create|status|wait)
      COMMAND="$1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
  esac
fi

PROMPT=""
PROMPT_FILE=""
MODEL="$DEFAULT_MODEL"
DURATION="$DEFAULT_DURATION"
ASPECT_RATIO="$DEFAULT_ASPECT_RATIO"
RESOLUTION="$DEFAULT_RESOLUTION"
SIZE=""
FIRST_FRAME=""
LAST_FRAME=""
REFERENCE_IMAGES=()
REFERENCE_AUDIOS=()
REFERENCE_VIDEOS=()
SEED=""
PROMPT_ENHANCEMENT="quality"
JOB_ID=""
DO_WAIT=1
POLL_INTERVAL=10
MAX_WAIT=600
DOWNLOAD_DIR=""
OUTPUT_FILE=""
TEXT_ONLY=0
DRY_RUN=0
TOKEN_OVERRIDE=""
AGENT_APP_INSTANCE_ID_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--prompt|--prompt-file|--model|--duration|--aspect-ratio|--resolution|--size|--first-frame|--image|--last-frame|--reference-image|--reference-audio|--reference-video|--seed|--prompt-enhancement|--job-id|--poll-interval|--max-wait|--download-dir|-o|--output|--token|--api-key|--agent-app-instance-id|--api-base-url)
      if [[ $# -lt 2 || -z "$2" || "$2" == --* ]]; then
        echo "Error: $1 requires a value." >&2
        exit 1
      fi
      ;;
  esac
  case "$1" in
    -p|--prompt) PROMPT="${2:-}"; shift 2 ;;
    --prompt-file) PROMPT_FILE="${2:-}"; shift 2 ;;
    --model) MODEL="${2:-}"; shift 2 ;;
    --duration) DURATION="${2:-}"; shift 2 ;;
    --aspect-ratio) ASPECT_RATIO="${2:-}"; shift 2 ;;
    --resolution) RESOLUTION="${2:-}"; shift 2 ;;
    --size) SIZE="${2:-}"; shift 2 ;;
    --first-frame|--image) FIRST_FRAME="${2:-}"; shift 2 ;;
    --last-frame) LAST_FRAME="${2:-}"; shift 2 ;;
    --reference-image) REFERENCE_IMAGES+=("${2:-}"); shift 2 ;;
    --reference-audio) REFERENCE_AUDIOS+=("${2:-}"); shift 2 ;;
    --reference-video) REFERENCE_VIDEOS+=("${2:-}"); shift 2 ;;
    --audio|--no-audio) echo "Error: HeyGen generates native audio; no audio toggle is supported. Omit --audio/--no-audio." >&2; exit 1 ;;
    --seed) SEED="${2:-}"; shift 2 ;;
    --prompt-enhancement) PROMPT_ENHANCEMENT="${2:-}"; shift 2 ;;
    --job-id) JOB_ID="${2:-}"; shift 2 ;;
    --wait) DO_WAIT=1; shift ;;
    --no-wait) DO_WAIT=0; shift ;;
    --poll-interval) POLL_INTERVAL="${2:-}"; shift 2 ;;
    --max-wait) MAX_WAIT="${2:-}"; shift 2 ;;
    --download-dir) DOWNLOAD_DIR="${2:-}"; shift 2 ;;
    -o|--output) OUTPUT_FILE="${2:-}"; shift 2 ;;
    -t|--text-only) TEXT_ONLY=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --token) TOKEN_OVERRIDE="${2:-}"; shift 2 ;;
    --api-key) echo "Error: This Frevana video route requires a JWT Bearer token; API key authentication is not supported. Use FREVANA_TOKEN or --token." >&2; exit 1 ;;
    --agent-app-instance-id) AGENT_APP_INSTANCE_ID_OVERRIDE="${2:-}"; shift 2 ;;
    --api-base-url) API_BASE_URL="${2:-}"; while [[ "$API_BASE_URL" == */ ]]; do API_BASE_URL="${API_BASE_URL%/}"; done; [[ "$API_BASE_URL" =~ ^https?://[^/?#]+(/[^?#]*)?$ ]] || { echo "Invalid API base URL after normalisation: ${API_BASE_URL:-<empty>}" >&2; exit 1; }; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *)
      if [[ -z "$COMMAND" && -z "$JOB_ID" && "$1" != -* && "$1" =~ ^[A-Za-z0-9_-]{10,}$ ]]; then
        JOB_ID="$1"
        shift
      else
        echo "Unknown argument: $1" >&2
        usage >&2
        exit 1
      fi
      ;;
  esac
done

if [[ -z "$COMMAND" ]]; then
  if [[ -n "$JOB_ID" ]]; then
    COMMAND="status"
  else
    COMMAND="create"
  fi
fi

if ! is_allowed "$MODEL" "${ALLOWED_MODELS[@]}"; then
  echo "Error: Invalid model '$MODEL'. Allowed: ${ALLOWED_MODELS[*]}" >&2
  exit 1
fi

if [[ -n "$DURATION" ]] && ! is_allowed "$DURATION" "${ALLOWED_DURATIONS[@]}"; then
  echo "Error: Invalid duration '$DURATION' for model $MODEL. Allowed durations: ${ALLOWED_DURATIONS[*]}" >&2
  exit 1
fi

if [[ -z "$SIZE" && -n "$RESOLUTION" ]] && ! is_allowed "$RESOLUTION" "${ALLOWED_RESOLUTIONS[@]}"; then
  echo "Error: Invalid resolution '$RESOLUTION' for model $MODEL. Allowed resolutions: ${ALLOWED_RESOLUTIONS[*]}" >&2
  exit 1
fi

if [[ -z "$SIZE" && -n "$ASPECT_RATIO" ]] && ! is_allowed "$ASPECT_RATIO" "${ALLOWED_ASPECT_RATIOS[@]}"; then
  echo "Error: Invalid aspect ratio '$ASPECT_RATIO' for model $MODEL. Allowed aspect ratios: ${ALLOWED_ASPECT_RATIOS[*]}" >&2
  exit 1
fi

if [[ -n "$SIZE" ]]; then
  [[ "$SIZE" =~ ^[1-9][0-9]*x[1-9][0-9]*$ ]] || { echo "Error: Invalid size '$SIZE'. Expected WIDTHxHEIGHT with positive integers." >&2; exit 1; }
fi

if [[ -n "$LAST_FRAME" ]] && ! is_allowed "last_frame" "${SUPPORTED_FRAME_IMAGES[@]}"; then
  echo "Error: Model $MODEL does not support --last-frame." >&2
  exit 1
fi

if [[ -n "$FIRST_FRAME" ]] && ! is_allowed "first_frame" "${SUPPORTED_FRAME_IMAGES[@]}"; then
  echo "Error: Model $MODEL does not support image-to-video / --first-frame." >&2
  exit 1
fi

if [[ ${#REFERENCE_IMAGES[@]} -gt 0 ]] && ! is_allowed "image_url" ${SUPPORTED_INPUT_REFERENCES[@]+"${SUPPORTED_INPUT_REFERENCES[@]}"}; then echo "Error: Model $MODEL does not support image input references." >&2; exit 1; fi
if [[ ${#REFERENCE_AUDIOS[@]} -gt 0 ]] && ! is_allowed "audio_url" ${SUPPORTED_INPUT_REFERENCES[@]+"${SUPPORTED_INPUT_REFERENCES[@]}"}; then echo "Error: Model $MODEL does not support audio input references." >&2; exit 1; fi
if [[ ${#REFERENCE_VIDEOS[@]} -gt 0 ]] && ! is_allowed "video_url" ${SUPPORTED_INPUT_REFERENCES[@]+"${SUPPORTED_INPUT_REFERENCES[@]}"}; then echo "Error: Model $MODEL does not support video input references." >&2; exit 1; fi
for reference_url in ${REFERENCE_AUDIOS[@]+"${REFERENCE_AUDIOS[@]}"} ${REFERENCE_VIDEOS[@]+"${REFERENCE_VIDEOS[@]}"}; do [[ "$reference_url" == http://* || "$reference_url" == https://* ]] || { echo "Error: Audio and video references must be HTTP(S) URLs." >&2; exit 1; }; done

if ! is_allowed "$PROMPT_ENHANCEMENT" turbo quality ultraquality disabled; then
  echo "Error: Invalid prompt enhancement. Choose turbo, quality, ultraquality, or disabled." >&2
  exit 1
fi
REFERENCE_COUNT=$((${#REFERENCE_IMAGES[@]} + ${#REFERENCE_AUDIOS[@]} + ${#REFERENCE_VIDEOS[@]}))
# OpenRouter selects image-to-video whenever frameImages is present, even if
# inputReferences is also supplied. Provider reference-mode limits apply only
# when references actually select the mode.
if [[ -z "$FIRST_FRAME" ]] && [[ ${#REFERENCE_IMAGES[@]} -gt 9 || ${#REFERENCE_AUDIOS[@]} -gt 3 || ${#REFERENCE_VIDEOS[@]} -gt 3 ]]; then
  echo "Error: At most 9 image, 3 audio, and 3 video references are supported." >&2
  exit 1
fi
if [[ -n "$FIRST_FRAME" && "$REFERENCE_COUNT" -gt 0 ]]; then
  echo "Note: OpenRouter gives frameImages precedence over inputReferences and selects image-to-video." >&2
fi
if [[ -z "$FIRST_FRAME" && ${#REFERENCE_AUDIOS[@]} -gt 0 && ${#REFERENCE_IMAGES[@]} -eq 0 && ${#REFERENCE_VIDEOS[@]} -eq 0 ]]; then
  echo "Error: Audio references require at least one reference image or video." >&2
  exit 1
fi
if [[ "$DURATION" -gt 15 ]] && { [[ -z "$FIRST_FRAME" && "$REFERENCE_COUNT" -gt 0 ]] || ! is_allowed "$PROMPT_ENHANCEMENT" turbo quality; }; then
  echo "Error: Durations above 15 seconds require text/first-frame generation with turbo or quality enhancement; reference generation is limited to 15 seconds." >&2
  exit 1
fi
if [[ -z "$SIZE" && -z "$FIRST_FRAME" ]] && is_allowed "$RESOLUTION" 1080p 2K && ! is_allowed "$ASPECT_RATIO" 16:9 9:16; then
  echo "Error: 1080p/2K text and reference generation requires aspect ratio 16:9 or 9:16." >&2
  exit 1
fi
python3 - "$SEED" "$POLL_INTERVAL" "$MAX_WAIT" <<'PY'
import sys
for value, name, minimum, maximum in (
    (sys.argv[1], "seed", 0, 4294967295),
    (sys.argv[2], "poll interval", 1, 2147483647),
    (sys.argv[3], "max wait", 1, 2147483647),
):
    if name == "seed" and not value:
        continue
    if not value.isascii() or not value.isdecimal() or not minimum <= int(value) <= maximum:
        sys.exit(f"Error: Invalid {name}; expected an integer from {minimum} to {maximum}.")
PY
# Normalize leading zeros before shell arithmetic.
POLL_INTERVAL=$((10#$POLL_INTERVAL))
MAX_WAIT=$((10#$MAX_WAIT))
if [[ "$COMMAND" == "create" && -n "$JOB_ID" ]]; then
  echo "Error: Use status or wait with an existing --job-id; do not create a replacement job." >&2
  exit 1
fi
if [[ "$COMMAND" != "create" && ! "$JOB_ID" =~ ^[A-Za-z0-9_-]+$ ]]; then
  echo "Error: --job-id is required and must contain only letters, digits, underscores, or hyphens." >&2
  exit 1
fi
if [[ "$COMMAND" == "status" || ( "$COMMAND" == "create" && "$DO_WAIT" -eq 0 ) ]] && [[ -n "$DOWNLOAD_DIR" || "$OUTPUT_FILE" == *.mp4 ]]; then
  echo "Error: Video downloads require wait (or create --wait). Use a JSON output file for status/--no-wait." >&2
  exit 1
fi

if [[ -n "$PROMPT_FILE" ]]; then
  if [[ ! -f "$PROMPT_FILE" ]]; then
    echo "Error: Prompt file not found: $PROMPT_FILE" >&2
    exit 1
  fi
  PROMPT="$(<"$PROMPT_FILE")"
fi

if [[ "$DRY_RUN" -eq 1 && "$COMMAND" != "create" ]]; then
  python3 - "${API_BASE_URL}${VIDEOS_PATH}/${JOB_ID}" <<'PY'
import json, sys
print(json.dumps({"method": "GET", "url": sys.argv[1]}, indent=2))
PY
  exit 0
fi

TOKEN="${TOKEN_OVERRIDE:-${FREVANA_TOKEN:-}}"
AGENT_APP_INSTANCE_ID="${AGENT_APP_INSTANCE_ID_OVERRIDE:-${FREVANA_AGENT_APP_INSTANCE_ID:-${X_FREVANA_AGENT_APP_INSTANCE_ID:-}}}"

if [[ "$DRY_RUN" -eq 0 && -z "$TOKEN" ]]; then
  echo "Error: Authentication required. Set FREVANA_TOKEN or pass --token with a Frevana JWT Bearer token. This route does not support API key authentication; FREVANA_API_KEY is ignored." >&2
  exit 1
fi

CURL_AUTH_HEADERS=()
if [[ -n "$TOKEN" ]]; then
  CURL_AUTH_HEADERS+=(-H "Authorization: Bearer $TOKEN")
fi
if [[ -n "$AGENT_APP_INSTANCE_ID" ]]; then
  CURL_AUTH_HEADERS+=(-H "x-frevana-agent-app-instance-id: $AGENT_APP_INSTANCE_ID")
fi

if [[ "$DRY_RUN" -eq 0 ]]; then
  if [[ -n "$OUTPUT_FILE" ]]; then
    mkdir -p "$(dirname "$OUTPUT_FILE")"
    if [[ -d "$OUTPUT_FILE" || ( -e "$OUTPUT_FILE" && ! -w "$OUTPUT_FILE" ) || ! -w "$(dirname "$OUTPUT_FILE")" ]]; then
      echo "Error: Output path is not writable: $OUTPUT_FILE" >&2
      exit 1
    fi
  fi
  [[ -z "$DOWNLOAD_DIR" ]] || mkdir -p "$DOWNLOAD_DIR"
fi

# Never retry a submission here. The Server SDK has an independent retry policy;
# see references/api.md. A transport failure can leave a paid job running.
request_api() {
  local method="$1" response_file="$2" url="$3" timeout="$4"
  shift 4
  if ! HTTP_STATUS="$(curl -q -sS -o "$response_file" -w "%{http_code}" \
    --connect-timeout "$CONNECT_TIMEOUT" --max-time "$timeout" \
    -X "$method" "$url" -H "Content-Type: application/json" \
    -H "Accept: application/json" "${CURL_AUTH_HEADERS[@]}" "$@")"; then
    echo "Error: $method transport failed. Do not automatically resubmit creation; resume a known job ID with status/wait. Job: ${JOB_ID:-unknown}." >&2
    [[ ! -f "$response_file" ]] || cat "$response_file" >&2
    exit 1
  fi
  if [[ ! "$HTTP_STATUS" =~ ^2[0-9][0-9]$ ]]; then
    echo "Error: $method returned HTTP $HTTP_STATUS. Job: ${JOB_ID:-unknown}. No automatic retry was made." >&2
    cat "$response_file" >&2
    echo "" >&2
    exit 1
  fi
}

save_json() {
  if [[ -n "$OUTPUT_FILE" && "$OUTPUT_FILE" != *.mp4 ]]; then
    if ! cp "$1" "$OUTPUT_FILE"; then
      echo "Error: Could not save response. Resume job ${JOB_ID:-unknown}; do not create a replacement." >&2
      cat "$1" >&2
      exit 1
    fi
  fi
}

# --- Action: CREATE ---
if [[ "$COMMAND" == "create" ]]; then
  if [[ -z "$PROMPT" ]]; then
    echo "Error: --prompt is required for create command." >&2
    exit 1
  fi

  REFERENCE_IMAGES_JSON="$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1:]))' ${REFERENCE_IMAGES[@]+"${REFERENCE_IMAGES[@]}"})"
  REFERENCE_AUDIOS_JSON="$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1:]))' ${REFERENCE_AUDIOS[@]+"${REFERENCE_AUDIOS[@]}"})"
  REFERENCE_VIDEOS_JSON="$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1:]))' ${REFERENCE_VIDEOS[@]+"${REFERENCE_VIDEOS[@]}"})"

  PAYLOAD_FILE="$TEMP_DIR/payload.json"
  ENV_PROMPT="$PROMPT" \
  ENV_MODEL="$MODEL" \
  ENV_DURATION="$DURATION" \
  ENV_ASPECT_RATIO="$ASPECT_RATIO" \
  ENV_RESOLUTION="$RESOLUTION" \
  ENV_SIZE="$SIZE" \
  ENV_SEED="$SEED" \
  ENV_PROMPT_ENHANCEMENT="$PROMPT_ENHANCEMENT" \
  ENV_FIRST_FRAME="$FIRST_FRAME" \
  ENV_REFERENCE_IMAGES="$REFERENCE_IMAGES_JSON" \
  ENV_REFERENCE_AUDIOS="$REFERENCE_AUDIOS_JSON" \
  ENV_REFERENCE_VIDEOS="$REFERENCE_VIDEOS_JSON" \
  python3 - "$PAYLOAD_FILE" <<'PY'
import base64, json, mimetypes, os, sys
from pathlib import Path
from urllib.parse import urlsplit

def public_url(src):
    parsed = urlsplit(src)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        sys.exit("Error: Media references must use public HTTPS URLs without embedded credentials.")
    return src

def image_source(src):
    if src.startswith(("http://", "https://")):
        return public_url(src)
    if src.startswith("data:image/"):
        return src
    path = Path(src)
    if not path.is_file():
        sys.exit(f"Error: Image file not found: {src}")
    mime = mimetypes.guess_type(src)[0]
    if not mime or not mime.startswith("image/"):
        sys.exit(f"Error: Expected an image file: {src}")
    if path.stat().st_size > 5 * 1024 * 1024:
        sys.exit("Error: Local images must be at most 5 MiB; use a public HTTPS URL for larger images.")
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"

prompt = os.environ["ENV_PROMPT"]
if not prompt.strip() or len(prompt) > 32000:
    sys.exit("Error: Prompt must contain 1-32000 characters and cannot be blank.")

payload_file = sys.argv[1]
payload = {
    "model": os.environ["ENV_MODEL"],
    "prompt": os.environ["ENV_PROMPT"],
}

duration = os.environ.get("ENV_DURATION")
if duration:
    payload["duration"] = int(duration)

size = os.environ.get("ENV_SIZE")
if size:
    payload["size"] = size
else:
    aspect_ratio = os.environ.get("ENV_ASPECT_RATIO")
    if aspect_ratio:
        payload["aspectRatio"] = aspect_ratio

    resolution = os.environ.get("ENV_RESOLUTION")
    if resolution:
        payload["resolution"] = resolution

seed = os.environ.get("ENV_SEED")
if seed:
    payload["seed"] = int(seed)

payload["provider"] = {"options": {"heygen": {
    "prompt_enhancement": os.environ["ENV_PROMPT_ENHANCEMENT"]
}}}

frame_images = []
first_frame = os.environ.get("ENV_FIRST_FRAME")
if first_frame:
    frame_images.append({
        "type": "image_url",
        "frameType": "first_frame",
        "imageUrl": {"url": image_source(first_frame)}
    })

if frame_images:
    payload["frameImages"] = frame_images

input_references = []
input_references.extend({"type": "image_url", "imageUrl": {"url": image_source(url)}} for url in json.loads(os.environ["ENV_REFERENCE_IMAGES"]))
input_references.extend({"type": "audio_url", "audioUrl": {"url": public_url(url)}} for url in json.loads(os.environ["ENV_REFERENCE_AUDIOS"]))
input_references.extend({"type": "video_url", "videoUrl": {"url": public_url(url)}} for url in json.loads(os.environ["ENV_REFERENCE_VIDEOS"]))
if input_references:
    payload["inputReferences"] = input_references

with open(payload_file, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)

# Frevana's Express JSON parser limits the complete body to 50 MiB. Per-image
# limits alone do not cover the combined Base64 expansion of reference images.
if Path(payload_file).stat().st_size > 50 * 1024 * 1024:
    sys.exit("Error: Encoded JSON request exceeds Frevana's 50 MiB body limit. Use smaller images or public HTTPS image URLs.")
PY

  if [[ "$DRY_RUN" -eq 1 ]]; then
    cat "$PAYLOAD_FILE"
    exit 0
  fi

  SUBMIT_RESPONSE="$TEMP_DIR/submit_response.json"
  request_api POST "$SUBMIT_RESPONSE" "${API_BASE_URL}${VIDEOS_PATH}" "$MAX_TIME" --data-binary @"$PAYLOAD_FILE"

  JOB_ID="$(python3 -c '
import json, sys
try:
    data = json.load(open(sys.argv[1]))
    print(data.get("id") or data.get("jobId") or "")
except Exception:
    print("")
' "$SUBMIT_RESPONSE")"

  if [[ ! "$JOB_ID" =~ ^[A-Za-z0-9_-]+$ ]]; then
    save_json "$SUBMIT_RESPONSE"
    echo "Error: No valid job ID returned by API. Submission outcome is uncertain; do not automatically resubmit." >&2
    cat "$SUBMIT_RESPONSE" >&2
    exit 1
  fi
  echo "Video job ID: $JOB_ID" >&2
  save_json "$SUBMIT_RESPONSE"

  if [[ "$DO_WAIT" -eq 0 ]]; then
    if [[ "$TEXT_ONLY" -eq 1 ]]; then
      echo "$JOB_ID"
    else
      cat "$SUBMIT_RESPONSE"
    fi
    exit 0
  fi

  COMMAND="wait"
fi

# --- Action: STATUS ---
if [[ "$COMMAND" == "status" ]]; then
  if [[ -z "$JOB_ID" ]]; then
    echo "Error: --job-id is required for status check." >&2
    exit 1
  fi

  STATUS_RESPONSE="$TEMP_DIR/status_response.json"
  request_api GET "$STATUS_RESPONSE" "${API_BASE_URL}${VIDEOS_PATH}/${JOB_ID}" 30
  save_json "$STATUS_RESPONSE"
  cat "$STATUS_RESPONSE"
  exit 0
fi

# --- Action: WAIT ---
if [[ "$COMMAND" == "wait" ]]; then
  if [[ -z "$JOB_ID" ]]; then
    echo "Error: --job-id is required to wait for completion." >&2
    exit 1
  fi

  START_TIME=$(date +%s)
  echo "Waiting for video generation job: $JOB_ID ..." >&2

  while true; do
    REMAINING=$((MAX_WAIT - $(date +%s) + START_TIME))
    if [[ "$REMAINING" -le 0 ]]; then
      echo "Error: Timed out after ${MAX_WAIT}s waiting for video job $JOB_ID. Resume with wait --job-id $JOB_ID." >&2
      exit 1
    fi
    REQUEST_TIMEOUT=30
    [[ "$REMAINING" -ge 30 ]] || REQUEST_TIMEOUT="$REMAINING"
    STATUS_RESPONSE="$TEMP_DIR/status_response.json"
    request_api GET "$STATUS_RESPONSE" "${API_BASE_URL}${VIDEOS_PATH}/${JOB_ID}" "$REQUEST_TIMEOUT"
    save_json "$STATUS_RESPONSE"

    if [[ "$HTTP_STATUS" -ge 200 && "$HTTP_STATUS" -lt 300 ]]; then
      ST="$(python3 -c '
import json, sys
try:
    data = json.load(open(sys.argv[1]))
    print(data.get("status") or "")
except Exception:
    print("")
' "$STATUS_RESPONSE")"

      case "$ST" in
        completed)
          read -r DELIVERY_STATUS HAS_VIDEO_URL < <(python3 -c '
import json, sys
try:
    data = json.load(open(sys.argv[1]))
    urls = data.get("unsigned_urls") or data.get("unsignedUrls") or data.get("playback_urls") or []
    has_url = bool(urls) or bool(isinstance(data.get("content"), dict) and data["content"].get("video_url"))
    print(data.get("delivery_status") or "unknown", "1" if has_url else "0")
except Exception:
    print("unknown", "0")
' "$STATUS_RESPONSE")
          if [[ "$DELIVERY_STATUS" == "failed" ]]; then
            echo "Error: Video generation completed, but result delivery failed." >&2
            cat "$STATUS_RESPONSE" >&2
            exit 1
          fi
          if [[ "$DELIVERY_STATUS" == "stored" || "$DELIVERY_STATUS" == "skipped" || ( "$DELIVERY_STATUS" == "unknown" && "$HAS_VIDEO_URL" == "1" ) ]]; then
            break
          fi
          ;;
        failed|cancelled|expired)
          ERR_MSG="$(python3 -c '
import json, sys
try:
    data = json.load(open(sys.argv[1]))
    print(data.get("error") or data.get("last_error") or "Video generation failed")
except Exception:
    print("Video generation failed")
' "$STATUS_RESPONSE")"
          echo "Error: Video generation $ST: $ERR_MSG" >&2
          cat "$STATUS_RESPONSE" >&2
          exit 1
          ;;
        pending|in_progress|queued|processing|running)
          ;;
        *)
          echo "Error: Missing or unknown video status for job $JOB_ID." >&2
          cat "$STATUS_RESPONSE" >&2
          exit 1
          ;;
      esac
    fi

    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    if [[ "$ELAPSED" -ge "$MAX_WAIT" ]]; then
      echo "Error: Timed out after ${MAX_WAIT}s waiting for video job $JOB_ID" >&2
      exit 1
    fi

    SLEEP_SECONDS="$POLL_INTERVAL"
    [[ "$SLEEP_SECONDS" -le $((MAX_WAIT - ELAPSED)) ]] || SLEEP_SECONDS=$((MAX_WAIT - ELAPSED))
    sleep "$SLEEP_SECONDS"
  done

  VIDEO_URL="$(python3 -c '
import json, sys
try:
    data = json.load(open(sys.argv[1]))
    urls = data.get("unsigned_urls") or data.get("unsignedUrls") or data.get("playback_urls") or []
    if isinstance(urls, list) and len(urls) > 0:
        print(urls[0])
    elif isinstance(data.get("content"), dict) and data["content"].get("video_url"):
        print(data["content"]["video_url"])
    else:
        print("")
except Exception:
    print("")
' "$STATUS_RESPONSE")"

  if [[ -z "$VIDEO_URL" ]]; then
    echo "Error: Video job completed without a result URL." >&2
    cat "$STATUS_RESPONSE" >&2
    exit 1
  fi

  SAVED_FILE=""
  if [[ -n "$VIDEO_URL" && (-n "$DOWNLOAD_DIR" || ( -n "$OUTPUT_FILE" && "$OUTPUT_FILE" == *.mp4 )) ]]; then
    if [[ -n "$OUTPUT_FILE" && "$OUTPUT_FILE" == *.mp4 ]]; then
      TARGET_PATH="$OUTPUT_FILE"
    else
      mkdir -p "$DOWNLOAD_DIR"
      TARGET_PATH="${DOWNLOAD_DIR}/video_${JOB_ID}.mp4"
    fi
    echo "Downloading generated video to $TARGET_PATH ..." >&2
    DOWNLOAD_HEADERS=()
    DOWNLOAD_MODE="$(python3 - "$API_BASE_URL" "$VIDEO_URL" <<'PY'
import sys
from urllib.parse import urlsplit
base, video = map(urlsplit, sys.argv[1:])
def origin(url):
    return url.scheme, url.hostname, url.port or (443 if url.scheme == 'https' else 80)
if video.scheme not in ('http', 'https') or not video.hostname or video.username or video.password:
    sys.exit('Error: Invalid video URL; expected HTTP(S) without embedded credentials.')
print('authenticated' if origin(base) == origin(video) else 'public')
PY
)"
    DOWNLOAD_REDIRECTS=(-L --proto-redir '=https')
    if [[ "$DOWNLOAD_MODE" == "authenticated" ]]; then
      DOWNLOAD_HEADERS=("${CURL_AUTH_HEADERS[@]}")
      # Do not forward Frevana headers across redirects.
      DOWNLOAD_REDIRECTS=()
    fi
    DOWNLOAD_TEMP="$(mktemp "${TARGET_PATH}.part.XXXXXX")"
    if ! DOWNLOAD_STATUS="$(curl -q -f -sS ${DOWNLOAD_REDIRECTS[@]+"${DOWNLOAD_REDIRECTS[@]}"} \
      ${DOWNLOAD_HEADERS[@]+"${DOWNLOAD_HEADERS[@]}"} --proto '=http,https' \
      --connect-timeout "$CONNECT_TIMEOUT" --max-time "$MAX_TIME" \
      -w '%{http_code}' "$VIDEO_URL" -o "$DOWNLOAD_TEMP")" || [[ ! "$DOWNLOAD_STATUS" =~ ^2[0-9][0-9]$ ]]; then
      echo "Error: Download failed for job $JOB_ID. Resume wait; do not create another video." >&2
      exit 1
    fi
    mv "$DOWNLOAD_TEMP" "$TARGET_PATH"
    DOWNLOAD_TEMP=""
    SAVED_FILE="$TARGET_PATH"
  fi

  if [[ "$TEXT_ONLY" -eq 1 ]]; then
    if [[ -n "$SAVED_FILE" ]]; then
      echo "$SAVED_FILE"
    else
      echo "$VIDEO_URL"
    fi
  else
    cat "$STATUS_RESPONSE"
  fi
fi
