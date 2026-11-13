#!/usr/bin/env bash

set -euo pipefail

FIXED_MODEL="anthropic/claude-fable-5.2"
DEFAULT_API_BASE_URL="https://ai-factory.frevana.com"
API_BASE_URL="${FREVANA_API_BASE_URL:-$DEFAULT_API_BASE_URL}"
while [[ "$API_BASE_URL" == */ ]]; do API_BASE_URL="${API_BASE_URL%/}"; done
[[ "$API_BASE_URL" =~ ^https?://[^/?#]+(/[^?#]*)?$ ]] || { echo "Invalid API base URL: ${API_BASE_URL:-<empty>}" >&2; exit 1; }
ENDPOINT="/openrouter/v1/responses"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

usage() {
  cat <<'EOF'
Usage:
  create_response.sh (--input "prompt" | --input-file FILE | --raw-payload-file FILE) [options]

Request:
  --model                anthropic/claude-fable-5.2 (alias: claude-fable-5.2)
  --input, --prompt      Prompt text or JSON message array
  --input-file           Prompt text or JSON message array file
  --instructions         Developer instructions
  --instructions-file    Developer instructions file
  --reasoning-effort     low, medium, high, xhigh, or max
  --max-output-tokens    1-128000
  --previous-response-id Continue a compatible stored response
  --service-tier         default only
  --tools                JSON array of tool definitions
  --tools-file           JSON tool definitions file
  --tool-choice          auto or none
  --raw-payload-file     Complete JSON request body (non-streaming)

Session, auth, and output:
  --session-file         Persist the last successful response ID
  --new-session, --new   Ignore old session state and replace after success
  --no-session           Disable session persistence
  --token                Required Frevana Bearer token override
  --api-key              Optional supplemental Frevana API key header
  --agent-app-instance-id Agent App instance/team ID override
  --text-only, -t        Print extracted response text only
  --output               Save full response JSON
  -h, --help             Show help
EOF
}

is_allowed() { local value="$1"; shift; local item; for item in "$@"; do [[ "$value" == "$item" ]] && return 0; done; return 1; }
is_integer() { [[ "$1" =~ ^[0-9]+$ ]]; }

MODEL="$FIXED_MODEL"
INPUT=""
INPUT_FILE=""
INSTRUCTIONS=""
INSTRUCTIONS_FILE=""
REASONING_EFFORT=""
MAX_OUTPUT_TOKENS=""
PREVIOUS_RESPONSE_ID=""
SERVICE_TIER=""
TOOLS=""
TOOLS_FILE=""
TOOL_CHOICE=""
RAW_PAYLOAD_FILE=""
SESSION_FILE=""
NEW_SESSION=0
NO_SESSION=0
API_KEY_OVERRIDE=""
TOKEN_OVERRIDE=""
AGENT_APP_INSTANCE_ID_OVERRIDE=""
TEXT_ONLY=0
OUTPUT_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model|--input|--prompt|--input-file|--instructions|--instructions-file|--reasoning-effort|--max-output-tokens|--previous-response-id|--service-tier|--tools|--tools-file|--tool-choice|--raw-payload-file|--session-file|--api-key|--token|--agent-app-instance-id|--output)
      [[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 1; }
      ;;
  esac
  case "$1" in
    --model) MODEL="$2"; shift 2 ;;
    --input|--prompt) INPUT="$2"; shift 2 ;;
    --input-file) INPUT_FILE="$2"; shift 2 ;;
    --instructions) INSTRUCTIONS="$2"; shift 2 ;;
    --instructions-file) INSTRUCTIONS_FILE="$2"; shift 2 ;;
    --reasoning-effort) REASONING_EFFORT="$2"; shift 2 ;;
    --max-output-tokens) MAX_OUTPUT_TOKENS="$2"; shift 2 ;;
    --previous-response-id) PREVIOUS_RESPONSE_ID="$2"; shift 2 ;;
    --service-tier) SERVICE_TIER="$2"; shift 2 ;;
    --tools) TOOLS="$2"; shift 2 ;;
    --tools-file) TOOLS_FILE="$2"; shift 2 ;;
    --tool-choice) TOOL_CHOICE="$2"; shift 2 ;;
    --raw-payload-file) RAW_PAYLOAD_FILE="$2"; shift 2 ;;
    --session-file) SESSION_FILE="$2"; shift 2 ;;
    --new-session|--new) NEW_SESSION=1; shift ;;
    --no-session) NO_SESSION=1; shift ;;
    --api-key) API_KEY_OVERRIDE="$2"; shift 2 ;;
    --token) TOKEN_OVERRIDE="$2"; shift 2 ;;
    --agent-app-instance-id) AGENT_APP_INSTANCE_ID_OVERRIDE="$2"; shift 2 ;;
    --text-only|-t) TEXT_ONLY=1; shift ;;
    --output) OUTPUT_PATH="$2"; shift 2 ;;
    --temperature|--top-p) echo "$1 is not supported by Claude Fable 5.2." >&2; exit 1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done

