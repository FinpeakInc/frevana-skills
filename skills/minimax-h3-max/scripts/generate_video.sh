#!/usr/bin/env bash

set -euo pipefail

DEFAULT_MODEL="minimax/hailuo-3-max"
ALLOWED_MODELS=("minimax/hailuo-3-max")
ALLOWED_RESOLUTIONS=("768p" "480p")
ALLOWED_ASPECT_RATIOS=("21:9" "16:9" "4:3" "1:1" "3:4" "9:16")
ALLOWED_DURATIONS=("5" "6" "7" "8" "9" "10" "11" "12" "13" "14" "15")
SUPPORTED_FRAME_IMAGES=("first_frame" "last_frame")
SUPPORTS_AUDIO=false
SUPPORTS_SEED=false

DEFAULT_RESOLUTION="768p"
DEFAULT_ASPECT_RATIO="16:9"
DEFAULT_DURATION="6"

DEFAULT_API_BASE_URL="https://ai-factory.frevana.com"
API_BASE_URL="${FREVANA_API_BASE_URL:-$DEFAULT_API_BASE_URL}"
API_BASE_URL="${API_BASE_URL%/}"
VIDEOS_PATH="/openrouter/v1/videos"
CONNECT_TIMEOUT="15"
MAX_TIME="600"

TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

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
  --model MODEL          Model slug (default: $DEFAULT_MODEL)
  --duration SEC         Duration in seconds (allowed: ${ALLOWED_DURATIONS[*]}, default: $DEFAULT_DURATION)
  --aspect-ratio RATIO   Aspect ratio (allowed: ${ALLOWED_ASPECT_RATIOS[*]}, default: $DEFAULT_ASPECT_RATIO)
  --resolution RES       Resolution (allowed: ${ALLOWED_RESOLUTIONS[*]}, default: $DEFAULT_RESOLUTION)
  --first-frame PATH/URL Image path or URL for the first frame
  --last-frame PATH/URL  Image path or URL for the last frame
  --image PATH/URL       Alias for --first-frame
  --watermark            Enable AIGC watermark
  --no-watermark         Disable AIGC watermark
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
  --token TOKEN          Frevana Bearer token (or FREVANA_TOKEN env)
  --api-key KEY          Frevana API key (or FREVANA_API_KEY env)
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
FIRST_FRAME=""
LAST_FRAME=""
WATERMARK=""
SEED=""
JOB_ID=""
DO_WAIT=1
POLL_INTERVAL=10
MAX_WAIT=600
DOWNLOAD_DIR=""
OUTPUT_FILE=""
TEXT_ONLY=0
DRY_RUN=0
TOKEN_OVERRIDE=""
API_KEY_OVERRIDE=""
AGENT_APP_INSTANCE_ID_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--prompt) PROMPT="${2:-}"; shift 2 ;;
    --prompt-file) PROMPT_FILE="${2:-}"; shift 2 ;;
    --model) MODEL="${2:-}"; shift 2 ;;
    --duration) DURATION="${2:-}"; shift 2 ;;
    --aspect-ratio) ASPECT_RATIO="${2:-}"; shift 2 ;;
    --resolution) RESOLUTION="${2:-}"; shift 2 ;;
    --first-frame|--image) FIRST_FRAME="${2:-}"; shift 2 ;;
    --last-frame) LAST_FRAME="${2:-}"; shift 2 ;;
    --watermark) WATERMARK="true"; shift ;;
    --no-watermark) WATERMARK="false"; shift ;;
    --audio)
      echo "Error: Model $MODEL does not support audio generation." >&2
      exit 1
      ;;
    --seed) SEED="${2:-}"; shift 2 ;;
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
    --api-key) API_KEY_OVERRIDE="${2:-}"; shift 2 ;;
    --agent-app-instance-id) AGENT_APP_INSTANCE_ID_OVERRIDE="${2:-}"; shift 2 ;;
    --api-base-url) API_BASE_URL="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *)
      if [[ -z "$COMMAND" && -z "$JOB_ID" && "$1" =~ ^[A-Za-z0-9_-]{10,}$ ]]; then
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

