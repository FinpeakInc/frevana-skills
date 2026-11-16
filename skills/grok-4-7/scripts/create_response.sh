#!/usr/bin/env bash

set -euo pipefail

DEFAULT_MODEL="x-ai/grok-4.7"
ALLOWED_MODEL="x-ai/grok-4.7"
MODEL_ALIAS="grok-4-7"
MODEL_MAX_OUTPUT="450000"
MODEL_REASONING_EFFORTS="low medium high xhigh"
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
  --model                x-ai/grok-4.7 (alias: grok-4-7)

Responses options:
  --input, --prompt      Input text prompt or JSON message array
  --input-file           Path to file containing input text or JSON messages
  --instructions         System-level developer instructions
  --instructions-file    Path to file containing system instructions
  --reasoning-effort     Reasoning effort: low, medium, high, xhigh
  --temperature          Sampling temperature (0.0 - 2.0; provider-dependent)
  --top-p                Top-p nucleus sampling (0.0 - 1.0)
  --max-output-tokens    Maximum tokens to generate (1 - 450000; server default: 8192)
  --session              Session name (e.g. default, chat1) saved under ~/.frevana/sessions
  --session-file         Local history file for stateless multi-turn conversations
  --new-session, --new   Reset conversation context and start a fresh session
  --no-session           Disable session persistence for this run
  --previous-response-id Unsupported with store:false; use --session-file instead
  --chat                 Start an interactive chat session in the terminal
  --service-tier         default only
  --tools                JSON array string of tools
  --tools-file           Path to JSON file with tools definitions
  --tool-choice          Tool choice strategy: auto, required, none, or JSON object
  --web-search           Enable search: tools=[{"type":"openrouter:web_search"}]
  --web-search-engine    auto or native (also enables search)
  --plugins              JSON plugin array (legacy web plugin compatibility)
  --plugins-file         Path to JSON plugin array (use one of --plugins/--plugins-file)
  --raw-payload-file     Complete non-streaming JSON payload; CLI fields override it

Auth & Attribution:
  --api-key              Optional supplemental API key (or FREVANA_API_KEY env)
  --token                Required Bearer token (or FREVANA_TOKEN env)
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
WEB_SEARCH=0
WEB_SEARCH_ENGINE=""
PLUGINS=""
PLUGINS_FILE=""
API_KEY_OVERRIDE=""
TOKEN_OVERRIDE=""
AGENT_APP_INSTANCE_ID_OVERRIDE=""
OUTPUT_PATH=""
TEXT_ONLY=0
CHAT_MODE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --input|--prompt|--input-file|--instructions|--instructions-file|--model|--reasoning-effort|--temperature|--top-p|--max-output-tokens|--session|--session-file|--previous-response-id|--service-tier|--tools|--tools-file|--tool-choice|--raw-payload-file|--plugins|--plugins-file|--web-search-engine|--api-key|--token|--agent-app-instance-id|--output)
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
    --previous-response-id) PREVIOUS_RESPONSE_ID="${2:-}"; shift 2 ;;
    --chat) CHAT_MODE=1; shift ;;
    --service-tier) SERVICE_TIER="${2:-}"; shift 2 ;;
    --tools) TOOLS="${2:-}"; shift 2 ;;
    --tools-file) TOOLS_FILE="${2:-}"; shift 2 ;;
    --tool-choice) TOOL_CHOICE="${2:-}"; shift 2 ;;
    --raw-payload-file) RAW_PAYLOAD_FILE="${2:-}"; shift 2 ;;
    --web-search) WEB_SEARCH=1; shift ;;
    --web-search-engine) WEB_SEARCH_ENGINE="$2"; WEB_SEARCH=1; shift 2 ;;
    --plugins) PLUGINS="$2"; shift 2 ;;
    --plugins-file) PLUGINS_FILE="$2"; shift 2 ;;
    --api-key) API_KEY_OVERRIDE="${2:-}"; shift 2 ;;
    --token) TOKEN_OVERRIDE="${2:-}"; shift 2 ;;
    --agent-app-instance-id) AGENT_APP_INSTANCE_ID_OVERRIDE="${2:-}"; shift 2 ;;
    --text-only|-t) TEXT_ONLY=1; shift ;;
    --output) OUTPUT_PATH="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done

