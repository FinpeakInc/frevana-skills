#!/usr/bin/env bash

set -euo pipefail

CONFIG_DIR="${HOME}/.config/redis-crud"
PROFILE_DIR="${CONFIG_DIR}/profiles"
DEFAULT_FILE="${CONFIG_DIR}/default_profile"

usage() {
  cat <<'EOF'
Usage:
  redis_crud.sh configure --profile NAME --mode direct|ssh-tunnel|ssh-remote [options]
  redis_crud.sh list-profiles [--output PATH]
  redis_crud.sh remove-profile --profile NAME [--output PATH]
  redis_crud.sh ping [--profile NAME] [--output PATH]
  redis_crud.sh get [--profile NAME] --key KEY [--output PATH]
  redis_crud.sh set [--profile NAME] --key KEY --value VALUE [--ttl SECONDS] [--execute] [--output PATH]
  redis_crud.sh del [--profile NAME] --key KEY [--execute] [--output PATH]
  redis_crud.sh hget [--profile NAME] --key KEY --field FIELD [--output PATH]
  redis_crud.sh hset [--profile NAME] --key KEY --field FIELD --value VALUE [--execute] [--output PATH]
  redis_crud.sh hgetall [--profile NAME] --key KEY [--output PATH]
  redis_crud.sh scan [--profile NAME] [--pattern PATTERN] [--count LIMIT] [--cursor CURSOR] [--all] [--output PATH]
  redis_crud.sh raw-command [--profile NAME] --arg COMMAND [--arg ARG ...] [--execute] [--allow-raw-write] [--output PATH]
  redis_crud.sh raw-command [--profile NAME] --command "GET key" [--execute] [--allow-raw-write] [--output PATH]

Common configure options:
  --readonly
  --default
  --test-connection
  --url redis://[:password@]host:6379/0
  --redis-host HOST --redis-port 6379 --redis-db 0 [--redis-username USER] [--redis-password PASS]
  --ssh-alias ALIAS
  --ssh-host HOST [--ssh-user USER] [--ssh-key PATH]
  --remote-cwd PATH --env-file .env --env-key REDIS_URL
EOF
}

die() {
  echo "$*" >&2
  exit 1
}