case "$MODEL" in
  anthropic/claude-fable-5.2|claude-fable-5.2|claude-fable-5-2) MODEL="$FIXED_MODEL" ;;
  *) echo "Invalid model: $MODEL" >&2; echo "Allowed model: $FIXED_MODEL" >&2; exit 1 ;;
esac
[[ -n "$INPUT" || -n "$INPUT_FILE" || -n "$RAW_PAYLOAD_FILE" ]] || { echo "Missing required argument: --input, --input-file, or --raw-payload-file" >&2; exit 1; }
[[ -z "$INPUT_FILE" || -f "$INPUT_FILE" ]] || { echo "Input file not found: $INPUT_FILE" >&2; exit 1; }
[[ -z "$INSTRUCTIONS_FILE" || -f "$INSTRUCTIONS_FILE" ]] || { echo "Instructions file not found: $INSTRUCTIONS_FILE" >&2; exit 1; }
[[ -z "$TOOLS_FILE" || -f "$TOOLS_FILE" ]] || { echo "Tools file not found: $TOOLS_FILE" >&2; exit 1; }
[[ -z "$RAW_PAYLOAD_FILE" || -f "$RAW_PAYLOAD_FILE" ]] || { echo "Raw payload file not found: $RAW_PAYLOAD_FILE" >&2; exit 1; }
[[ -z "$REASONING_EFFORT" ]] || is_allowed "$REASONING_EFFORT" low medium high xhigh max || { echo "Invalid --reasoning-effort: $REASONING_EFFORT" >&2; exit 1; }
if [[ -n "$MAX_OUTPUT_TOKENS" ]] && { ! is_integer "$MAX_OUTPUT_TOKENS" || (( MAX_OUTPUT_TOKENS < 1 || MAX_OUTPUT_TOKENS > 128000 )); }; then echo "Invalid --max-output-tokens: $MAX_OUTPUT_TOKENS" >&2; exit 1; fi
[[ -z "$SERVICE_TIER" || "$SERVICE_TIER" == "default" ]] || { echo "Invalid --service-tier: $SERVICE_TIER (allowed: default)" >&2; exit 1; }
[[ -z "$TOOL_CHOICE" ]] || is_allowed "$TOOL_CHOICE" auto none || { echo "Invalid --tool-choice: $TOOL_CHOICE" >&2; exit 1; }
(( ! NEW_SESSION || ${#PREVIOUS_RESPONSE_ID} == 0 )) || { echo "--new-session cannot be combined with --previous-response-id" >&2; exit 1; }
(( NO_SESSION == 0 )) || SESSION_FILE=""

command -v curl >/dev/null 2>&1 || { echo "curl is required." >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is required." >&2; exit 1; }

PAYLOAD_FILE="$TEMP_DIR/payload.json"
export MODEL INPUT INPUT_FILE INSTRUCTIONS INSTRUCTIONS_FILE REASONING_EFFORT MAX_OUTPUT_TOKENS PREVIOUS_RESPONSE_ID SERVICE_TIER TOOLS TOOLS_FILE TOOL_CHOICE RAW_PAYLOAD_FILE SESSION_FILE NEW_SESSION PAYLOAD_FILE
python3 <<'PY'
import json, os, pathlib

fixed = os.environ["MODEL"]
raw = os.environ.get("RAW_PAYLOAD_FILE")
if raw:
    payload = json.loads(pathlib.Path(raw).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("Raw payload must be a JSON object")
    supplied = payload.get("model")
    if supplied not in (None, fixed, "claude-fable-5.2"):
        raise SystemExit(f"Raw payload model must be {fixed}")
    payload["model"] = fixed
else:
    input_value = os.environ.get("INPUT", "")
    input_file = os.environ.get("INPUT_FILE", "")
    if input_file:
        input_value = pathlib.Path(input_file).read_text(encoding="utf-8")
    try:
        parsed = json.loads(input_value)
        request_input = parsed if isinstance(parsed, list) else input_value
    except json.JSONDecodeError:
        request_input = input_value
    payload = {"model": fixed, "input": request_input}

    instructions = os.environ.get("INSTRUCTIONS", "")
    if os.environ.get("INSTRUCTIONS_FILE"):
        instructions = pathlib.Path(os.environ["INSTRUCTIONS_FILE"]).read_text(encoding="utf-8")
    if instructions:
        payload["instructions"] = instructions
    if os.environ.get("REASONING_EFFORT"):
        payload["reasoning"] = {"effort": os.environ["REASONING_EFFORT"]}
    if os.environ.get("MAX_OUTPUT_TOKENS"):
        payload["max_output_tokens"] = int(os.environ["MAX_OUTPUT_TOKENS"])
    if os.environ.get("SERVICE_TIER"):
        payload["service_tier"] = os.environ["SERVICE_TIER"]
    tools_value = os.environ.get("TOOLS", "")
    if os.environ.get("TOOLS_FILE"):
        tools_value = pathlib.Path(os.environ["TOOLS_FILE"]).read_text(encoding="utf-8")
    if tools_value:
        tools = json.loads(tools_value)
        if not isinstance(tools, list):
            raise SystemExit("Tools must be a JSON array")
        payload["tools"] = tools
    if os.environ.get("TOOL_CHOICE"):
        payload["tool_choice"] = os.environ["TOOL_CHOICE"]

previous = os.environ.get("PREVIOUS_RESPONSE_ID", "")
session_file = os.environ.get("SESSION_FILE", "")
if session_file and not int(os.environ.get("NEW_SESSION", "0")) and not previous and pathlib.Path(session_file).exists():
    state = json.loads(pathlib.Path(session_file).read_text(encoding="utf-8"))
    if not isinstance(state, dict) or state.get("model") != fixed or not isinstance(state.get("response_id"), str):
        raise SystemExit("Invalid or mismatched session file; use --new-session to replace it")
    previous = state["response_id"]
if int(os.environ.get("NEW_SESSION", "0")):
    payload.pop("previous_response_id", None)
elif previous:
    payload["previous_response_id"] = previous

if "input" not in payload:
    raise SystemExit("Request needs input: pass --input/--input-file or include input in --raw-payload-file")
if payload.get("stream") not in (None, False):
    raise SystemExit("Streaming is unsupported by this helper")
if "temperature" in payload:
    raise SystemExit("temperature is not supported by Claude Fable 5.2")
if "top_p" in payload:
    raise SystemExit("top_p is not supported by Claude Fable 5.2")
if payload.get("service_tier") not in (None, "default"):
    raise SystemExit("Claude Fable 5.2 supports only default service tier through Frevana")
max_output_tokens = payload.get("max_output_tokens")
if max_output_tokens is not None and (
    isinstance(max_output_tokens, bool)
    or not isinstance(max_output_tokens, int)
    or not 1 <= max_output_tokens <= 128000
):
    raise SystemExit("max_output_tokens must be an integer from 1 to 128000")
reasoning = payload.get("reasoning")
if reasoning is not None:
    if not isinstance(reasoning, dict):
        raise SystemExit("reasoning must be a JSON object")
    if reasoning.get("enabled") is False:
        raise SystemExit("Claude Fable 5.2 reasoning cannot be explicitly disabled")
    if "max_tokens" in reasoning:
        raise SystemExit("Use reasoning.effort instead of reasoning.max_tokens")
    if reasoning.get("effort") not in (None, "low", "medium", "high", "xhigh", "max"):
        raise SystemExit("Unsupported Claude Fable 5.2 reasoning effort")
if "tools" in payload and not isinstance(payload["tools"], list):
    raise SystemExit("tools must be a JSON array")
tool_choice = payload.get("tool_choice")
if tool_choice not in (None, "auto", "none") and not (
    isinstance(tool_choice, dict) and tool_choice.get("type") in ("auto", "none")
):
    raise SystemExit("Claude Fable 5.2 supports tool_choice auto or none in this helper")
payload["model"] = fixed
payload["stream"] = False
pathlib.Path(os.environ["PAYLOAD_FILE"]).write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
PY

API_KEY="${API_KEY_OVERRIDE:-${FREVANA_API_KEY:-}}"
TOKEN="${TOKEN_OVERRIDE:-${FREVANA_TOKEN:-}}"
AGENT_APP_INSTANCE_ID="${AGENT_APP_INSTANCE_ID_OVERRIDE:-${FREVANA_AGENT_APP_INSTANCE_ID:-${X_FREVANA_AGENT_APP_INSTANCE_ID:-}}}"
[[ -n "$TOKEN" ]] || { echo "Bearer authentication required: set FREVANA_TOKEN or pass --token. FREVANA_API_KEY does not replace the token for this server route." >&2; exit 1; }

RESPONSE_FILE="$TEMP_DIR/response.json"
CURL_ARGS=(-sS --connect-timeout 10 --max-time 600 -X POST "$API_BASE_URL$ENDPOINT" -H 'Content-Type: application/json' --data-binary "@$PAYLOAD_FILE" -o "$RESPONSE_FILE" -w '%{http_code}')
[[ -n "$API_KEY" ]] && CURL_ARGS+=(-H "X-API-Key: $API_KEY")
[[ -n "$TOKEN" ]] && CURL_ARGS+=(-H "Authorization: Bearer $TOKEN")
[[ -n "$AGENT_APP_INSTANCE_ID" ]] && CURL_ARGS+=(-H "x-frevana-agent-app-instance-id: $AGENT_APP_INSTANCE_ID")

set +e
HTTP_STATUS="$(curl "${CURL_ARGS[@]}")"
CURL_STATUS=$?
set -e
if (( CURL_STATUS != 0 )); then echo "Frevana API request failed: curl exited $CURL_STATUS. Do not retry automatically." >&2; exit "$CURL_STATUS"; fi
[[ -s "$RESPONSE_FILE" ]] || { echo "Frevana API returned an empty response (HTTP $HTTP_STATUS)." >&2; exit 1; }
if [[ ! "$HTTP_STATUS" =~ ^2[0-9][0-9]$ ]]; then cat "$RESPONSE_FILE"; printf '\n'; echo "Frevana API returned HTTP $HTTP_STATUS. Do not retry automatically." >&2; exit 1; fi

export RESPONSE_FILE OUTPUT_PATH SESSION_FILE TEXT_ONLY MODEL
python3 <<'PY'
import json, os, pathlib, tempfile

path = pathlib.Path(os.environ["RESPONSE_FILE"])
data = json.loads(path.read_text(encoding="utf-8"))
if not isinstance(data, dict) or not isinstance(data.get("id"), str):
    raise SystemExit("Invalid Frevana response: missing response ID")

def text_of(response):
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    chunks = []
    for item in response.get("output", []) if isinstance(response.get("output"), list) else []:
        if not isinstance(item, dict): continue
        for content in item.get("content", []) if isinstance(item.get("content"), list) else []:
            if isinstance(content, dict) and content.get("type") in ("text", "output_text") and isinstance(content.get("text"), str):
                chunks.append(content["text"])
    return "".join(chunks)

rendered = text_of(data) if int(os.environ.get("TEXT_ONLY", "0")) else json.dumps(data, ensure_ascii=False, separators=(",", ":"))
print(rendered, flush=True)

def atomic_write(target, value):
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=target.name + ".", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(value)
            if not value.endswith("\n"):
                f.write("\n")
        os.replace(temp_path, target)
    except BaseException:
        try: os.unlink(temp_path)
        except FileNotFoundError: pass
        raise

try:
    if os.environ.get("OUTPUT_PATH"):
        atomic_write(
            pathlib.Path(os.environ["OUTPUT_PATH"]),
            json.dumps(data, ensure_ascii=False, indent=2),
        )
    if os.environ.get("SESSION_FILE") and data.get("status") != "incomplete":
        atomic_write(
            pathlib.Path(os.environ["SESSION_FILE"]),
            json.dumps(
                {"model": os.environ["MODEL"], "response_id": data["id"]},
                ensure_ascii=False,
                indent=2,
            ),
        )
except OSError as exc:
    raise SystemExit(f"API response was emitted, but local persistence failed: {exc}")
if data.get("status") == "incomplete":
    raise SystemExit(2)
PY