[[ "$MODEL" != "$MODEL_ALIAS" ]] || MODEL="$ALLOWED_MODEL"
if [[ "$MODEL" != "$ALLOWED_MODEL" ]]; then
  echo "Invalid model: $MODEL" >&2
  echo "Allowed model for this skill: $ALLOWED_MODEL" >&2
  exit 1
fi

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
      SESSION_FILE="$SESSION_DIR/${SAFE_ID}_${MODEL_ALIAS}.json"
    fi
  fi
fi

if [[ -n "$PREVIOUS_RESPONSE_ID" ]]; then
  echo "--previous-response-id is unsupported with Frevana store:false; use --session-file with local history." >&2
  exit 1
fi

if (( CHAT_MODE )); then
  command -v curl >/dev/null 2>&1 || { echo "curl is required." >&2; exit 1; }
  command -v python3 >/dev/null 2>&1 || { echo "python3 is required." >&2; exit 1; }
  echo "=== Interactive Chat Session: $MODEL ==="
  echo "Type 'exit' or 'quit' to quit."
  echo ""
  CURRENT_SESSION_FILE="${SESSION_FILE:-$TEMP_DIR/chat_session.json}"
  CHAT_ARGS=(--model "$MODEL" --text-only --session-file "$CURRENT_SESSION_FILE")
  (( ! WEB_SEARCH )) || CHAT_ARGS+=(--web-search)
  for OPTION_VAR in WEB_SEARCH_ENGINE PLUGINS PLUGINS_FILE INSTRUCTIONS INSTRUCTIONS_FILE REASONING_EFFORT TEMPERATURE TOP_P MAX_OUTPUT_TOKENS SERVICE_TIER TOOLS TOOLS_FILE TOOL_CHOICE RAW_PAYLOAD_FILE API_KEY_OVERRIDE TOKEN_OVERRIDE AGENT_APP_INSTANCE_ID_OVERRIDE OUTPUT_PATH; do
    case "$OPTION_VAR" in
      API_KEY_OVERRIDE) OPTION_NAME=api-key ;;
      TOKEN_OVERRIDE) OPTION_NAME=token ;;
      AGENT_APP_INSTANCE_ID_OVERRIDE) OPTION_NAME=agent-app-instance-id ;;
      OUTPUT_PATH) OPTION_NAME=output ;;
      *) OPTION_NAME="$(printf '%s' "$OPTION_VAR" | tr 'A-Z_' 'a-z-')" ;;
    esac
    [[ -z "${!OPTION_VAR}" ]] || CHAT_ARGS+=("--$OPTION_NAME" "${!OPTION_VAR}")
  done
  while true; do
    printf "You: "
    read -r user_prompt || break
    [[ "$user_prompt" == "exit" || "$user_prompt" == "quit" ]] && break
    [[ -z "$user_prompt" ]] && continue
    echo ""
    printf '%s: ' "$MODEL"
    TURN_ARGS=("${CHAT_ARGS[@]}")
    (( ! NEW_SESSION )) || TURN_ARGS+=(--new-session)
    bash "$0" "${TURN_ARGS[@]}" --input "$user_prompt"
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

if [[ -n "$REASONING_EFFORT" ]] && ! is_allowed "$REASONING_EFFORT" $MODEL_REASONING_EFFORTS; then
  echo "Invalid --reasoning-effort: $REASONING_EFFORT (allowed: low, medium, high, xhigh)" >&2
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

if [[ -n "$SERVICE_TIER" ]] && ! is_allowed "$SERVICE_TIER" default; then
  echo "Invalid --service-tier: $SERVICE_TIER (allowed: default)" >&2
  exit 1
