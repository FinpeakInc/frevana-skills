#!/usr/bin/env bash
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_NAME="$(basename "$(dirname "$SCRIPT_DIR")")"
case "$SKILL_NAME" in
  douyin-hot-search) CREATE_PATH="hot-search/tasks" ;;
  douyin-search) CREATE_PATH="search/tasks" ;;
  *) echo "Unsupported Douyin skill directory: $SKILL_NAME" >&2; exit 1 ;;
esac

API_BASE_URL="${FREVANA_API_BASE_URL:-https://ai-factory.frevana.com}"
WINDOWS_GIT_BASH=0
case "${OSTYPE:-}" in
  msys*|mingw*) WINDOWS_GIT_BASH=1 ;;
esac
POLL_SECONDS=10
DEFAULT_TIMEOUT=21600
MAX_RESPONSE_BYTES=$((52 * 1024 * 1024))
SEARCH_DEFAULT_RESULTS_PER_QUERY=10
ACTION="${1:-}"
if (( $# > 0 )); then shift; fi

usage() {
  cat <<EOF
Usage: douyin_task.sh {create|status|result|wait|run} [options]

Creation options:
  --client-task-id ID           Stable ID for an idempotent retry
$(if [[ "$SKILL_NAME" == douyin-hot-search ]]; then
    printf '%s\n' '  --board BOARD                Repeatable: hotspot, seeding, entertainment, social, challenge' \
      '  --max-results-per-board N    Integer 1-60; server default 50'
  else
    printf '%s\n' '  --keyword TEXT               Repeatable, 1-50 keywords' \
      '  --max-results-per-query N    Integer 1-1999; skill default 10' \
      '  --sort VALUE                general, most_liked, latest' \
      '  --publish-time VALUE        unlimited, one_day, one_week, half_year' \
      '  --duration VALUE            unlimited, under_1m, one_to_five, over_5m'
  fi)

Other options:
  --task-id UUID                Required for status, result, and wait
  --wait                        Wait after create; same as run
  --timeout SECONDS             Wait timeout; 0 disables it (default: 21600)
  --output FILE                 Save API JSON; run and wait save under ./out/ by default
  --token TOKEN                 One-time Frevana Bearer token override
  --api-base-url URL            Default: https://ai-factory.frevana.com
  -h, --help                    Show this help
EOF
}

fail() { echo "Error: $*" >&2; exit 1; }
need_value() {
  [[ $# -ge 2 && -n "$2" && "$2" != --* ]] || fail "Missing value for $1"
}
is_uint() { [[ "$1" =~ ^[0-9]+$ ]]; }
valid_choice() {
  local chosen="$1" option
  shift
  for option in "$@"; do [[ "$chosen" == "$option" ]] && return 0; done
  return 1
}
valid_uuid_v4() {
  [[ "$1" =~ ^[[:xdigit:]]{8}-[[:xdigit:]]{4}-4[[:xdigit:]]{3}-[89abAB][[:xdigit:]]{3}-[[:xdigit:]]{12}$ ]]
}
normalize_shell_path() {
  local path="$1"
  if [[ "$path" =~ ^[A-Za-z]:[\\/] || "$path" == \\\\* ]]; then
    if (( WINDOWS_GIT_BASH )); then cygpath -u "$path"
    elif command -v wslpath >/dev/null 2>&1; then wslpath -u "$path"
    else fail "Windows paths require Git Bash or WSL; use a POSIX path here"; fi
  else
    printf '%s\n' "$path"
  fi
}

case "$ACTION" in
  -h|--help) usage; exit 0 ;;
  create|status|result|wait|run) ;;
  *) usage >&2; fail "Choose create, status, result, wait, or run" ;;
esac

CLIENT_TASK_ID=""
TASK_ID=""
MAX_PER_BOARD=""
MAX_PER_QUERY=""
SORT=""
PUBLISH_TIME=""
DURATION=""
WAIT_AFTER_CREATE=0
TIMEOUT="$DEFAULT_TIMEOUT"
TIMEOUT_GIVEN=0
OUTPUT_PATH=""
TOKEN_OVERRIDE=""
BOARDS=()
KEYWORDS=()

while (( $# > 0 )); do
  case "$1" in
    --client-task-id) need_value "$@"; CLIENT_TASK_ID="$2"; shift 2 ;;
    --task-id) need_value "$@"; TASK_ID="$2"; shift 2 ;;
    --board)
      [[ "$SKILL_NAME" == douyin-hot-search ]] || fail "--board is only valid for douyin-hot-search"
      need_value "$@"; BOARDS+=("$2"); shift 2 ;;
    --max-results-per-board)
      [[ "$SKILL_NAME" == douyin-hot-search ]] || fail "--max-results-per-board is only valid for douyin-hot-search"
      need_value "$@"; MAX_PER_BOARD="$2"; shift 2 ;;
    --keyword)
      [[ "$SKILL_NAME" == douyin-search ]] || fail "--keyword is only valid for douyin-search"
      need_value "$@"; KEYWORDS+=("$2"); shift 2 ;;
    --max-results-per-query)
      [[ "$SKILL_NAME" == douyin-search ]] || fail "--max-results-per-query is only valid for douyin-search"
      need_value "$@"; MAX_PER_QUERY="$2"; shift 2 ;;
    --sort) [[ "$SKILL_NAME" == douyin-search ]] || fail "--sort is only valid for douyin-search"
      need_value "$@"; SORT="$2"; shift 2 ;;
    --publish-time) [[ "$SKILL_NAME" == douyin-search ]] || fail "--publish-time is only valid for douyin-search"
      need_value "$@"; PUBLISH_TIME="$2"; shift 2 ;;
    --duration) [[ "$SKILL_NAME" == douyin-search ]] || fail "--duration is only valid for douyin-search"
      need_value "$@"; DURATION="$2"; shift 2 ;;
    --wait) WAIT_AFTER_CREATE=1; shift ;;
    --timeout) need_value "$@"; TIMEOUT="$2"; TIMEOUT_GIVEN=1; shift 2 ;;
    --output) need_value "$@"; OUTPUT_PATH="$2"; shift 2 ;;
    --token) need_value "$@"; TOKEN_OVERRIDE="$2"; shift 2 ;;
    --api-base-url) need_value "$@"; API_BASE_URL="$2"; shift 2 ;;
    *) fail "Unknown option: $1" ;;
  esac
