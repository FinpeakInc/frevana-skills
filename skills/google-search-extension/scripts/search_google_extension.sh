#!/usr/bin/env bash

set -euo pipefail

PROVIDER="google"
DAEMON_PORT="${FREVANA_PORT:-12306}"
FREVANA_TIMEOUT_SEC="${FREVANA_TIMEOUT:-180}"
TIMEOUT_MS=$(( FREVANA_TIMEOUT_SEC * 1000 ))
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
SETUP_SCRIPT="${SCRIPT_DIR}/setup.sh"

usage() {
  cat <<'EOF'
Usage:
  search_google_extension.sh --prompt "query 1" [--prompt "query 2"] [--prompt-file /path/to/queries.txt] [--format text|json] [--timeout MS] [--output /path/to/result.txt]

Options:
  --prompt       Prompt/query to send. May be repeated.
  --question     Alias for --prompt. May be repeated.
  --prompt-file  Optional UTF-8 text file with one prompt per non-empty line
  --format       Output format: text or json. Default text
  --timeout      Optional Frevana tool timeout in milliseconds
  --output       Optional file path for saving the answer(s)
  -h, --help     Show this help message

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
  else
    echo "Error: Frevana setup script failed with exit code $setup_status." >&2
    exit "$setup_status"
  fi
}

PROMPTS=()
PROMPT_FILE=""
OUTPUT_FORMAT="text"
TOOL_TIMEOUT=""
OUTPUT_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prompt|--question)
      PROMPTS+=("${2:-}")
      shift 2
      ;;
    --prompt-file)
      PROMPT_FILE="${2:-}"
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

if [[ -n "$PROMPT_FILE" ]]; then
  if [[ ! -f "$PROMPT_FILE" ]]; then
    echo "Invalid --prompt-file value: file not found: $PROMPT_FILE" >&2
    exit 1
  fi
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" ]] && continue
    PROMPTS+=("$line")
  done < "$PROMPT_FILE"
fi

if [[ "${#PROMPTS[@]}" -eq 0 ]]; then
  echo "Missing required argument: --prompt" >&2
  exit 1
fi

for prompt in "${PROMPTS[@]}"; do
  if [[ -z "$prompt" ]]; then
    echo "Invalid --prompt value: prompt cannot be empty." >&2
    exit 1
  fi
done

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

RESULT_FILE="$(mktemp)"
JSON_ITEMS_DIR="$(mktemp -d)"
cleanup() {
  rm -f "$RESULT_FILE"
  rm -rf "$JSON_ITEMS_DIR"
}
trap cleanup EXIT

>"$RESULT_FILE"

prompt_count="${#PROMPTS[@]}"
for index in "${!PROMPTS[@]}"; do
  prompt="${PROMPTS[$index]}"
  if [[ -z "$prompt" ]]; then
    echo "Invalid --prompt value: prompt cannot be empty." >&2
    exit 1
  fi

  payload_file="$(mktemp)"
  export PROVIDER PROMPT="$prompt" TOOL_TIMEOUT
  python3 - "$payload_file" <<'PY'
import json
import os
import sys
from pathlib import Path

payload = {
    "provider": os.environ["PROVIDER"],
    "prompt": os.environ["PROMPT"],
}

timeout = os.environ.get("TOOL_TIMEOUT")
if timeout:
    payload["timeout"] = int(timeout)

Path(sys.argv[1]).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
PY

  answer_file="$(mktemp)"
  "$FREVANA_BIN" call frevana_ask "$(cat "$payload_file")" \
    --port "$DAEMON_PORT" \
    --timeout "$TIMEOUT_MS" > "$answer_file"

  rm -f "$payload_file"

  if (( prompt_count > 1 )); then
    {
      if (( index > 0 )); then
        printf '\n'
      fi
      printf '## Question %d\n\n' "$((index + 1))"
      printf '%s\n\n' "$prompt"
      printf '## Answer %d\n\n' "$((index + 1))"
      cat "$answer_file"
      printf '\n'
    } >> "$RESULT_FILE"
  else
    cat "$answer_file" > "$RESULT_FILE"
  fi

  if [[ "$OUTPUT_FORMAT" == "json" ]]; then
    item_file="${JSON_ITEMS_DIR}/item-${index}.json"
    python3 - "$item_file" "$PROVIDER" "$((index + 1))" "$prompt" "$answer_file" <<'PY'
import json
import sys
from pathlib import Path

item_path = Path(sys.argv[1])
provider = sys.argv[2]
index = int(sys.argv[3])
prompt = sys.argv[4]
answer = Path(sys.argv[5]).read_text(encoding="utf-8")

item_path.write_text(json.dumps({
    "index": index,
    "provider": provider,
    "prompt": prompt,
    "answer": answer,
}, ensure_ascii=False), encoding="utf-8")
PY
  fi

  rm -f "$answer_file"
done

if [[ "$OUTPUT_FORMAT" == "json" ]]; then
  python3 - "$RESULT_FILE" "$PROVIDER" "$JSON_ITEMS_DIR" <<'PY'
import json
import sys
from pathlib import Path

result_path = Path(sys.argv[1])
provider = sys.argv[2]
items_dir = Path(sys.argv[3])

items = []
for path in sorted(items_dir.glob("item-*.json"), key=lambda p: int(p.stem.split("-")[1])):
    items.append(json.loads(path.read_text(encoding="utf-8")))

result_path.write_text(json.dumps({
    "provider": provider,
    "count": len(items),
    "results": items,
}, ensure_ascii=False, indent=2), encoding="utf-8")
PY
fi

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  cp "$RESULT_FILE" "$OUTPUT_PATH"
  echo "Saved Google Search answer to $OUTPUT_PATH" >&2
fi

cat "$RESULT_FILE"
