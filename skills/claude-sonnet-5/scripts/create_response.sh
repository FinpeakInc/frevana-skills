#!/usr/bin/env bash

set -euo pipefail

FIXED_PROVIDER="openrouter"
DEFAULT_MODEL="anthropic/claude-sonnet-5"
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
  --model                anthropic/claude-sonnet-5 (default)

Responses options:
  --input, --prompt      Input text prompt or JSON message array
  --input-file           Path to file containing input text or JSON messages
  --instructions         System-level developer instructions
  --instructions-file    Path to file containing system instructions
  --reasoning-effort     Reasoning effort: low, medium, high
  --temperature          Sampling temperature (0.0 - 2.0)
  --top-p                Top-p nucleus sampling (0.0 - 1.0)
  --max-continuations    Maximum automatic continuation requests (0 - 32; default 8)
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
MAX_CONTINUATIONS=8
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
    --max-continuations) MAX_CONTINUATIONS="${2:-}"; shift 2 ;;
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

if ! [[ "$MAX_CONTINUATIONS" =~ ^([0-9]|[12][0-9]|3[0-2])$ ]]; then
  echo "Invalid --max-continuations: $MAX_CONTINUATIONS (allowed: 0 - 32)" >&2
  exit 1
fi

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

if (( NO_SESSION )); then
  SESSION_FILE=""
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
    CHAT_ARGS=(--model "$MODEL" --session-file "$CURRENT_SESSION_FILE" --input "$user_prompt" --text-only --max-continuations "$MAX_CONTINUATIONS")
    [[ -n "$INSTRUCTIONS" ]] && CHAT_ARGS+=(--instructions "$INSTRUCTIONS")
    [[ -n "$INSTRUCTIONS_FILE" ]] && CHAT_ARGS+=(--instructions-file "$INSTRUCTIONS_FILE")
    [[ -n "$REASONING_EFFORT" ]] && CHAT_ARGS+=(--reasoning-effort "$REASONING_EFFORT")
    [[ -n "$TEMPERATURE" ]] && CHAT_ARGS+=(--temperature "$TEMPERATURE")
    [[ -n "$TOP_P" ]] && CHAT_ARGS+=(--top-p "$TOP_P")
    [[ -n "$MAX_OUTPUT_TOKENS" ]] && CHAT_ARGS+=(--max-output-tokens "$MAX_OUTPUT_TOKENS")
    [[ -n "$SERVICE_TIER" ]] && CHAT_ARGS+=(--service-tier "$SERVICE_TIER")
    [[ -n "$TOOLS" ]] && CHAT_ARGS+=(--tools "$TOOLS")
    [[ -n "$TOOLS_FILE" ]] && CHAT_ARGS+=(--tools-file "$TOOLS_FILE")
    [[ -n "$TOOL_CHOICE" ]] && CHAT_ARGS+=(--tool-choice "$TOOL_CHOICE")
    [[ -n "$API_KEY_OVERRIDE" ]] && CHAT_ARGS+=(--api-key "$API_KEY_OVERRIDE")
    [[ -n "$TOKEN_OVERRIDE" ]] && CHAT_ARGS+=(--token "$TOKEN_OVERRIDE")
    [[ -n "$AGENT_APP_INSTANCE_ID_OVERRIDE" ]] && CHAT_ARGS+=(--agent-app-instance-id "$AGENT_APP_INSTANCE_ID_OVERRIDE")
    (( NEW_SESSION )) && CHAT_ARGS+=(--new-session)
    "$0" "${CHAT_ARGS[@]}"
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

if [[ -n "$SESSION_FILE" && -f "$SESSION_FILE" && -z "$PREVIOUS_RESPONSE_ID" ]] && (( ! NEW_SESSION )); then
  PREVIOUS_RESPONSE_ID="$(python3 -c "import json, sys
try:
    with open(sys.argv[1], encoding='utf-8') as f:
        d = json.load(f)
    print(d.get('last_response_id') or d.get('id') or '')
except Exception:
    pass" "$SESSION_FILE" 2>/dev/null || true)"
fi

