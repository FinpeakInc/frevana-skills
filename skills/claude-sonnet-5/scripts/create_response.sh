#!/usr/bin/env bash

set -euo pipefail

FIXED_PROVIDER="openrouter"
DEFAULT_MODEL="anthropic/claude-sonnet-5"
DEFAULT_API_BASE_URL="https://ai-factory.frevana.com"
API_BASE_URL="${FREVANA_API_BASE_URL:-$DEFAULT_API_BASE_URL}"
while [[ "$API_BASE_URL" == */ ]]; do API_BASE_URL="${API_BASE_URL%/}"; done; [[ "$API_BASE_URL" =~ ^https?://[^/]+ ]] || { echo "Invalid API base URL after normalisation: ${API_BASE_URL:-<empty>}" >&2; exit 1; }
RESPONSES_PATH="/openrouter/v1/responses"
CONNECT_TIMEOUT="10"
MAX_TIME="600"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

usage() {
  cat <<'EOF'
Usage:
  create_response.sh (--input "prompt text" | --input-file /path/to/file) [options]

Model:
  --model                anthropic/claude-sonnet-5 (default)

Responses options:
  --input, --prompt      Input text prompt or JSON message array
  --input-file           Path to file containing input text or JSON messages
  --instructions         System-level developer instructions
  --instructions-file    Path to file containing system instructions
  --reasoning-effort     Reasoning effort: low, medium, high
  --temperature          Sampling temperature (0.0 - 2.0)
  --top-p                Top-p nucleus sampling (0.0 - 1.0)
  --max-output-tokens    Maximum tokens to generate
  --session              Session name (e.g. default, chat1) saved under ~/.frevana/sessions
  --session-file         File path to persist/resume conversation state across calls
  --new-session, --new   Reset conversation context and start a fresh session
  --no-session           Disable session persistence for this run
  --previous-response-id Continue a previous response (multi-turn conversation by ID)
  --chat                 Start an interactive chat session in the terminal
  --service-tier         Latency/pricing tier: auto, default, flex, priority, ultrafast
  --tools                JSON array string of tools
  --tools-file           Path to JSON file with tools definitions
  --tool-choice          Tool choice strategy: auto, required, none, or JSON object
  --raw-payload-file     Path to complete JSON payload file to send to the Responses API

Auth & Attribution:
  --api-key              Frevana API key (or FREVANA_API_KEY env)
  --token                Frevana Bearer token (or FREVANA_TOKEN env)
  --agent-app-instance-id Agent App instance/team ID (or FREVANA_AGENT_APP_INSTANCE_ID env)

Output:
  --text-only, -t        Output only the extracted response text
  --output               Optional path to save full response JSON
  -h, --help             Show help
EOF
}

is_allowed() {
  local value="$1"
  shift
  local allowed
  for allowed in "$@"; do
    [[ "$value" == "$allowed" ]] && return 0
  done
  return 1
}

is_integer() { [[ "$1" =~ ^[0-9]+$ ]]; }
is_number() { [[ "$1" =~ ^-?[0-9]+([.][0-9]+)?$ ]]; }

MODEL="$DEFAULT_MODEL"
INPUT=""
INPUT_FILE=""
INSTRUCTIONS=""
INSTRUCTIONS_FILE=""
REASONING_EFFORT=""
TEMPERATURE=""
TOP_P=""
MAX_OUTPUT_TOKENS=""
SESSION_NAME=""
SESSION_FILE=""
NEW_SESSION=0
NO_SESSION=0
PREVIOUS_RESPONSE_ID=""
SERVICE_TIER=""
TOOLS=""
TOOLS_FILE=""
TOOL_CHOICE=""
RAW_PAYLOAD_FILE=""
API_KEY_OVERRIDE=""
TOKEN_OVERRIDE=""
AGENT_APP_INSTANCE_ID_OVERRIDE=""
OUTPUT_PATH=""
TEXT_ONLY=0
CHAT_MODE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --input|--prompt) INPUT="${2:-}"; shift 2 ;;
    --input-file) INPUT_FILE="${2:-}"; shift 2 ;;
    --instructions) INSTRUCTIONS="${2:-}"; shift 2 ;;
    --instructions-file) INSTRUCTIONS_FILE="${2:-}"; shift 2 ;;
    --model) MODEL="${2:-}"; shift 2 ;;
    --reasoning-effort) REASONING_EFFORT="${2:-}"; shift 2 ;;
    --temperature) TEMPERATURE="${2:-}"; shift 2 ;;
    --top-p) TOP_P="${2:-}"; shift 2 ;;
    --max-output-tokens) MAX_OUTPUT_TOKENS="${2:-}"; shift 2 ;;
    --session) SESSION_NAME="${2:-}"; shift 2 ;;
    --session-file) SESSION_FILE="${2:-}"; shift 2 ;;
    --new-session|--new) NEW_SESSION=1; shift ;;
    --no-session) NO_SESSION=1; shift ;;
    --previous-response-id) PREVIOUS_RESPONSE_ID="${2:-}"; shift 2 ;;
    --chat) CHAT_MODE=1; shift ;;
    --service-tier) SERVICE_TIER="${2:-}"; shift 2 ;;
    --tools) TOOLS="${2:-}"; shift 2 ;;
    --tools-file) TOOLS_FILE="${2:-}"; shift 2 ;;
    --tool-choice) TOOL_CHOICE="${2:-}"; shift 2 ;;
    --raw-payload-file) RAW_PAYLOAD_FILE="${2:-}"; shift 2 ;;
    --api-key) API_KEY_OVERRIDE="${2:-}"; shift 2 ;;
    --token) TOKEN_OVERRIDE="${2:-}"; shift 2 ;;
    --agent-app-instance-id) AGENT_APP_INSTANCE_ID_OVERRIDE="${2:-}"; shift 2 ;;
    --text-only|-t) TEXT_ONLY=1; shift ;;
    --output) OUTPUT_PATH="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done

