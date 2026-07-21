#!/usr/bin/env bash

set -euo pipefail

DEFAULT_API_BASE_URL="https://api.seedance2.ai"
API_BASE_URL="${SEEDANCE_API_BASE_URL:-$DEFAULT_API_BASE_URL}"
MIN_POLL_INTERVAL=10
CONNECT_TIMEOUT=10
REQUEST_TIMEOUT=120

TEMP_DIR=""
HTTP_BODY=""
HTTP_HEADERS=""
HTTP_STATUS=""
VALIDATED_INTEGER=""

cleanup() {
  if [[ -n "$TEMP_DIR" && -d "$TEMP_DIR" ]]; then
    rm -rf "$TEMP_DIR"
  fi
}
trap cleanup EXIT

usage() {
  cat <<'EOF'
Seedance 2.0 video CLI

Usage:
  seedance.sh create --prompt TEXT [options]
  seedance.sh status --task-id ID [--download-dir DIR] [--output FILE]
  seedance.sh wait --task-id ID [wait options]

Create options:
  --prompt TEXT                       Required video prompt
  --model MODEL                       seedance-2-0 (default), seedance-2-0-fast, seedance-2-0-mini
  --generation-type TYPE              text-to-video (default), image-to-video, reference-to-video
  --image-url URL                     Repeatable public image URL
  --video-url URL                     Repeatable public video URL
  --audio-url URL                     Repeatable public audio URL
  --duration SECONDS                  4-15 (default: 5)
  --aspect-ratio RATIO                16:9, 4:3, 1:1, 3:4, 9:16, 21:9, adaptive (default)
  --resolution VALUE                  480p, 720p (default), 1080p, 4k
  --generate-audio BOOL               true (default) or false
  --watermark BOOL                    false (default) or true
  --web-search BOOL                   false (default) or true
  --return-last-frame BOOL            false (default) or true
  --seed INTEGER                      -1 (random) or 0-4294967295
  --wait                              Poll after creation until terminal

Wait options:
  Polling runs at a fixed 10-second interval.
  --timeout SECONDS                   Stop after this many seconds (default: 900; 0 disables)
  --download-dir DIRECTORY            Download completed results and optional last frame

Common options:
  --output FILE                       Save the final raw API JSON to a file
  -h, --help                          Show help

Environment:
  SEEDANCE_API_KEY                    Required Bearer API key
  SEEDANCE_API_BASE_URL               Optional API base override
EOF
}