export MODEL INPUT INPUT_FILE INSTRUCTIONS INSTRUCTIONS_FILE REASONING_EFFORT TEMPERATURE TOP_P MAX_OUTPUT_TOKENS PREVIOUS_RESPONSE_ID NEW_SESSION SERVICE_TIER TOOLS TOOLS_FILE TOOL_CHOICE RAW_PAYLOAD_FILE

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

if os.environ.get("NEW_SESSION") == "1":
    payload.pop("previous_response_id", None)
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

python3 - "$PAYLOAD_FILE" "$RESPONSE_FILE" "$RESULT_FILE" "$TEXT_ONLY" "$OUTPUT_PATH" "$MAX_CONTINUATIONS" "${CURL_ARGS[@]}" <<'PYCONTINUE'
import copy, json, os, subprocess, sys

request_path, response_path, result_path, text_only, output_path, limit = sys.argv[1:7]
curl_args = sys.argv[7:]
with open(request_path, encoding="utf-8") as f:
    request = json.load(f)
if request.get("stream") is True:
    raise SystemExit("Streaming raw payloads are unsupported; use stream=false for automatic continuation")
responses = []
original_formats = {}
text_config = request.get("text")
if isinstance(text_config, dict) and isinstance(text_config.get("format"), dict):
    if text_config["format"].get("type") in ("json_object", "json_schema"):
        original_formats["text.format"] = copy.deepcopy(text_config["format"])
response_format = request.get("response_format")
if isinstance(response_format, dict) and response_format.get("type") in ("json_object", "json_schema"):
    original_formats["response_format"] = copy.deepcopy(response_format)
continuation_prompt = (
    "Your previous answer was cut off by the output token limit. Continue exactly "
    "where it stopped, including mid-word or mid-code if needed. Output only the "
    "remaining content; do not repeat, summarize, or add a preamble or extra fences."
)

if original_formats:
    continuation_prompt += (
        " The concatenation of all answer chunks must be one JSON document matching "
        "this original format; emit only its missing suffix: "
        + json.dumps(original_formats, ensure_ascii=False)
    )


def extract_text(response):
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    parts = []
    for item in (response.get("output") or []):
        if isinstance(item, dict) and item.get("type") == "message":
            for part in item.get("content", []):
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    parts.append(part["text"])
                elif isinstance(part, str):
                    parts.append(part)
    if parts:
        return "\n".join(parts)
    choices = response.get("choices") or []
    if choices:
        return choices[0].get("message", {}).get("content") or ""
    return ""

def reject_json_constant(value):
    raise ValueError(f"Invalid JSON constant: {value}")

def sum_usage(values):
    result = {}
    for value in values:
        if not isinstance(value, dict):
            continue
        for key, item in value.items():
            if isinstance(item, dict):
                result[key] = sum_usage([result.get(key, {}), item])
            elif isinstance(item, (int, float)) and not isinstance(item, bool):
                result[key] = result.get(key, 0) + item
    return result

def emit(error=None):
    if not responses:
        return
    result = copy.deepcopy(responses[-1])
    if len(responses) > 1 or error:
        joined = "".join(extract_text(r) for r in responses)
        result["output_text"] = joined
        # One stitched message keeps output consumers consistent with text-only output.
        result["output"] = [copy.deepcopy(item) for r in responses for item in (r.get("output") or [])
                            if isinstance(item, dict) and item.get("type") != "message"]
        result["output"].append({"type": "message", "role": "assistant",
            "status": "incomplete" if error else result.get("status", "completed"),
            "content": [{"type": "output_text", "text": joined, "annotations": []}]})
        if result.get("choices"):
            result["choices"][0].setdefault("message", {})["content"] = joined
        result["continuation"] = {"responses": responses, "count": len(responses) - 1}
        result["usage"] = sum_usage(r.get("usage") for r in responses)
    if error:
        result["status"] = "incomplete"
        result["continuation"]["error"] = error
    formatted = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    with open(result_path, "w", encoding="utf-8") as f:
        f.write(formatted)
    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(formatted)
    if text_only == "1":
        text = extract_text(result)
        print(text if text or "output_text" in result else formatted, end="\n" if text else "")
    elif error:
        # Successful JSON is printed by the shell after session persistence.
        print(formatted, end="")

def fail(message, raw=None):
    print(message, file=sys.stderr)
    if raw:
        print(raw, file=sys.stderr)
    emit(message)
    raise SystemExit(1)