# Validation
if ! is_allowed "$MODEL" "${ALLOWED_MODELS[@]}"; then
  echo "Error: Invalid model '$MODEL'. Allowed: ${ALLOWED_MODELS[*]}" >&2
  exit 1
fi

if [[ -n "$DURATION" ]] && ! is_allowed "$DURATION" "${ALLOWED_DURATIONS[@]}"; then
  echo "Error: Invalid duration '$DURATION' for model $MODEL. Allowed durations: ${ALLOWED_DURATIONS[*]}" >&2
  exit 1
fi

if [[ -n "$RESOLUTION" ]] && ! is_allowed "$RESOLUTION" "${ALLOWED_RESOLUTIONS[@]}"; then
  echo "Error: Invalid resolution '$RESOLUTION' for model $MODEL. Allowed resolutions: ${ALLOWED_RESOLUTIONS[*]}" >&2
  exit 1
fi

if [[ -n "$ASPECT_RATIO" ]] && ! is_allowed "$ASPECT_RATIO" "${ALLOWED_ASPECT_RATIOS[@]}"; then
  echo "Error: Invalid aspect ratio '$ASPECT_RATIO' for model $MODEL. Allowed aspect ratios: ${ALLOWED_ASPECT_RATIOS[*]}" >&2
  exit 1
fi

if [[ -n "$LAST_FRAME" ]] && ! is_allowed "last_frame" "${SUPPORTED_FRAME_IMAGES[@]}"; then
  echo "Error: Model $MODEL does not support --last-frame." >&2
  exit 1
fi

if [[ -n "$FIRST_FRAME" ]] && ! is_allowed "first_frame" "${SUPPORTED_FRAME_IMAGES[@]}"; then
  echo "Error: Model $MODEL does not support image-to-video / --first-frame." >&2
  exit 1
fi

if [[ -n "$SEED" ]] && [[ "$SUPPORTS_SEED" != "true" ]]; then
  echo "Error: Model $MODEL does not support deterministic --seed." >&2
  exit 1
fi

if [[ -n "$PROMPT_FILE" ]]; then
  if [[ ! -f "$PROMPT_FILE" ]]; then
    echo "Error: Prompt file not found: $PROMPT_FILE" >&2
    exit 1
  fi
  PROMPT="$(<"$PROMPT_FILE")"
fi

API_KEY="${API_KEY_OVERRIDE:-${FREVANA_API_KEY:-}}"
TOKEN="${TOKEN_OVERRIDE:-${FREVANA_TOKEN:-}}"
AGENT_APP_INSTANCE_ID="${AGENT_APP_INSTANCE_ID_OVERRIDE:-${FREVANA_AGENT_APP_INSTANCE_ID:-${X_FREVANA_AGENT_APP_INSTANCE_ID:-}}}"

if [[ "$DRY_RUN" -eq 0 && -z "$TOKEN" && -z "$API_KEY" ]]; then
  echo "Error: Authentication required. Set FREVANA_TOKEN (or FREVANA_API_KEY) in environment, or pass --token / --api-key." >&2
  exit 1
fi

CURL_AUTH_HEADERS=()
if [[ -n "$TOKEN" ]]; then
  CURL_AUTH_HEADERS+=(-H "Authorization: Bearer $TOKEN")
elif [[ -n "$API_KEY" ]]; then
  CURL_AUTH_HEADERS+=(-H "Authorization: Bearer $API_KEY" -H "X-API-Key: $API_KEY")
fi
if [[ -n "$AGENT_APP_INSTANCE_ID" ]]; then
  CURL_AUTH_HEADERS+=(-H "x-frevana-agent-app-instance-id: $AGENT_APP_INSTANCE_ID")
fi