json_escape() {
  local s="${1-}"
  s=${s//\\/\\\\}
  s=${s//\"/\\\"}
  s=${s//$'\n'/\\n}
  s=${s//$'\r'/\\r}
  s=${s//$'\t'/\\t}
  printf '%s' "$s"
}

json_string() {
  printf '"%s"' "$(json_escape "$1")"
}

shell_quote() {
  printf '%q' "$1"
}

safe_name() {
  [[ "$1" =~ ^[A-Za-z0-9_.-]+$ ]]
}

profile_path() {
  local profile="$1"
  safe_name "$profile" || die "Invalid profile name: $profile"
  printf '%s/%s.conf' "$PROFILE_DIR" "$profile"
}

write_kv() {
  local key="$1"
  local value="${2-}"
  printf '%s=' "$key"
  shell_quote "$value"
  printf '\n'
}

chmod_config() {
  mkdir -p "$PROFILE_DIR"
  chmod 700 "$CONFIG_DIR" "$PROFILE_DIR" 2>/dev/null || true
}

load_profile() {
  local requested="${1-}"
  if [[ -z "$requested" ]]; then
    [[ -f "$DEFAULT_FILE" ]] || die "No profile specified and no default profile configured."
    requested="$(<"$DEFAULT_FILE")"
  fi
  local path
  path="$(profile_path "$requested")"
  [[ -f "$path" ]] || die "Profile not found: $requested. Run configure first."
  # shellcheck disable=SC1090
  source "$path"
  PROFILE_NAME="$requested"
}

redact_url() {
  local url="${1-}"
  if [[ "$url" =~ ^([^:]+://)([^@]*@)(.*)$ ]]; then
    printf '%s****@%s' "${BASH_REMATCH[1]}" "${BASH_REMATCH[3]}"
  else
    printf '%s' "$url"
  fi
}

emit_json() {
  local json="$1"
  local output="${2-}"
  if [[ -z "$output" ]]; then
    mkdir -p out
    output="out/redis-crud-$(date -u +%Y%m%dT%H%M%SZ)-$$.json"
  else
    mkdir -p "$(dirname "$output")"
  fi
  printf '%s\n' "$json" >"$output"
  echo "Saved JSON to $output" >&2
  printf '%s\n' "$json"
}

redis_args() {
  REDIS_HOST="${REDIS_HOST:-127.0.0.1}"
  REDIS_PORT="${REDIS_PORT:-6379}"
  REDIS_DB="${REDIS_DB:-0}"
}

ssh_target_and_opts() {
  SSH_OPTS=()
  if [[ -n "${SSH_KEY:-}" ]]; then
    SSH_OPTS+=("-i" "${SSH_KEY/#\~/$HOME}")
  fi
  if [[ -n "${SSH_ALIAS:-}" ]]; then
    SSH_TARGET="$SSH_ALIAS"
  else
    [[ -n "${SSH_HOST:-}" ]] || die "SSH host or alias is required."
    if [[ -n "${SSH_USER:-}" ]]; then
      SSH_TARGET="${SSH_USER}@${SSH_HOST}"
    else
      SSH_TARGET="$SSH_HOST"
    fi
  fi
}

result_lines_json() {
  local output="$1"
  if [[ -z "$output" ]]; then
    printf '[]'
    return
  fi
  local json="["
  local first=true
  local line
  while IFS= read -r line; do
    [[ "$first" == false ]] && json+=","
    json+="$(json_string "$line")"
    first=false
  done <<<"$output"
  json+="]"
  printf '%s' "$json"
}

port_is_open() {
  local port="$1"
  if command -v nc >/dev/null 2>&1; then
    nc -z 127.0.0.1 "$port" >/dev/null 2>&1
    return $?
  fi
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
    return $?
  fi
  if command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null | grep -Eq "[:.]${port}[[:space:]]"
    return $?
  fi
  if command -v netstat >/dev/null 2>&1; then
    netstat -an 2>/dev/null | grep -E "[.:]${port}[[:space:]].*(LISTEN|LISTENING)" >/dev/null 2>&1
    return $?
  fi
  die "Port probing requires one of: nc, lsof, ss, or netstat."
}

run_local_redis() {
  local tmp status=0
  tmp="$(mktemp)"
  if [[ -n "${URL:-}" && -z "${REDIS_HOST:-}" ]]; then
    redis-cli --raw -u "$URL" "$@" >"$tmp" || status=$?
  else
    redis_args
    local args=(--raw -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB")
    [[ -n "${REDIS_USERNAME:-}" ]] && args+=(--user "$REDIS_USERNAME")
    [[ -n "${REDIS_PASSWORD:-}" ]] && args+=(--no-auth-warning -a "$REDIS_PASSWORD")
    redis-cli "${args[@]}" "$@" >"$tmp" || status=$?
  fi
  if [[ $status -ne 0 ]]; then
    rm -f "$tmp"
    return "$status"
  fi
  REDIS_OUTPUT="$(<"$tmp")"
  rm -f "$tmp"
}

run_remote_redis() {
  ssh_target_and_opts
  local remote_cmd="REMOTE_CWD=$(shell_quote "${REMOTE_CWD:-}")"
  remote_cmd+=" ENV_FILE=$(shell_quote "${ENV_FILE:-}")"
  remote_cmd+=" ENV_KEY=$(shell_quote "${ENV_KEY:-REDIS_URL}")"
  remote_cmd+=" URL=$(shell_quote "${URL:-}")"
  remote_cmd+=" REDIS_HOST=$(shell_quote "${REDIS_HOST:-}")"
  remote_cmd+=" REDIS_PORT=$(shell_quote "${REDIS_PORT:-6379}")"
  remote_cmd+=" REDIS_DB=$(shell_quote "${REDIS_DB:-0}")"
  remote_cmd+=" REDIS_USERNAME=$(shell_quote "${REDIS_USERNAME:-}")"
  remote_cmd+=" REDIS_PASSWORD=$(shell_quote "${REDIS_PASSWORD:-}")"
  remote_cmd+=" bash -s --"

  local arg
  for arg in "$@"; do
    remote_cmd+=" $(shell_quote "$arg")"
  done

  local tmp status=0
  tmp="$(mktemp)"
  ssh "${SSH_OPTS[@]}" "$SSH_TARGET" "$remote_cmd" >"$tmp" <<'REMOTE' || status=$?
set -euo pipefail
if [[ -n "${REMOTE_CWD:-}" ]]; then
  cd "$REMOTE_CWD"
fi
if [[ -z "${URL:-}" && -z "${REDIS_HOST:-}" ]]; then
  [[ -n "${ENV_FILE:-}" ]] || { echo "Missing ENV_FILE or URL." >&2; exit 2; }
  [[ -f "$ENV_FILE" ]] || { echo "Env file not found: $ENV_FILE" >&2; exit 2; }
  URL="$(grep -E "^${ENV_KEY:-REDIS_URL}=" "$ENV_FILE" | tail -n 1 | sed 's/^[^=]*=//' | sed "s/^['\"]//;s/['\"]$//")"
fi
if [[ -n "${URL:-}" && -z "${REDIS_HOST:-}" ]]; then
  redis-cli --raw -u "$URL" "$@"
else
  REDIS_HOST="${REDIS_HOST:-127.0.0.1}"
  REDIS_PORT="${REDIS_PORT:-6379}"
  REDIS_DB="${REDIS_DB:-0}"
  args=(--raw -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB")
  [[ -n "${REDIS_USERNAME:-}" ]] && args+=(--user "$REDIS_USERNAME")
  [[ -n "${REDIS_PASSWORD:-}" ]] && args+=(--no-auth-warning -a "$REDIS_PASSWORD")
  redis-cli "${args[@]}" "$@"
fi
REMOTE
  if [[ $status -ne 0 ]]; then
    rm -f "$tmp"
    return "$status"
  fi
  REDIS_OUTPUT="$(<"$tmp")"
  rm -f "$tmp"
}

find_free_port() {
  local port
  for port in $(seq 43201 43300); do
    if ! port_is_open "$port"; then
      echo "$port"
      return
    fi
  done
  die "Could not find a free local tunnel port."
}

wait_for_local_port() {
  local port="$1"
  local i
  for i in $(seq 1 50); do
    if port_is_open "$port"; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

run_redis() {
  case "${MODE:-direct}" in
    direct)
      command -v redis-cli >/dev/null 2>&1 || die "redis-cli is required for direct mode."
      run_local_redis "$@"
      ;;
    ssh-remote)
      command -v ssh >/dev/null 2>&1 || die "ssh is required for ssh-remote mode."
      run_remote_redis "$@"
      ;;
    ssh-tunnel)
      command -v ssh >/dev/null 2>&1 || die "ssh is required for ssh-tunnel mode."
      command -v redis-cli >/dev/null 2>&1 || die "redis-cli is required for ssh-tunnel mode."
      redis_args
      ssh_target_and_opts
      local local_port ssh_err tunnel_pid err
      local_port="$(find_free_port)"
      ssh_err="$(mktemp)"
      ssh -N -L "127.0.0.1:${local_port}:${REDIS_HOST}:${REDIS_PORT}" -o ExitOnForwardFailure=yes "${SSH_OPTS[@]}" "$SSH_TARGET" 2>"$ssh_err" &
      tunnel_pid=$!
      trap 'kill "$tunnel_pid" >/dev/null 2>&1 || true; rm -f "$ssh_err"' RETURN
      if ! kill -0 "$tunnel_pid" >/dev/null 2>&1; then
        err="$(<"$ssh_err")"
        die "SSH tunnel failed: ${err:-unknown error}"
      fi
      if ! wait_for_local_port "$local_port"; then
        err="$(<"$ssh_err")"
        die "SSH tunnel did not become ready: ${err:-timeout waiting for local port}"
      fi
      REDIS_HOST="127.0.0.1" REDIS_PORT="$local_port" run_local_redis "$@"
      ;;
    *)
      die "Unsupported mode: ${MODE:-}"
      ;;
  esac
}

readonly_guard() {
  if [[ "${READONLY:-false}" == "true" ]]; then
    die "This profile is readonly; write Redis commands are blocked."
  fi
}

is_read_command() {
  local cmd
  cmd="$(printf '%s' "$1" | tr '[:lower:]' '[:upper:]')"
  case "$cmd" in
    GET|MGET|HGET|HGETALL|HEXISTS|HLEN|LRANGE|LLEN|SMEMBERS|SCARD|ZRANGE|ZCARD|TTL|PTTL|TYPE|EXISTS|SCAN|PING|INFO|DBSIZE)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

profile_json() {
  local profile="$1"
  local path
  path="$(profile_path "$profile")"
  # shellcheck disable=SC1090
  source "$path"
  local json="{\"mode\":$(json_string "${MODE:-direct}"),\"readonly\":${READONLY:-false}"
  if [[ -n "${SSH_ALIAS:-}${SSH_HOST:-}" ]]; then
    json+=",\"ssh\":{"
    local first=true
    if [[ -n "${SSH_ALIAS:-}" ]]; then json+="\"alias\":$(json_string "$SSH_ALIAS")"; first=false; fi
    if [[ -n "${SSH_HOST:-}" ]]; then [[ "$first" == false ]] && json+=","; json+="\"host\":$(json_string "$SSH_HOST")"; first=false; fi
    if [[ -n "${SSH_USER:-}" ]]; then [[ "$first" == false ]] && json+=","; json+="\"user\":$(json_string "$SSH_USER")"; first=false; fi
    if [[ -n "${SSH_KEY:-}" ]]; then [[ "$first" == false ]] && json+=","; json+="\"key_path\":$(json_string "$SSH_KEY")"; fi
    json+="}"
  fi
  [[ -n "${REMOTE_CWD:-}" ]] && json+=",\"remote_cwd\":$(json_string "$REMOTE_CWD")"
  [[ -n "${ENV_FILE:-}" ]] && json+=",\"env_file\":$(json_string "$ENV_FILE")"
  [[ -n "${ENV_KEY:-}" ]] && json+=",\"env_key\":$(json_string "$ENV_KEY")"
  [[ -n "${URL:-}" ]] && json+=",\"url\":$(json_string "$(redact_url "$URL")")"
  if [[ -n "${REDIS_HOST:-}${REDIS_DB:-}${REDIS_USERNAME:-}" ]]; then
    json+=",\"redis\":{\"host\":$(json_string "${REDIS_HOST:-127.0.0.1}"),\"port\":${REDIS_PORT:-6379},\"db\":${REDIS_DB:-0}"
    [[ -n "${REDIS_USERNAME:-}" ]] && json+=",\"username\":$(json_string "$REDIS_USERNAME")"
    [[ -n "${REDIS_PASSWORD:-}" ]] && json+=",\"password\":\"****\""
    json+="}"
  fi
  json+="}"
  printf '%s' "$json"
}

cmd_configure() {
  local PROFILE="" MODE="" READONLY=false DEFAULT=false TEST_CONNECTION=false URL=""
  local SSH_ALIAS="" SSH_HOST="" SSH_USER="" SSH_KEY=""
  local REMOTE_CWD="" ENV_FILE="" ENV_KEY="REDIS_URL"
  local REDIS_HOST="" REDIS_PORT="6379" REDIS_DB="0" REDIS_USERNAME="" REDIS_PASSWORD=""
  local OUTPUT=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --mode) MODE="${2:-}"; shift 2 ;;
      --readonly) READONLY=true; shift ;;
      --default) DEFAULT=true; shift ;;
      --test-connection) TEST_CONNECTION=true; shift ;;
      --url) URL="${2:-}"; shift 2 ;;
      --ssh-alias) SSH_ALIAS="${2:-}"; shift 2 ;;
      --ssh-host) SSH_HOST="${2:-}"; shift 2 ;;
      --ssh-user) SSH_USER="${2:-}"; shift 2 ;;
      --ssh-key) SSH_KEY="${2:-}"; shift 2 ;;
      --remote-cwd) REMOTE_CWD="${2:-}"; shift 2 ;;
      --env-file) ENV_FILE="${2:-}"; shift 2 ;;
      --env-key) ENV_KEY="${2:-}"; shift 2 ;;
      --redis-host) REDIS_HOST="${2:-}"; shift 2 ;;
      --redis-port) REDIS_PORT="${2:-}"; shift 2 ;;
      --redis-db) REDIS_DB="${2:-}"; shift 2 ;;
      --redis-username) REDIS_USERNAME="${2:-}"; shift 2 ;;
      --redis-password) REDIS_PASSWORD="${2:-}"; shift 2 ;;
      --prompt-redis-password) read -r -s -p "Redis password: " REDIS_PASSWORD; echo >&2; shift ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown configure argument: $1" ;;
    esac
  done
  [[ -n "$PROFILE" ]] || die "Missing --profile"
  [[ "$MODE" =~ ^(direct|ssh-tunnel|ssh-remote)$ ]] || die "Missing or invalid --mode"
  if [[ "$MODE" == "direct" && -z "$URL$REDIS_HOST" ]]; then
    die "direct mode requires --url or Redis connection fields."
  fi
  if [[ "$MODE" == "ssh-tunnel" ]]; then
    [[ -n "$SSH_ALIAS$SSH_HOST" ]] || die "ssh-tunnel requires --ssh-alias or --ssh-host."
    [[ -n "$REDIS_HOST" ]] || die "ssh-tunnel requires --redis-host."
  fi
  if [[ "$MODE" == "ssh-remote" ]]; then
    [[ -n "$SSH_ALIAS$SSH_HOST" ]] || die "ssh-remote requires --ssh-alias or --ssh-host."
    [[ -n "$ENV_FILE$URL$REDIS_HOST" ]] || die "ssh-remote requires --env-file, --url, or Redis connection fields."
  fi
  if [[ "$TEST_CONNECTION" == "true" ]]; then
    PROFILE_NAME="$PROFILE"
    run_redis PING >/dev/null
  fi
  chmod_config
  local path
  path="$(profile_path "$PROFILE")"
  {
    write_kv MODE "$MODE"
    write_kv READONLY "$READONLY"
    write_kv URL "$URL"
    write_kv SSH_ALIAS "$SSH_ALIAS"
    write_kv SSH_HOST "$SSH_HOST"
    write_kv SSH_USER "$SSH_USER"
    write_kv SSH_KEY "$SSH_KEY"
    write_kv REMOTE_CWD "$REMOTE_CWD"
    write_kv ENV_FILE "$ENV_FILE"
    write_kv ENV_KEY "$ENV_KEY"
    write_kv REDIS_HOST "$REDIS_HOST"
    write_kv REDIS_PORT "$REDIS_PORT"
    write_kv REDIS_DB "$REDIS_DB"
    write_kv REDIS_USERNAME "$REDIS_USERNAME"
    write_kv REDIS_PASSWORD "$REDIS_PASSWORD"
  } >"$path"
  chmod 600 "$path"
  if [[ "$DEFAULT" == "true" || ! -f "$DEFAULT_FILE" ]]; then
    printf '%s\n' "$PROFILE" >"$DEFAULT_FILE"
    chmod 600 "$DEFAULT_FILE"
  fi
  local default_profile
  default_profile="$(<"$DEFAULT_FILE")"
  emit_json "{\"configured\":$(json_string "$PROFILE"),\"default_profile\":$(json_string "$default_profile"),\"profile\":$(profile_json "$PROFILE"),\"config_dir\":$(json_string "$CONFIG_DIR")}" "$OUTPUT"
}