case "$MODEL" in
  anthropic/claude-sonnet-5|claude-sonnet-5)
    MODEL="anthropic/claude-sonnet-5"
    ;;
  *)
    echo "Invalid model: $MODEL" >&2
    echo "Allowed model for this skill: anthropic/claude-sonnet-5" >&2
    exit 1
    ;;
esac

if (( ! NO_SESSION )); then
  if [[ -z "$SESSION_FILE" ]]; then
    RESOLVED_SESSION_ID="${SESSION_NAME:-${FREVANA_SESSION_ID:-${CONVERSATION_ID:-${SESSION_ID:-}}}}"
    if [[ -n "$RESOLVED_SESSION_ID" ]]; then
      SESSION_DIR="${FREVANA_SESSION_DIR:-$HOME/.frevana/sessions}"
      mkdir -p "$SESSION_DIR"
      SAFE_ID="$(printf '%s' "$RESOLVED_SESSION_ID" | tr -c 'a-zA-Z0-9_-' '_')"
      SAFE_MODEL="$(printf '%s' "$MODEL" | tr -c 'a-zA-Z0-9_-' '_')"
      SESSION_FILE="$SESSION_DIR/${SAFE_ID}_${SAFE_MODEL}.json"
    fi
  fi
fi

if (( NEW_SESSION )) && [[ -n "$SESSION_FILE" && -f "$SESSION_FILE" ]]; then
  rm -f "$SESSION_FILE"
fi

