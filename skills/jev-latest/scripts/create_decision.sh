#!/usr/bin/env bash

set -euo pipefail

DEFAULT_MODEL="~typesafe/jev-latest"
DEFAULT_API_BASE_URL="https://ai-factory.frevana.com"
API_BASE_URL="${FREVANA_API_BASE_URL:-$DEFAULT_API_BASE_URL}"
while [[ "$API_BASE_URL" == */ ]]; do API_BASE_URL="${API_BASE_URL%/}"; done
[[ "$API_BASE_URL" =~ ^https?://[^/?#]+(/[^?#]*)?$ ]] || {
  echo "Invalid API base URL after normalisation: ${API_BASE_URL:-<empty>}" >&2
  exit 1
}
API_PATH="/openrouter/v1/decisions"
CONNECT_TIMEOUT="10"
MAX_TIME="330"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

usage() {
  cat <<'EOF'
Usage:
  create_decision.sh (--state "text" | --state-file /path/to/state) \
    (--questions '{...}' | --questions-file /path/to/questions.json) [options]
  create_decision.sh --raw-payload-file /path/to/request.json [options]

Decision request:
  --model                   ~typesafe/jev-latest (default; jev-latest alias accepted)
  --state                   Text or inline JSON object/array state to evaluate
  --state-file              Text or JSON file containing the state
  --questions               JSON object of named choice, noul, or score questions
  --questions-file          JSON file containing the questions object
  --provider                JSON object with OpenRouter provider preferences
  --provider-file           JSON file with OpenRouter provider preferences
  --trace                   JSON object with trace metadata
  --trace-file              JSON file with trace metadata
  --session-id              Observability grouping identifier (maximum 256 characters)
  --user                    End-user identifier
  --raw-payload-file        Complete Decisions request body; cannot be combined with fields above

Auth & attribution:
  --token                   Frevana Bearer token (or FREVANA_TOKEN env)
  --agent-app-instance-id   Agent App instance ID (or FREVANA_AGENT_APP_INSTANCE_ID env)

Output:
  --answers-only, -a        Print only the response answers object
  --output                  Save the full response JSON to this path
  -h, --help                Show help
EOF
}

fail() {
  echo "$1" >&2
  exit 1
}

MODEL="$DEFAULT_MODEL"
STATE=""
STATE_SET=0
STATE_FILE=""
QUESTIONS=""
QUESTIONS_FILE=""
PROVIDER=""
PROVIDER_FILE=""
TRACE=""
TRACE_FILE=""
SESSION_ID=""
USER_ID=""
RAW_PAYLOAD_FILE=""
TOKEN_OVERRIDE=""
AGENT_APP_INSTANCE_ID_OVERRIDE=""
OUTPUT_PATH=""
ANSWERS_ONLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model) MODEL="${2:-}"; shift 2 ;;
    --state) STATE="${2:-}"; STATE_SET=1; shift 2 ;;
    --state-file) STATE_FILE="${2:-}"; shift 2 ;;
    --questions) QUESTIONS="${2:-}"; shift 2 ;;
    --questions-file) QUESTIONS_FILE="${2:-}"; shift 2 ;;
    --provider) PROVIDER="${2:-}"; shift 2 ;;
    --provider-file) PROVIDER_FILE="${2:-}"; shift 2 ;;
    --trace) TRACE="${2:-}"; shift 2 ;;
    --trace-file) TRACE_FILE="${2:-}"; shift 2 ;;
    --session-id) SESSION_ID="${2:-}"; shift 2 ;;
    --user) USER_ID="${2:-}"; shift 2 ;;
    --raw-payload-file) RAW_PAYLOAD_FILE="${2:-}"; shift 2 ;;
    --token) TOKEN_OVERRIDE="${2:-}"; shift 2 ;;
    --agent-app-instance-id) AGENT_APP_INSTANCE_ID_OVERRIDE="${2:-}"; shift 2 ;;
    --answers-only|-a) ANSWERS_ONLY=1; shift ;;
    --output) OUTPUT_PATH="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done

case "$MODEL" in
  "$DEFAULT_MODEL"|jev-latest|typesafe/jev-latest) MODEL="$DEFAULT_MODEL" ;;
  *) fail "Invalid model: $MODEL. Allowed model for this skill: $DEFAULT_MODEL" ;;
