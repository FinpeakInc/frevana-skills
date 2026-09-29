#!/usr/bin/env bash

set -euo pipefail

FIXED_PROVIDER="openrouter"
DEFAULT_MODEL="anthropic/claude-opus-5.5"
DEFAULT_API_BASE_URL="https://ai-factory.frevana.com"
API_BASE_URL="${FREVANA_API_BASE_URL:-$DEFAULT_API_BASE_URL}"
while [[ "$API_BASE_URL" == */ ]]; do API_BASE_URL="${API_BASE_URL%/}"; done; [[ "$API_BASE_URL" =~ ^https?://[^/?#]+(/[^?#]*)?$ ]] || { echo "Invalid API base URL after normalisation: ${API_BASE_URL:-<empty>}" >&2; exit 1; }
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
  --model                anthropic/claude-opus-5.5 (default)

Responses options:
  --input, --prompt      Input text prompt or JSON message array
  --input-file           Path to file containing input text or JSON messages
  --instructions         System-level developer instructions
  --instructions-file    Path to file containing system instructions
  --reasoning-effort     Reasoning effort: low, medium, high, xhigh, max
  --temperature          Sampling temperature (0.0 - 2.0)
  --top-p                Unsupported for Claude 5.5 (rejected locally)
  --max-output-tokens    Maximum tokens to generate (1 - 128000)
  --session              Session name (e.g. default, chat1) saved under ~/.frevana/sessions
  --session-file         File path to persist/resume conversation state across calls
  --new-session, --new   Reset conversation context and start a fresh session
  --no-session           Disable session persistence for this run
  --previous-response-id Continue a previous response (multi-turn conversation by ID)
  --chat                 Start an interactive chat session in the terminal
  --service-tier         Service tier: default (Claude 5.5 billing boundary)
  --tools                JSON array string of tools (availability varies by endpoint)
  --tools-file           Path to JSON file with tools definitions
  --tool-choice          auto or none; forced tool use is unsupported
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
PREVIOUS_RESPONSE_ID_EXPLICIT=0
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
    --input|--prompt|--input-file|--instructions|--instructions-file|--model|--reasoning-effort|--temperature|--top-p|--max-output-tokens|--session|--session-file|--previous-response-id|--service-tier|--tools|--tools-file|--tool-choice|--raw-payload-file|--api-key|--token|--agent-app-instance-id|--output)
      if [[ $# -lt 2 || -z "$2" ]]; then
        echo "Missing value for $1" >&2
        exit 1
      fi
      ;;
  esac
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
    --previous-response-id) PREVIOUS_RESPONSE_ID="${2:-}"; PREVIOUS_RESPONSE_ID_EXPLICIT=1; shift 2 ;;
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
  anthropic/claude-opus-5.5|claude-opus-5.5|claude-ops-5.5)
    MODEL="anthropic/claude-opus-5.5"
    ;;
  *)
    echo "Invalid model: $MODEL" >&2
    echo "Allowed model for this skill: anthropic/claude-opus-5.5" >&2
    exit 1
    ;;
esac

if (( NO_SESSION )); then
  SESSION_FILE=""
fi

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

if (( NEW_SESSION )) && [[ -n "$PREVIOUS_RESPONSE_ID" ]]; then
  echo "--new-session cannot be combined with --previous-response-id" >&2
  exit 1
fi

