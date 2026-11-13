#!/usr/bin/env bash

set -euo pipefail

FIXED_MODEL="bytedance-seed/seedream-5-5"
DEFAULT_API_BASE_URL="https://ai-factory.frevana.com"
API_BASE_URL="${FREVANA_API_BASE_URL:-$DEFAULT_API_BASE_URL}"
while [[ "$API_BASE_URL" == */ ]]; do API_BASE_URL="${API_BASE_URL%/}"; done
[[ "$API_BASE_URL" =~ ^https?://[^/?#]+(/[^?#]*)?$ ]] || { echo "Invalid API base URL: ${API_BASE_URL:-<empty>}" >&2; exit 1; }
ENDPOINT="/openrouter/v1/images"
MAX_IMAGE_COUNT=10
MAX_IMAGE_SIZE_BYTES=$((50 * 1024 * 1024))
MAX_JSON_BODY_BYTES=$((50 * 1024 * 1024))
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

usage() {
  cat <<'EOF'
Usage:
  generate_image.sh (--prompt "image prompt" | --contents "image prompt") [options]

Model and image settings:
  --model                bytedance-seed/seedream-5-5 (alias: seedream-5-5)
  --n                    Must be 1
  --resolution           1K, 1.5K, or 2K
  --aspect-ratio         Supported Seedream aspect ratio or auto
  --seed                 Integer seed
  --image                Local PNG/JPEG/WebP reference (repeatable, <50MB)
  --image-url            Remote HTTP(S) reference (repeatable)
  --image-dir            Reference image directory (repeatable, recursive)
  --session-id           Optional session ID (maximum 256 characters)
  --user                 Optional user attribution string

Auth and output:
  --token                Required Frevana Bearer token override
  --api-key              Optional supplemental Frevana API key header
  --agent-app-instance-id Agent App instance/team ID override
  --output               Optional path for returned JSON
  -h, --help             Show help
EOF
}

is_allowed() { local value="$1"; shift; local item; for item in "$@"; do [[ "$value" == "$item" ]] && return 0; done; return 1; }
is_integer() { [[ "$1" =~ ^-?[0-9]+$ ]]; }
is_http_url() { [[ "$1" =~ ^https?://[^[:space:]]+$ ]]; }
is_image_path() { [[ "$1" =~ \.(png|PNG|jpg|JPG|jpeg|JPEG|webp|WEBP)$ ]]; }

PROMPT=""
MODEL="$FIXED_MODEL"
N=""
RESOLUTION=""
ASPECT_RATIO=""
SEED=""
SESSION_ID=""
USER_VALUE=""
API_KEY_OVERRIDE=""
TOKEN_OVERRIDE=""
AGENT_APP_INSTANCE_ID_OVERRIDE=""
OUTPUT_PATH=""
INPUT_SPECS=("sentinel:")

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prompt|--contents|--model|--n|--resolution|--aspect-ratio|--seed|--image|--image-url|--image-dir|--session-id|--user|--api-key|--token|--agent-app-instance-id|--output)
      [[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 1; }
      ;;
  esac
  case "$1" in
    --prompt|--contents) PROMPT="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    --n) N="$2"; shift 2 ;;
    --resolution) RESOLUTION="$2"; shift 2 ;;
    --aspect-ratio) ASPECT_RATIO="$2"; shift 2 ;;
    --seed) SEED="$2"; shift 2 ;;
    --image) INPUT_SPECS+=("file:$2"); shift 2 ;;
    --image-url) INPUT_SPECS+=("url:$2"); shift 2 ;;
    --image-dir) INPUT_SPECS+=("dir:$2"); shift 2 ;;
    --session-id) SESSION_ID="$2"; shift 2 ;;
    --user) USER_VALUE="$2"; shift 2 ;;
    --api-key) API_KEY_OVERRIDE="$2"; shift 2 ;;
    --token) TOKEN_OVERRIDE="$2"; shift 2 ;;
    --agent-app-instance-id) AGENT_APP_INSTANCE_ID_OVERRIDE="$2"; shift 2 ;;
    --output) OUTPUT_PATH="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    --provider|--provider=*) echo "This skill fixes the provider and model." >&2; exit 1 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done

