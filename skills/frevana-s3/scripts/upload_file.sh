#!/usr/bin/env bash

set -euo pipefail

DEFAULT_API_BASE_URL="https://api.frevana.com"
API_BASE_URL="${FREVANA_API_BASE_URL:-$DEFAULT_API_BASE_URL}"
while [[ "$API_BASE_URL" == */ ]]; do API_BASE_URL="${API_BASE_URL%/}"; done
UPLOAD_URL_PATH="/s3/custom-upload-url"
FIXED_SCENE_TYPE="universal"
CONNECT_TIMEOUT="15"
MAX_TIME="600"

TEMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

usage() {
  cat <<'EOF'
Usage:
  upload_file.sh --file <path> [options]

Upload any local file to S3 via Frevana's custom-upload-url API (scene_type=universal).

Options:
  -f, --file PATH           Local file to upload (required)
  -k, --file-key KEY        Previous file_key; pass only when updating existing content
  -t, --title TITLE         File title (default: filename stem)
  --content-type MIME       Override MIME type (default: auto-detected)
  --file-extension EXT      Override file extension (default: auto-detected)

Optional Metadata (can be omitted):
  --agent-id ID             Agent ID (or FREVANA_AGENT_ID env)
  --task-id ID              Task/Thread ID (or FREVANA_TASK_ID / CODEX_THREAD_ID env)
  --team-id ID              Team ID (or FREVANA_TEAM_ID / CODEX_TEAM_ID env)
  --publish-type TYPE       Publish type (e.g. only_share_link, custom_domain, frevana_community)
  --tags TAGS               Tags, comma-separated or JSON array (e.g. "report,v1")
  --category CAT            Category (e.g. report, guides, faq, agent_app_result)
  --preview-image-url URL   Preview image URL
  --description DESC        File description
  --language-code CODE      Language code (e.g. en, zh, ja)

Output & Behavior:
  --text-only               Output only the public URL
  -o, --output FILE         Save output JSON to specified file
  --dry-run                 Print payload JSON and exit without network requests

Auth:
  --token TOKEN             Frevana Bearer token (or FREVANA_TOKEN env)
  --api-key KEY             Frevana API key (or FREVANA_API_KEY env)
  --api-base-url URL        API base URL override (default: https://api.frevana.com)
  -h, --help                Show this help message
EOF
}

FILE_PATH=""
FILE_KEY=""
FILE_TITLE=""
CONTENT_TYPE_OVERRIDE=""
FILE_EXTENSION_OVERRIDE=""
AGENT_ID="${FREVANA_AGENT_ID:-}"
TASK_ID="${FREVANA_TASK_ID:-${CODEX_THREAD_ID:-}}"
TEAM_ID="${FREVANA_TEAM_ID:-${CODEX_TEAM_ID:-}}"
PUBLISH_TYPE=""
TAGS=""
CATEGORY=""
PREVIEW_IMAGE_URL=""
DESCRIPTION=""
LANGUAGE_CODE=""
TEXT_ONLY=0
OUTPUT_FILE=""
DRY_RUN=0
TOKEN_OVERRIDE=""
API_KEY_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  if [[ "$1" == --*=* ]]; then
    set -- "${1%%=*}" "${1#*=}" "${@:2}"
  fi

  case "$1" in
    -f|--file)
      FILE_PATH="${2:-}"
      shift 2
      ;;
    -k|--file-key)
      FILE_KEY="${2:-}"
      shift 2
      ;;
    -t|--title)
      FILE_TITLE="${2:-}"
      shift 2
      ;;
    --content-type)
      CONTENT_TYPE_OVERRIDE="${2:-}"
      shift 2
      ;;
    --file-extension)
      FILE_EXTENSION_OVERRIDE="${2:-}"
      shift 2
      ;;
    --agent-id)
      AGENT_ID="${2:-}"
      shift 2
      ;;
    --task-id)
      TASK_ID="${2:-}"
      shift 2
      ;;
    --team-id)
      TEAM_ID="${2:-}"
      shift 2
      ;;
    --publish-type)
      PUBLISH_TYPE="${2:-}"
      shift 2
      ;;
    --tags)
      TAGS="${2:-}"
      shift 2
      ;;
    --category)
      CATEGORY="${2:-}"
      shift 2
      ;;
    --preview-image-url)
      PREVIEW_IMAGE_URL="${2:-}"
      shift 2
      ;;
    --description)
      DESCRIPTION="${2:-}"
      shift 2
      ;;
    --language-code)
      LANGUAGE_CODE="${2:-}"
      shift 2
      ;;
    --text-only)
      TEXT_ONLY=1
      shift
      ;;
    -o|--output)
      OUTPUT_FILE="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --token)
      TOKEN_OVERRIDE="${2:-}"
      shift 2
      ;;
    --api-key)
      API_KEY_OVERRIDE="${2:-}"
      shift 2
      ;;
    --api-base-url)
      API_BASE_URL="${2:-}"
      while [[ "$API_BASE_URL" == */ ]]; do API_BASE_URL="${API_BASE_URL%/}"; done
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Error: Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$FILE_PATH" ]]; then
  echo "Error: Missing required argument: --file" >&2
  exit 1