if (( CHAT_MODE )); then
  command -v curl >/dev/null 2>&1 || { echo "curl is required." >&2; exit 1; }
  command -v python3 >/dev/null 2>&1 || { echo "python3 is required." >&2; exit 1; }
  echo "=== Interactive Chat Session: $MODEL ==="
  echo "Type 'exit' or 'quit' to quit."
  echo ""
  CURRENT_SESSION_FILE="${SESSION_FILE:-$TEMP_DIR/chat_session.json}"
  CHAT_PREVIOUS_RESPONSE_ID="$PREVIOUS_RESPONSE_ID"
  while true; do
    printf "You: "
    read -r user_prompt || break
    [[ "$user_prompt" == "exit" || "$user_prompt" == "quit" ]] && break
    [[ -z "$user_prompt" ]] && continue
    echo ""
    printf "$MODEL: "
    CHAT_ARGS=(--model "$MODEL" --session-file "$CURRENT_SESSION_FILE" --input "$user_prompt" --text-only)
    [[ -n "$INSTRUCTIONS" ]] && CHAT_ARGS+=(--instructions "$INSTRUCTIONS")
    [[ -n "$INSTRUCTIONS_FILE" ]] && CHAT_ARGS+=(--instructions-file "$INSTRUCTIONS_FILE")
    [[ -n "$REASONING_EFFORT" ]] && CHAT_ARGS+=(--reasoning-effort "$REASONING_EFFORT")
    [[ -n "$TEMPERATURE" ]] && CHAT_ARGS+=(--temperature "$TEMPERATURE")
    [[ -n "$MAX_OUTPUT_TOKENS" ]] && CHAT_ARGS+=(--max-output-tokens "$MAX_OUTPUT_TOKENS")
    [[ -n "$SERVICE_TIER" ]] && CHAT_ARGS+=(--service-tier "$SERVICE_TIER")
    [[ -n "$TOOLS" ]] && CHAT_ARGS+=(--tools "$TOOLS")
    [[ -n "$TOOLS_FILE" ]] && CHAT_ARGS+=(--tools-file "$TOOLS_FILE")
    [[ -n "$TOOL_CHOICE" ]] && CHAT_ARGS+=(--tool-choice "$TOOL_CHOICE")
    [[ -n "$API_KEY_OVERRIDE" ]] && CHAT_ARGS+=(--api-key "$API_KEY_OVERRIDE")
    [[ -n "$TOKEN_OVERRIDE" ]] && CHAT_ARGS+=(--token "$TOKEN_OVERRIDE")
    [[ -n "$AGENT_APP_INSTANCE_ID_OVERRIDE" ]] && CHAT_ARGS+=(--agent-app-instance-id "$AGENT_APP_INSTANCE_ID_OVERRIDE")
    [[ -n "$CHAT_PREVIOUS_RESPONSE_ID" ]] && CHAT_ARGS+=(--previous-response-id "$CHAT_PREVIOUS_RESPONSE_ID")
    (( NEW_SESSION )) && CHAT_ARGS+=(--new-session)
    "$0" "${CHAT_ARGS[@]}"
    CHAT_PREVIOUS_RESPONSE_ID=""
    NEW_SESSION=0
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

if [[ -n "$REASONING_EFFORT" ]] && ! is_allowed "$REASONING_EFFORT" low medium high xhigh max; then
  echo "Invalid --reasoning-effort: $REASONING_EFFORT (allowed: low, medium, high, xhigh, max)" >&2
  exit 1
fi

if [[ -n "$TEMPERATURE" ]]; then
  if ! is_number "$TEMPERATURE" || ! python3 -c 'import sys; v = float(sys.argv[1]); sys.exit(0 if 0.0 <= v <= 2.0 else 1)' "$TEMPERATURE" 2>/dev/null; then
    echo "Invalid --temperature: $TEMPERATURE (allowed: 0.0 - 2.0)" >&2
    exit 1
  fi
fi

if [[ -n "$TOP_P" ]]; then
  echo "--top-p is not supported by Claude 5.5 OpenRouter endpoints" >&2
  exit 1
fi

if [[ -n "$MAX_OUTPUT_TOKENS" ]] && { ! is_integer "$MAX_OUTPUT_TOKENS" || (( MAX_OUTPUT_TOKENS < 1 || MAX_OUTPUT_TOKENS > 128000 )); }; then
  echo "Invalid --max-output-tokens: $MAX_OUTPUT_TOKENS (must be integer from 1 to 128000)" >&2
  exit 1
fi

if [[ -n "$SERVICE_TIER" ]] && ! is_allowed "$SERVICE_TIER" default; then
  echo "Invalid --service-tier: $SERVICE_TIER (allowed: default)" >&2
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

if [[ -n "$SESSION_FILE" && -f "$SESSION_FILE" ]] && (( ! NEW_SESSION )); then
  SAVED_RESPONSE_ID="$(python3 - "$SESSION_FILE" "$MODEL" <<'PYSESSION'
import json, sys
path, model = sys.argv[1:]
try:
    with open(path, encoding="utf-8") as f:
        session = json.load(f)
except (OSError, ValueError) as exc:
    raise SystemExit(f"Cannot read session file {path}: {exc}")
if not isinstance(session, dict):
    raise SystemExit(f"Invalid session file {path}: expected a JSON object")
saved_model = session.get("model")
if saved_model and saved_model != model:
    raise SystemExit(f"Session file {path} belongs to {saved_model}; use --new-session or a different file")
response_id = session.get("last_response_id") or session.get("id") or ""
if not isinstance(response_id, str):
    raise SystemExit(f"Invalid session file {path}: response ID must be a string")
print(response_id)
PYSESSION
)"
  if [[ -z "$PREVIOUS_RESPONSE_ID" ]]; then
    PREVIOUS_RESPONSE_ID="$SAVED_RESPONSE_ID"
  fi
fi

