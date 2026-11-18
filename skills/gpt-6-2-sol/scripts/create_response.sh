#!/usr/bin/env bash

set -euo pipefail

FIXED_MODEL="gpt-6.2-sol"
DEFAULT_API_BASE_URL="https://ai-factory.frevana.com"
API_BASE_URL="${FREVANA_API_BASE_URL:-$DEFAULT_API_BASE_URL}"
while [[ "$API_BASE_URL" == */ ]]; do API_BASE_URL="${API_BASE_URL%/}"; done; [[ "$API_BASE_URL" =~ ^https?://[^/?#]+(/[^?#]*)?$ ]] || { echo "Invalid API base URL after normalisation: ${API_BASE_URL:-<empty>}" >&2; exit 1; }
RESPONSES_PATH="/openai/v1/responses"
CONNECT_TIMEOUT="10"
MAX_TIME="600"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

usage() {
  cat <<EOF
Usage:
  create_response.sh (--input "prompt text" | --input-file /path/to/file) [options]

Model:
  --model                $FIXED_MODEL (fixed)

Responses options:
  --input, --prompt      Input text prompt or JSON message array
  --input-file           Path to file containing input text or JSON messages
  --instructions         System-level developer instructions
  --instructions-file    Path to file containing system instructions
  --reasoning-effort     Reasoning effort: low, medium, high, xhigh, max
  --max-output-tokens    Output and reasoning token cap (16 - 128000)
  --session              Session name (e.g. default, chat1) saved under ~/.frevana/sessions
  --session-file         Local history file for stateless multi-turn conversations
  --new-session, --new   Reset conversation context and start a fresh session
  --no-session           Disable session persistence for this run
  --previous-response-id Unsupported with store:false; use --session-file instead
  --chat                 Start an interactive chat session in the terminal
  --service-tier         Latency/pricing tier: auto, default, flex, fast, priority, ultrafast
  --tools                JSON array string of tools
  --tools-file           Path to JSON file with tools definitions
  --tool-choice          Tool choice strategy: auto, required, none, or JSON object
  --raw-payload-file     Path to complete JSON payload file to send to the Responses API

Auth & Attribution:
  FREVANA_TOKEN          Required Frevana Bearer token environment variable
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

MODEL="$FIXED_MODEL"
INPUT=""
INPUT_FILE=""
INSTRUCTIONS=""
INSTRUCTIONS_FILE=""
REASONING_EFFORT=""
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
AGENT_APP_INSTANCE_ID_OVERRIDE=""
OUTPUT_PATH=""
TEXT_ONLY=0
CHAT_MODE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --input|--prompt|--input-file|--instructions|--instructions-file|--model|--reasoning-effort|--max-output-tokens|--session|--session-file|--previous-response-id|--service-tier|--tools|--tools-file|--tool-choice|--raw-payload-file|--agent-app-instance-id|--output)
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
    --temperature|--top-p|--top-logprobs)
      echo "Unsupported sampling option for $FIXED_MODEL: $1" >&2
      exit 1 ;;
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
    --agent-app-instance-id) AGENT_APP_INSTANCE_ID_OVERRIDE="${2:-}"; shift 2 ;;
    --text-only|-t) TEXT_ONLY=1; shift ;;
    --output) OUTPUT_PATH="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done

if [[ "$MODEL" != "$FIXED_MODEL" ]]; then
  echo "Invalid model: $MODEL" >&2
  echo "Allowed model for this skill: $FIXED_MODEL" >&2
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
      SESSION_FILE="$SESSION_DIR/${SAFE_ID}_${MODEL}.json"
    fi
  fi
fi

if [[ -n "$PREVIOUS_RESPONSE_ID" ]]; then
  echo "--previous-response-id is unsupported with Frevana store:false; use --session-file with local history." >&2
  exit 1
fi

if [[ -z "${FREVANA_TOKEN:-}" ]]; then
  echo "Authentication required. Set the FREVANA_TOKEN environment variable." >&2
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
  for OPTION_VAR in INSTRUCTIONS INSTRUCTIONS_FILE REASONING_EFFORT MAX_OUTPUT_TOKENS SERVICE_TIER TOOLS TOOLS_FILE TOOL_CHOICE RAW_PAYLOAD_FILE AGENT_APP_INSTANCE_ID_OVERRIDE OUTPUT_PATH; do
    case "$OPTION_VAR" in
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

if [[ -n "$REASONING_EFFORT" ]] && ! is_allowed "$REASONING_EFFORT" low medium high xhigh max; then
  echo "Invalid --reasoning-effort: $REASONING_EFFORT (allowed: low, medium, high, xhigh, max)" >&2
  exit 1
fi

if [[ -n "$SERVICE_TIER" ]] && ! is_allowed "$SERVICE_TIER" auto default flex fast priority ultrafast; then
  echo "Invalid --service-tier: $SERVICE_TIER (allowed: auto, default, flex, fast, priority, ultrafast)" >&2
  exit 1
fi