fi

if [[ ! -f "$FILE_PATH" ]]; then
  echo "Error: File not found or not a regular file: $FILE_PATH" >&2
  exit 1
fi

if [[ ! -r "$FILE_PATH" ]]; then
  echo "Error: File is not readable: $FILE_PATH" >&2
  exit 1
fi

# Detect extension and MIME type using Python
DETECT_RESULT="$TEMP_DIR/detect.json"

# Resolve python3 binary (prefer Homebrew python if available to bypass shim restrictions)
PYTHON_BIN=""
if [[ -x "/opt/homebrew/bin/python3" ]]; then
  PYTHON_BIN="/opt/homebrew/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
else
  echo "Error: python3 is required but was not found." >&2
  exit 1
fi

ENV_FILE_PATH="$FILE_PATH" \
ENV_EXT_OVERRIDE="$FILE_EXTENSION_OVERRIDE" \
ENV_MIME_OVERRIDE="$CONTENT_TYPE_OVERRIDE" \
ENV_TITLE_OVERRIDE="$FILE_TITLE" \
"$PYTHON_BIN" - "$DETECT_RESULT" <<'PY'
import os, sys, json, mimetypes
from pathlib import Path

out_file = sys.argv[1]
file_path = Path(os.environ["ENV_FILE_PATH"])
ext_override = os.environ.get("ENV_EXT_OVERRIDE", "").strip().lstrip(".")
mime_override = os.environ.get("ENV_MIME_OVERRIDE", "").strip()
title_override = os.environ.get("ENV_TITLE_OVERRIDE", "").strip()

# Extension resolution
if ext_override:
    file_ext = ext_override
else:
    file_ext = file_path.suffix.lstrip(".").lower()
    if not file_ext:
        file_ext = "bin"

# MIME type resolution
COMMON_MIMES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "gif": "image/gif",
    "svg": "image/svg+xml",
    "ico": "image/x-icon",
    "mp4": "video/mp4",
    "mov": "video/quicktime",
    "webm": "video/webm",
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "pdf": "application/pdf",
    "json": "application/json",
    "html": "text/html",
    "htm": "text/html",
    "css": "text/css",
    "js": "text/javascript",
    "txt": "text/plain",
    "csv": "text/csv",
    "xml": "application/xml",
    "zip": "application/zip",
    "tar": "application/x-tar",
    "gz": "application/gzip",
    "md": "text/markdown",
}

if mime_override:
    content_type = mime_override
elif file_ext in COMMON_MIMES:
    content_type = COMMON_MIMES[file_ext]
else:
    guessed, _ = mimetypes.guess_type(str(file_path))
    content_type = guessed or "application/octet-stream"

# Title resolution
resolved_title = title_override or file_path.stem or file_path.name

with open(out_file, "w", encoding="utf-8") as f:
    json.dump({
        "file_extension": file_ext,
        "content_type": content_type,
        "file_title": resolved_title,
    }, f)
PY

FILE_EXTENSION="$("$PYTHON_BIN" -c 'import json, sys; print(json.load(open(sys.argv[1]))["file_extension"])' "$DETECT_RESULT")"
CONTENT_TYPE="$("$PYTHON_BIN" -c 'import json, sys; print(json.load(open(sys.argv[1]))["content_type"])' "$DETECT_RESULT")"
RESOLVED_TITLE="$("$PYTHON_BIN" -c 'import json, sys; print(json.load(open(sys.argv[1]))["file_title"])' "$DETECT_RESULT")"

