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
  automate.sh --steps '<json-array>' [--url "https://..."] [--allow-domains '<json-array>'] [--timeout MS] [--confirm-payment]

Perceive -> act loop: call repeatedly. First call passes --url + [{"op":"snapshot"}];
read the snapshot, then call again (omit --url to reuse the tab) with action steps that
reference the [ref]s you saw, ending in {"op":"snapshot"}.

Options:
  --steps            REQUIRED. JSON array of DSL step objects, e.g.
                     '[{"op":"type","ref":2,"text":"hello","submit":true},{"op":"snapshot"}]'
  --url              Open/reuse the dedicated Frevana tab at this http(s) URL (first call).
  --allow-domains    Optional JSON array; navigation/actions outside these are refused.
  --timeout          Optional frevana_automate timeout in milliseconds.
  --confirm-payment  ONE-SHOT: allow payment/place-order controls for THIS call only.
                     Pass ONLY after the human user explicitly confirmed the order in chat
                     (after being shown items + total price). Never on your own initiative.
  -h, --help         Show this help.

Step ops: navigate{url} | snapshot | click{ref} | type{ref,text,submit?} | select{ref,value}
  | scroll{to:"ref|top|bottom",ref?} | pressKey{key} | waitFor{for:"navigation|idle|ref",ref?}
  | assert{ref,exists?} | extract{ref,as} | getHtml{ref,as?} | wait{ms}

SAFETY: pay / place-order is blocked by default; a NEEDS HUMAN (payment) result means STOP,
show the user the order summary (items, total), and ask them to confirm in chat. Only after
an explicit user confirmation, re-send the single order-submit step with --confirm-payment.
Never retry a payment submit without asking the user again.

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

URL=""
STEPS=""
ALLOW_DOMAINS=""
TOOL_TIMEOUT=""
CONFIRM_PAYMENT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --url)
      URL="${2:-}"
      shift 2
      ;;
    --steps)
      STEPS="${2:-}"
      shift 2
      ;;
    --allow-domains)
      ALLOW_DOMAINS="${2:-}"
      shift 2
      ;;
    --timeout)
      TOOL_TIMEOUT="${2:-}"
      shift 2
      ;;
    --confirm-payment)
      CONFIRM_PAYMENT="1"
      shift
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

if [[ -z "$STEPS" ]]; then
  echo "Missing required argument: --steps (a JSON array of step objects)" >&2
  exit 1
fi

if [[ -n "$URL" ]]; then
  case "$URL" in
    http://*|https://*) ;;
    *)
      echo "Invalid --url value: $URL. Expected an absolute URL starting with http:// or https://." >&2
      exit 1
      ;;
  esac
fi

if [[ -n "$TOOL_TIMEOUT" ]]; then
  if ! [[ "$TOOL_TIMEOUT" =~ ^[0-9]+$ ]]; then
    echo "Invalid --timeout value: $TOOL_TIMEOUT. Expected a positive integer (milliseconds)." >&2
    exit 1
  fi
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

if [[ -n "$CONFIRM_PAYMENT" ]]; then
  echo "[automate] --confirm-payment: payment/place-order controls allowed for this single call (human-confirmed in chat)" >&2
fi

export URL STEPS ALLOW_DOMAINS TOOL_TIMEOUT CONFIRM_PAYMENT

# Build the JSON payload. --steps / --allow-domains are parsed as JSON so the agent
# passes structured DSL, not a stringified blob. Invalid JSON fails loudly here.
python3 - "$PAYLOAD_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path

payload_path = Path(sys.argv[1])

try:
    steps = json.loads(os.environ["STEPS"])
except json.JSONDecodeError as e:
    sys.stderr.write(f"--steps is not valid JSON: {e}\n")
    raise SystemExit(1)
if not isinstance(steps, list):
    sys.stderr.write("--steps must be a JSON array of step objects.\n")
    raise SystemExit(1)

payload = {"steps": steps}

url = os.environ.get("URL")
if url:
    payload["url"] = url

allow = os.environ.get("ALLOW_DOMAINS")
if allow:
    try:
        payload["allow_domains"] = json.loads(allow)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"--allow-domains is not valid JSON: {e}\n")
        raise SystemExit(1)

timeout = os.environ.get("TOOL_TIMEOUT")
if timeout:
    payload["timeout"] = int(timeout)

# One-shot human payment confirmation (see --confirm-payment in usage).
if os.environ.get("CONFIRM_PAYMENT"):
    payload["confirm_payment"] = True

payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
PY

"$FREVANA_BIN" call frevana_automate "$(cat "$PAYLOAD_FILE")" \
  --port "$DAEMON_PORT" \
  --timeout "$TIMEOUT_MS" > "$RESULT_FILE"

cat "$RESULT_FILE"