export MODEL INPUT INPUT_FILE INSTRUCTIONS INSTRUCTIONS_FILE REASONING_EFFORT TEMPERATURE TOP_P MAX_OUTPUT_TOKENS PREVIOUS_RESPONSE_ID PREVIOUS_RESPONSE_ID_EXPLICIT NEW_SESSION SERVICE_TIER TOOLS TOOLS_FILE TOOL_CHOICE RAW_PAYLOAD_FILE

python3 - "$PAYLOAD_FILE" <<'PY'
import json, os, sys

model = os.environ["MODEL"]
payload = {"model": model}

raw_file = os.environ.get("RAW_PAYLOAD_FILE", "")
if raw_file and os.path.isfile(raw_file):
    with open(raw_file, encoding="utf-8") as f:
        raw_payload = json.load(f)
    if not isinstance(raw_payload, dict):
        raise SystemExit("--raw-payload-file must contain a JSON object")
    payload.update(raw_payload)
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

if os.environ.get("NEW_SESSION") == "1":
    payload.pop("previous_response_id", None)
if os.environ.get("PREVIOUS_RESPONSE_ID") and (
    os.environ.get("PREVIOUS_RESPONSE_ID_EXPLICIT") == "1" or "previous_response_id" not in payload
):
    payload["previous_response_id"] = os.environ["PREVIOUS_RESPONSE_ID"]

if os.environ.get("SERVICE_TIER"):
    payload["service_tier"] = os.environ["SERVICE_TIER"]

tools_val = os.environ.get("TOOLS", "")
tools_file = os.environ.get("TOOLS_FILE", "")
if tools_file and os.path.isfile(tools_file):
    with open(tools_file, encoding="utf-8") as f:
        tools_val = f.read()
if tools_val:
    parsed_tools = json.loads(tools_val)
    if not isinstance(parsed_tools, list):
        raise SystemExit("--tools/--tools-file must contain a JSON array")
    payload["tools"] = parsed_tools

tool_choice = os.environ.get("TOOL_CHOICE", "")
if tool_choice:
    if tool_choice in ("auto", "none"):
        payload["tool_choice"] = tool_choice
    elif tool_choice == "required":
        raise SystemExit("Claude 5.5 forced tool use is unavailable")
    else:
        try:
            parsed_choice = json.loads(tool_choice)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid --tool-choice: {exc}")
        payload["tool_choice"] = parsed_choice

choice = payload.get("tool_choice")
if choice not in (None, "auto", "none") and not (
    isinstance(choice, dict) and choice.get("type") in ("auto", "none")
):
    raise SystemExit("Claude 5.5 supports tool_choice auto or none; forced tool use is unavailable")

if "input" not in payload:
    raise SystemExit("Request needs input: pass --input/--input-file or include input in --raw-payload-file")
if payload.get("service_tier") not in (None, "default"):
    raise SystemExit("Claude 5.5 supports only default service tier through Frevana")
reasoning = payload.get("reasoning")
if isinstance(reasoning, dict):
    if reasoning.get("enabled") is False or reasoning.get("effort") in ("none", "minimal"):
        raise SystemExit("Claude 5.5 reasoning cannot be disabled")
    if "max_tokens" in reasoning:
        raise SystemExit("Claude 5.5 ignores reasoning.max_tokens; use reasoning.effort")
    if reasoning.get("effort") not in (None, "low", "medium", "high", "xhigh", "max"):
        raise SystemExit("Unsupported Claude 5.5 reasoning effort")
if "top_p" in payload:
    raise SystemExit("top_p is not supported by Claude 5.5 OpenRouter endpoints")
if "tools" in payload and not isinstance(payload["tools"], list):
    raise SystemExit("tools must be a JSON array")

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
if payload.get("status") == "failed" or payload.get("error"):
    fail("Frevana API returned a failed response.")

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
  python3 - "$RESULT_FILE" "$SESSION_FILE" "$MODEL" "$NEW_SESSION" <<'PY'
import json, os, sys, tempfile, time
res_file, session_file, model, new_session = sys.argv[1:]
with open(res_file, encoding="utf-8") as f:
    res = json.load(f)
resp_id = res.get("id")
if not isinstance(resp_id, str) or not resp_id:
    raise SystemExit("Cannot persist session: response has no valid id")
if resp_id:
    session_data = {}
    if new_session != "1" and os.path.isfile(session_file):
        with open(session_file, encoding="utf-8") as f:
            session_data = json.load(f)
    session_data["last_response_id"] = resp_id
    session_data["model"] = model
    session_data["updated_at"] = int(time.time())
    directory = os.path.dirname(os.path.abspath(session_file))
    os.makedirs(directory, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".frevana-session-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(temp_path, session_file)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
PY
fi

if (( ! TEXT_ONLY )); then
  cat "$RESULT_FILE"
fi