fail() {
  echo "Error: $*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

require_value() {
  local flag="$1"
  local value="${2-}"
  if [[ -z "$value" || "$value" == --* ]]; then
    fail "missing value for $flag"
  fi
}

is_integer() {
  [[ "$1" =~ ^-?[0-9]+$ ]]
}

validate_integer_range() {
  local value="$1"
  local flag="$2"
  local minimum="$3"
  local maximum="$4"
  is_integer "$value" || fail "$flag must be an integer"
  local sign=""
  local digits="$value"
  if [[ "$digits" == -* ]]; then
    sign="-"
    digits="${digits#-}"
  fi
  while [[ ${#digits} -gt 1 && "$digits" == 0* ]]; do
    digits="${digits#0}"
  done
  local normalized="${sign}${digits}"
  if [[ ${#digits} -gt 18 ]] || (( normalized < minimum || normalized > maximum )); then
    fail "$flag must be between $minimum and $maximum"
  fi
  VALIDATED_INTEGER="$normalized"
}

validate_boolean() {
  local value="$1"
  local flag="$2"
  [[ "$value" == "true" || "$value" == "false" ]] || fail "$flag must be true or false"
}

validate_http_url() {
  local value="$1"
  local flag="$2"
  [[ "$value" =~ ^https?://[^[:space:]]+$ ]] || fail "$flag must use http:// or https://"
}

validate_https_url() {
  local value="$1"
  local flag="$2"
  [[ "$value" =~ ^https://[^[:space:]]+$ ]] || fail "$flag must use https://"
}

contains_value() {
  local target="$1"
  shift
  local value
  for value in "$@"; do
    [[ "$target" == "$value" ]] && return 0
  done
  return 1
}

ACTION="${1-}"
if [[ -z "$ACTION" || "$ACTION" == "--help" || "$ACTION" == "-h" ]]; then
  usage
  exit 0
fi
contains_value "$ACTION" create status wait || fail "unknown action '$ACTION'; use create, status, or wait"
shift

PROMPT=""
MODEL="seedance-2-0"
GENERATION_TYPE="text-to-video"
DURATION="5"
ASPECT_RATIO="adaptive"
RESOLUTION="720p"
GENERATE_AUDIO="true"
WATERMARK="false"
WEB_SEARCH="false"
RETURN_LAST_FRAME="false"
SEED="-1"
TASK_ID=""
WAIT_FOR_TASK="false"
POLL_INTERVAL="10"
WAIT_TIMEOUT="900"
DOWNLOAD_DIR=""
OUTPUT_FILE=""
CREATE_OPTION_SEEN="false"
WAIT_OPTION_SEEN="false"
IMAGE_URLS=()
VIDEO_URLS=()
AUDIO_URLS=()

while (( $# > 0 )); do
  case "$1" in
    --prompt)
      require_value "$1" "${2-}"
      PROMPT="$2"
      CREATE_OPTION_SEEN="true"
      shift 2
      ;;
    --model)
      require_value "$1" "${2-}"
      MODEL="$2"
      CREATE_OPTION_SEEN="true"
      shift 2
      ;;
    --generation-type)
      require_value "$1" "${2-}"
      GENERATION_TYPE="$2"
      CREATE_OPTION_SEEN="true"
      shift 2
      ;;
    --image-url)
      require_value "$1" "${2-}"
      IMAGE_URLS+=("$2")
      CREATE_OPTION_SEEN="true"
      shift 2
      ;;
    --video-url)
      require_value "$1" "${2-}"
      VIDEO_URLS+=("$2")
      CREATE_OPTION_SEEN="true"
      shift 2
      ;;
    --audio-url)
      require_value "$1" "${2-}"
      AUDIO_URLS+=("$2")
      CREATE_OPTION_SEEN="true"
      shift 2
      ;;
    --duration)
      require_value "$1" "${2-}"
      DURATION="$2"
      CREATE_OPTION_SEEN="true"
      shift 2
      ;;
    --aspect-ratio)
      require_value "$1" "${2-}"
      ASPECT_RATIO="$2"
      CREATE_OPTION_SEEN="true"
      shift 2
      ;;
    --resolution)
      require_value "$1" "${2-}"
      RESOLUTION="$2"
      CREATE_OPTION_SEEN="true"
      shift 2
      ;;
    --generate-audio)
      require_value "$1" "${2-}"
      GENERATE_AUDIO="$2"
      CREATE_OPTION_SEEN="true"
      shift 2
      ;;
    --watermark)
      require_value "$1" "${2-}"
      WATERMARK="$2"
      CREATE_OPTION_SEEN="true"
      shift 2
      ;;
    --web-search)
      require_value "$1" "${2-}"
      WEB_SEARCH="$2"
      CREATE_OPTION_SEEN="true"
      shift 2
      ;;
    --return-last-frame)
      require_value "$1" "${2-}"
      RETURN_LAST_FRAME="$2"
      CREATE_OPTION_SEEN="true"
      shift 2
      ;;
    --seed)
      require_value "$1" "${2-}"
      SEED="$2"
      CREATE_OPTION_SEEN="true"
      shift 2
      ;;
    --wait)
      WAIT_FOR_TASK="true"
      CREATE_OPTION_SEEN="true"
      shift
      ;;
    --task-id)
      require_value "$1" "${2-}"
      TASK_ID="$2"
      shift 2
      ;;
    --timeout)
      require_value "$1" "${2-}"
      WAIT_TIMEOUT="$2"
      WAIT_OPTION_SEEN="true"
      shift 2
      ;;
    --download-dir)
      require_value "$1" "${2-}"
      DOWNLOAD_DIR="$2"
      shift 2
      ;;
    --output)
      require_value "$1" "${2-}"
      OUTPUT_FILE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --*)
      fail "unknown option: $1"
      ;;
    *)
      fail "unexpected positional argument: $1"
      ;;
  esac
done

if [[ "$ACTION" != "create" && "$CREATE_OPTION_SEEN" == "true" ]]; then
  fail "create options are only valid with create"
fi
if [[ "$ACTION" == "status" && "$WAIT_OPTION_SEEN" == "true" ]]; then
  fail "--timeout is only valid with wait or create --wait"
fi
if [[ "$ACTION" == "create" && -n "$TASK_ID" ]]; then
  fail "--task-id is not valid with create"
fi
if [[ "$ACTION" == "create" && "$WAIT_FOR_TASK" == "false" ]]; then
  [[ "$WAIT_OPTION_SEEN" == "false" ]] || fail "--timeout requires create --wait"
  [[ -z "$DOWNLOAD_DIR" ]] || fail "--download-dir requires create --wait"