# Prepare payload for /s3/custom-upload-url
PAYLOAD_FILE="$TEMP_DIR/payload.json"
ENV_FILE_EXT="$FILE_EXTENSION" \
ENV_CONTENT_TYPE="$CONTENT_TYPE" \
ENV_SCENE_TYPE="$FIXED_SCENE_TYPE" \
ENV_FILE_TITLE="$RESOLVED_TITLE" \
ENV_FILE_KEY="$FILE_KEY" \
ENV_AGENT_ID="$AGENT_ID" \
ENV_TASK_ID="$TASK_ID" \
ENV_TEAM_ID="$TEAM_ID" \
ENV_PUBLISH_TYPE="$PUBLISH_TYPE" \
ENV_TAGS="$TAGS" \
ENV_CATEGORY="$CATEGORY" \
ENV_PREVIEW_IMG="$PREVIEW_IMAGE_URL" \
ENV_DESCRIPTION="$DESCRIPTION" \
ENV_LANG="$LANGUAGE_CODE" \
"$PYTHON_BIN" - "$PAYLOAD_FILE" <<'PY'
import os, sys, json

payload_file = sys.argv[1]

payload = {
    "file_extension": os.environ["ENV_FILE_EXT"],
    "content_type": os.environ["ENV_CONTENT_TYPE"],
    "scene_type": os.environ["ENV_SCENE_TYPE"],
}

file_title = os.environ.get("ENV_FILE_TITLE", "").strip()
if file_title:
    payload["file_title"] = file_title

file_key = os.environ.get("ENV_FILE_KEY", "").strip()
if file_key:
    payload["file_key"] = file_key

agent_id = os.environ.get("ENV_AGENT_ID", "").strip()
if agent_id:
    payload["agent_id"] = agent_id

task_id = os.environ.get("ENV_TASK_ID", "").strip()
if task_id:
    payload["task_id"] = task_id

team_id = os.environ.get("ENV_TEAM_ID", "").strip()
if team_id:
    payload["team_id"] = team_id

publish_type = os.environ.get("ENV_PUBLISH_TYPE", "").strip()
if publish_type:
    payload["publish_type"] = publish_type

tags_raw = os.environ.get("ENV_TAGS", "").strip()
if tags_raw:
    if tags_raw.startswith("[") and tags_raw.endswith("]"):
        try:
            payload["tags"] = json.loads(tags_raw)
        except Exception:
            payload["tags"] = [t.strip() for t in tags_raw.strip("[]").split(",") if t.strip()]
    else:
        payload["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]

category = os.environ.get("ENV_CATEGORY", "").strip()
if category:
    payload["category"] = category

preview_img = os.environ.get("ENV_PREVIEW_IMG", "").strip()
if preview_img:
    payload["preview_image_url"] = preview_img

desc = os.environ.get("ENV_DESCRIPTION", "").strip()
if desc:
    payload["description"] = desc

lang = os.environ.get("ENV_LANG", "").strip()
if lang:
    payload["language_code"] = lang

with open(payload_file, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)
PY

if [[ "$DRY_RUN" -eq 1 ]]; then
  cat "$PAYLOAD_FILE"
  exit 0
fi

# Auth resolution
TOKEN="${TOKEN_OVERRIDE:-${FREVANA_TOKEN:-}}"
API_KEY="${API_KEY_OVERRIDE:-${FREVANA_API_KEY:-}}"

if [[ -z "$TOKEN" && -z "$API_KEY" ]]; then
  if [[ -t 0 ]]; then
    read -r -s -p "Authentication required. Enter Frevana Bearer token: " TOKEN
    echo >&2
  fi
fi

if [[ -z "$TOKEN" && -z "$API_KEY" ]]; then
  echo "Error: Authentication required. Set FREVANA_TOKEN in environment or pass --token explicitly." >&2
  exit 1
fi

CURL_AUTH_HEADERS=()
if [[ -n "$TOKEN" ]]; then
  CURL_AUTH_HEADERS+=(-H "Authorization: Bearer $TOKEN")
elif [[ -n "$API_KEY" ]]; then
  CURL_AUTH_HEADERS+=(-H "Authorization: Bearer $API_KEY" -H "X-API-Key: $API_KEY")
fi

# Step 1: Request presigned upload URL
UPLOAD_URL_RESPONSE="$TEMP_DIR/upload_url_response.json"
HTTP_STATUS="$(
  curl -sS \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -o "$UPLOAD_URL_RESPONSE" \
    -w "%{http_code}" \
    -X POST "${API_BASE_URL}${UPLOAD_URL_PATH}" \
    -H "Content-Type: application/json" \
    "${CURL_AUTH_HEADERS[@]}" \
    --data @"$PAYLOAD_FILE"
)"