command -v curl >/dev/null 2>&1 || { echo "curl is required." >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is required." >&2; exit 1; }

AGENT_APP_INSTANCE_ID="${AGENT_APP_INSTANCE_ID_OVERRIDE:-${FREVANA_AGENT_APP_INSTANCE_ID:-${X_FREVANA_AGENT_APP_INSTANCE_ID:-}}}"

PAYLOAD_FILE="$TEMP_DIR/payload.json"
RESPONSE_FILE="$TEMP_DIR/response.json"
RESULT_FILE="$TEMP_DIR/result.json"

SESSION_CONTEXT_FILE="$TEMP_DIR/session-context.json"
export SESSION_FILE NEW_SESSION API_BASE_URL SESSION_CONTEXT_FILE OUTPUT_PATH TEXT_ONLY

ALLOWED_REASONING_EFFORTS="low medium high xhigh max"
ALLOWED_SERVICE_TIERS="auto default flex fast priority ultrafast"
export ALLOWED_REASONING_EFFORTS ALLOWED_SERVICE_TIERS
export MODEL INPUT INPUT_FILE INSTRUCTIONS INSTRUCTIONS_FILE REASONING_EFFORT MAX_OUTPUT_TOKENS PREVIOUS_RESPONSE_ID SERVICE_TIER TOOLS TOOLS_FILE TOOL_CHOICE RAW_PAYLOAD_FILE

python3 - "$PAYLOAD_FILE" <<'PY'
import json, os, re, sys

model = os.environ["MODEL"]
payload = {"model": model}

raw_file = os.environ.get("RAW_PAYLOAD_FILE", "")
if raw_file and os.path.isfile(raw_file):
    with open(raw_file, encoding="utf-8") as f:
        raw_payload = json.load(f)
    if not isinstance(raw_payload, dict):
        raise SystemExit("Raw payload must be a JSON object.")
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

reasoning = payload.get("reasoning", {})
if not isinstance(reasoning, dict):
    raise SystemExit("reasoning must be a JSON object.")
reasoning_effort = os.environ["REASONING_EFFORT"]
if reasoning_effort:
    reasoning["effort"] = reasoning_effort
    payload["reasoning"] = reasoning

max_output_tokens = os.environ["MAX_OUTPUT_TOKENS"]
if max_output_tokens:
    if not re.fullmatch(r"[0-9]+", max_output_tokens):
        raise SystemExit("--max-output-tokens must be an integer from 16 to 128000.")
    try:
        payload["max_output_tokens"] = int(max_output_tokens)
    except ValueError:
        raise SystemExit("--max-output-tokens must be an integer from 16 to 128000.") from None

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

effort = reasoning.get("effort")
if "effort" in reasoning and effort not in os.environ["ALLOWED_REASONING_EFFORTS"].split():
    raise SystemExit(f"Invalid reasoning.effort: {effort}")
if "service_tier" in payload and payload["service_tier"] not in os.environ["ALLOWED_SERVICE_TIERS"].split():
    raise SystemExit(f"Invalid service_tier: {payload['service_tier']}")
for key in ("temperature", "top_p", "top_logprobs"):
    if key in payload:
        raise SystemExit(f"{model} does not support {key}.")
if "max_output_tokens" in payload:
    limit = payload["max_output_tokens"]
    if type(limit) is not int or not 16 <= limit <= 128000:
        raise SystemExit("max_output_tokens must be an integer from 16 to 128000.")
include = payload.get("include")
if include is not None:
    if not isinstance(include, list) or any(not isinstance(item, str) for item in include):
        raise SystemExit("include must be an array of strings.")
    if "message.output_text.logprobs" in include:
        raise SystemExit(f"{model} does not support include=message.output_text.logprobs.")

current_input = payload.get("input")
if not current_input or not (
    isinstance(current_input, str)
    or (isinstance(current_input, list) and all(isinstance(item, dict) for item in current_input))
):
    raise SystemExit("input must be non-empty text or an array of Responses input items.")
if payload.get("stream") or payload.get("background"):
    raise SystemExit("This helper requires non-streaming, foreground responses.")

# Frevana does not retain upstream Responses; replay local history instead of IDs.
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
    output_path = os.environ["OUTPUT_PATH"]
    if output_path:
        output = Path(output_path)
        if target.resolve() == output.resolve() or (
            target.exists() and output.exists() and target.samefile(output)
        ):
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
    if isinstance(current_input, str):
        current_input = [{"role": "user", "content": current_input}]
    payload["input"] = session.get("history", []) + current_input
    if "instructions" not in payload and "instructions" in session:
        payload["instructions"] = session["instructions"]
    include = include or []
    if "reasoning.encrypted_content" not in include:
        include = include + ["reasoning.encrypted_content"]
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
  -H "Authorization: Bearer $FREVANA_TOKEN"
)

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
    output_path = os.environ["OUTPUT_PATH"]
    if output_path:
        output = Path(output_path)
        if session_path and target.exists() and output.exists() and target.samefile(output):
            raise OSError("--output and --session-file point to the same file.")
        atomic_write(output, response)
        # Creating the output file can reveal aliases on case-insensitive filesystems.
        if session_path and target.exists() and target.samefile(output):
            raise OSError("--output and --session-file point to the same file.")
    if state is not None:
        atomic_write(session_path, state)
except (OSError, ValueError) as exc:
    # Keep the successful turn outside the shell's temporary directory, without auth headers.
    recovery = dict(state) if state is not None else {}
    recovery["recovery_response"] = response
    try:
        fd, recovery_path = tempfile.mkstemp(prefix=f"{model}-recovery-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(recovery, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"Persistence failed: {exc}. Response/history saved to {recovery_path}; do not resubmit the same turn.", file=sys.stderr)
    except OSError as recovery_error:
        print(f"Persistence failed: {exc}; recovery file failed: {recovery_error}. Full response follows:", file=sys.stderr)
        print(raw, file=sys.stderr)
    raise SystemExit(1)

if response.get("status") == "incomplete":
    details = response.get("incomplete_details")
    reason = details.get("reason") if isinstance(details, dict) else None
    print(f"Frevana response incomplete ({reason or 'reason unavailable'}).", file=sys.stderr)

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