[[ -n "${PROMPT//[[:space:]]/}" ]] || { echo "Missing required argument: --prompt or --contents" >&2; exit 1; }
(( ${#PROMPT} <= 32000 )) || { echo "Prompt exceeds 32000 characters." >&2; exit 1; }
case "$MODEL" in
  bytedance-seed/seedream-5-5|seedream-5-5) MODEL="$FIXED_MODEL" ;;
  *) echo "Invalid model: $MODEL" >&2; echo "Allowed model: $FIXED_MODEL" >&2; exit 1 ;;
esac
[[ -z "$N" || "$N" == "1" ]] || { echo "Invalid --n: $N (Seedream 5.5 supports exactly 1)" >&2; exit 1; }
[[ -z "$RESOLUTION" ]] || is_allowed "$RESOLUTION" 1K 1.5K 2K || { echo "Invalid --resolution: $RESOLUTION" >&2; exit 1; }
[[ -z "$ASPECT_RATIO" ]] || is_allowed "$ASPECT_RATIO" 1:1 1:2 2:1 2:3 3:2 3:4 4:3 4:5 5:4 9:16 16:9 9:19.5 19.5:9 9:20 20:9 9:21 21:9 auto || { echo "Invalid --aspect-ratio: $ASPECT_RATIO" >&2; exit 1; }
[[ -z "$SEED" ]] || is_integer "$SEED" || { echo "Invalid --seed: $SEED (must be an integer)" >&2; exit 1; }
(( ${#SESSION_ID} <= 256 )) || { echo "--session-id exceeds 256 characters." >&2; exit 1; }

command -v curl >/dev/null 2>&1 || { echo "curl is required." >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is required." >&2; exit 1; }

EXPANDED_INPUTS="$TEMP_DIR/inputs.txt"
: > "$EXPANDED_INPUTS"
for spec in "${INPUT_SPECS[@]}"; do
  kind="${spec%%:*}"
  value="${spec#*:}"
  case "$kind" in
    sentinel) ;;
    file)
      [[ -f "$value" ]] || { echo "Reference image not found: $value" >&2; exit 1; }
      is_image_path "$value" || { echo "Unsupported reference image type: $value" >&2; exit 1; }
      printf 'file\t%s\n' "$value" >> "$EXPANDED_INPUTS"
      ;;
    url)
      is_http_url "$value" || { echo "Invalid --image-url: $value" >&2; exit 1; }
      printf 'url\t%s\n' "$value" >> "$EXPANDED_INPUTS"
      ;;
    dir)
      [[ -d "$value" ]] || { echo "Reference image directory not found: $value" >&2; exit 1; }
      while IFS= read -r -d '' path; do printf 'file\t%s\n' "$path" >> "$EXPANDED_INPUTS"; done < <(
        python3 - "$value" <<'PYDIR'
import os, pathlib, sys
root = pathlib.Path(sys.argv[1])
paths = []
for current, directories, files in os.walk(root):
    directories.sort(key=os.fsencode)
    for name in files:
        path = pathlib.Path(current, name)
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            paths.append(path)
for path in sorted(paths, key=lambda item: os.fsencode(str(item))):
    sys.stdout.buffer.write(os.fsencode(str(path)) + b"\0")
PYDIR
      )
      ;;
  esac
done

INPUT_COUNT="$(wc -l < "$EXPANDED_INPUTS" | tr -d ' ')"
(( INPUT_COUNT <= MAX_IMAGE_COUNT )) || { echo "Too many reference images: $INPUT_COUNT (maximum $MAX_IMAGE_COUNT)" >&2; exit 1; }

PAYLOAD_FILE="$TEMP_DIR/payload.json"
export MODEL PROMPT N RESOLUTION ASPECT_RATIO SEED SESSION_ID USER_VALUE MAX_IMAGE_SIZE_BYTES EXPANDED_INPUTS PAYLOAD_FILE
python3 <<'PY'
import base64, json, os, pathlib, sys

refs = []
with open(os.environ["EXPANDED_INPUTS"], encoding="utf-8") as source:
    rows = [line.rstrip("\n").split("\t", 1) for line in source if line.strip()]
for kind, value in rows:
    if kind == "url":
        url = value
    else:
        path = pathlib.Path(value)
        size = path.stat().st_size
        if size >= int(os.environ["MAX_IMAGE_SIZE_BYTES"]):
            raise SystemExit(f"Reference image must be under 50MB: {value}")
        data = path.read_bytes()
        suffix = path.suffix.lower()
        signatures = {
            ".png": ("image/png", data.startswith(b"\x89PNG\r\n\x1a\n")),
            ".jpg": ("image/jpeg", data.startswith(b"\xff\xd8\xff")),
            ".jpeg": ("image/jpeg", data.startswith(b"\xff\xd8\xff")),
            ".webp": ("image/webp", data[:4] == b"RIFF" and data[8:12] == b"WEBP"),
        }
        mime, valid = signatures[suffix]
        if not valid:
            raise SystemExit(f"File does not match its declared image format: {value}")
        url = f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
    refs.append({"type": "image_url", "imageUrl": {"url": url}})

payload = {"model": os.environ["MODEL"], "prompt": os.environ["PROMPT"], "n": 1, "stream": False}
optional = {
    "resolution": os.environ.get("RESOLUTION"),
    "aspectRatio": os.environ.get("ASPECT_RATIO"),
    "sessionId": os.environ.get("SESSION_ID"),
    "user": os.environ.get("USER_VALUE"),
}
payload.update({k: v for k, v in optional.items() if v})
if os.environ.get("SEED"):
    payload["seed"] = int(os.environ["SEED"])
if refs:
    payload["inputReferences"] = refs
with open(os.environ["PAYLOAD_FILE"], "w", encoding="utf-8") as target:
    json.dump(payload, target, ensure_ascii=False, separators=(",", ":"))
PY

PAYLOAD_SIZE="$(python3 - "$PAYLOAD_FILE" <<'PY'
import os, sys
print(os.path.getsize(sys.argv[1]))
PY
)"
if (( PAYLOAD_SIZE >= MAX_JSON_BODY_BYTES )); then
  echo "Encoded image request exceeds the server's 50MB JSON body limit (${PAYLOAD_SIZE} bytes). Use smaller local references or remote image URLs." >&2
  exit 1