format_image_source() {
  local src="$1"
  python3 - "$src" <<'PY'
import sys, os, base64, mimetypes

src = sys.argv[1]
if src.startswith("http://") or src.startswith("https://") or src.startswith("data:"):
    print(src)
    sys.exit(0)

if not os.path.isfile(src):
    sys.stderr.write(f"Error: Frame image file not found: {src}\n")
    sys.exit(1)

mime, _ = mimetypes.guess_type(src)
if not mime:
    ext = os.path.splitext(src)[1].lower()
    if ext in [".jpg", ".jpeg"]:
        mime = "image/jpeg"
    elif ext == ".png":
        mime = "image/png"
    elif ext == ".webp":
        mime = "image/webp"
    else:
        mime = "image/jpeg"

with open(src, "rb") as f:
    b64 = base64.b64encode(f.read()).decode("ascii")

print(f"data:{mime};base64,{b64}")
PY
}

# --- Action: CREATE ---
if [[ "$COMMAND" == "create" ]]; then
  if [[ -z "$PROMPT" ]]; then
    echo "Error: --prompt is required for create command." >&2
    exit 1
  fi

  FORMATTED_FIRST_FRAME=""
  if [[ -n "$FIRST_FRAME" ]]; then
    FORMATTED_FIRST_FRAME="$(format_image_source "$FIRST_FRAME")"
  fi

  FORMATTED_LAST_FRAME=""
  if [[ -n "$LAST_FRAME" ]]; then
    FORMATTED_LAST_FRAME="$(format_image_source "$LAST_FRAME")"
  fi

  PAYLOAD_FILE="$TEMP_DIR/payload.json"
  ENV_PROMPT="$PROMPT" \
  ENV_MODEL="$MODEL" \
  ENV_DURATION="$DURATION" \
  ENV_ASPECT_RATIO="$ASPECT_RATIO" \
  ENV_RESOLUTION="$RESOLUTION" \
  ENV_WATERMARK="$WATERMARK" \
  ENV_FIRST_FRAME="$FORMATTED_FIRST_FRAME" \
  ENV_LAST_FRAME="$FORMATTED_LAST_FRAME" \
  python3 - "$PAYLOAD_FILE" <<'PY'
import os, sys, json

payload_file = sys.argv[1]
payload = {
    "model": os.environ["ENV_MODEL"],
    "prompt": os.environ["ENV_PROMPT"],
}

duration = os.environ.get("ENV_DURATION")
if duration:
    payload["duration"] = int(duration)

aspect_ratio = os.environ.get("ENV_ASPECT_RATIO")
if aspect_ratio:
    payload["aspect_ratio"] = aspect_ratio

resolution = os.environ.get("ENV_RESOLUTION")
if resolution:
    payload["resolution"] = resolution

watermark = os.environ.get("ENV_WATERMARK")
if watermark == "true":
    payload.setdefault("provider", {}).setdefault("options", {}).setdefault("minimax", {})["aigc_watermark"] = True
elif watermark == "false":
    payload.setdefault("provider", {}).setdefault("options", {}).setdefault("minimax", {})["aigc_watermark"] = False

frame_images = []
first_frame = os.environ.get("ENV_FIRST_FRAME")
if first_frame:
    frame_images.append({
        "type": "image_url",
        "frame_type": "first_frame",
        "image_url": {"url": first_frame}
    })

last_frame = os.environ.get("ENV_LAST_FRAME")
if last_frame:
    frame_images.append({
        "type": "image_url",
        "frame_type": "last_frame",
        "image_url": {"url": last_frame}
    })

if frame_images:
    payload["frame_images"] = frame_images

