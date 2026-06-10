#!/usr/bin/env bash

set -euo pipefail

PROVIDER="facebook"
TOOL_NAME="frevana_publish"
DAEMON_PORT="${FREVANA_PORT:-12306}"
FREVANA_TIMEOUT_SEC="${FREVANA_TIMEOUT:-180}"
TIMEOUT_MS=$(( FREVANA_TIMEOUT_SEC * 1000 ))
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
SETUP_SCRIPT="${SCRIPT_DIR}/setup.sh"

usage() {
  cat <<'EOF'
Usage:
  publish_facebook_post.sh --text "post text" [--format text|json] [--timeout MS] [--output /path/to/result.txt]

Options:
  --text       Final post text. Mutually exclusive with --text-file
  --text-file  UTF-8 text file containing final post text
  --format     Output format: text or json. Default text
  --timeout    Optional Frevana tool timeout in milliseconds
  --output     Optional file path for saving the publish result
  -h, --help   Show this help message

Environment:
  FREVANA_PORT     Local daemon port, default 12306
  FREVANA_TIMEOUT  frevana call timeout in seconds, default 180
EOF
}

run_frevana_setup() {
  local setup_output setup_status

  if [[ ! -x "$SETUP_SCRIPT" ]]; then
    echo "Error: Frevana setup wrapper not found or not executable: $SETUP_SCRIPT" >&2
    exit 1
  fi

  setup_output="$(mktemp)"
  set +e
  bash "$SETUP_SCRIPT" > "$setup_output"
  setup_status=$?
  set -e

  if [[ "$setup_status" -eq 0 ]]; then
    rm -f "$setup_output"
    return 0
  fi

  cat "$setup_output" >&2
  rm -f "$setup_output"

  if [[ "$setup_status" -eq 2 ]]; then
    echo "Frevana setup completed, but Chrome is not connected." >&2
    echo "Open Chrome, connect the Frevana extension, then retry." >&2
    exit 2
  fi

  echo "Error: Frevana setup script failed with exit code $setup_status." >&2
  exit "$setup_status"
}

TEXT=""
TEXT_FILE=""
OUTPUT_FORMAT="text"
TOOL_TIMEOUT=""
OUTPUT_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --text)
      TEXT="${2:-}"
      shift 2
      ;;
    --text-file)
      TEXT_FILE="${2:-}"
      shift 2
      ;;
    --format)
      OUTPUT_FORMAT="${2:-}"
      shift 2
      ;;
    --timeout)
      TOOL_TIMEOUT="${2:-}"
      shift 2
      ;;
    --output)
      OUTPUT_PATH="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -n "$TEXT" && -n "$TEXT_FILE" ]]; then
  echo "--text and --text-file are mutually exclusive." >&2
  exit 1
fi

if [[ -n "$TEXT_FILE" ]]; then
  if [[ ! -f "$TEXT_FILE" ]]; then
    echo "Invalid --text-file value: file not found: $TEXT_FILE" >&2
    exit 1
  fi
  TEXT="$(cat "$TEXT_FILE")"
fi

if [[ -z "$TEXT" ]]; then
  echo "Missing required argument: --text or --text-file" >&2
  exit 1
fi

if [[ -n "$TOOL_TIMEOUT" && ! "$TOOL_TIMEOUT" =~ ^[0-9]+$ ]]; then
  echo "Invalid --timeout value: $TOOL_TIMEOUT. Expected a positive integer." >&2
  exit 1
fi

if [[ "$OUTPUT_FORMAT" != "text" && "$OUTPUT_FORMAT" != "json" ]]; then
  echo "Invalid --format value: $OUTPUT_FORMAT. Allowed values: text, json" >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required but was not found in PATH." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required but was not found in PATH." >&2
  exit 1
fi

run_frevana_setup

EXT=""
case "$(uname -s 2>/dev/null || echo)" in
  MINGW*|MSYS*|CYGWIN*) EXT=".exe" ;;
esac

FREVANA_BIN="$HOME/.frevana/bin/frevana${EXT}"
if [[ ! -x "$FREVANA_BIN" ]]; then
  if command -v frevana >/dev/null 2>&1; then
    FREVANA_BIN="$(command -v frevana)"
  else
    echo "Error: Frevana setup completed but frevana binary was not found at $FREVANA_BIN or on PATH." >&2
    exit 1
  fi
fi

if ! curl -s --max-time 2 "http://127.0.0.1:${DAEMON_PORT}/health" >/dev/null 2>&1; then
  echo "Error: Frevana daemon is not running on port ${DAEMON_PORT}." >&2
  echo "Frevana setup was already run, but the daemon health check still failed." >&2
  exit 1
fi

PAYLOAD_FILE="$(mktemp)"
RESULT_FILE="$(mktemp)"
cleanup() {
  rm -f "$PAYLOAD_FILE" "$RESULT_FILE"
}
trap cleanup EXIT

export PROVIDER TEXT TOOL_TIMEOUT
python3 - "$PAYLOAD_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path

payload = {
    "provider": os.environ["PROVIDER"],
    "text": os.environ["TEXT"],
}
timeout = os.environ.get("TOOL_TIMEOUT")
if timeout:
    payload["timeout"] = int(timeout)

Path(sys.argv[1]).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
PY

"$FREVANA_BIN" call "$TOOL_NAME" "$(cat "$PAYLOAD_FILE")" \
  --port "$DAEMON_PORT" \
  --timeout "$TIMEOUT_MS" > "$RESULT_FILE"

if [[ "$OUTPUT_FORMAT" == "json" ]]; then
  python3 - "$RESULT_FILE" "$PROVIDER" <<'PY'
import json
import sys
from pathlib import Path

result_path = Path(sys.argv[1])
provider = sys.argv[2]
result = result_path.read_text(encoding="utf-8")
result_path.write_text(json.dumps({
    "tool": "frevana_publish",
    "provider": provider,
    "result": result,
}, ensure_ascii=False, indent=2), encoding="utf-8")
PY
fi

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  cp "$RESULT_FILE" "$OUTPUT_PATH"
  echo "Saved Facebook publish result to $OUTPUT_PATH" >&2
fi

cat "$RESULT_FILE"