fi
if [[ "$ACTION" != "create" ]]; then
  [[ -n "$TASK_ID" ]] || fail "--task-id is required"
fi

api_request() {
  local method="$1"
  local path="$2"
  local request_file="${3-}"
  HTTP_BODY="$TEMP_DIR/response.json"
  HTTP_HEADERS="$TEMP_DIR/headers.txt"
  local curl_args=(
    --silent --show-error
    --connect-timeout "$CONNECT_TIMEOUT"
    --max-time "$REQUEST_TIMEOUT"
    --dump-header "$HTTP_HEADERS"
    --output "$HTTP_BODY"
    --write-out '%{http_code}'
    --request "$method"
    --header "@$AUTH_HEADER_FILE"
  )
  if [[ -n "$request_file" ]]; then
    curl_args+=(--header 'Content-Type: application/json' --data-binary "@$request_file")
  fi
  if ! HTTP_STATUS="$(curl "${curl_args[@]}" "$API_BASE_URL$path")"; then
    fail "API request failed; the task was not resubmitted"
  fi
}

is_success_status() {
  [[ "$1" =~ ^2[0-9][0-9]$ ]]
}

print_api_error() {
  if [[ -s "$HTTP_BODY" ]]; then
    cat "$HTTP_BODY" >&2
    printf '\n' >&2
  else
    echo "HTTP $HTTP_STATUS" >&2
  fi
}

json_field() {
  local file="$1"
  local field="$2"
  python3 - "$file" "$field" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    data = json.load(handle)
value = data
for part in sys.argv[2].split("."):
    if not isinstance(value, dict) or part not in value:
        raise SystemExit(0)
    value = value[part]
if value is not None:
    print(value)
PY
}

build_request_file() {
  local request_file="$1"
  python3 - "$request_file" "$MODEL" "$PROMPT" "$GENERATION_TYPE" \
    "$DURATION" "$ASPECT_RATIO" "$RESOLUTION" "$GENERATE_AUDIO" "$WATERMARK" \
    "$WEB_SEARCH" "$RETURN_LAST_FRAME" "$SEED" \
    --images ${IMAGE_URLS[@]+"${IMAGE_URLS[@]}"} \
    --videos ${VIDEO_URLS[@]+"${VIDEO_URLS[@]}"} \
    --audios ${AUDIO_URLS[@]+"${AUDIO_URLS[@]}"} <<'PY'
import json
import sys

(
    output_file, model, prompt, generation_type, duration,
    aspect_ratio, resolution, generate_audio, watermark, web_search,
    return_last_frame, seed, *media_args
) = sys.argv[1:]

groups = {"--images": [], "--videos": [], "--audios": []}
current = None
for value in media_args:
    if value in groups:
        current = value
    elif current is not None:
        groups[current].append(value)

input_data = {
    "prompt": prompt,
    "generation_type": generation_type,
    "duration": int(duration),
    "aspect_ratio": aspect_ratio,
    "resolution": resolution,
    "generate_audio": generate_audio == "true",
    "watermark": watermark == "true",
    "web_search": web_search == "true",
    "return_last_frame": return_last_frame == "true",
    "seed": int(seed),
}
if groups["--images"]:
    input_data["image_urls"] = groups["--images"]
if groups["--videos"]:
    input_data["video_urls"] = groups["--videos"]
if groups["--audios"]:
    input_data["audio_urls"] = groups["--audios"]

body = {"model": model, "input": input_data}
with open(output_file, "w", encoding="utf-8") as handle:
    json.dump(body, handle, ensure_ascii=False, separators=(",", ":"))
PY
}