with open(payload_file, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)
PY

  if [[ "$DRY_RUN" -eq 1 ]]; then
    cat "$PAYLOAD_FILE"
    exit 0
  fi

  SUBMIT_RESPONSE="$TEMP_DIR/submit_response.json"
  HTTP_STATUS="$(curl -sS -o "$SUBMIT_RESPONSE" -w "%{http_code}" \
    --connect-timeout "$CONNECT_TIMEOUT" --max-time "$MAX_TIME" \
    -X POST "${API_BASE_URL}${VIDEOS_PATH}" \
    -H "Content-Type: application/json" \
    "${CURL_AUTH_HEADERS[@]}" \
    -d @"$PAYLOAD_FILE")"

  if [[ "$HTTP_STATUS" -lt 200 || "$HTTP_STATUS" -ge 300 ]]; then
    echo "Error: Video creation failed with HTTP $HTTP_STATUS" >&2
    cat "$SUBMIT_RESPONSE" >&2
    echo "" >&2
    exit 1
  fi

  JOB_ID="$(python3 -c '
import json, sys
try:
    data = json.load(open(sys.argv[1]))
    print(data.get("id") or data.get("jobId") or "")
except Exception:
    print("")
' "$SUBMIT_RESPONSE")"

  if [[ -z "$JOB_ID" ]]; then
    echo "Error: No job ID returned by API." >&2
    cat "$SUBMIT_RESPONSE" >&2
    exit 1
  fi

  if [[ "$DO_WAIT" -eq 0 ]]; then
    if [[ "$TEXT_ONLY" -eq 1 ]]; then
      echo "$JOB_ID"
    else
      if [[ -n "$OUTPUT_FILE" ]]; then
        cp "$SUBMIT_RESPONSE" "$OUTPUT_FILE"
      fi
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
  HTTP_STATUS="$(curl -sS -o "$STATUS_RESPONSE" -w "%{http_code}" \
    --connect-timeout "$CONNECT_TIMEOUT" --max-time "$MAX_TIME" \
    -X GET "${API_BASE_URL}${VIDEOS_PATH}/${JOB_ID}" \
    -H "Accept: application/json" \
    "${CURL_AUTH_HEADERS[@]}")"

  if [[ "$HTTP_STATUS" -lt 200 || "$HTTP_STATUS" -ge 300 ]]; then
    echo "Error: Failed to retrieve job status with HTTP $HTTP_STATUS" >&2
    cat "$STATUS_RESPONSE" >&2
    echo "" >&2
    exit 1
  fi

  if [[ -n "$OUTPUT_FILE" ]]; then
    cp "$STATUS_RESPONSE" "$OUTPUT_FILE"
  fi
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
    STATUS_RESPONSE="$TEMP_DIR/status_response.json"
    HTTP_STATUS="$(curl -sS -o "$STATUS_RESPONSE" -w "%{http_code}" \
      --connect-timeout "$CONNECT_TIMEOUT" --max-time 30 \
      -X GET "${API_BASE_URL}${VIDEOS_PATH}/${JOB_ID}" \
      -H "Accept: application/json" \
      "${CURL_AUTH_HEADERS[@]}")"

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
          break
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
        *)
          ;;
      esac
    fi

    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    if [[ "$ELAPSED" -ge "$MAX_WAIT" ]]; then
      echo "Error: Timed out after ${MAX_WAIT}s waiting for video job $JOB_ID" >&2
      exit 1
    fi

    sleep "$POLL_INTERVAL"
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
    if [[ "$VIDEO_URL" == *"openrouter.ai"* || "$VIDEO_URL" == "${API_BASE_URL}"* || "$VIDEO_URL" == *"/videos/"* ]]; then
      DOWNLOAD_HEADERS=("${CURL_AUTH_HEADERS[@]}")
    fi
    curl -sS -L "${DOWNLOAD_HEADERS[@]}" "$VIDEO_URL" -o "$TARGET_PATH"
    SAVED_FILE="$TARGET_PATH"
  fi

  if [[ "$TEXT_ONLY" -eq 1 ]]; then
    if [[ -n "$SAVED_FILE" ]]; then
      echo "$SAVED_FILE"
    else
      echo "$VIDEO_URL"
    fi
  else
    if [[ -n "$OUTPUT_FILE" && "$OUTPUT_FILE" != *.mp4 ]]; then
      cp "$STATUS_RESPONSE" "$OUTPUT_FILE"
    fi
    cat "$STATUS_RESPONSE"
  fi
fi
