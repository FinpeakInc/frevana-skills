#!/usr/bin/env bash

set -euo pipefail

DAEMON_PORT="${FREVANA_PORT:-12306}"
FREVANA_TIMEOUT_SEC="${FREVANA_TIMEOUT:-180}"
TIMEOUT_MS=$(( FREVANA_TIMEOUT_SEC * 1000 ))
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
SETUP_SCRIPT="${SCRIPT_DIR}/setup.sh"

usage() {
  cat <<'EOF'
Usage:
  search_reddit.sh --q "openai" [--sort new|top] [--limit 25] [--after TOKEN] [--timeout MS] [--output /path/to/result.json]

Options:
  --q          Search query to send
  --query      Alias for --q
  --sort       Sort order: new or top (default: new)
  --limit      Number of results to request, 1-100 (default: 25)
  --after      Optional pagination token from previous response data.after
  --timeout    Optional Frevana scrape timeout in milliseconds
  --output     Optional file path for saving returned JSON
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
  else
    echo "Error: Frevana setup script failed with exit code $setup_status." >&2
    exit "$setup_status"
  fi
}

Q=""
SORT="new"
LIMIT="25"
AFTER=""
TOOL_TIMEOUT=""
OUTPUT_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --q|--query)
      Q="${2:-}"
      shift 2
      ;;
    --sort)
      SORT="${2:-}"
      shift 2
      ;;
    --limit)
      LIMIT="${2:-}"
      shift 2
      ;;
    --after)
      AFTER="${2:-}"
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

if [[ -z "$Q" ]]; then
  echo "Missing required argument: --q" >&2
  exit 1
fi

if [[ "$SORT" != "new" && "$SORT" != "top" ]]; then
  echo "Error: --sort must be either 'new' or 'top'. Got: $SORT" >&2
  exit 1
fi

if [[ ! "$LIMIT" =~ ^[0-9]+$ ]]; then
  echo "Error: --limit must be an integer from 1 to 100. Got: $LIMIT" >&2
  exit 1
fi

if (( LIMIT < 1 || LIMIT > 100 )); then
  echo "Error: --limit must be between 1 and 100. Got: $LIMIT" >&2
  exit 1
fi

if [[ -n "$TOOL_TIMEOUT" && ! "$TOOL_TIMEOUT" =~ ^[0-9]+$ ]]; then
  echo "Invalid --timeout value: $TOOL_TIMEOUT. Expected a positive integer." >&2
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
HOME_PAYLOAD_FILE="$(mktemp)"
SCRAPE_FILE="$(mktemp)"
RESULT_FILE="$(mktemp)"
cleanup() {
  rm -f "$PAYLOAD_FILE" "$HOME_PAYLOAD_FILE" "$SCRAPE_FILE" "$RESULT_FILE"
}
trap cleanup EXIT

export Q SORT LIMIT AFTER TOOL_TIMEOUT

python3 - "$HOME_PAYLOAD_FILE" "$PAYLOAD_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlencode

home_payload_path = Path(sys.argv[1])
search_payload_path = Path(sys.argv[2])

params = {
    "q": os.environ["Q"],
    "type": "link",
    "sort": os.environ["SORT"],
    "limit": os.environ["LIMIT"],
}

after = os.environ.get("AFTER", "").strip()
if after:
    params["after"] = after

timeout = os.environ.get("TOOL_TIMEOUT", "").strip()

home_payload = {
    "url": "https://www.reddit.com/",
    "provider": "url",
}
search_payload = {
    "url": "https://www.reddit.com/search.json?" + urlencode(params),
    "provider": "url",
}

if timeout:
    home_payload["timeout"] = int(timeout)
    search_payload["timeout"] = int(timeout)

home_payload_path.write_text(json.dumps(home_payload, ensure_ascii=False), encoding="utf-8")
search_payload_path.write_text(json.dumps(search_payload, ensure_ascii=False), encoding="utf-8")
PY

# Warm up the browser/extension session on reddit.com before requesting the JSON URL.
"$FREVANA_BIN" call frevana_scrape "$(cat "$HOME_PAYLOAD_FILE")" \
  --port "$DAEMON_PORT" \
  --timeout "$TIMEOUT_MS" >/dev/null

"$FREVANA_BIN" call frevana_scrape "$(cat "$PAYLOAD_FILE")" \
  --port "$DAEMON_PORT" \
  --timeout "$TIMEOUT_MS" > "$SCRAPE_FILE"

python3 - "$SCRAPE_FILE" "$RESULT_FILE" <<'PY'
import html
import json
import re
import sys
from pathlib import Path

scrape_path = Path(sys.argv[1])
result_path = Path(sys.argv[2])
raw = scrape_path.read_text(encoding="utf-8")

def candidate_strings(text):
    stripped = text.strip()
    if stripped:
        yield stripped

    for match in re.finditer(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE):
        yield match.group(1).strip()

    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and last > first:
        yield text[first:last + 1]

    unescaped = html.unescape(text)
    if unescaped != text:
        first = unescaped.find("{")
        last = unescaped.rfind("}")
        if first != -1 and last != -1 and last > first:
            yield unescaped[first:last + 1]


def markdown_unescape_json(text):
    # frevana_scrape can return JSON as Markdown, escaping punctuation such as
    # underscores and brackets. These escapes are invalid inside JSON tokens.
    previous = None
    current = text
    while previous != current:
        previous = current
        current = re.sub(r"\\([_*\[\]{}()#+.!`>-])", r"\1", current)

    # JSON strings legitimately use \" for embedded quotes. Markdown rendering
    # can add one more slash, producing \\" which json.loads rejects.
    current = current.replace('\\\\\"', '\\\"')
    return current


expanded_candidates = []
for candidate in candidate_strings(raw):
    expanded_candidates.append(candidate)
    unescaped = markdown_unescape_json(candidate)
    if unescaped != candidate:
        expanded_candidates.append(unescaped)
    html_unescaped = html.unescape(candidate)
    if html_unescaped != candidate:
        expanded_candidates.append(html_unescaped)
        html_markdown_unescaped = markdown_unescape_json(html_unescaped)
        if html_markdown_unescaped != html_unescaped:
            expanded_candidates.append(html_markdown_unescaped)

for candidate in expanded_candidates:
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        continue

    result_path.write_text(json.dumps(parsed, ensure_ascii=False), encoding="utf-8")
    break
else:
    print("Reddit extension scrape did not return parseable JSON.", file=sys.stderr)
    print(raw[:4000], file=sys.stderr)
    if len(raw) > 4000:
        print("\n[response truncated]", file=sys.stderr)
    sys.exit(1)
PY

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  cp "$RESULT_FILE" "$OUTPUT_PATH"
fi

cat "$RESULT_FILE"