done

if [[ "$ACTION" == create || "$ACTION" == run ]]; then
  [[ -z "$TASK_ID" ]] || fail "--task-id is not valid with $ACTION"
else
  [[ -n "$TASK_ID" ]] || fail "$ACTION requires --task-id"
  valid_uuid_v4 "$TASK_ID" || fail "--task-id must be a UUID v4"
  if [[ -n "$CLIENT_TASK_ID$MAX_PER_BOARD$MAX_PER_QUERY$SORT$PUBLISH_TIME$DURATION" ]] ||
    (( ${#BOARDS[@]} > 0 || ${#KEYWORDS[@]} > 0 )); then
    fail "Creation options are not valid with $ACTION"
  fi
fi
(( WAIT_AFTER_CREATE == 0 )) || [[ "$ACTION" == create ]] || fail "--wait is valid only with create"
is_uint "$TIMEOUT" || fail "--timeout must be a nonnegative integer"
(( ${#TIMEOUT} <= 10 )) || fail "--timeout is too large"
TIMEOUT=$((10#$TIMEOUT))
if (( TIMEOUT_GIVEN == 1 )) && [[ "$ACTION" != wait && "$ACTION" != run ]] &&
  ! [[ "$ACTION" == create && "$WAIT_AFTER_CREATE" == 1 ]]; then
  fail "--timeout is valid only with wait, run, or create --wait"
fi

[[ "$API_BASE_URL" =~ ^https?://[^[:space:]/?#@]+(/[^[:space:]?#]*)?$ ]] ||
  fail "--api-base-url must be an HTTP(S) URL without credentials, query, or fragment"
API_BASE_URL="${API_BASE_URL%/}"
command -v curl >/dev/null 2>&1 || fail "curl is required"
command -v jq >/dev/null 2>&1 || fail "jq is required"
if (( WINDOWS_GIT_BASH )); then
  command -v cygpath >/dev/null 2>&1 || fail "cygpath is required in Git Bash"
fi
if [[ -n "$OUTPUT_PATH" ]]; then OUTPUT_PATH="$(normalize_shell_path "$OUTPUT_PATH")"; fi

TOKEN="${TOKEN_OVERRIDE:-${FREVANA_TOKEN:-}}"
if [[ -z "$TOKEN" && -t 0 ]]; then
  read -r -s -p "FREVANA_TOKEN not found. Enter Frevana bearer token: " TOKEN
  echo >&2
fi
[[ -n "$TOKEN" ]] || fail "FREVANA_TOKEN is not set; set it or pass --token"
[[ "$TOKEN" != *$'\n'* && "$TOKEN" != *$'\r'* ]] || fail "Bearer token must not contain line breaks"

TEMP_BASE="${TMPDIR:-/tmp}"
TEMP_BASE="$(normalize_shell_path "$TEMP_BASE")"
TEMP_DIR="$(mktemp -d "$TEMP_BASE/douyin-task.XXXXXX")"
trap 'rm -rf -- "$TEMP_DIR"' EXIT
RESPONSE_FILE="$TEMP_DIR/response.json"
PAYLOAD_FILE="$TEMP_DIR/payload.json"
CURL_RESPONSE_FILE="$RESPONSE_FILE"
CURL_PAYLOAD_FILE="$PAYLOAD_FILE"
if (( WINDOWS_GIT_BASH )); then
  CURL_RESPONSE_FILE="$(cygpath -m "$RESPONSE_FILE")"
  CURL_PAYLOAD_FILE="$(cygpath -m "$PAYLOAD_FILE")"
fi

generate_client_id() {
  if command -v uuidgen >/dev/null 2>&1; then uuidgen
  elif command -v openssl >/dev/null 2>&1; then openssl rand -hex 16
  else fail "uuidgen or openssl is required to generate client_task_id"; fi
}

if [[ "$ACTION" == create || "$ACTION" == run ]]; then
  if [[ -z "$CLIENT_TASK_ID" ]]; then CLIENT_TASK_ID="$(generate_client_id)"; fi
  [[ -n "${CLIENT_TASK_ID//[[:space:]]/}" && ${#CLIENT_TASK_ID} -le 128 ]] ||
    fail "--client-task-id must be nonempty and at most 128 characters"
  CLIENT_TASK_ID="$(printf '%s' "$CLIENT_TASK_ID" | jq -Rr 'gsub("^\\s+|\\s+$"; "")')"
  [[ -n "$CLIENT_TASK_ID" ]] || fail "--client-task-id must not be empty"

  if [[ "$SKILL_NAME" == douyin-hot-search ]]; then
    for board in "${BOARDS[@]}"; do
      valid_choice "$board" hotspot seeding entertainment social challenge || fail "Invalid --board: $board"
    done
    if [[ -n "$MAX_PER_BOARD" ]]; then
      is_uint "$MAX_PER_BOARD" || fail "--max-results-per-board must be between 1 and 60"
      (( ${#MAX_PER_BOARD} <= 10 )) || fail "--max-results-per-board is too large"
      MAX_PER_BOARD=$((10#$MAX_PER_BOARD))
      (( MAX_PER_BOARD >= 1 && MAX_PER_BOARD <= 60 )) || fail "--max-results-per-board must be between 1 and 60"
    fi
    BOARDS_JSON="$(jq -cn '$ARGS.positional | reduce .[] as $board ([]; if index($board) == null then . + [$board] else . end)' --args "${BOARDS[@]}")"
    jq -nc --arg id "$CLIENT_TASK_ID" --argjson boards "$BOARDS_JSON" --arg max "$MAX_PER_BOARD" \
      '{client_task_id:$id} + (if ($boards|length)>0 then {boards:$boards} else {} end) + (if $max!="" then {max_results_per_board:($max|tonumber)} else {} end)' > "$PAYLOAD_FILE"
  else
    (( ${#KEYWORDS[@]} >= 1 && ${#KEYWORDS[@]} <= 50 )) || fail "Provide between 1 and 50 --keyword values"
    KEYWORDS_JSON="$(jq -cn '$ARGS.positional | map(gsub("^\\s+|\\s+$"; ""))' --args "${KEYWORDS[@]}")"
    jq -e 'all(.[]; length > 0 and length <= 128)' <<< "$KEYWORDS_JSON" >/dev/null ||
      fail "Each --keyword must be nonempty and at most 128 characters"
    if [[ -z "$MAX_PER_QUERY" ]]; then MAX_PER_QUERY="$SEARCH_DEFAULT_RESULTS_PER_QUERY"; fi
    is_uint "$MAX_PER_QUERY" || fail "--max-results-per-query must be between 1 and 1999"
    (( ${#MAX_PER_QUERY} <= 10 )) || fail "--max-results-per-query is too large"
    MAX_PER_QUERY=$((10#$MAX_PER_QUERY))
    (( MAX_PER_QUERY >= 1 && MAX_PER_QUERY <= 1999 )) || fail "--max-results-per-query must be between 1 and 1999"
    UNIQUE_COUNT="$(jq 'unique | length' <<< "$KEYWORDS_JSON")"
    (( UNIQUE_COUNT * MAX_PER_QUERY <= 1999 )) || fail "Unique keywords × max results per query must not exceed 1999"
    [[ -z "$SORT" ]] || valid_choice "$SORT" general most_liked latest || fail "Invalid --sort: $SORT"
    [[ -z "$PUBLISH_TIME" ]] || valid_choice "$PUBLISH_TIME" unlimited one_day one_week half_year || fail "Invalid --publish-time: $PUBLISH_TIME"
    [[ -z "$DURATION" ]] || valid_choice "$DURATION" unlimited under_1m one_to_five over_5m || fail "Invalid --duration: $DURATION"
    jq -nc --arg id "$CLIENT_TASK_ID" --argjson keywords "$KEYWORDS_JSON" --argjson max "$MAX_PER_QUERY" \
      --arg sort "$SORT" --arg publish "$PUBLISH_TIME" --arg duration "$DURATION" \
      '{client_task_id:$id,keywords:$keywords,max_results_per_query:$max} + (if $sort!="" then {sort:$sort} else {} end) + (if $publish!="" then {publish_time:$publish} else {} end) + (if $duration!="" then {duration:$duration} else {} end)' > "$PAYLOAD_FILE"
  fi
fi

request() {
  local method="$1" path="$2" http_code
  local curl_args=(-q --silent --show-error --request "$method" --connect-timeout 10 --max-time 600
    --max-filesize "$MAX_RESPONSE_BYTES" --proto '=http,https' --output "$CURL_RESPONSE_FILE"
    --write-out '%{http_code}' --header @- --header 'Accept: application/json')
  if [[ "$method" == POST ]]; then
    curl_args+=(--header 'Content-Type: application/json' --data-binary "@$CURL_PAYLOAD_FILE")
  fi
  if ! http_code="$(printf 'Authorization: Bearer %s\n' "$TOKEN" | curl "${curl_args[@]}" "$API_BASE_URL/service/douyin/$path")"; then
    if [[ "$method" == POST ]]; then
      echo "Creation outcome may be unknown. Retry only with identical options and --client-task-id $CLIENT_TASK_ID" >&2
    fi
    fail "Frevana Douyin API transport failed"
  fi
  if [[ ! "$http_code" =~ ^2[0-9][0-9]$ ]]; then
    echo "Error: Frevana Douyin API request failed with HTTP $http_code" >&2
    head -c 65536 "$RESPONSE_FILE" >&2 || true
    echo >&2
    if [[ "$method" == POST && "$http_code" =~ ^5 ]]; then
      echo "Creation outcome may be unknown. Retry only with identical options and --client-task-id $CLIENT_TASK_ID" >&2
    fi
    exit 1
  fi
  [[ -s "$RESPONSE_FILE" ]] || fail "Frevana Douyin API returned an empty response"
}

task_field() { jq -er "$1" < "$RESPONSE_FILE"; }
validate_task() { jq -e 'type=="object"' < "$RESPONSE_FILE" >/dev/null || fail "API did not return a task object"; }
check_terminal() {
  local status="$1" detail
  case "$status" in
    FAILED|TIMED_OUT|ABORTED|RESULT_EXPIRED|TRIGGER_UNKNOWN)
      detail="$(jq -r '.error_message // "no error detail"' < "$RESPONSE_FILE")"
      fail "Douyin task $TASK_ID ended with $status: $detail" ;;
  esac
}
emit() {
  local destination="${1:-}"
  if [[ -n "$destination" ]]; then
    mkdir -p "$(dirname "$destination")"
    cp "$RESPONSE_FILE" "$destination"
    echo "Saved Douyin JSON to $destination" >&2
  fi
  cat "$RESPONSE_FILE"
}
default_output() {
  printf 'out/%s-result-%s-%s.json' "$SKILL_NAME" "$(date -u +%Y%m%dT%H%M%SZ)" "$$"
}
fetch_result() {
  request GET "tasks/$TASK_ID/result"
  jq -e 'type=="array"' < "$RESPONSE_FILE" >/dev/null || fail "Result endpoint did not return a JSON array"
  emit "$1"
}
wait_for_result() {
  local started="$SECONDS" last_state="" status billing state
  while true; do
    request GET "tasks/$TASK_ID"
    validate_task
    status="$(task_field '.status | select(type=="string")')" || fail "Task response is missing status"
    billing="$(task_field '.billing_status | select(type=="string")')" || fail "Task response is missing billing_status"
    check_terminal "$status"
    state="$status/$billing"
    if [[ "$state" != "$last_state" ]]; then
      echo "Douyin task $TASK_ID: status=$status, billing_status=$billing" >&2
      last_state="$state"
    fi
    if [[ "$status" == READY && "$billing" == BILLED ]]; then
      fetch_result "${OUTPUT_PATH:-$(default_output)}"
      return
    fi
    [[ "$billing" != NOT_CHARGED ]] || fail "Douyin task $TASK_ID cannot return a billed result"
    if (( TIMEOUT > 0 && SECONDS - started >= TIMEOUT )); then
      fail "Timed out waiting for Douyin task $TASK_ID"
    fi
    sleep "$POLL_SECONDS"
  done
}

case "$ACTION" in
  create|run)
    echo "Using client_task_id: $CLIENT_TASK_ID" >&2
    request POST "$CREATE_PATH"
    validate_task
    TASK_ID="$(task_field '.task_id | select(type=="string" and length>0)')" || fail "Create response is missing task_id"
    status="$(task_field '.status | select(type=="string")')" || fail "Create response is missing status"
    check_terminal "$status"
    if [[ "$ACTION" == run || "$WAIT_AFTER_CREATE" == 1 ]]; then wait_for_result
    else emit "$OUTPUT_PATH"; fi
    ;;
  status)
    request GET "tasks/$TASK_ID"
    validate_task
    emit "$OUTPUT_PATH"
    ;;
  result) fetch_result "$OUTPUT_PATH" ;;
  wait) wait_for_result ;;
esac
