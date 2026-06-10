#!/usr/bin/env bash

set -euo pipefail

PROVIDER="amazon-product-reviews"
DEFAULT_TOOL_TIMEOUT="180000"
DAEMON_PORT="${FREVANA_PORT:-12306}"
FREVANA_TIMEOUT_SEC="${FREVANA_TIMEOUT:-240}"
TIMEOUT_MS=$(( FREVANA_TIMEOUT_SEC * 1000 ))
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
SETUP_SCRIPT="${SCRIPT_DIR}/setup.sh"

usage() {
  cat <<'EOF'
Usage:
  get_amazon_top_reviews.sh --url "https://www.amazon.com/dp/B0XXXXXXXX" [--max-reviews 100] [--sort-by helpful] [--reviewer-type all_reviews] [--filter-by-star five_star] [--format text|json] [--timeout MS] [--output /path/to/result.txt]

Options:
  --url             Full Amazon product page URL containing /dp/<ASIN> or /gp/product/<ASIN>
  --max-reviews     Optional review cap. Default provider behavior is 100; max 500
  --sort-by         Optional Amazon reviews sort value, for example helpful
  --reviewer-type   Optional Amazon reviewer type, for example all_reviews
  --filter-by-star  Optional star filter, for example five_star
  --format          Output format: text or json. Default text
  --timeout         Optional Frevana tool timeout in milliseconds. Default 180000
  --output          Optional file path for saving the result
  -h, --help        Show this help message

Environment:
  FREVANA_PORT     Local daemon port, default 12306
  FREVANA_TIMEOUT  frevana call timeout in seconds, default 240
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

URL=""
MAX_REVIEWS=""
SORT_BY=""
REVIEWER_TYPE=""
FILTER_BY_STAR=""
OUTPUT_FORMAT="text"
TOOL_TIMEOUT="$DEFAULT_TOOL_TIMEOUT"
OUTPUT_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --url)
      URL="${2:-}"
      shift 2
      ;;
    --max-reviews)
      MAX_REVIEWS="${2:-}"
      shift 2
      ;;
    --sort-by)
      SORT_BY="${2:-}"
      shift 2
      ;;
    --reviewer-type)
      REVIEWER_TYPE="${2:-}"
      shift 2
      ;;
    --filter-by-star)
      FILTER_BY_STAR="${2:-}"
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

if [[ -z "$URL" ]]; then
  echo "Missing required argument: --url" >&2
  exit 1
fi

if ! [[ "$URL" =~ ^https?://([^/]+.)?amazon.[^/]+/.*(dp|gp/product)/[A-Za-z0-9]{10} ]]; then
  echo "Invalid --url value: expected a full Amazon product URL containing /dp/<ASIN> or /gp/product/<ASIN>." >&2
  exit 1
fi

if [[ -n "$MAX_REVIEWS" ]]; then
  if ! [[ "$MAX_REVIEWS" =~ ^[0-9]+$ ]] || (( MAX_REVIEWS < 1 || MAX_REVIEWS > 500 )); then
    echo "Invalid --max-reviews value: $MAX_REVIEWS. Expected an integer from 1 to 500." >&2
    exit 1
  fi
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
PROMPT_FILE="$(mktemp)"
cleanup() {
  rm -f "$PAYLOAD_FILE" "$RESULT_FILE" "$PROMPT_FILE"
}
trap cleanup EXIT

export URL MAX_REVIEWS SORT_BY REVIEWER_TYPE FILTER_BY_STAR PROMPT_FILE
python3 - <<'PY'
import json
import os
from pathlib import Path

config = {}
if os.environ.get("MAX_REVIEWS"):
    config["maxReviews"] = int(os.environ["MAX_REVIEWS"])
if os.environ.get("SORT_BY"):
    config["sortBy"] = os.environ["SORT_BY"]
if os.environ.get("REVIEWER_TYPE"):
    config["reviewerType"] = os.environ["REVIEWER_TYPE"]
if os.environ.get("FILTER_BY_STAR"):
    config["filterByStar"] = os.environ["FILTER_BY_STAR"]

prompt = os.environ["URL"]
if config:
    prompt += " " + json.dumps(config, ensure_ascii=False, separators=(",", ":"))

Path(os.environ["PROMPT_FILE"]).write_text(prompt, encoding="utf-8")
PY

PROMPT="$(cat "$PROMPT_FILE")"
export PROVIDER PROMPT TOOL_TIMEOUT
python3 - "$PAYLOAD_FILE" <<'PY'
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

"$FREVANA_BIN" call frevana_ask "$(cat "$PAYLOAD_FILE")" \
  --port "$DAEMON_PORT" \
  --timeout "$TIMEOUT_MS" > "$RESULT_FILE"

if [[ "$OUTPUT_FORMAT" == "json" ]]; then
  python3 - "$RESULT_FILE" "$PROVIDER" "$PROMPT" <<'PY'
import json
import sys
from pathlib import Path

result_path = Path(sys.argv[1])
provider = sys.argv[2]
prompt = sys.argv[3]
answer = result_path.read_text(encoding="utf-8")
result_path.write_text(json.dumps({
    "provider": provider,
    "prompt": prompt,
    "answer": answer,
}, ensure_ascii=False, indent=2), encoding="utf-8")
PY
fi

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  cp "$RESULT_FILE" "$OUTPUT_PATH"
  echo "Saved Amazon top reviews result to $OUTPUT_PATH" >&2
fi

cat "$RESULT_FILE"