validate_create_options() {
  [[ -n "${PROMPT//[[:space:]]/}" ]] || fail "--prompt is required for create"
  contains_value "$MODEL" seedance-2-0 seedance-2-0-fast seedance-2-0-mini || fail "unsupported --model: $MODEL"
  contains_value "$GENERATION_TYPE" text-to-video image-to-video reference-to-video || fail "unsupported --generation-type: $GENERATION_TYPE"
  contains_value "$ASPECT_RATIO" 16:9 4:3 1:1 3:4 9:16 21:9 adaptive || fail "unsupported --aspect-ratio: $ASPECT_RATIO"
  contains_value "$RESOLUTION" 480p 720p 1080p 4k || fail "unsupported --resolution: $RESOLUTION"
  validate_integer_range "$DURATION" "--duration" 4 15
  DURATION="$VALIDATED_INTEGER"
  validate_integer_range "$SEED" "--seed" -1 4294967295
  SEED="$VALIDATED_INTEGER"
  validate_boolean "$GENERATE_AUDIO" "--generate-audio"
  validate_boolean "$WATERMARK" "--watermark"
  validate_boolean "$WEB_SEARCH" "--web-search"
  validate_boolean "$RETURN_LAST_FRAME" "--return-last-frame"

  local url
  for url in ${IMAGE_URLS[@]+"${IMAGE_URLS[@]}"} \
    ${VIDEO_URLS[@]+"${VIDEO_URLS[@]}"} \
    ${AUDIO_URLS[@]+"${AUDIO_URLS[@]}"}; do
    [[ -z "$url" ]] || validate_http_url "$url" "media URL"
  done
  local image_count=${#IMAGE_URLS[@]}
  local video_count=${#VIDEO_URLS[@]}
  local audio_count=${#AUDIO_URLS[@]}
  local total_count=$((image_count + video_count + audio_count))
  case "$GENERATION_TYPE" in
    text-to-video)
      (( total_count == 0 )) || fail "text-to-video does not accept media URLs"
      ;;
    image-to-video)
      (( image_count >= 1 && image_count <= 2 )) || fail "image-to-video requires 1 or 2 --image-url values"
      (( video_count == 0 && audio_count == 0 )) || fail "image-to-video does not accept video or audio URLs"
      ;;
    reference-to-video)
      (( image_count <= 9 )) || fail "reference-to-video accepts at most 9 image URLs"
      (( video_count <= 3 )) || fail "reference-to-video accepts at most 3 video URLs"
      (( audio_count <= 3 )) || fail "reference-to-video accepts at most 3 audio URLs"
      (( image_count + video_count > 0 )) || fail "reference-to-video requires at least one image or video URL"
      (( total_count <= 12 )) || fail "reference-to-video accepts at most 12 total assets"
      ;;
  esac
}

get_task() {
  local task_id="$1"
  local encoded_task_id
  encoded_task_id="$(python3 - "$task_id" <<'PY'
import sys
import urllib.parse
print(urllib.parse.quote(sys.argv[1], safe=""))
PY
)"
  api_request GET "/v1/tasks/$encoded_task_id"
}

retry_after_seconds() {
  local fallback="$1"
  local value
  value="$(awk 'tolower($1) == "retry-after:" { gsub("\\r", "", $2); print $2; exit }' "$HTTP_HEADERS")"
  if [[ "$value" =~ ^[0-9]+$ && "$value" -gt "$fallback" ]]; then
    echo "$value"
  else
    echo "$fallback"
  fi
}

wait_for_task() {
  local task_id="$1"
  local start_epoch
  start_epoch="$(date +%s)"

  while true; do
    get_task "$task_id"
    if is_success_status "$HTTP_STATUS"; then
      local status
      status="$(json_field "$HTTP_BODY" status)"
      echo "Task $task_id: ${status:-unknown}" >&2
      if [[ "$status" == "completed" || "$status" == "failed" ]]; then
        return 0
      fi
    elif [[ "$HTTP_STATUS" == "429" || "$HTTP_STATUS" =~ ^5[0-9][0-9]$ ]]; then
      local retry_seconds
      retry_seconds="$(retry_after_seconds "$POLL_INTERVAL")"
      local now_epoch
      now_epoch="$(date +%s)"
      if (( WAIT_TIMEOUT > 0 && now_epoch - start_epoch + retry_seconds >= WAIT_TIMEOUT )); then
        fail "timed out waiting for task $task_id; the task was not resubmitted"
      fi
      echo "Status request returned HTTP $HTTP_STATUS; retrying in ${retry_seconds}s" >&2
      sleep "$retry_seconds"
      continue
    else
      print_api_error
      exit 1
    fi

    local now_epoch
    now_epoch="$(date +%s)"
    if (( WAIT_TIMEOUT > 0 && now_epoch - start_epoch + POLL_INTERVAL >= WAIT_TIMEOUT )); then
      fail "timed out waiting for task $task_id; the task was not resubmitted"
    fi
    sleep "$POLL_INTERVAL"
  done
}

safe_extension() {
  local url="$1"
  local fallback="$2"
  python3 - "$url" "$fallback" <<'PY'
import pathlib
import re
import sys
import urllib.parse

suffix = pathlib.PurePosixPath(urllib.parse.urlparse(sys.argv[1]).path).suffix.lower()
print(suffix if re.fullmatch(r"\.[a-z0-9]{1,5}", suffix) else sys.argv[2])
PY
}

safe_filename_component() {
  python3 - "$1" <<'PY'
import re
import sys

value = re.sub(r"[^A-Za-z0-9._-]+", "-", sys.argv[1]).strip(".-")
print(value or "result")
PY
}