esac

[[ -z "$STATE_FILE" || -f "$STATE_FILE" ]] || fail "State file not found: $STATE_FILE"
[[ -z "$QUESTIONS_FILE" || -f "$QUESTIONS_FILE" ]] || fail "Questions file not found: $QUESTIONS_FILE"
[[ -z "$PROVIDER_FILE" || -f "$PROVIDER_FILE" ]] || fail "Provider file not found: $PROVIDER_FILE"
[[ -z "$TRACE_FILE" || -f "$TRACE_FILE" ]] || fail "Trace file not found: $TRACE_FILE"
[[ -z "$RAW_PAYLOAD_FILE" || -f "$RAW_PAYLOAD_FILE" ]] || fail "Raw payload file not found: $RAW_PAYLOAD_FILE"

if [[ -n "$RAW_PAYLOAD_FILE" ]]; then
  (( STATE_SET == 0 )) && [[ -z "$STATE_FILE" && -z "$QUESTIONS" && -z "$QUESTIONS_FILE" && -z "$PROVIDER" && -z "$PROVIDER_FILE" && -z "$TRACE" && -z "$TRACE_FILE" && -z "$SESSION_ID" && -z "$USER_ID" ]] || \
    fail "--raw-payload-file cannot be combined with state, questions, provider, trace, session, or user options."
else
  if (( STATE_SET == 1 )) && [[ -n "$STATE_FILE" ]]; then
    fail "Use only one of --state or --state-file."
  fi
  (( STATE_SET == 1 )) || [[ -n "$STATE_FILE" ]] || fail "Missing required argument: --state or --state-file"
  [[ -z "$QUESTIONS" || -z "$QUESTIONS_FILE" ]] || fail "Use only one of --questions or --questions-file."
  [[ -n "$QUESTIONS" || -n "$QUESTIONS_FILE" ]] || fail "Missing required argument: --questions or --questions-file"
  [[ -z "$PROVIDER" || -z "$PROVIDER_FILE" ]] || fail "Use only one of --provider or --provider-file."
  [[ -z "$TRACE" || -z "$TRACE_FILE" ]] || fail "Use only one of --trace or --trace-file."
fi

command -v curl >/dev/null 2>&1 || fail "curl is required."
command -v python3 >/dev/null 2>&1 || fail "python3 is required."

PAYLOAD_FILE="$TEMP_DIR/payload.json"
RESPONSE_FILE="$TEMP_DIR/response.json"
RESULT_FILE="$TEMP_DIR/result.json"

export MODEL STATE STATE_SET STATE_FILE QUESTIONS QUESTIONS_FILE PROVIDER PROVIDER_FILE TRACE TRACE_FILE SESSION_ID USER_ID RAW_PAYLOAD_FILE
python3 - "$PAYLOAD_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path


def fail(message):
    print(message, file=sys.stderr)
    raise SystemExit(1)