if [[ "$HTTP_STATUS" -lt 200 || "$HTTP_STATUS" -ge 300 ]]; then
  echo "Error: Failed to obtain upload URL from Frevana with HTTP $HTTP_STATUS" >&2
  cat "$UPLOAD_URL_RESPONSE" >&2
  echo "" >&2
  exit 1
fi

# Parse response fields
PARSED_RESPONSE="$TEMP_DIR/parsed.json"
"$PYTHON_BIN" - "$UPLOAD_URL_RESPONSE" "$PARSED_RESPONSE" <<'PY'
import sys, json

in_path = sys.argv[1]
out_path = sys.argv[2]

try:
    data = json.load(open(in_path, encoding="utf-8"))
except Exception as exc:
    sys.stderr.write(f"Error parsing API response: {exc}\n")
    sys.exit(1)

presigned_url = data.get("presigned_url") or ""
public_url = data.get("url") or ""
file_key = data.get("key") or data.get("file_key") or ""
content_id = str(data.get("content_id") or "")

if not presigned_url:
    sys.stderr.write("Error: API response missing 'presigned_url'\n")
    sys.exit(1)

with open(out_path, "w", encoding="utf-8") as f:
    json.dump({
        "presigned_url": presigned_url,
        "url": public_url,
        "file_key": file_key,
        "content_id": content_id,
    }, f)
PY

PRESIGNED_URL="$("$PYTHON_BIN" -c 'import json, sys; print(json.load(open(sys.argv[1]))["presigned_url"])' "$PARSED_RESPONSE")"
PUBLIC_URL="$("$PYTHON_BIN" -c 'import json, sys; print(json.load(open(sys.argv[1]))["url"])' "$PARSED_RESPONSE")"
RESULT_FILE_KEY="$("$PYTHON_BIN" -c 'import json, sys; print(json.load(open(sys.argv[1]))["file_key"])' "$PARSED_RESPONSE")"
CONTENT_ID="$("$PYTHON_BIN" -c 'import json, sys; print(json.load(open(sys.argv[1]))["content_id"])' "$PARSED_RESPONSE")"

# Step 2: Upload file directly to S3 presigned URL using PUT
# IMPORTANT: Do not forward Frevana auth headers to S3 presigned URL
UPLOAD_HTTP_CODE="$(
  curl -sS \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -o "$TEMP_DIR/s3_response.txt" \
    -w "%{http_code}" \
    -X PUT "$PRESIGNED_URL" \
    -H "Content-Type: $CONTENT_TYPE" \
    --upload-file "$FILE_PATH"
)"

if [[ "$UPLOAD_HTTP_CODE" -lt 200 || "$UPLOAD_HTTP_CODE" -ge 300 ]]; then
  echo "Error: S3 file upload failed with HTTP $UPLOAD_HTTP_CODE" >&2
  cat "$TEMP_DIR/s3_response.txt" >&2
  echo "" >&2
  exit 1
fi

# Step 3: Format and output result
RESULT_JSON="$TEMP_DIR/result.json"
"$PYTHON_BIN" - "$PUBLIC_URL" "$RESULT_FILE_KEY" "$CONTENT_ID" "$RESULT_JSON" <<'PY'
import sys, json

public_url = sys.argv[1]
file_key = sys.argv[2]
content_id = sys.argv[3]
out_file = sys.argv[4]

res = {
    "url": public_url,
    "file_key": file_key,
    "content_id": content_id,
}

with open(out_file, "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False, indent=2)
PY

if [[ "$TEXT_ONLY" -eq 1 ]]; then
  echo "$PUBLIC_URL"
else
  if [[ -n "$OUTPUT_FILE" ]]; then
    cp "$RESULT_JSON" "$OUTPUT_FILE"
  fi
  cat "$RESULT_JSON"
fi