for attempt in range(int(limit) + 1):
    with open(request_path, "w", encoding="utf-8") as f:
        json.dump(request, f, ensure_ascii=False)
    completed = subprocess.run(["curl", *curl_args], text=True, capture_output=True)
    if completed.returncode:
        fail(f"Frevana API request failed: curl exited {completed.returncode}", completed.stderr)
    try:
        code = int(completed.stdout.strip())
    except ValueError:
        fail("Frevana API returned an invalid HTTP status")
    raw = open(response_path, encoding="utf-8").read() if os.path.exists(response_path) else ""
    if not 200 <= code < 300:
        fail(f"Frevana API request failed with HTTP {code}", raw)
    if not raw:
        fail("Frevana API returned an empty response body.")
    try:
        response = json.loads(raw)
    except json.JSONDecodeError as exc:
        fail(f"Frevana API returned non-JSON: {exc}", raw)
    if not isinstance(response, dict):
        fail("Frevana API returned JSON, but not an object.", raw)
    if response.get("status") == "failed" or response.get("error"):
        fail("Frevana API returned a failed response.", raw)
    responses.append(response)
    reason = (response.get("incomplete_details") or {}).get("reason")
    if response.get("status") != "incomplete" or reason != "max_output_tokens":
        if response.get("status") == "incomplete":
            fail(f"Frevana API response incomplete: {reason or 'unknown reason'}")
        if original_formats and len(responses) > 1:
            try:
                document = json.loads("".join(extract_text(r) for r in responses), parse_constant=reject_json_constant)
            except ValueError:
                fail("Continued structured output is not valid JSON; partial output preserved")
            if any(fmt.get("type") == "json_object" for fmt in original_formats.values()) and not isinstance(document, dict):
                fail("Continued structured output must be a JSON object; partial output preserved")
        emit()
        break
    # Hosted tools may already be finished. Client tools still need caller-supplied
    # results, even when the model has finished generating their arguments.
    tool_items = [item for item in (response.get("output") or [])
                  if isinstance(item, dict) and item.get("type") not in ("message", "reasoning")]
    supplied_results = {item.get("call_id") for item in tool_items
                        if item.get("type", "").endswith("_call_output") and "output" in item
                        and isinstance(item.get("call_id"), str) and item["call_id"]}
    client_calls = {"function_call", "custom_tool_call", "computer_call", "local_shell_call", "shell_call", "apply_patch_call"}
    for item in tool_items:
        kind = item.get("type", "")
        if kind in client_calls:
            ready = item.get("status") == "completed" and item.get("call_id") in supplied_results
        elif kind.endswith("_call_output"):
            ready = "output" in item and item.get("status") in (None, "completed")
        else:
            ready = item.get("status") == "completed" and kind != "mcp_approval_request"
        if not ready:
            fail("Token limit interrupted a tool call or left a pending result; partial output preserved for caller handling")
    text = extract_text(response)
    if not text:
        fail("Token limit reached without text to continue; increase --max-output-tokens")
    if attempt == int(limit):
        fail(f"Reached --max-continuations={limit}; partial output preserved")
    history = request["input"]
    if isinstance(history, str):
        history = [{"role": "user", "content": history}]
    elif isinstance(history, dict):
        history = [history]
    if not isinstance(history, list):
        fail("Cannot continue this input shape; partial output preserved")
    request["input"] = history + copy.deepcopy(tool_items) + [
        {"role": "assistant", "content": text},
        {"role": "user", "content": continuation_prompt},
    ]
    # A JSON suffix cannot satisfy a full-document format by itself. Keep the
    # original schema in the continuation prompt, but generate the suffix as text.
    if "text.format" in original_formats:
        request["text"] = {**request["text"], "format": {"type": "text"}}
    if "response_format" in original_formats:
        request.pop("response_format", None)
    # Keep the original conversation anchor when the configured API supports
    # response-ID state. History already includes this turn and its partial text;
    # switching to the latest response ID would replay this turn twice.
    print(f"Output token limit reached; continuing ({attempt + 1}/{limit})...", file=sys.stderr)
PYCONTINUE

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
        if os.path.isfile(session_file) and os.environ.get("NEW_SESSION") != "1":
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