def load_json_value(raw, file_path, label):
    if file_path:
        try:
            raw = Path(file_path).read_text(encoding="utf-8")
        except OSError as exc:
            fail(f"Could not read {label} file: {exc}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        fail(f"Invalid {label} JSON: {exc}")


def structured(value):
    return isinstance(value, (str, dict, list)) and not isinstance(value, bool)


def rename_keys(value, aliases, label):
    for wire_name, sdk_name in aliases.items():
        if wire_name in value and sdk_name in value:
            fail(
                f"{label} cannot contain both {wire_name!r} and {sdk_name!r}."
            )
        if wire_name in value:
            value[sdk_name] = value.pop(wire_name)


def normalize_provider(provider):
    if not isinstance(provider, dict):
        return
    rename_keys(
        provider,
        {
            "allow_fallbacks": "allowFallbacks",
            "data_collection": "dataCollection",
            "enforce_distillable_text": "enforceDistillableText",
            "max_price": "maxPrice",
            "preferred_max_latency": "preferredMaxLatency",
            "preferred_min_throughput": "preferredMinThroughput",
            "require_parameters": "requireParameters",
        },
        "Provider preferences",
    )


def normalize_trace(trace):
    if not isinstance(trace, dict):
        return
    rename_keys(
        trace,
        {
            "generation_name": "generationName",
            "parent_span_id": "parentSpanId",
            "span_name": "spanName",
            "trace_id": "traceId",
            "trace_name": "traceName",
        },
        "Trace",
    )
    known = {
        "generationName",
        "parentSpanId",
        "spanName",
        "traceId",
        "traceName",
        "additionalProperties",
    }
    custom = {key: trace.pop(key) for key in list(trace) if key not in known}
    if custom:
        additional = trace.get("additionalProperties", {})
        if not isinstance(additional, dict):
            fail("Trace additionalProperties must be a JSON object.")
        overlap = set(additional) & set(custom)
        if overlap:
            fail(
                "Trace custom metadata is duplicated in additionalProperties: "
                + ", ".join(sorted(overlap))
            )
        trace["additionalProperties"] = {**additional, **custom}


raw_payload = os.environ.get("RAW_PAYLOAD_FILE", "")
if raw_payload:
    payload = load_json_value("", raw_payload, "raw payload")
    if not isinstance(payload, dict):
        fail("Raw payload must be a JSON object.")
else:
    if os.environ.get("STATE_FILE"):
        state_text = Path(os.environ["STATE_FILE"]).read_text(encoding="utf-8")
        try:
            state = json.loads(state_text)
        except json.JSONDecodeError:
            state = state_text
    else:
        state_text = os.environ.get("STATE", "")
        trimmed_state = state_text.strip()
        if (
            trimmed_state.startswith("{") and trimmed_state.endswith("}")
        ) or (
            trimmed_state.startswith("[") and trimmed_state.endswith("]")
        ):
            try:
                state = json.loads(trimmed_state)
            except json.JSONDecodeError as exc:
                fail(f"Invalid inline state JSON: {exc}")
        else:
            state = state_text

    questions = load_json_value(
        os.environ.get("QUESTIONS", ""),
        os.environ.get("QUESTIONS_FILE", ""),
        "questions",
    )
    payload = {"model": os.environ["MODEL"], "state": state, "questions": questions}

    for key, raw_name, file_name in (
        ("provider", "PROVIDER", "PROVIDER_FILE"),
        ("trace", "TRACE", "TRACE_FILE"),
    ):
        raw = os.environ.get(raw_name, "")
        file_path = os.environ.get(file_name, "")
        if raw or file_path:
            value = load_json_value(raw, file_path, key)
            if not isinstance(value, dict):
                fail(f"{key.capitalize()} must be a JSON object.")
            payload[key] = value

    if os.environ.get("SESSION_ID"):
        payload["sessionId"] = os.environ["SESSION_ID"]
    if os.environ.get("USER_ID"):
        payload["user"] = os.environ["USER_ID"]

if "session_id" in payload and "sessionId" in payload:
    fail("Request cannot contain both 'session_id' and 'sessionId'.")
if "session_id" in payload:
    payload["sessionId"] = payload.pop("session_id")
normalize_provider(payload.get("provider"))
normalize_trace(payload.get("trace"))
payload["model"] = os.environ["MODEL"]

if not structured(payload.get("state")):
    fail("State must be a string, JSON object, or JSON array.")

questions = payload.get("questions")
if not isinstance(questions, dict):
    fail("Questions must be a JSON object.")

for name, question in questions.items():
    if not isinstance(name, str) or not name:
        fail("Every question must have a non-empty string name.")
    if not isinstance(question, dict):
        fail(f"Question {name!r} must be a JSON object.")
    question_type = question.get("type")
    instructions = question.get("instructions")
    if not structured(instructions):
        fail(f"Question {name!r} must have string, object, or array instructions.")

    criteria = question.get("criteria")
    if question_type == "choice":
        if not isinstance(criteria, dict):
            fail(f"Choice question {name!r} must have a criteria object.")
        if not all(value is None or structured(value) for value in criteria.values()):
            fail(f"Choice question {name!r} has an invalid criteria value.")
    elif question_type == "noul":
        if criteria is not None:
            if not isinstance(criteria, dict) or set(criteria) != {"true", "false"}:
                fail(f"Noul question {name!r} criteria must contain exactly true and false.")
            if not all(structured(value) for value in criteria.values()):
                fail(f"Noul question {name!r} has an invalid criteria value.")
    elif question_type == "score":
        if not isinstance(criteria, list) or not criteria:
            fail(f"Score question {name!r} must have a non-empty criteria array.")
        if not all(structured(value) for value in criteria):
            fail(f"Score question {name!r} has an invalid criteria value.")
    else:
        fail(f"Question {name!r} has invalid type {question_type!r}; allowed: choice, noul, score.")

session_id = payload.get("sessionId")
if session_id is not None and (not isinstance(session_id, str) or len(session_id) > 256):
    fail("sessionId must be a string of at most 256 characters.")
if "provider" in payload and payload["provider"] is not None and not isinstance(payload["provider"], dict):
    fail("Provider must be a JSON object or null.")
if "trace" in payload and not isinstance(payload["trace"], dict):
    fail("Trace must be a JSON object.")
if "user" in payload and (
    not isinstance(payload["user"], str) or len(payload["user"]) > 256
):
    fail("User must be a string of at most 256 characters.")

Path(sys.argv[1]).write_text(
    json.dumps(payload, ensure_ascii=False), encoding="utf-8"
)
PY

TOKEN="${TOKEN_OVERRIDE:-${FREVANA_TOKEN:-}}"
AGENT_APP_INSTANCE_ID="${AGENT_APP_INSTANCE_ID_OVERRIDE:-${FREVANA_AGENT_APP_INSTANCE_ID:-${X_FREVANA_AGENT_APP_INSTANCE_ID:-}}}"

if [[ -z "$TOKEN" ]]; then
  if [[ -t 0 ]]; then
    read -r -s -p "Authentication required. Enter Frevana Bearer token: " TOKEN
    echo >&2
  else
    fail "Authentication required: set FREVANA_TOKEN or pass --token explicitly."
  fi
fi
[[ -n "$TOKEN" ]] || fail "Bearer token is required."

CURL_ARGS=(
  -sS
  --connect-timeout "$CONNECT_TIMEOUT"
  --max-time "$MAX_TIME"
  -o "$RESPONSE_FILE"
  -w '%{http_code}'
  -X POST "$API_BASE_URL$API_PATH"
  -H "Content-Type: application/json"
  -H "Authorization: Bearer $TOKEN"
)
[[ -z "$AGENT_APP_INSTANCE_ID" ]] || CURL_ARGS+=(-H "x-frevana-agent-app-instance-id: $AGENT_APP_INSTANCE_ID")
CURL_ARGS+=(--data "@$PAYLOAD_FILE")

HTTP_CODE="$(curl "${CURL_ARGS[@]}")"
if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "Frevana API request failed with HTTP $HTTP_CODE" >&2
  cat "$RESPONSE_FILE" >&2
  exit 1
fi
[[ -s "$RESPONSE_FILE" ]] || fail "Frevana API returned an empty response body."

python3 - "$RESPONSE_FILE" "$RESULT_FILE" "$ANSWERS_ONLY" <<'PY'
import json
import sys
from pathlib import Path

raw = Path(sys.argv[1]).read_text(encoding="utf-8")
try:
    payload = json.loads(raw)
except json.JSONDecodeError as exc:
    print(f"Frevana API returned non-JSON: {exc}", file=sys.stderr)
    print(raw, file=sys.stderr)
    raise SystemExit(1)

if not isinstance(payload, dict):
    print("Frevana API returned JSON, but not an object.", file=sys.stderr)
    raise SystemExit(1)
answers = payload.get("answers")
usage = payload.get("usage")
if not isinstance(answers, dict) or not isinstance(payload.get("model"), str) or not isinstance(usage, dict):
    print("Frevana API returned an invalid Decisions response.", file=sys.stderr)
    print(raw, file=sys.stderr)
    raise SystemExit(1)
if not isinstance(usage.get("inputTokens"), (int, float)) or isinstance(usage.get("inputTokens"), bool):
    print("Frevana API response usage.inputTokens is invalid.", file=sys.stderr)
    raise SystemExit(1)
if not isinstance(usage.get("outputTokens"), (int, float)) or isinstance(usage.get("outputTokens"), bool):
    print("Frevana API response usage.outputTokens is invalid.", file=sys.stderr)
    raise SystemExit(1)

Path(sys.argv[2]).write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
selected = answers if sys.argv[3] == "1" else payload
print(json.dumps(selected, ensure_ascii=False, indent=2))
PY

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  cp "$RESULT_FILE" "$OUTPUT_PATH"
fi