fi

command -v curl >/dev/null 2>&1 || { echo "curl is required." >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is required." >&2; exit 1; }

API_KEY="${API_KEY_OVERRIDE:-${FREVANA_API_KEY:-}}"
TOKEN="${TOKEN_OVERRIDE:-${FREVANA_TOKEN:-}}"
AGENT_APP_INSTANCE_ID="${AGENT_APP_INSTANCE_ID_OVERRIDE:-${FREVANA_AGENT_APP_INSTANCE_ID:-${X_FREVANA_AGENT_APP_INSTANCE_ID:-}}}"

if [[ -z "$TOKEN" ]]; then
  echo "Authentication required: set FREVANA_TOKEN or pass --token; an API key alone cannot authenticate this route." >&2
  exit 1
fi

PAYLOAD_FILE="$TEMP_DIR/payload.json"
RESPONSE_FILE="$TEMP_DIR/response.json"
RESULT_FILE="$TEMP_DIR/result.json"

SESSION_CONTEXT_FILE="$TEMP_DIR/session-context.json"
export SESSION_FILE NEW_SESSION API_BASE_URL SESSION_CONTEXT_FILE OUTPUT_PATH TEXT_ONLY

ALLOWED_REASONING_EFFORTS="$MODEL_REASONING_EFFORTS"
ALLOWED_SERVICE_TIERS="default"
export ALLOWED_REASONING_EFFORTS ALLOWED_SERVICE_TIERS MODEL_MAX_OUTPUT MODEL_ALIAS
export WEB_SEARCH WEB_SEARCH_ENGINE PLUGINS PLUGINS_FILE
export MODEL INPUT INPUT_FILE INSTRUCTIONS INSTRUCTIONS_FILE REASONING_EFFORT TEMPERATURE TOP_P MAX_OUTPUT_TOKENS PREVIOUS_RESPONSE_ID SERVICE_TIER TOOLS TOOLS_FILE TOOL_CHOICE RAW_PAYLOAD_FILE

python3 - "$PAYLOAD_FILE" <<'PY'
import json, os, sys

model = os.environ["MODEL"]
payload = {"model": model}

raw_file = os.environ.get("RAW_PAYLOAD_FILE", "")
if raw_file and os.path.isfile(raw_file):
    with open(raw_file, encoding="utf-8") as f:
        raw_payload = json.load(f)
    if not isinstance(raw_payload, dict):
        raise SystemExit("Raw payload must be a JSON object.")
    if raw_payload.get("model") not in (None, model, os.environ["MODEL_ALIAS"]):
        raise SystemExit(f"Raw payload model must be {model}.")
    payload.update(raw_payload)
    payload["model"] = model

input_val = os.environ.get("INPUT", "")
input_file = os.environ.get("INPUT_FILE", "")
if input_file and os.path.isfile(input_file):
    with open(input_file, encoding="utf-8") as f:
        input_val = f.read()

if input_val:
    trimmed = input_val.strip()
    if trimmed.startswith("[") and trimmed.endswith("]"):
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
    reasoning = payload.get("reasoning") or {}
    if not isinstance(reasoning, dict):
        raise SystemExit("reasoning must be a JSON object.")
    payload["reasoning"] = {**reasoning, "effort": reasoning_effort}

if os.environ.get("TEMPERATURE"):
    payload["temperature"] = float(os.environ["TEMPERATURE"])
if os.environ.get("TOP_P"):
    payload["top_p"] = float(os.environ["TOP_P"])
if os.environ.get("MAX_OUTPUT_TOKENS"):
    payload["max_output_tokens"] = int(os.environ["MAX_OUTPUT_TOKENS"])

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

# Validate the effective request, including raw payloads and CLI overrides.
request_input = payload.get("input")
if not ((isinstance(request_input, str) and request_input.strip()) or
        (isinstance(request_input, list) and request_input and all(isinstance(item, dict) for item in request_input))):
    raise SystemExit("input must be non-empty text or a non-empty array of Responses input items.")
reasoning = payload.get("reasoning", {})
if not isinstance(reasoning, dict):
    raise SystemExit("reasoning must be a JSON object.")
if "effort" in reasoning and reasoning["effort"] not in os.environ["ALLOWED_REASONING_EFFORTS"].split():
    raise SystemExit(f"Invalid reasoning.effort: {reasoning['effort']}")
if "enabled" in reasoning and reasoning["enabled"] is not True:
    raise SystemExit("Reasoning is mandatory; reasoning.enabled must be true when supplied.")
if "max_tokens" in reasoning:
    raise SystemExit("Use reasoning.effort instead of reasoning.max_tokens.")
if "exclude" in reasoning or "reasoning_effort" in payload or "include_reasoning" in payload:
    raise SystemExit("Use reasoning.effort on Responses; reasoning.exclude/include_reasoning are Chat Completions fields.")
for key, upper in (("temperature", 2), ("top_p", 1)):
    if key in payload and (type(payload[key]) not in (int, float) or not 0 <= payload[key] <= upper):
        raise SystemExit(f"{key} must be a number from 0 to {upper}.")
if "service_tier" in payload and payload["service_tier"] not in os.environ["ALLOWED_SERVICE_TIERS"].split():
    raise SystemExit("Frevana supports only default service_tier in this helper.")
provider = payload.get("provider", {})
if not isinstance(provider, dict):
    raise SystemExit("provider must be a JSON object.")
for key in ("order", "only", "ignore"):
    values = provider.get(key, [])
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        raise SystemExit(f"provider.{key} must be an array of strings.")
    if key != "ignore" and any(value.lower().endswith(("/fast", "/priority")) for value in values):
        raise SystemExit("Frevana does not support fast/priority provider routes.")
if payload.get("speed") == "fast":
    raise SystemExit("Frevana does not support speed=fast.")
if "max_output_tokens" in payload:
    limit = payload["max_output_tokens"]
    upper = int(os.environ["MODEL_MAX_OUTPUT"])
    if type(limit) is not int or not 1 <= limit <= upper:
        raise SystemExit(f"max_output_tokens must be an integer from 1 to {upper}.")
if payload.get("stream") not in (None, False) or payload.get("background") not in (None, False):
    raise SystemExit("This helper requires non-streaming, foreground responses.")
if "tools" in payload and (not isinstance(payload["tools"], list) or any(not isinstance(tool, dict) for tool in payload["tools"])):
    raise SystemExit("tools must be a JSON array of objects.")
choice = payload.get("tool_choice", "auto")
if not ((isinstance(choice, str) and choice in ("auto", "none", "required")) or
        (isinstance(choice, dict) and choice.get("type") == "function" and isinstance(choice.get("name"), str) and choice["name"])):
    raise SystemExit("tool_choice must be auto, none, required or a Responses function choice object.")

plugins_value = os.environ.get("PLUGINS", "")
plugins_file = os.environ.get("PLUGINS_FILE", "")
if plugins_value and plugins_file:
    raise SystemExit("Use one of --plugins or --plugins-file.")
if plugins_file:
    from pathlib import Path
    plugins_value = Path(plugins_file).read_text(encoding="utf-8")
if plugins_value:
    payload["plugins"] = json.loads(plugins_value)
plugins = payload.get("plugins", [])
if not isinstance(plugins, list) or any(not isinstance(plugin, dict) or not isinstance(plugin.get("id"), str) or not plugin["id"] for plugin in plugins):
    raise SystemExit("plugins must be a JSON array of objects with non-empty string id fields.")
if len({plugin["id"] for plugin in plugins}) != len(plugins):
    raise SystemExit("Duplicate plugin IDs are unsupported; supply one configuration per plugin.")
engine = os.environ.get("WEB_SEARCH_ENGINE", "")
if engine not in ("", "auto", "native"):
    raise SystemExit("Invalid --web-search-engine: allowed auto or native.")
search_enabled = os.environ.get("WEB_SEARCH") == "1"
search_tools = [tool for tool in payload.get("tools", []) if tool.get("type") == "openrouter:web_search"]
if len(search_tools) > 1:
    raise SystemExit("Supply only one openrouter:web_search tool configuration.")
if search_tools and not isinstance(search_tools[0].get("parameters", {}), dict):
    raise SystemExit("openrouter:web_search parameters must be a JSON object.")
if search_enabled:
    if any(plugin["id"] == "web" for plugin in plugins):
        raise SystemExit("Use --web-search or the legacy web plugin separately, not both in one request.")
    tools = payload.get("tools", [])
    web = search_tools[0] if search_tools else {"type": "openrouter:web_search"}
    if not search_tools:
        tools.append(web)
    if engine:
        web["parameters"] = {**web.get("parameters", {}), "engine": engine}
    payload["tools"] = tools

# This Responses route is stateless; replay local history instead of response IDs.
session_path = os.environ.get("SESSION_FILE", "")
new_session = os.environ.get("NEW_SESSION") == "1"
context = {"exists": False, "sha256": None}
session = {}
if payload.get("previous_response_id") is not None:
    raise SystemExit("previous_response_id is unsupported with Frevana store:false; use --session-file with local history.")
payload.pop("previous_response_id", None)
if payload.get("conversation") is not None:
    raise SystemExit("Stored conversations are unsupported; use --session-file with local history.")
payload.pop("conversation", None)
payload["store"] = False

if session_path:
    import hashlib, tempfile
    from pathlib import Path

    target = Path(session_path)
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise SystemExit("Session path must be a regular file, not a directory or symlink.")
    if os.path.abspath(session_path) == os.path.abspath(os.environ.get("OUTPUT_PATH") or "."):
        raise SystemExit("--output and --session-file must use different files.")
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Check persistence before making a billable request.
    fd, probe = tempfile.mkstemp(prefix=".frevana-write-check-", dir=target.parent)
    os.close(fd)
    os.unlink(probe)
    if target.exists():
        saved = target.read_bytes()
        context = {"exists": True, "sha256": hashlib.sha256(saved).hexdigest()}
        if not new_session:
            try:
                session = json.loads(saved)
            except (ValueError, UnicodeDecodeError) as exc:
                raise SystemExit(f"Invalid session JSON: {exc}. Use --new-session to intentionally start over.")
            if not isinstance(session, dict) or session.get("schema_version") != 1 or "history" not in session:
                raise SystemExit("Legacy or invalid session: response IDs alone cannot restore store:false history. Use --new-session to start over.")
            if session.get("model") != model:
                raise SystemExit("Session model does not match this skill; use a separate file or --new-session.")
            if session.get("api_base_url") != os.environ["API_BASE_URL"]:
                raise SystemExit("Session API origin does not match; use a separate file or --new-session.")
            if not isinstance(session["history"], list) or any(not isinstance(item, dict) for item in session["history"]):
                raise SystemExit("Invalid session history; use --new-session to intentionally start over.")
    current_input = payload.get("input")
    if isinstance(current_input, str) and current_input:
        current_input = [{"role": "user", "content": current_input}]
    elif not isinstance(current_input, list) or not current_input or any(not isinstance(item, dict) for item in current_input):
        raise SystemExit("Session input must be non-empty text or an array of Responses input items.")
    payload["input"] = session.get("history", []) + current_input
    if "instructions" not in payload and "instructions" in session:
        payload["instructions"] = session["instructions"]
    include = payload.get("include") or []
    if not isinstance(include, list) or any(not isinstance(item, str) for item in include):
        raise SystemExit("include must be an array of strings.")
    if "include" in payload:
        payload["include"] = include
with open(os.environ["SESSION_CONTEXT_FILE"], "w", encoding="utf-8") as f:
    json.dump(context, f)

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

python3 - "$RESPONSE_FILE" "$RESULT_FILE" "$PAYLOAD_FILE" "$SESSION_CONTEXT_FILE" <<'PY_FINALIZE'
import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

response_path, result_path, request_path, context_path = sys.argv[1:]
raw = Path(response_path).read_text(encoding="utf-8")
def fail(message):
    print(message, file=sys.stderr)
    print(raw, file=sys.stderr)
    raise SystemExit(1)

try:
    response = json.loads(raw)
except json.JSONDecodeError as exc:
    fail(f"Frevana API returned non-JSON: {exc}")
if not isinstance(response, dict):
    fail("Frevana API returned JSON, but not an object.")
if response.get("error") is not None or response.get("status", "completed") not in ("completed", "incomplete"):
    fail(f"Frevana response did not complete: status={response.get('status')}, error={response.get('error')}")
if "output" in response and (not isinstance(response["output"], list) or any(not isinstance(item, dict) for item in response["output"])):
    fail("Frevana response output must be an array of objects.")
if "output" not in response and not isinstance(response.get("output_text"), str):
    fail("Frevana response has neither output items nor output_text.")

request = json.loads(Path(request_path).read_text(encoding="utf-8"))
model = os.environ["MODEL"]
session_path = os.environ.get("SESSION_FILE", "")
state = None
if session_path:
    # Replay every native output item, preserving reasoning, tools, phase and ordering.
    output_items = response.get("output", [])
    if not output_items and response.get("output_text"):
        output_items = [{"type": "message", "role": "assistant", "content": [
            {"type": "output_text", "text": response["output_text"]}
        ]}]
    state = {"schema_version": 1, "model": model, "api_base_url": os.environ["API_BASE_URL"],
             "history": request["input"] + output_items, "last_response_id": response.get("id"),
             "updated_at": int(time.time())}
    if "instructions" in request:
        state["instructions"] = request["instructions"]

def atomic_write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

try:
    if session_path:
        expected = json.loads(Path(context_path).read_text(encoding="utf-8"))
        target = Path(session_path)
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise OSError("Session target changed during the request.")
        exists = target.exists()
        digest = hashlib.sha256(target.read_bytes()).hexdigest() if exists else None
        if exists != expected["exists"] or digest != expected["sha256"]:
            raise OSError("Session changed during the request; use one invocation per session at a time.")
    if os.environ.get("OUTPUT_PATH"):
        atomic_write(os.environ["OUTPUT_PATH"], response)
    if state is not None:
        atomic_write(session_path, state)
except (OSError, ValueError) as exc:
    # Keep the successful turn outside the shell's temporary directory, without auth headers.
    recovery = dict(state) if state is not None else {}
    recovery["recovery_response"] = response
    try:
        fd, recovery_path = tempfile.mkstemp(prefix=f"{os.environ['MODEL_ALIAS']}-recovery-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(recovery, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"Persistence failed: {exc}. Response/history saved to {recovery_path}; do not resubmit the same turn.", file=sys.stderr)
    except OSError as recovery_error:
        print(f"Persistence failed: {exc}; recovery file failed: {recovery_error}. Full response follows:", file=sys.stderr)
        print(raw, file=sys.stderr)
    raise SystemExit(1)

Path(result_path).write_text(json.dumps(response, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
if os.environ["TEXT_ONLY"] == "1":
    text = response.get("output_text")
    if not isinstance(text, str):
        parts = []
        for item in response.get("output", []):
            if item.get("type") == "message":
                for part in item.get("content", []):
                    if isinstance(part, dict) and part.get("type") in ("text", "output_text"):
                        parts.append(part.get("text", ""))
                    elif isinstance(part, str):
                        parts.append(part)
        text = "\n".join(parts) if parts else json.dumps(response, ensure_ascii=False, indent=2)
    print(text)
else:
    print(Path(result_path).read_text(encoding="utf-8"), end="")
PY_FINALIZE