if (( CHAT_MODE )); then
  command -v curl >/dev/null 2>&1 || { echo "curl is required." >&2; exit 1; }
  command -v python3 >/dev/null 2>&1 || { echo "python3 is required." >&2; exit 1; }
  echo "=== Interactive Chat Session: $MODEL ==="
  echo "Type 'exit' or 'quit' to quit."
  echo ""
  CURRENT_SESSION_FILE="${SESSION_FILE:-$TEMP_DIR/chat_session.json}"
  while true; do
    printf "You: "
    read -r user_prompt || break
    [[ "$user_prompt" == "exit" || "$user_prompt" == "quit" ]] && break
    [[ -z "$user_prompt" ]] && continue
    echo ""
    printf "$MODEL: "
    "$0" --model "$MODEL" --session-file "$CURRENT_SESSION_FILE" --input "$user_prompt" --text-only \
      ${INSTRUCTIONS:+--instructions "$INSTRUCTIONS"} \
      ${REASONING_EFFORT:+--reasoning-effort "$REASONING_EFFORT"} \
      ${API_KEY_OVERRIDE:+--api-key "$API_KEY_OVERRIDE"} \
      ${TOKEN_OVERRIDE:+--token "$TOKEN_OVERRIDE"} \
      ${AGENT_APP_INSTANCE_ID_OVERRIDE:+--agent-app-instance-id "$AGENT_APP_INSTANCE_ID_OVERRIDE"}
    echo ""
    echo ""
  done
  exit 0
fi

if [[ -z "$INPUT" && -z "$INPUT_FILE" && -z "$RAW_PAYLOAD_FILE" ]]; then
  echo "Missing required argument: --input, --input-file, --raw-payload-file, or --chat" >&2
  exit 1
fi

if [[ -n "$INPUT_FILE" && ! -f "$INPUT_FILE" ]]; then
  echo "Input file not found: $INPUT_FILE" >&2
  exit 1
fi

if [[ -n "$INSTRUCTIONS_FILE" && ! -f "$INSTRUCTIONS_FILE" ]]; then
  echo "Instructions file not found: $INSTRUCTIONS_FILE" >&2
  exit 1
fi

if [[ -n "$TOOLS_FILE" && ! -f "$TOOLS_FILE" ]]; then
  echo "Tools file not found: $TOOLS_FILE" >&2
  exit 1
fi

if [[ -n "$RAW_PAYLOAD_FILE" && ! -f "$RAW_PAYLOAD_FILE" ]]; then
  echo "Raw payload file not found: $RAW_PAYLOAD_FILE" >&2
  exit 1
fi

if [[ -n "$REASONING_EFFORT" ]] && ! is_allowed "$REASONING_EFFORT" low medium high; then
  echo "Invalid --reasoning-effort: $REASONING_EFFORT (allowed: low, medium, high)" >&2
  exit 1
fi

if [[ -n "$TEMPERATURE" ]]; then
  if ! is_number "$TEMPERATURE" || ! python3 -c 'import sys; v = float(sys.argv[1]); sys.exit(0 if 0.0 <= v <= 2.0 else 1)' "$TEMPERATURE" 2>/dev/null; then
    echo "Invalid --temperature: $TEMPERATURE (allowed: 0.0 - 2.0)" >&2
    exit 1
  fi
fi

if [[ -n "$TOP_P" ]]; then
  if ! is_number "$TOP_P" || ! python3 -c 'import sys; v = float(sys.argv[1]); sys.exit(0 if 0.0 <= v <= 1.0 else 1)' "$TOP_P" 2>/dev/null; then
    echo "Invalid --top-p: $TOP_P (allowed: 0.0 - 1.0)" >&2
    exit 1
  fi
fi

if [[ -n "$MAX_OUTPUT_TOKENS" ]] && { ! is_integer "$MAX_OUTPUT_TOKENS" || (( MAX_OUTPUT_TOKENS < 1 )); }; then
  echo "Invalid --max-output-tokens: $MAX_OUTPUT_TOKENS (must be positive integer)" >&2
  exit 1
fi

if [[ -n "$SERVICE_TIER" ]] && ! is_allowed "$SERVICE_TIER" auto default flex priority ultrafast; then
  echo "Invalid --service-tier: $SERVICE_TIER (allowed: auto, default, flex, priority, ultrafast)" >&2
  exit 1
fi

