#!/usr/bin/env bash

set -euo pipefail

CONFIG_DIR="${HOME}/.config/mongodb-crud"
PROFILE_DIR="${CONFIG_DIR}/profiles"
DEFAULT_FILE="${CONFIG_DIR}/default_profile"

usage() {
  cat <<'EOF'
Usage:
  mongodb_crud.sh configure --profile NAME --mode direct|ssh-tunnel|ssh-remote [options]
  mongodb_crud.sh list-profiles [--output PATH]
  mongodb_crud.sh remove-profile --profile NAME [--output PATH]
  mongodb_crud.sh ping [--profile NAME] [--output PATH]
  mongodb_crud.sh databases [--profile NAME] [--output PATH]
  mongodb_crud.sh collections [--profile NAME] [--database DB] [--output PATH]
  mongodb_crud.sh find [--profile NAME] --collection NAME [--database DB] [--filter JSON] [--projection JSON] [--sort JSON] [--limit N] [--output PATH]
  mongodb_crud.sh count [--profile NAME] --collection NAME [--database DB] [--filter JSON] [--output PATH]
  mongodb_crud.sh insert [--profile NAME] --collection NAME [--database DB] --document JSON [--execute] [--output PATH]
  mongodb_crud.sh update [--profile NAME] --collection NAME [--database DB] --filter JSON --update JSON [--many] [--execute] [--output PATH]
  mongodb_crud.sh delete [--profile NAME] --collection NAME [--database DB] --filter JSON [--many] [--execute] [--output PATH]
  mongodb_crud.sh raw-eval [--profile NAME] --eval JS [--execute] [--allow-raw-write] [--output PATH]

Common configure options:
  --readonly
  --default
  --test-connection
  --uri mongodb://user:pass@host:27017/db?authSource=admin
  --mongo-host HOST --mongo-port 27017 --database DB [--mongo-username USER] [--mongo-password PASS] [--auth-database admin]
  --ssh-alias ALIAS
  --ssh-host HOST [--ssh-user USER] [--ssh-key PATH]
  --remote-cwd PATH --env-file .env --env-key MONGODB_URI
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

js_string() {
  json_string "$1"
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

redact_uri() {
  local uri="${1-}"
  if [[ "$uri" =~ ^([^:]+://)([^@]*@)(.*)$ ]]; then
    printf '%s****@%s' "${BASH_REMATCH[1]}" "${BASH_REMATCH[3]}"
  else
    printf '%s' "$uri"
  fi
}

emit_json() {
  local json="$1"
  local output="${2-}"
  if [[ -z "$output" ]]; then
    mkdir -p out
    output="out/mongodb-crud-$(date -u +%Y%m%dT%H%M%SZ)-$$.json"
  else
    mkdir -p "$(dirname "$output")"
  fi
  printf '%s\n' "$json" >"$output"
  echo "Saved JSON to $output" >&2
  printf '%s\n' "$json"
}

mongo_defaults() {
  MONGO_HOST="${MONGO_HOST:-127.0.0.1}"
  MONGO_PORT="${MONGO_PORT:-27017}"
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

run_local_mongo() {
  local eval_js="$1"
  local tmp status=0
  tmp="$(mktemp)"
  if [[ -n "${URI:-}" && -z "${MONGO_HOST:-}" ]]; then
    mongosh "$URI" --quiet --eval "$eval_js" >"$tmp" || status=$?
  else
    mongo_defaults
    local args=(--quiet --host "$MONGO_HOST" --port "$MONGO_PORT")
    [[ -n "${MONGO_USERNAME:-}" ]] && args+=(--username "$MONGO_USERNAME")
    [[ -n "${MONGO_PASSWORD:-}" ]] && args+=(--password "$MONGO_PASSWORD")
    [[ -n "${AUTH_DATABASE:-}" ]] && args+=(--authenticationDatabase "$AUTH_DATABASE")
    [[ -n "${DATABASE:-}" ]] && args+=("$DATABASE")
    mongosh "${args[@]}" --eval "$eval_js" >"$tmp" || status=$?
  fi
  if [[ $status -ne 0 ]]; then
    rm -f "$tmp"
    return "$status"
  fi
  MONGO_OUTPUT="$(<"$tmp")"
  rm -f "$tmp"
}

run_remote_mongo() {
  ssh_target_and_opts
  local remote_cmd="REMOTE_CWD=$(shell_quote "${REMOTE_CWD:-}")"
  remote_cmd+=" ENV_FILE=$(shell_quote "${ENV_FILE:-}")"
  remote_cmd+=" ENV_KEY=$(shell_quote "${ENV_KEY:-MONGODB_URI}")"
  remote_cmd+=" URI=$(shell_quote "${URI:-}")"
  remote_cmd+=" MONGO_HOST=$(shell_quote "${MONGO_HOST:-}")"
  remote_cmd+=" MONGO_PORT=$(shell_quote "${MONGO_PORT:-27017}")"
  remote_cmd+=" DATABASE=$(shell_quote "${DATABASE:-}")"
  remote_cmd+=" MONGO_USERNAME=$(shell_quote "${MONGO_USERNAME:-}")"
  remote_cmd+=" MONGO_PASSWORD=$(shell_quote "${MONGO_PASSWORD:-}")"
  remote_cmd+=" AUTH_DATABASE=$(shell_quote "${AUTH_DATABASE:-}")"
  remote_cmd+=" bash -s -- $(shell_quote "$1")"

  local tmp status=0
  tmp="$(mktemp)"
  ssh "${SSH_OPTS[@]}" "$SSH_TARGET" "$remote_cmd" >"$tmp" <<'REMOTE' || status=$?
set -euo pipefail
eval_js="$1"
if [[ -n "${REMOTE_CWD:-}" ]]; then
  cd "$REMOTE_CWD"
fi
if [[ -z "${URI:-}" && -z "${MONGO_HOST:-}" ]]; then
  [[ -n "${ENV_FILE:-}" ]] || { echo "Missing ENV_FILE or URI." >&2; exit 2; }
  [[ -f "$ENV_FILE" ]] || { echo "Env file not found: $ENV_FILE" >&2; exit 2; }
  URI="$(grep -E "^${ENV_KEY:-MONGODB_URI}=" "$ENV_FILE" | tail -n 1 | sed 's/^[^=]*=//' | sed "s/^['\"]//;s/['\"]$//")"
fi
if [[ -n "${URI:-}" && -z "${MONGO_HOST:-}" ]]; then
  mongosh "$URI" --quiet --eval "$eval_js"
else
  MONGO_HOST="${MONGO_HOST:-127.0.0.1}"
  MONGO_PORT="${MONGO_PORT:-27017}"
  args=(--quiet --host "$MONGO_HOST" --port "$MONGO_PORT")
  [[ -n "${MONGO_USERNAME:-}" ]] && args+=(--username "$MONGO_USERNAME")
  [[ -n "${MONGO_PASSWORD:-}" ]] && args+=(--password "$MONGO_PASSWORD")
  [[ -n "${AUTH_DATABASE:-}" ]] && args+=(--authenticationDatabase "$AUTH_DATABASE")
  [[ -n "${DATABASE:-}" ]] && args+=("$DATABASE")
  mongosh "${args[@]}" --eval "$eval_js"
fi
REMOTE
  if [[ $status -ne 0 ]]; then
    rm -f "$tmp"
    return "$status"
  fi
  MONGO_OUTPUT="$(<"$tmp")"
  rm -f "$tmp"
}

find_free_port() {
  local port
  for port in $(seq 43301 43400); do
    if ! (echo >/dev/tcp/127.0.0.1/"$port") >/dev/null 2>&1; then
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
    if (echo >/dev/tcp/127.0.0.1/"$port") >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

run_mongo() {
  local eval_js="$1"
  case "${MODE:-direct}" in
    direct)
      command -v mongosh >/dev/null 2>&1 || die "mongosh is required for direct mode."
      run_local_mongo "$eval_js"
      ;;
    ssh-remote)
      command -v ssh >/dev/null 2>&1 || die "ssh is required for ssh-remote mode."
      run_remote_mongo "$eval_js"
      ;;
    ssh-tunnel)
      command -v ssh >/dev/null 2>&1 || die "ssh is required for ssh-tunnel mode."
      command -v mongosh >/dev/null 2>&1 || die "mongosh is required for ssh-tunnel mode."
      mongo_defaults
      ssh_target_and_opts
      local local_port ssh_err tunnel_pid err
      local_port="$(find_free_port)"
      ssh_err="$(mktemp)"
      ssh -N -L "127.0.0.1:${local_port}:${MONGO_HOST}:${MONGO_PORT}" -o ExitOnForwardFailure=yes "${SSH_OPTS[@]}" "$SSH_TARGET" 2>"$ssh_err" &
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
      MONGO_HOST="127.0.0.1" MONGO_PORT="$local_port" run_local_mongo "$eval_js"
      ;;
    *)
      die "Unsupported mode: ${MODE:-}"
      ;;
  esac
}

readonly_guard() {
  if [[ "${READONLY:-false}" == "true" ]]; then
    die "This profile is readonly; write MongoDB commands are blocked."
  fi
}

is_raw_write_eval() {
  local js
  js="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  case "$js" in
    *insertone*|*insertmany*|*updateone*|*updatemany*|*replaceone*|*deleteone*|*deletemany*|*dropdatabase*|*drop\(*|*createcollection*|*createindex*|*dropindex*|*bulk/write*|*bulkwrite*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

target_db_js() {
  local db_name="${1:-${DATABASE:-}}"
  if [[ -n "$db_name" ]]; then
    printf 'db.getSiblingDB(%s)' "$(js_string "$db_name")"
  else
    printf 'db'
  fi
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
  [[ -n "${URI:-}" ]] && json+=",\"uri\":$(json_string "$(redact_uri "$URI")")"
  [[ -n "${DATABASE:-}" ]] && json+=",\"database\":$(json_string "$DATABASE")"
  if [[ -n "${MONGO_HOST:-}${MONGO_USERNAME:-}${AUTH_DATABASE:-}" ]]; then
    json+=",\"mongo\":{\"host\":$(json_string "${MONGO_HOST:-127.0.0.1}"),\"port\":${MONGO_PORT:-27017}"
    [[ -n "${MONGO_USERNAME:-}" ]] && json+=",\"username\":$(json_string "$MONGO_USERNAME")"
    [[ -n "${MONGO_PASSWORD:-}" ]] && json+=",\"password\":\"****\""
    [[ -n "${AUTH_DATABASE:-}" ]] && json+=",\"auth_database\":$(json_string "$AUTH_DATABASE")"
    json+="}"
  fi
  json+="}"
  printf '%s' "$json"
}

cmd_configure() {
  local PROFILE="" MODE="" READONLY=false DEFAULT=false TEST_CONNECTION=false URI=""
  local SSH_ALIAS="" SSH_HOST="" SSH_USER="" SSH_KEY=""
  local REMOTE_CWD="" ENV_FILE="" ENV_KEY="MONGODB_URI"
  local MONGO_HOST="" MONGO_PORT="27017" DATABASE="" MONGO_USERNAME="" MONGO_PASSWORD="" AUTH_DATABASE=""
  local OUTPUT=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --mode) MODE="${2:-}"; shift 2 ;;
      --readonly) READONLY=true; shift ;;
      --default) DEFAULT=true; shift ;;
      --test-connection) TEST_CONNECTION=true; shift ;;
      --uri) URI="${2:-}"; shift 2 ;;
      --ssh-alias) SSH_ALIAS="${2:-}"; shift 2 ;;
      --ssh-host) SSH_HOST="${2:-}"; shift 2 ;;
      --ssh-user) SSH_USER="${2:-}"; shift 2 ;;
      --ssh-key) SSH_KEY="${2:-}"; shift 2 ;;
      --remote-cwd) REMOTE_CWD="${2:-}"; shift 2 ;;
      --env-file) ENV_FILE="${2:-}"; shift 2 ;;
      --env-key) ENV_KEY="${2:-}"; shift 2 ;;
      --mongo-host) MONGO_HOST="${2:-}"; shift 2 ;;
      --mongo-port) MONGO_PORT="${2:-}"; shift 2 ;;
      --database) DATABASE="${2:-}"; shift 2 ;;
      --mongo-username) MONGO_USERNAME="${2:-}"; shift 2 ;;
      --mongo-password) MONGO_PASSWORD="${2:-}"; shift 2 ;;
      --prompt-mongo-password) read -r -s -p "MongoDB password: " MONGO_PASSWORD; echo >&2; shift ;;
      --auth-database) AUTH_DATABASE="${2:-}"; shift 2 ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown configure argument: $1" ;;
    esac
  done
  [[ -n "$PROFILE" ]] || die "Missing --profile"
  [[ "$MODE" =~ ^(direct|ssh-tunnel|ssh-remote)$ ]] || die "Missing or invalid --mode"
  if [[ "$MODE" == "direct" && -z "$URI$MONGO_HOST" ]]; then
    die "direct mode requires --uri or MongoDB connection fields."
  fi
  if [[ "$MODE" == "ssh-tunnel" ]]; then
    [[ -n "$SSH_ALIAS$SSH_HOST" ]] || die "ssh-tunnel requires --ssh-alias or --ssh-host."
    [[ -n "$MONGO_HOST" ]] || die "ssh-tunnel requires --mongo-host."
  fi
  if [[ "$MODE" == "ssh-remote" ]]; then
    [[ -n "$SSH_ALIAS$SSH_HOST" ]] || die "ssh-remote requires --ssh-alias or --ssh-host."
    [[ -n "$ENV_FILE$URI$MONGO_HOST" ]] || die "ssh-remote requires --env-file, --uri, or MongoDB connection fields."
  fi
  if [[ "$TEST_CONNECTION" == "true" ]]; then
    PROFILE_NAME="$PROFILE"
    run_mongo 'print(EJSON.stringify(db.runCommand({ping:1})))' >/dev/null
  fi
  chmod_config
  local path
  path="$(profile_path "$PROFILE")"
  {
    write_kv MODE "$MODE"
    write_kv READONLY "$READONLY"
    write_kv URI "$URI"
    write_kv SSH_ALIAS "$SSH_ALIAS"
    write_kv SSH_HOST "$SSH_HOST"
    write_kv SSH_USER "$SSH_USER"
    write_kv SSH_KEY "$SSH_KEY"
    write_kv REMOTE_CWD "$REMOTE_CWD"
    write_kv ENV_FILE "$ENV_FILE"
    write_kv ENV_KEY "$ENV_KEY"
    write_kv MONGO_HOST "$MONGO_HOST"
    write_kv MONGO_PORT "$MONGO_PORT"
    write_kv DATABASE "$DATABASE"
    write_kv MONGO_USERNAME "$MONGO_USERNAME"
    write_kv MONGO_PASSWORD "$MONGO_PASSWORD"
    write_kv AUTH_DATABASE "$AUTH_DATABASE"
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
  local json="{\"default_profile\":$(json_string "$default_profile"),\"profiles\":["
  local first=true file profile
  for file in "$PROFILE_DIR"/*.conf; do
    [[ -e "$file" ]] || continue
    profile="$(basename "$file" .conf)"
    [[ "$first" == false ]] && json+=","
    json+="{\"name\":$(json_string "$profile"),\"default\":"
    if [[ "$profile" == "$default_profile" ]]; then json+="true"; else json+="false"; fi
    json+=",\"profile\":$(profile_json "$profile")}"
    first=false
  done
  json+="]}"
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
  if [[ -f "$DEFAULT_FILE" && "$(<"$DEFAULT_FILE")" == "$PROFILE" ]]; then
    rm -f "$DEFAULT_FILE"
  fi
  emit_json "{\"removed\":$(json_string "$PROFILE")}" "$OUTPUT"
}

parse_common_profile_output() {
  PROFILE=""
  OUTPUT=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown argument: $1" ;;
    esac
  done
}

cmd_ping() {
  parse_common_profile_output "$@"
  load_profile "$PROFILE"
  run_mongo 'print(EJSON.stringify(db.runCommand({ping:1})))'
  emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "${MODE:-direct}"),\"operation\":\"ping\",\"result\":${MONGO_OUTPUT:-null}}" "$OUTPUT"
}

cmd_databases() {
  parse_common_profile_output "$@"
  load_profile "$PROFILE"
  run_mongo 'print(EJSON.stringify(db.adminCommand({listDatabases:1}).databases))'
  emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "${MODE:-direct}"),\"operation\":\"databases\",\"result\":${MONGO_OUTPUT:-[]}}" "$OUTPUT"
}

cmd_collections() {
  local PROFILE="" OUTPUT="" DB_OVERRIDE=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --database) DB_OVERRIDE="${2:-}"; shift 2 ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown collections argument: $1" ;;
    esac
  done
  load_profile "$PROFILE"
  local db_expr
  db_expr="$(target_db_js "$DB_OVERRIDE")"
  run_mongo "print(EJSON.stringify(${db_expr}.getCollectionNames()))"
  emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "${MODE:-direct}"),\"operation\":\"collections\",\"database\":$(json_string "${DB_OVERRIDE:-${DATABASE:-}}"),\"result\":${MONGO_OUTPUT:-[]}}" "$OUTPUT"
}

cmd_find() {
  local PROFILE="" OUTPUT="" DB_OVERRIDE="" COLLECTION="" FILTER="{}" PROJECTION="" SORT="" LIMIT="20"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --database) DB_OVERRIDE="${2:-}"; shift 2 ;;
      --collection) COLLECTION="${2:-}"; shift 2 ;;
      --filter) FILTER="${2:-}"; shift 2 ;;
      --projection) PROJECTION="${2:-}"; shift 2 ;;
      --sort) SORT="${2:-}"; shift 2 ;;
      --limit) LIMIT="${2:-}"; shift 2 ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown find argument: $1" ;;
    esac
  done
  [[ -n "$COLLECTION" ]] || die "Missing --collection"
  [[ "$LIMIT" =~ ^[0-9]+$ ]] || die "--limit must be a non-negative integer"
  load_profile "$PROFILE"
  local db_expr js
  db_expr="$(target_db_js "$DB_OVERRIDE")"
  js="const q=EJSON.parse($(js_string "$FILTER"));"
  if [[ -n "$PROJECTION" ]]; then js+="const p=EJSON.parse($(js_string "$PROJECTION"));"; else js+="const p=undefined;"; fi
  if [[ -n "$SORT" ]]; then js+="const s=EJSON.parse($(js_string "$SORT"));"; else js+="const s=null;"; fi
  js+="let c=${db_expr}.getCollection($(js_string "$COLLECTION")).find(q,p); if(s)c=c.sort(s); print(EJSON.stringify(c.limit($LIMIT).toArray()));"
  run_mongo "$js"
  emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "${MODE:-direct}"),\"operation\":\"find\",\"database\":$(json_string "${DB_OVERRIDE:-${DATABASE:-}}"),\"collection\":$(json_string "$COLLECTION"),\"filter\":$FILTER,\"limit\":$LIMIT,\"result\":${MONGO_OUTPUT:-[]}}" "$OUTPUT"
}

cmd_count() {
  local PROFILE="" OUTPUT="" DB_OVERRIDE="" COLLECTION="" FILTER="{}"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --database) DB_OVERRIDE="${2:-}"; shift 2 ;;
      --collection) COLLECTION="${2:-}"; shift 2 ;;
      --filter) FILTER="${2:-}"; shift 2 ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown count argument: $1" ;;
    esac
  done
  [[ -n "$COLLECTION" ]] || die "Missing --collection"
  load_profile "$PROFILE"
  local db_expr js
  db_expr="$(target_db_js "$DB_OVERRIDE")"
  js="const q=EJSON.parse($(js_string "$FILTER")); print(EJSON.stringify({count:${db_expr}.getCollection($(js_string "$COLLECTION")).countDocuments(q)}));"
  run_mongo "$js"
  emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "${MODE:-direct}"),\"operation\":\"count\",\"database\":$(json_string "${DB_OVERRIDE:-${DATABASE:-}}"),\"collection\":$(json_string "$COLLECTION"),\"filter\":$FILTER,\"result\":${MONGO_OUTPUT:-null}}" "$OUTPUT"
}

cmd_insert() {
  local PROFILE="" OUTPUT="" DB_OVERRIDE="" COLLECTION="" DOCUMENT="" EXECUTE=false
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --database) DB_OVERRIDE="${2:-}"; shift 2 ;;
      --collection) COLLECTION="${2:-}"; shift 2 ;;
      --document) DOCUMENT="${2:-}"; shift 2 ;;
      --execute) EXECUTE=true; shift ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown insert argument: $1" ;;
    esac
  done
  [[ -n "$COLLECTION" ]] || die "Missing --collection"
  [[ -n "$DOCUMENT" ]] || die "Missing --document"
  load_profile "$PROFILE"
  readonly_guard
  if [[ "$EXECUTE" != "true" ]]; then
    emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "${MODE:-direct}"),\"operation\":\"insert\",\"dry_run\":true,\"database\":$(json_string "${DB_OVERRIDE:-${DATABASE:-}}"),\"collection\":$(json_string "$COLLECTION"),\"document\":$DOCUMENT}" "$OUTPUT"
    return
  fi
  local db_expr js
  db_expr="$(target_db_js "$DB_OVERRIDE")"
  js="const d=EJSON.parse($(js_string "$DOCUMENT")); print(EJSON.stringify(${db_expr}.getCollection($(js_string "$COLLECTION")).insertOne(d)));"
  run_mongo "$js"
  emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "${MODE:-direct}"),\"operation\":\"insert\",\"dry_run\":false,\"database\":$(json_string "${DB_OVERRIDE:-${DATABASE:-}}"),\"collection\":$(json_string "$COLLECTION"),\"result\":${MONGO_OUTPUT:-null}}" "$OUTPUT"
}

cmd_update() {
  local PROFILE="" OUTPUT="" DB_OVERRIDE="" COLLECTION="" FILTER="" UPDATE="" MANY=false EXECUTE=false
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --database) DB_OVERRIDE="${2:-}"; shift 2 ;;
      --collection) COLLECTION="${2:-}"; shift 2 ;;
      --filter) FILTER="${2:-}"; shift 2 ;;
      --update) UPDATE="${2:-}"; shift 2 ;;
      --many) MANY=true; shift ;;
      --execute) EXECUTE=true; shift ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown update argument: $1" ;;
    esac
  done
  [[ -n "$COLLECTION" ]] || die "Missing --collection"
  [[ -n "$FILTER" ]] || die "Missing --filter"
  [[ -n "$UPDATE" ]] || die "Missing --update"
  [[ "$FILTER" != "{}" ]] || die "Refusing update with empty filter. Use raw-eval with explicit approval for broad updates."
  load_profile "$PROFILE"
  readonly_guard
  if [[ "$EXECUTE" != "true" ]]; then
    emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "${MODE:-direct}"),\"operation\":\"update\",\"dry_run\":true,\"many\":$MANY,\"database\":$(json_string "${DB_OVERRIDE:-${DATABASE:-}}"),\"collection\":$(json_string "$COLLECTION"),\"filter\":$FILTER,\"update\":$UPDATE}" "$OUTPUT"
    return
  fi
  local db_expr method js
  db_expr="$(target_db_js "$DB_OVERRIDE")"
  if [[ "$MANY" == "true" ]]; then method="updateMany"; else method="updateOne"; fi
  js="const q=EJSON.parse($(js_string "$FILTER")); const u=EJSON.parse($(js_string "$UPDATE")); print(EJSON.stringify(${db_expr}.getCollection($(js_string "$COLLECTION")).${method}(q,u)));"
  run_mongo "$js"
  emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "${MODE:-direct}"),\"operation\":\"update\",\"dry_run\":false,\"many\":$MANY,\"database\":$(json_string "${DB_OVERRIDE:-${DATABASE:-}}"),\"collection\":$(json_string "$COLLECTION"),\"result\":${MONGO_OUTPUT:-null}}" "$OUTPUT"
}

cmd_delete() {
  local PROFILE="" OUTPUT="" DB_OVERRIDE="" COLLECTION="" FILTER="" MANY=false EXECUTE=false
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --database) DB_OVERRIDE="${2:-}"; shift 2 ;;
      --collection) COLLECTION="${2:-}"; shift 2 ;;
      --filter) FILTER="${2:-}"; shift 2 ;;
      --many) MANY=true; shift ;;
      --execute) EXECUTE=true; shift ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown delete argument: $1" ;;
    esac
  done
  [[ -n "$COLLECTION" ]] || die "Missing --collection"
  [[ -n "$FILTER" ]] || die "Missing --filter"
  [[ "$FILTER" != "{}" ]] || die "Refusing delete with empty filter. Use raw-eval with explicit approval for broad deletes."
  load_profile "$PROFILE"
  readonly_guard
  if [[ "$EXECUTE" != "true" ]]; then
    emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "${MODE:-direct}"),\"operation\":\"delete\",\"dry_run\":true,\"many\":$MANY,\"database\":$(json_string "${DB_OVERRIDE:-${DATABASE:-}}"),\"collection\":$(json_string "$COLLECTION"),\"filter\":$FILTER}" "$OUTPUT"
    return
  fi
  local db_expr method js
  db_expr="$(target_db_js "$DB_OVERRIDE")"
  if [[ "$MANY" == "true" ]]; then method="deleteMany"; else method="deleteOne"; fi
  js="const q=EJSON.parse($(js_string "$FILTER")); print(EJSON.stringify(${db_expr}.getCollection($(js_string "$COLLECTION")).${method}(q)));"
  run_mongo "$js"
  emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "${MODE:-direct}"),\"operation\":\"delete\",\"dry_run\":false,\"many\":$MANY,\"database\":$(json_string "${DB_OVERRIDE:-${DATABASE:-}}"),\"collection\":$(json_string "$COLLECTION"),\"result\":${MONGO_OUTPUT:-null}}" "$OUTPUT"
}

cmd_raw_eval() {
  local PROFILE="" OUTPUT="" EVAL_JS="" EXECUTE=false ALLOW_RAW_WRITE=false
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --eval) EVAL_JS="${2:-}"; shift 2 ;;
      --execute) EXECUTE=true; shift ;;
      --allow-raw-write) ALLOW_RAW_WRITE=true; shift ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown raw-eval argument: $1" ;;
    esac
  done
  [[ -n "$EVAL_JS" ]] || die "Missing --eval"
  load_profile "$PROFILE"
  local IS_WRITE=false
  if is_raw_write_eval "$EVAL_JS"; then
    IS_WRITE=true
  fi
  if [[ "$IS_WRITE" == "true" ]]; then
    readonly_guard
    if [[ "$EXECUTE" != "true" || "$ALLOW_RAW_WRITE" != "true" ]]; then
      emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "${MODE:-direct}"),\"operation\":\"raw-eval\",\"dry_run\":true,\"requires\":\"--execute --allow-raw-write\",\"eval\":$(json_string "$EVAL_JS")}" "$OUTPUT"
      return
    fi
  fi
  run_mongo "$EVAL_JS"
  emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "${MODE:-direct}"),\"operation\":\"raw-eval\",\"dry_run\":false,\"raw_write\":$IS_WRITE,\"result\":$(json_string "$MONGO_OUTPUT")}" "$OUTPUT"
}

main() {
  local cmd="${1:-}"
  [[ -n "$cmd" ]] || { usage; exit 1; }
  shift || true
  case "$cmd" in
    configure) cmd_configure "$@" ;;
    list-profiles) cmd_list_profiles "$@" ;;
    remove-profile) cmd_remove_profile "$@" ;;
    ping) cmd_ping "$@" ;;
    databases) cmd_databases "$@" ;;
    collections) cmd_collections "$@" ;;
    find) cmd_find "$@" ;;
    count) cmd_count "$@" ;;
    insert) cmd_insert "$@" ;;
    update) cmd_update "$@" ;;
    delete) cmd_delete "$@" ;;
    raw-eval) cmd_raw_eval "$@" ;;
    -h|--help|help) usage ;;
    *) die "Unknown command: $cmd" ;;
  esac
}

main "$@"