cmd_list_profiles() {
  local OUTPUT=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown list-profiles argument: $1" ;;
    esac
  done
  chmod_config
  local default_profile=""
  [[ -f "$DEFAULT_FILE" ]] && default_profile="$(<"$DEFAULT_FILE")"
  local json="{\"default_profile\":$(json_string "$default_profile"),\"profiles\":{"
  local first=true path name
  shopt -s nullglob
  for path in "$PROFILE_DIR"/*.conf; do
    name="$(basename "$path" .conf)"
    [[ "$first" == false ]] && json+=","
    json+="\"$(json_escape "$name")\":$(profile_json "$name")"
    first=false
  done
  json+="},\"config_dir\":$(json_string "$CONFIG_DIR")}"
  emit_json "$json" "$OUTPUT"
}

cmd_remove_profile() {
  local PROFILE="" OUTPUT=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown remove-profile argument: $1" ;;
    esac
  done
  [[ -n "$PROFILE" ]] || die "Missing --profile"
  local path
  path="$(profile_path "$PROFILE")"
  [[ -f "$path" ]] || die "Profile not found: $PROFILE"
  rm -f "$path"
  emit_json "{\"removed\":$(json_string "$PROFILE")}" "$OUTPUT"
}

emit_result() {
  local operation="$1"
  local extra="$2"
  local lines
  lines="$(result_lines_json "$REDIS_OUTPUT")"
  emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "$MODE"),\"operation\":$(json_string "$operation")${extra},\"result\":$(json_string "$REDIS_OUTPUT"),\"lines\":${lines}}" "$OUTPUT"
}

cmd_ping() {
  local PROFILE="" OUTPUT=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown ping argument: $1" ;;
    esac
  done
  load_profile "$PROFILE"
  run_redis PING
  emit_result ping ""
}

cmd_get() {
  local PROFILE="" KEY="" OUTPUT=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --key) KEY="${2:-}"; shift 2 ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown get argument: $1" ;;
    esac
  done
  [[ -n "$KEY" ]] || die "Missing --key"
  load_profile "$PROFILE"
  run_redis GET "$KEY"
  emit_result get ",\"key\":$(json_string "$KEY")"
}

cmd_set() {
  local PROFILE="" KEY="" VALUE="" TTL="" EXECUTE=false OUTPUT="" VALUE_SET=false
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --key) KEY="${2:-}"; shift 2 ;;
      --value) VALUE="${2-}"; VALUE_SET=true; shift 2 ;;
      --ttl) TTL="${2:-}"; shift 2 ;;
      --execute) EXECUTE=true; shift ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown set argument: $1" ;;
    esac
  done
  [[ -n "$KEY" ]] || die "Missing --key"
  [[ "$VALUE_SET" == "true" ]] || die "Missing --value"
  load_profile "$PROFILE"
  readonly_guard
  if [[ "$EXECUTE" != "true" ]]; then
    emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "$MODE"),\"operation\":\"set\",\"dry_run\":true,\"key\":$(json_string "$KEY"),\"ttl\":$(json_string "$TTL"),\"message\":\"Pass --execute only after user confirmation.\"}" "$OUTPUT"
    return
  fi
  if [[ -n "$TTL" ]]; then
    run_redis SET "$KEY" "$VALUE" EX "$TTL"
  else
    run_redis SET "$KEY" "$VALUE"
  fi
  emit_result set ",\"key\":$(json_string "$KEY"),\"ttl\":$(json_string "$TTL")"
}

cmd_del() {
  local PROFILE="" KEY="" EXECUTE=false OUTPUT=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --key) KEY="${2:-}"; shift 2 ;;
      --execute) EXECUTE=true; shift ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown del argument: $1" ;;
    esac
  done
  [[ -n "$KEY" ]] || die "Missing --key"
  load_profile "$PROFILE"
  readonly_guard
  if [[ "$EXECUTE" != "true" ]]; then
    emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "$MODE"),\"operation\":\"del\",\"dry_run\":true,\"key\":$(json_string "$KEY"),\"message\":\"Pass --execute only after user confirmation.\"}" "$OUTPUT"
    return
  fi
  run_redis DEL "$KEY"
  emit_result del ",\"key\":$(json_string "$KEY")"
}

cmd_hget() {
  local PROFILE="" KEY="" FIELD="" OUTPUT=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --key) KEY="${2:-}"; shift 2 ;;
      --field) FIELD="${2:-}"; shift 2 ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown hget argument: $1" ;;
    esac
  done
  [[ -n "$KEY" && -n "$FIELD" ]] || die "Missing --key or --field"
  load_profile "$PROFILE"
  run_redis HGET "$KEY" "$FIELD"
  emit_result hget ",\"key\":$(json_string "$KEY"),\"field\":$(json_string "$FIELD")"
}

cmd_hset() {
  local PROFILE="" KEY="" FIELD="" VALUE="" EXECUTE=false OUTPUT="" VALUE_SET=false
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --key) KEY="${2:-}"; shift 2 ;;
      --field) FIELD="${2:-}"; shift 2 ;;
      --value) VALUE="${2-}"; VALUE_SET=true; shift 2 ;;
      --execute) EXECUTE=true; shift ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown hset argument: $1" ;;
    esac
  done
  [[ -n "$KEY" && -n "$FIELD" ]] || die "Missing --key or --field"
  [[ "$VALUE_SET" == "true" ]] || die "Missing --value"
  load_profile "$PROFILE"
  readonly_guard
  if [[ "$EXECUTE" != "true" ]]; then
    emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "$MODE"),\"operation\":\"hset\",\"dry_run\":true,\"key\":$(json_string "$KEY"),\"field\":$(json_string "$FIELD"),\"message\":\"Pass --execute only after user confirmation.\"}" "$OUTPUT"
    return
  fi
  run_redis HSET "$KEY" "$FIELD" "$VALUE"
  emit_result hset ",\"key\":$(json_string "$KEY"),\"field\":$(json_string "$FIELD")"
}

cmd_hgetall() {
  local PROFILE="" KEY="" OUTPUT=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --key) KEY="${2:-}"; shift 2 ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown hgetall argument: $1" ;;
    esac
  done
  [[ -n "$KEY" ]] || die "Missing --key"
  load_profile "$PROFILE"
  run_redis HGETALL "$KEY"
  emit_result hgetall ",\"key\":$(json_string "$KEY")"
}

scan_keys_json() {
  local output="$1"
  local json="["
  local first=true
  local line_number=0
  local line
  while IFS= read -r line; do
    line_number=$((line_number + 1))
    [[ $line_number -eq 1 ]] && continue
    [[ "$first" == false ]] && json+=","
    json+="$(json_string "$line")"
    first=false
  done <<<"$output"
  json+="]"
  printf '%s' "$json"
}

scan_next_cursor() {
  local output="$1"
  local line
  IFS= read -r line <<<"$output" || true
  printf '%s' "${line:-0}"
}

args_json() {
  local json="["
  local first=true
  local arg
  for arg in "$@"; do
    [[ "$first" == false ]] && json+=","
    json+="$(json_string "$arg")"
    first=false
  done
  json+="]"
  printf '%s' "$json"
}

cmd_scan() {
  local PROFILE="" PATTERN="*" COUNT="100" CURSOR="0" ALL=false OUTPUT=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --pattern) PATTERN="${2:-}"; shift 2 ;;
      --count) COUNT="${2:-}"; shift 2 ;;
      --cursor) CURSOR="${2:-}"; shift 2 ;;
      --all) ALL=true; shift ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown scan argument: $1" ;;
    esac
  done
  [[ "$COUNT" =~ ^[0-9]+$ ]] || die "--count must be a positive integer"
  [[ "$COUNT" != "0" ]] || die "--count must be a positive integer"
  [[ "$CURSOR" =~ ^[0-9]+$ ]] || die "--cursor must be a non-negative integer"
  load_profile "$PROFILE"
  if [[ "$ALL" != "true" ]]; then
    run_redis SCAN "$CURSOR" MATCH "$PATTERN" COUNT "$COUNT"
    local next_cursor keys
    next_cursor="$(scan_next_cursor "$REDIS_OUTPUT")"
    keys="$(scan_keys_json "$REDIS_OUTPUT")"
    emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "$MODE"),\"operation\":\"scan\",\"pattern\":$(json_string "$PATTERN"),\"count\":$COUNT,\"cursor\":$(json_string "$CURSOR"),\"next_cursor\":$(json_string "$next_cursor"),\"complete\":$(if [[ "$next_cursor" == "0" ]]; then printf true; else printf false; fi),\"keys\":${keys},\"result\":$(json_string "$REDIS_OUTPUT"),\"lines\":$(result_lines_json "$REDIS_OUTPUT")}" "$OUTPUT"
    return
  fi

  local current_cursor="$CURSOR"
  local next_cursor all_keys_json="[" first=true line line_number
  while :; do
    run_redis SCAN "$current_cursor" MATCH "$PATTERN" COUNT "$COUNT"
    next_cursor="$(scan_next_cursor "$REDIS_OUTPUT")"
    line_number=0
    while IFS= read -r line; do
      line_number=$((line_number + 1))
      [[ $line_number -eq 1 ]] && continue
      [[ "$first" == false ]] && all_keys_json+=","
      all_keys_json+="$(json_string "$line")"
      first=false
    done <<<"$REDIS_OUTPUT"
    [[ "$next_cursor" == "0" ]] && break
    current_cursor="$next_cursor"
  done
  all_keys_json+="]"
  emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "$MODE"),\"operation\":\"scan\",\"pattern\":$(json_string "$PATTERN"),\"count\":$COUNT,\"cursor\":$(json_string "$CURSOR"),\"next_cursor\":\"0\",\"complete\":true,\"keys\":${all_keys_json}}" "$OUTPUT"
}

cmd_raw_command() {
  local PROFILE="" COMMAND="" EXECUTE=false ALLOW_RAW_WRITE=false OUTPUT=""
  local COMMAND_ARGS=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --command) COMMAND="${2:-}"; shift 2 ;;
      --arg) COMMAND_ARGS+=("${2-}"); shift 2 ;;
      --execute) EXECUTE=true; shift ;;
      --allow-raw-write) ALLOW_RAW_WRITE=true; shift ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown raw-command argument: $1" ;;
    esac
  done
  if [[ -n "$COMMAND" && ${#COMMAND_ARGS[@]} -gt 0 ]]; then
    die "Use either --command or repeated --arg values, not both."
  fi
  if [[ ${#COMMAND_ARGS[@]} -eq 0 ]]; then
    [[ -n "$COMMAND" ]] || die "Missing --command or --arg"
    read -r -a COMMAND_ARGS <<<"$COMMAND"
  fi
  [[ ${#COMMAND_ARGS[@]} -gt 0 ]] || die "Missing command name"
  local command_name="${COMMAND_ARGS[0]}"
  load_profile "$PROFILE"
  if ! is_read_command "$command_name"; then
    readonly_guard
    if [[ "$EXECUTE" != "true" || "$ALLOW_RAW_WRITE" != "true" ]]; then
      emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "$MODE"),\"operation\":\"raw-command\",\"dry_run\":true,\"command\":$(json_string "$COMMAND"),\"args\":$(args_json "${COMMAND_ARGS[@]}"),\"message\":\"Raw write command was not executed. Pass both --execute and --allow-raw-write only after user confirmation.\"}" "$OUTPUT"
      return
    fi
  fi
  run_redis "${COMMAND_ARGS[@]}"
  emit_result raw-command ",\"command\":$(json_string "$COMMAND"),\"args\":$(args_json "${COMMAND_ARGS[@]}")"
}

main() {
  [[ $# -gt 0 ]] || { usage; exit 0; }
  local cmd="$1"
  shift
  case "$cmd" in
    configure) cmd_configure "$@" ;;
    list-profiles) cmd_list_profiles "$@" ;;
    remove-profile) cmd_remove_profile "$@" ;;
    ping) cmd_ping "$@" ;;
    get) cmd_get "$@" ;;
    set) cmd_set "$@" ;;
    del) cmd_del "$@" ;;
    hget) cmd_hget "$@" ;;
    hset) cmd_hset "$@" ;;
    hgetall) cmd_hgetall "$@" ;;
    scan) cmd_scan "$@" ;;
    raw-command) cmd_raw_command "$@" ;;
    -h|--help|help) usage ;;
    *) die "Unknown command: $cmd" ;;
  esac
}

main "$@"