command -v curl >/dev/null 2>&1 || { echo "curl is required." >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is required." >&2; exit 1; }

API_KEY="${API_KEY_OVERRIDE:-${FREVANA_API_KEY:-}}"
TOKEN="${TOKEN_OVERRIDE:-${FREVANA_TOKEN:-}}"
AGENT_APP_INSTANCE_ID="${AGENT_APP_INSTANCE_ID_OVERRIDE:-${FREVANA_AGENT_APP_INSTANCE_ID:-${X_FREVANA_AGENT_APP_INSTANCE_ID:-}}}"

if [[ -z "$API_KEY" && -z "$TOKEN" ]]; then
  if [[ -t 0 ]]; then
    read -r -s -p "Authentication required. Enter Frevana Bearer token or API key: " TOKEN
    echo >&2
  else
    echo "Authentication required: set FREVANA_API_KEY or FREVANA_TOKEN, or pass --api-key / --token explicitly." >&2
    exit 1
  fi
fi

PAYLOAD_FILE="$TEMP_DIR/payload.json"
RESPONSE_FILE="$TEMP_DIR/response.json"
RESULT_FILE="$TEMP_DIR/result.json"

if [[ -n "$SESSION_FILE" && -f "$SESSION_FILE" && -z "$PREVIOUS_RESPONSE_ID" ]]; then
  PREVIOUS_RESPONSE_ID="$(python3 -c "import json, sys
try:
    with open(sys.argv[1], encoding='utf-8') as f:
        d = json.load(f)
    print(d.get('last_response_id') or d.get('id') or '')
except Exception:
    pass" "$SESSION_FILE" 2>/dev/null || true)"
fi

export MODEL INPUT INPUT_FILE INSTRUCTIONS INSTRUCTIONS_FILE REASONING_EFFORT TEMPERATURE TOP_P MAX_OUTPUT_TOKENS PREVIOUS_RESPONSE_ID SERVICE_TIER TOOLS TOOLS_FILE TOOL_CHOICE RAW_PAYLOAD_FILE

python3 - "$PAYLOAD_FILE" <<'PY'
import json, os, sys

model = os.environ["MODEL"]
payload = {"model": model}

raw_file = os.environ.get("RAW_PAYLOAD_FILE", "")
if raw_file and os.path.isfile(raw_file):
    with open(raw_file, encoding="utf-8") as f:
        payload.update(json.load(f))
    payload["model"] = model

input_val = os.environ.get("INPUT", "")
input_file = os.environ.get("INPUT_FILE", "")
if input_file and os.path.isfile(input_file):
    with open(input_file, encoding="utf-8") as f:
        input_val = f.read()

if input_val:
    trimmed = input_val.strip()
    if (trimmed.startswith("[") and trimmed.endswith("]")) or (trimmed.startswith("{") and trimmed.endswith("}")):
        try:
            payload["input"] = json.loads(trimmed)
        except Exception:
            payload["input"] = input_val
    else:
        payload["input"] = input_val

inst_val = os.environ.get("INSTRUCTIONS", "")
inst_file = os.environ.get("INSTRUCTIONS_FILE", "")
if inst_file and os.path.isfile(inst_file):
    with open(inst_file, encoding="utf-8") as f:
        inst_val = f.read()
if inst_val:
    payload["instructions"] = inst_val

reasoning_effort = os.environ.get("REASONING_EFFORT", "")
if reasoning_effort:
    payload["reasoning"] = {"effort": reasoning_effort}

if os.environ.get("TEMPERATURE"):
    payload["temperature"] = float(os.environ["TEMPERATURE"])
if os.environ.get("TOP_P"):
    payload["top_p"] = float(os.environ["TOP_P"])
if os.environ.get("MAX_OUTPUT_TOKENS"):
    payload["max_output_tokens"] = int(os.environ["MAX_OUTPUT_TOKENS"])

if os.environ.get("PREVIOUS_RESPONSE_ID"):
    payload["previous_response_id"] = os.environ["PREVIOUS_RESPONSE_ID"]

if os.environ.get("SERVICE_TIER"):
    payload["service_tier"] = os.environ["SERVICE_TIER"]

tools_val = os.environ.get("TOOLS", "")
tools_file = os.environ.get("TOOLS_FILE", "")
if tools_file and os.path.isfile(tools_file):
    with open(tools_file, encoding="utf-8") as f:
        tools_val = f.read()
if tools_val:
    payload["tools"] = json.loads(tools_val)

tool_choice = os.environ.get("TOOL_CHOICE", "")
if tool_choice:
    try:
        payload["tool_choice"] = json.loads(tool_choice)
    except Exception:
        payload["tool_choice"] = tool_choice

with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False)
PY