download_results() {
  local response_file="$1"
  local directory="$2"
  local status
  status="$(json_field "$response_file" status)"
  [[ "$status" == "completed" ]] || return 0
  mkdir -p "$directory"
  local task_id
  task_id="$(json_field "$response_file" id)"
  [[ -n "$task_id" ]] || task_id="result"
  task_id="$(safe_filename_component "$task_id")"

  local index=0
  local url
  while IFS= read -r url; do
    [[ -n "$url" ]] || continue
    index=$((index + 1))
    local extension
    extension="$(safe_extension "$url" .mp4)"
    local target="$directory/seedance-${task_id}-${index}${extension}"
    curl --fail --silent --show-error --location --connect-timeout "$CONNECT_TIMEOUT" \
      --max-time 600 --output "$target" "$url"
    echo "Downloaded video: $target" >&2
  done < <(python3 - "$response_file" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as handle:
    data = json.load(handle)
for url in data.get("data", {}).get("results", []):
    print(url)
PY
)

  local last_frame_url
  last_frame_url="$(json_field "$response_file" data.last_frame_url)"
  if [[ -n "$last_frame_url" ]]; then
    local extension
    extension="$(safe_extension "$last_frame_url" .jpg)"
    local target="$directory/seedance-${task_id}-last-frame${extension}"
    curl --fail --silent --show-error --location --connect-timeout "$CONNECT_TIMEOUT" \
      --max-time 600 --output "$target" "$last_frame_url"
    echo "Downloaded last frame: $target" >&2
  fi
}

save_and_print() {
  local response_file="$1"
  if [[ -n "$OUTPUT_FILE" ]]; then
    mkdir -p "$(dirname "$OUTPUT_FILE")"
    cp "$response_file" "$OUTPUT_FILE"
    echo "Saved API response: $OUTPUT_FILE" >&2
  fi
  cat "$response_file"
  [[ -s "$response_file" ]] && printf '\n'
}

if [[ "$ACTION" == "create" ]]; then
  validate_create_options
fi
if [[ "$ACTION" == "wait" || "$WAIT_FOR_TASK" == "true" ]]; then
  validate_integer_range "$WAIT_TIMEOUT" "--timeout" 0 604800
  WAIT_TIMEOUT="$VALIDATED_INTEGER"
fi

require_command curl
require_command python3
[[ -n "${SEEDANCE_API_KEY:-}" ]] || fail "SEEDANCE_API_KEY is not set"
if [[ "$SEEDANCE_API_KEY" == *$'\n'* || "$SEEDANCE_API_KEY" == *$'\r'* ]]; then
  fail "SEEDANCE_API_KEY contains an invalid newline"
fi
validate_https_url "$API_BASE_URL" "SEEDANCE_API_BASE_URL"
API_BASE_URL="${API_BASE_URL%/}"

TEMP_DIR="$(mktemp -d)"
AUTH_HEADER_FILE="$TEMP_DIR/auth-header.txt"
printf 'Authorization: Bearer %s\n' "$SEEDANCE_API_KEY" > "$AUTH_HEADER_FILE"
chmod 600 "$AUTH_HEADER_FILE"

if [[ "$ACTION" == "create" ]]; then
  REQUEST_FILE="$TEMP_DIR/request.json"
  build_request_file "$REQUEST_FILE"
  api_request POST /v1/videos/generations "$REQUEST_FILE"
  if ! is_success_status "$HTTP_STATUS"; then
    print_api_error
    exit 1
  fi
  if [[ "$WAIT_FOR_TASK" == "false" ]]; then
    save_and_print "$HTTP_BODY"
    exit 0
  fi
  TASK_ID="$(json_field "$HTTP_BODY" taskId)"
  [[ -n "$TASK_ID" ]] || fail "create response did not include taskId"
  echo "Created task $TASK_ID; waiting for terminal status" >&2
  wait_for_task "$TASK_ID"
else
  if [[ "$ACTION" == "status" ]]; then
    get_task "$TASK_ID"
    if ! is_success_status "$HTTP_STATUS"; then
      print_api_error
      exit 1
    fi
  else
    wait_for_task "$TASK_ID"
  fi
fi

if [[ -n "$DOWNLOAD_DIR" ]]; then
  download_results "$HTTP_BODY" "$DOWNLOAD_DIR"
fi
save_and_print "$HTTP_BODY"

FINAL_STATUS="$(json_field "$HTTP_BODY" status)"
if [[ "$FINAL_STATUS" == "failed" ]]; then
  exit 2
fi