fi

API_KEY="${API_KEY_OVERRIDE:-${FREVANA_API_KEY:-}}"
TOKEN="${TOKEN_OVERRIDE:-${FREVANA_TOKEN:-}}"
AGENT_APP_INSTANCE_ID="${AGENT_APP_INSTANCE_ID_OVERRIDE:-${FREVANA_AGENT_APP_INSTANCE_ID:-${X_FREVANA_AGENT_APP_INSTANCE_ID:-}}}"
[[ -n "$TOKEN" ]] || { echo "Bearer authentication required: set FREVANA_TOKEN or pass --token. FREVANA_API_KEY does not replace the token for this server route." >&2; exit 1; }

RESPONSE_FILE="$TEMP_DIR/response.json"
HEADERS_FILE="$TEMP_DIR/response.headers"
: > "$HEADERS_FILE"
CURL_ARGS=(-sS --connect-timeout 10 --max-time 600 -X POST "$API_BASE_URL$ENDPOINT" -H 'Content-Type: application/json' --data-binary "@$PAYLOAD_FILE" -D "$HEADERS_FILE" -o "$RESPONSE_FILE" -w '%{http_code}')
[[ -n "$API_KEY" ]] && CURL_ARGS+=(-H "X-API-Key: $API_KEY")
[[ -n "$TOKEN" ]] && CURL_ARGS+=(-H "Authorization: Bearer $TOKEN")
[[ -n "$AGENT_APP_INSTANCE_ID" ]] && CURL_ARGS+=(-H "x-frevana-agent-app-instance-id: $AGENT_APP_INSTANCE_ID")

set +e
HTTP_STATUS="$(curl "${CURL_ARGS[@]}")"
CURL_STATUS=$?
set -e
REQUEST_ID="$(python3 - "$HEADERS_FILE" <<'PY'
import sys
values = []
with open(sys.argv[1], encoding="utf-8", errors="replace") as source:
    for line in source:
        if line.lower().startswith("x-request-id:"):
            value = line.split(":", 1)[1].strip()
            if value:
                values.append(value)
print(values[-1] if values else "")
PY
)"
[[ -z "$REQUEST_ID" ]] || echo "Frevana request ID: $REQUEST_ID" >&2
if (( CURL_STATUS != 0 )); then
  echo "Frevana API request failed: curl exited $CURL_STATUS. The generation outcome may be uncertain; do not retry automatically." >&2
  exit "$CURL_STATUS"
fi
[[ -s "$RESPONSE_FILE" ]] || { echo "Frevana API returned an empty response (HTTP $HTTP_STATUS)." >&2; exit 1; }
cat "$RESPONSE_FILE"
printf '\n'
if [[ ! "$HTTP_STATUS" =~ ^2[0-9][0-9]$ ]]; then
  echo "Frevana API returned HTTP $HTTP_STATUS. Do not retry automatically." >&2
  exit 1
fi

python3 - "$RESPONSE_FILE" "$OUTPUT_PATH" <<'PY'
import json, os, pathlib, sys, tempfile
source, output = sys.argv[1:]
with open(source, encoding="utf-8") as f:
    data = json.load(f)
if not isinstance(data.get("created"), (int, float)) or not isinstance(data.get("credits_consumed"), (int, float)):
    raise SystemExit("Invalid Frevana image response: missing created or credits_consumed")
items = data.get("data")
if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0].get("image_url"), str):
    raise SystemExit("Invalid Frevana image response: expected one hosted image")
if output:
    path = pathlib.Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(temp_path, path)
    except BaseException:
        try: os.unlink(temp_path)
        except FileNotFoundError: pass
        raise
PY