CURL_ARGS=(
  -sS
  --connect-timeout "$CONNECT_TIMEOUT"
  --max-time "$MAX_TIME"
  -o "$RESPONSE_FILE"
  -w '%{http_code}'
  -X POST "$API_BASE_URL$RESPONSES_PATH"
  -H "Content-Type: application/json"
)

if [[ -n "$API_KEY" ]]; then
  CURL_ARGS+=(-H "X-API-Key: $API_KEY")
fi
if [[ -n "$TOKEN" ]]; then
  CURL_ARGS+=(-H "Authorization: Bearer $TOKEN")
fi
if [[ -n "$AGENT_APP_INSTANCE_ID" ]]; then
  CURL_ARGS+=(-H "x-frevana-agent-app-instance-id: $AGENT_APP_INSTANCE_ID")
fi

CURL_ARGS+=(--data "@$PAYLOAD_FILE")

HTTP_CODE="$(curl "${CURL_ARGS[@]}")"
if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "Frevana API request failed with HTTP $HTTP_CODE" >&2
  cat "$RESPONSE_FILE" >&2
  exit 1
fi
[[ -s "$RESPONSE_FILE" ]] || { echo "Frevana API returned an empty response body." >&2; exit 1; }

python3 - "$RESPONSE_FILE" "$RESULT_FILE" "$TEXT_ONLY" <<'PY'
import json, sys

raw = open(sys.argv[1], encoding="utf-8").read()
def fail(message):
    print(message, file=sys.stderr); print(raw, file=sys.stderr); raise SystemExit(1)

try:
    payload = json.loads(raw)
except json.JSONDecodeError as exc:
    fail(f"Frevana API returned non-JSON: {exc}")

if not isinstance(payload, dict):
    fail("Frevana API returned JSON, but not an object.")

with open(sys.argv[2], "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)
    f.write("\n")

text_only = sys.argv[3] == "1"
if text_only:
    # Attempt to extract text from Responses API output shape
    if "output_text" in payload and isinstance(payload["output_text"], str):
        print(payload["output_text"])
    elif "output" in payload and isinstance(payload["output"], list):
        extracted = []
        for item in payload["output"]:
            if isinstance(item, dict):
                if item.get("type") == "message" and "content" in item:
                    for part in item.get("content", []):
                        if isinstance(part, dict):
                            if part.get("type") in ("text", "output_text") and "text" in part:
                                extracted.append(part["text"])
                            elif "text" in part:
                                extracted.append(part["text"])
                        elif isinstance(part, str):
                            extracted.append(part)
        if extracted:
            print("\n".join(extracted))
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif "choices" in payload and isinstance(payload["choices"], list) and payload["choices"]:
        msg = payload["choices"][0].get("message", {})
        print(msg.get("content", ""))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
PY

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  cp "$RESULT_FILE" "$OUTPUT_PATH"
fi

if [[ -n "$SESSION_FILE" ]]; then
  python3 - "$RESULT_FILE" "$SESSION_FILE" "$MODEL" <<'PY'
import json, os, sys, time
res_file, session_file, model = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    with open(res_file, encoding="utf-8") as f:
        res = json.load(f)
    resp_id = res.get("id")
    if resp_id:
        session_data = {}
        if os.path.isfile(session_file):
            try:
                with open(session_file, encoding="utf-8") as f:
                    session_data = json.load(f)
            except Exception:
                session_data = {}
        session_data["last_response_id"] = resp_id
        session_data["model"] = model
        session_data["updated_at"] = int(time.time())
        os.makedirs(os.path.dirname(os.path.abspath(session_file)), exist_ok=True)
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)
            f.write("\n")
except Exception:
    pass
PY
fi

if (( ! TEXT_ONLY )); then
  cat "$RESULT_FILE"
fi
