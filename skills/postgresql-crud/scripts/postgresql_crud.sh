#!/usr/bin/env bash

set -euo pipefail

CONFIG_DIR="${HOME}/.config/postgresql-crud"
PROFILE_DIR="${CONFIG_DIR}/profiles"
DEFAULT_FILE="${CONFIG_DIR}/default_profile"

usage() {
  cat <<'EOF'
Usage:
  postgresql_crud.sh configure --profile NAME --mode direct|ssh-tunnel|ssh-remote [options]
  postgresql_crud.sh list-profiles [--output PATH]
  postgresql_crud.sh remove-profile --profile NAME [--output PATH]
  postgresql_crud.sh schema [--profile NAME] [--schema public] [--all-schemas] [--table TABLE] [--output PATH]
  postgresql_crud.sh select [--profile NAME] [--schema public] --table TABLE [--columns c1,c2] [--where "id = :id"] [--param id=1] [--limit 50] [--output PATH]
  postgresql_crud.sh insert [--profile NAME] [--schema public] --table TABLE --value col=value [--execute] [--output PATH]
  postgresql_crud.sh update [--profile NAME] [--schema public] --table TABLE --set col=value --where "id = :id" [--param id=1] [--execute] [--output PATH]
  postgresql_crud.sh delete [--profile NAME] [--schema public] --table TABLE --where "id = :id" [--param id=1] [--execute] [--output PATH]
  postgresql_crud.sh raw-sql [--profile NAME] --sql "SELECT 1" [--execute] [--allow-raw-write] [--output PATH]

Common configure options:
  --readonly
  --default
  --test-connection
  --url postgresql://user:password@host:5432/database
  --pg-host HOST --pg-port 5432 --pg-database DB --pg-user USER [--pg-password PASS]
  --ssh-alias ALIAS
  --ssh-host HOST [--ssh-user USER] [--ssh-key PATH]
  --remote-cwd PATH --env-file .env --env-key DATABASE_URL
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

safe_identifier() {
  [[ "$1" =~ ^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$ ]]
}

quote_ident() {
  local value="$1"
  safe_identifier "$value" || die "Unsafe identifier: $value"
  local old_ifs="$IFS"
  IFS='.'
  read -r -a parts <<<"$value"
  IFS="$old_ifs"
  local out=""
  local part
  for part in "${parts[@]}"; do
    part="${part//\"/\"\"}"
    if [[ -z "$out" ]]; then
      out="\"${part}\""
    else
      out="${out}.\"${part}\""
    fi
  done
  printf '%s' "$out"
}

qualify_table() {
  local schema="$1"
  local table="$2"
  if [[ "$table" == *.* ]]; then
    quote_ident "$table"
  else
    quote_ident "${schema}.${table}"
  fi
}

schema_for_table() {
  local schema="$1"
  local table="$2"
  if [[ "$table" == *.* ]]; then
    printf '%s' "${table%%.*}"
  else
    printf '%s' "$schema"
  fi
}

name_for_table() {
  local table="$1"
  if [[ "$table" == *.* ]]; then
    printf '%s' "${table#*.}"
  else
    printf '%s' "$table"
  fi
}

sql_literal() {
  local s="${1-}"
  s=${s//\'/\'\'}
  printf "'%s'" "$s"
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
  if [[ "$url" =~ ^([^:]+://[^:/@]+):([^@]*)@(.*)$ ]]; then
    printf '%s:****@%s' "${BASH_REMATCH[1]}" "${BASH_REMATCH[3]}"
  else
    printf '%s' "$url"
  fi
}

emit_json() {
  local json="$1"
  local output="${2-}"
  if [[ -z "$output" ]]; then
    mkdir -p out
    output="out/postgresql-crud-$(date -u +%Y%m%dT%H%M%SZ)-$$.json"
  else
    mkdir -p "$(dirname "$output")"
  fi
  printf '%s\n' "$json" >"$output"
  echo "Saved JSON to $output" >&2
  printf '%s\n' "$json"
}

parse_url_to_pg_vars() {
  local url="$1"
  [[ "$url" =~ ^postgres(ql)?://([^:/@]+)(:([^@]*))?@([^:/]+)(:([0-9]+))?/([^?]+) ]] || die "Unsupported PostgreSQL URL format. Prefer explicit --pg-* fields."
  PG_USER="${BASH_REMATCH[2]}"
  PG_PASSWORD="${BASH_REMATCH[4]-}"
  PG_HOST="${BASH_REMATCH[5]}"
  PG_PORT="${BASH_REMATCH[7]:-5432}"
  PG_DATABASE="${BASH_REMATCH[8]}"
}

pg_args() {
  if [[ -n "${URL:-}" && -z "${PG_HOST:-}" ]]; then
    parse_url_to_pg_vars "$URL"
  fi
  [[ -n "${PG_USER:-}" ]] || die "PostgreSQL user is missing in profile."
  [[ -n "${PG_DATABASE:-}" ]] || die "PostgreSQL database is missing in profile."
  PG_HOST="${PG_HOST:-127.0.0.1}"
  PG_PORT="${PG_PORT:-5432}"
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

tsv_to_json_rows() {
  local tsv="$1"
  local header
  header="$(printf '%s\n' "$tsv" | sed -n '1p')"
  if [[ -z "$header" ]]; then
    ROW_COUNT=0
    ROWS_JSON="[]"
    return
  fi
  local old_ifs="$IFS"
  IFS=$'\t'
  read -r -a cols <<<"$header"
  IFS="$old_ifs"
  local rows="[]"
  local count=0
  local line
  while IFS= read -r line; do
    [[ -n "$line" ]] || continue
    IFS=$'\t'
    read -r -a vals <<<"$line"
    IFS="$old_ifs"
    local obj="{"
    local i
    for ((i = 0; i < ${#cols[@]}; i++)); do
      [[ $i -gt 0 ]] && obj+=","
      obj+="\"$(json_escape "${cols[$i]}")\":"
      if [[ "${vals[$i]-}" == "\\N" ]]; then
        obj+="null"
      else
        obj+="\"$(json_escape "${vals[$i]-}")\""
      fi
    done
    obj+="}"
    if [[ "$rows" == "[]" ]]; then
      rows="[$obj]"
    else
      rows="${rows%]},$obj]"
    fi
    count=$((count + 1))
  done < <(printf '%s\n' "$tsv" | sed '1d')
  ROW_COUNT="$count"
  ROWS_JSON="$rows"
}

json_query_sql() {
  local sql="$1"
  sql="${sql%;}"
  printf "SELECT json_build_object('row_count', COUNT(*), 'rows', COALESCE(json_agg(row_to_json(_postgresql_crud_row)), '[]'::json)) FROM (%s) AS _postgresql_crud_row" "$sql"
}

run_local_pg() {
  local sql="$1"
  if [[ -z "${URL:-}" || -n "${PG_HOST:-}" ]]; then
    pg_args
  fi
  local tmp
  tmp="$(mktemp)"
  local status=0
  if [[ -n "${URL:-}" && -z "${PG_HOST:-}" ]]; then
    psql -X -q -v ON_ERROR_STOP=1 -A -F $'\t' "$URL" -c "$sql" >"$tmp" || status=$?
  else
    PGPASSWORD="${PG_PASSWORD:-}" psql -X -q -v ON_ERROR_STOP=1 -A -F $'\t' \
      -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DATABASE" \
      -c "$sql" >"$tmp" || status=$?
  fi
  if [[ $status -ne 0 ]]; then
    rm -f "$tmp"
    return "$status"
  fi
  PG_OUTPUT="$(sed '/^([0-9]\+ rows*)$/d;/^INSERT /d;/^UPDATE /d;/^DELETE /d' "$tmp")"
  rm -f "$tmp"
}

run_local_pg_json() {
  local sql
  sql="$(json_query_sql "$1")"
  if [[ -z "${URL:-}" || -n "${PG_HOST:-}" ]]; then
    pg_args
  fi
  local tmp
  tmp="$(mktemp)"
  local status=0
  if [[ -n "${URL:-}" && -z "${PG_HOST:-}" ]]; then
    psql -X -q -v ON_ERROR_STOP=1 -t -A "$URL" -c "$sql" >"$tmp" || status=$?
  else
    PGPASSWORD="${PG_PASSWORD:-}" psql -X -q -v ON_ERROR_STOP=1 -t -A \
      -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DATABASE" \
      -c "$sql" >"$tmp" || status=$?
  fi
  if [[ $status -ne 0 ]]; then
    rm -f "$tmp"
    return "$status"
  fi
  PG_RESULT_JSON="$(tr -d '\n' <"$tmp")"
  [[ -n "$PG_RESULT_JSON" ]] || PG_RESULT_JSON='{"row_count":0,"rows":[]}'
  rm -f "$tmp"
}

run_remote_pg() {
  local sql="$1"
  ssh_target_and_opts
  local remote_cmd="SQL=$(shell_quote "$sql")"
  remote_cmd+=" REMOTE_CWD=$(shell_quote "${REMOTE_CWD:-}")"
  remote_cmd+=" ENV_FILE=$(shell_quote "${ENV_FILE:-}")"
  remote_cmd+=" ENV_KEY=$(shell_quote "${ENV_KEY:-DATABASE_URL}")"
  remote_cmd+=" URL=$(shell_quote "${URL:-}")"
  remote_cmd+=" PG_HOST=$(shell_quote "${PG_HOST:-}")"
  remote_cmd+=" PG_PORT=$(shell_quote "${PG_PORT:-5432}")"
  remote_cmd+=" PG_DATABASE=$(shell_quote "${PG_DATABASE:-}")"
  remote_cmd+=" PG_USER=$(shell_quote "${PG_USER:-}")"
  remote_cmd+=" PG_PASSWORD=$(shell_quote "${PG_PASSWORD:-}")"
  remote_cmd+=" bash -s"

  local tmp
  tmp="$(mktemp)"
  local status=0
  ssh "${SSH_OPTS[@]}" "$SSH_TARGET" "$remote_cmd" >"$tmp" <<'REMOTE' || status=$?
set -euo pipefail

if [[ -n "${REMOTE_CWD:-}" ]]; then
  cd "$REMOTE_CWD"
fi

parse_url() {
  local url="$1"
  if [[ "$url" =~ ^postgres(ql)?://([^:/@]+)(:([^@]*))?@([^:/]+)(:([0-9]+))?/([^?]+) ]]; then
    PG_USER="${BASH_REMATCH[2]}"
    PG_PASSWORD="${BASH_REMATCH[4]-}"
    PG_HOST="${BASH_REMATCH[5]}"
    PG_PORT="${BASH_REMATCH[7]:-5432}"
    PG_DATABASE="${BASH_REMATCH[8]}"
  else
    echo "Unsupported PostgreSQL URL format in remote env." >&2
    exit 2
  fi
}

USE_URL=false
if [[ -z "${PG_HOST:-}" ]]; then
  if [[ -z "${URL:-}" ]]; then
    [[ -n "${ENV_FILE:-}" ]] || { echo "Missing ENV_FILE or URL." >&2; exit 2; }
    [[ -f "$ENV_FILE" ]] || { echo "Env file not found: $ENV_FILE" >&2; exit 2; }
    URL="$(grep -E "^${ENV_KEY:-DATABASE_URL}=" "$ENV_FILE" | tail -n 1 | sed 's/^[^=]*=//' | sed "s/^['\"]//;s/['\"]$//")"
  fi
  [[ -n "$URL" ]] || { echo "DATABASE_URL not found." >&2; exit 2; }
  USE_URL=true
fi

if [[ "$USE_URL" == "true" ]]; then
  psql -X -q -v ON_ERROR_STOP=1 -A -F $'\t' "$URL" \
    -c "$SQL" | sed '/^([0-9]\+ rows*)$/d;/^INSERT /d;/^UPDATE /d;/^DELETE /d'
else
  PG_HOST="${PG_HOST:-127.0.0.1}"
  PG_PORT="${PG_PORT:-5432}"
  PGPASSWORD="${PG_PASSWORD:-}" psql -X -q -v ON_ERROR_STOP=1 -A -F $'\t' \
    -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DATABASE" \
    -c "$SQL" | sed '/^([0-9]\+ rows*)$/d;/^INSERT /d;/^UPDATE /d;/^DELETE /d'
fi
REMOTE
  if [[ $status -ne 0 ]]; then
    rm -f "$tmp"
    return "$status"
  fi
  PG_OUTPUT="$(<"$tmp")"
  rm -f "$tmp"
}

run_remote_pg_json() {
  local sql
  sql="$(json_query_sql "$1")"
  ssh_target_and_opts
  local remote_cmd="SQL=$(shell_quote "$sql")"
  remote_cmd+=" REMOTE_CWD=$(shell_quote "${REMOTE_CWD:-}")"
  remote_cmd+=" ENV_FILE=$(shell_quote "${ENV_FILE:-}")"
  remote_cmd+=" ENV_KEY=$(shell_quote "${ENV_KEY:-DATABASE_URL}")"
  remote_cmd+=" URL=$(shell_quote "${URL:-}")"
  remote_cmd+=" PG_HOST=$(shell_quote "${PG_HOST:-}")"
  remote_cmd+=" PG_PORT=$(shell_quote "${PG_PORT:-5432}")"
  remote_cmd+=" PG_DATABASE=$(shell_quote "${PG_DATABASE:-}")"
  remote_cmd+=" PG_USER=$(shell_quote "${PG_USER:-}")"
  remote_cmd+=" PG_PASSWORD=$(shell_quote "${PG_PASSWORD:-}")"
  remote_cmd+=" bash -s"

  local tmp
  tmp="$(mktemp)"
  local status=0
  ssh "${SSH_OPTS[@]}" "$SSH_TARGET" "$remote_cmd" >"$tmp" <<'REMOTE' || status=$?
set -euo pipefail

if [[ -n "${REMOTE_CWD:-}" ]]; then
  cd "$REMOTE_CWD"
fi

parse_url() {
  local url="$1"
  if [[ "$url" =~ ^postgres(ql)?://([^:/@]+)(:([^@]*))?@([^:/]+)(:([0-9]+))?/([^?]+) ]]; then
    PG_USER="${BASH_REMATCH[2]}"
    PG_PASSWORD="${BASH_REMATCH[4]-}"
    PG_HOST="${BASH_REMATCH[5]}"
    PG_PORT="${BASH_REMATCH[7]:-5432}"
    PG_DATABASE="${BASH_REMATCH[8]}"
  else
    echo "Unsupported PostgreSQL URL format in remote env." >&2
    exit 2
  fi
}

USE_URL=false
if [[ -z "${PG_HOST:-}" ]]; then
  if [[ -z "${URL:-}" ]]; then
    [[ -n "${ENV_FILE:-}" ]] || { echo "Missing ENV_FILE or URL." >&2; exit 2; }
    [[ -f "$ENV_FILE" ]] || { echo "Env file not found: $ENV_FILE" >&2; exit 2; }
    URL="$(grep -E "^${ENV_KEY:-DATABASE_URL}=" "$ENV_FILE" | tail -n 1 | sed 's/^[^=]*=//' | sed "s/^['\"]//;s/['\"]$//")"
  fi
  [[ -n "$URL" ]] || { echo "DATABASE_URL not found." >&2; exit 2; }
  USE_URL=true
fi

if [[ "$USE_URL" == "true" ]]; then
  psql -X -q -v ON_ERROR_STOP=1 -t -A "$URL" -c "$SQL" | tr -d '\n'
else
  PG_HOST="${PG_HOST:-127.0.0.1}"
  PG_PORT="${PG_PORT:-5432}"
  PGPASSWORD="${PG_PASSWORD:-}" psql -X -q -v ON_ERROR_STOP=1 -t -A \
    -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DATABASE" \
    -c "$SQL" | tr -d '\n'
fi
REMOTE
  if [[ $status -ne 0 ]]; then
    rm -f "$tmp"
    return "$status"
  fi
  PG_RESULT_JSON="$(<"$tmp")"
  [[ -n "$PG_RESULT_JSON" ]] || PG_RESULT_JSON='{"row_count":0,"rows":[]}'
  rm -f "$tmp"
}

find_free_port() {
  local port
  for port in $(seq 43101 43200); do
    if ! (echo >/dev/tcp/127.0.0.1/"$port") >/dev/null 2>&1; then
      echo "$port"
      return
    fi
  done
  die "Could not find a free local tunnel port."
}

run_query() {
  local sql="$1"
  case "${MODE:-direct}" in
    direct)
      command -v psql >/dev/null 2>&1 || die "psql client is required for direct mode."
      run_local_pg "$sql"
      ;;
    ssh-remote)
      command -v ssh >/dev/null 2>&1 || die "ssh is required for ssh-remote mode."
      run_remote_pg "$sql"
      ;;
    ssh-tunnel)
      command -v ssh >/dev/null 2>&1 || die "ssh is required for ssh-tunnel mode."
      command -v psql >/dev/null 2>&1 || die "psql client is required for ssh-tunnel mode."
      pg_args
      ssh_target_and_opts
      local local_port
      local_port="$(find_free_port)"
      local ssh_err
      ssh_err="$(mktemp)"
      ssh -N -L "127.0.0.1:${local_port}:${PG_HOST}:${PG_PORT}" -o ExitOnForwardFailure=yes "${SSH_OPTS[@]}" "$SSH_TARGET" 2>"$ssh_err" &
      local tunnel_pid=$!
      trap 'kill "${tunnel_pid:-}" >/dev/null 2>&1 || true; rm -f "${ssh_err:-}"' RETURN
      local wait_seconds=10 waited=0
      while ! (echo >/dev/tcp/127.0.0.1/"$local_port") >/dev/null 2>&1; do
        if ! kill -0 "$tunnel_pid" >/dev/null 2>&1; then
          local err
          err="$(<"$ssh_err")"
          die "SSH tunnel failed: ${err:-unknown error}"
        fi
        if [[ "$waited" -ge "$wait_seconds" ]]; then
          die "SSH tunnel did not become ready within ${wait_seconds}s"
        fi
        sleep 0.5
        ((waited++))
      done
      PG_HOST="127.0.0.1" PG_PORT="$local_port" run_local_pg "$sql"
      ;;
    *)
      die "Unsupported mode: ${MODE:-}"
      ;;
  esac
}

run_json_query() {
  local sql="$1"
  case "${MODE:-direct}" in
    direct)
      command -v psql >/dev/null 2>&1 || die "psql client is required for direct mode."
      run_local_pg_json "$sql"
      ;;
    ssh-remote)
      command -v ssh >/dev/null 2>&1 || die "ssh is required for ssh-remote mode."
      run_remote_pg_json "$sql"
      ;;
    ssh-tunnel)
      command -v ssh >/dev/null 2>&1 || die "ssh is required for ssh-tunnel mode."
      command -v psql >/dev/null 2>&1 || die "psql client is required for ssh-tunnel mode."
      pg_args
      ssh_target_and_opts
      local local_port
      local_port="$(find_free_port)"
      local ssh_err
      ssh_err="$(mktemp)"
      ssh -N -L "127.0.0.1:${local_port}:${PG_HOST}:${PG_PORT}" -o ExitOnForwardFailure=yes "${SSH_OPTS[@]}" "$SSH_TARGET" 2>"$ssh_err" &
      local tunnel_pid=$!
      trap 'kill "${tunnel_pid:-}" >/dev/null 2>&1 || true; rm -f "${ssh_err:-}"' RETURN
      local wait_seconds=10 waited=0
      while ! (echo >/dev/tcp/127.0.0.1/"$local_port") >/dev/null 2>&1; do
        if ! kill -0 "$tunnel_pid" >/dev/null 2>&1; then
          local err
          err="$(<"$ssh_err")"
          die "SSH tunnel failed: ${err:-unknown error}"
        fi
        if [[ "$waited" -ge "$wait_seconds" ]]; then
          die "SSH tunnel did not become ready within ${wait_seconds}s"
        fi
        sleep 0.5
        ((waited++))
      done
      PG_HOST="127.0.0.1" PG_PORT="$local_port" run_local_pg_json "$sql"
      ;;
    *)
      die "Unsupported mode: ${MODE:-}"
      ;;
  esac
}

PARAM_ITEMS=()

parse_params() {
  PARAM_KEYS=()
  PARAM_VALUES=()
  local item key value
  for item in "${PARAM_ITEMS[@]:-}"; do
    [[ "$item" == *=* ]] || die "Expected key=value, got: $item"
    key="${item%%=*}"
    value="${item#*=}"
    PARAM_KEYS+=("$key")
    PARAM_VALUES+=("$value")
  done
}

param_value() {
  local key="$1"
  local i
  for ((i = 0; i < ${#PARAM_KEYS[@]}; i++)); do
    if [[ "${PARAM_KEYS[$i]}" == "$key" ]]; then
      printf '%s' "${PARAM_VALUES[$i]}"
      return
    fi
  done
  die "Missing --param for placeholder :$key"
}

render_placeholders() {
  local sql="$1"
  parse_params
  local key
  while [[ "$sql" =~ :([A-Za-z_][A-Za-z0-9_]*) ]]; do
    key="${BASH_REMATCH[1]}"
    sql="${sql/:$key/$(sql_literal "$(param_value "$key")")}"
  done
  printf '%s' "$sql"
}

readonly_guard() {
  if [[ "${READONLY:-false}" == "true" ]]; then
    die "This profile is readonly; insert, update, delete, and raw write SQL are blocked."
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
  [[ -n "${URL:-}" ]] && json+=",\"url\":$(json_string "$(redact_url "$URL")")"
  if [[ -n "${PG_HOST:-}${PG_DATABASE:-}${PG_USER:-}" ]]; then
    json+=",\"postgres\":{\"host\":$(json_string "${PG_HOST:-127.0.0.1}"),\"port\":${PG_PORT:-5432},\"database\":$(json_string "${PG_DATABASE:-}"),\"user\":$(json_string "${PG_USER:-}")"
    [[ -n "${PG_PASSWORD:-}" ]] && json+=",\"password\":\"****\""
    json+="}"
  fi
  json+="}"
  printf '%s' "$json"
}

cmd_configure() {
  local PROFILE="" MODE="" READONLY=false DEFAULT=false TEST_CONNECTION=false URL=""
  local SSH_ALIAS="" SSH_HOST="" SSH_USER="" SSH_KEY=""
  local REMOTE_CWD="" ENV_FILE="" ENV_KEY="DATABASE_URL"
  local PG_HOST="" PG_PORT="5432" PG_DATABASE="" PG_USER="" PG_PASSWORD=""
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
      --pg-host) PG_HOST="${2:-}"; shift 2 ;;
      --pg-port) PG_PORT="${2:-}"; shift 2 ;;
      --pg-database) PG_DATABASE="${2:-}"; shift 2 ;;
      --pg-user) PG_USER="${2:-}"; shift 2 ;;
      --pg-password) PG_PASSWORD="${2:-}"; shift 2 ;;
      --prompt-pg-password) read -r -s -p "PostgreSQL password: " PG_PASSWORD; echo >&2; shift ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown configure argument: $1" ;;
    esac
  done
  [[ -n "$PROFILE" ]] || die "Missing --profile"
  [[ "$MODE" =~ ^(direct|ssh-tunnel|ssh-remote)$ ]] || die "Missing or invalid --mode"
  if [[ "$MODE" == "direct" && -z "$URL$PG_HOST$PG_DATABASE$PG_USER" ]]; then
    die "direct mode requires --url or PostgreSQL connection fields."
  fi
  if [[ "$MODE" == "ssh-tunnel" ]]; then
    [[ -n "$SSH_ALIAS$SSH_HOST" ]] || die "ssh-tunnel requires --ssh-alias or --ssh-host."
    [[ -n "$PG_HOST$PG_DATABASE$PG_USER" ]] || die "ssh-tunnel requires PostgreSQL connection fields."
  fi
  if [[ "$MODE" == "ssh-remote" ]]; then
    [[ -n "$SSH_ALIAS$SSH_HOST" ]] || die "ssh-remote requires --ssh-alias or --ssh-host."
    [[ -n "$ENV_FILE$URL$PG_HOST$PG_DATABASE$PG_USER" ]] || die "ssh-remote requires --env-file, --url, or PostgreSQL connection fields."
  fi
  if [[ "$TEST_CONNECTION" == "true" ]]; then
    PROFILE_NAME="$PROFILE"
    run_json_query "SELECT 1 AS ok"
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
    write_kv PG_HOST "$PG_HOST"
    write_kv PG_PORT "$PG_PORT"
    write_kv PG_DATABASE "$PG_DATABASE"
    write_kv PG_USER "$PG_USER"
    write_kv PG_PASSWORD "$PG_PASSWORD"
  } >"$path"
  chmod 600 "$path"
  if [[ "$DEFAULT" == "true" || ! -f "$DEFAULT_FILE" ]]; then
    printf '%s\n' "$PROFILE" >"$DEFAULT_FILE"
    chmod 600 "$DEFAULT_FILE"
  fi
  local default_profile
  default_profile="$(<"$DEFAULT_FILE")"
  local json="{\"configured\":$(json_string "$PROFILE"),\"default_profile\":$(json_string "$default_profile"),\"profile\":$(profile_json "$PROFILE"),\"config_dir\":$(json_string "$CONFIG_DIR")}"
  emit_json "$json" "$OUTPUT"
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
  local default_profile=""
  if [[ -f "$DEFAULT_FILE" && "$(<"$DEFAULT_FILE")" == "$PROFILE" ]]; then
    local next=""
    shopt -s nullglob
    for path in "$PROFILE_DIR"/*.conf; do next="$(basename "$path" .conf)"; break; done
    printf '%s\n' "$next" >"$DEFAULT_FILE"
    default_profile="$next"
  elif [[ -f "$DEFAULT_FILE" ]]; then
    default_profile="$(<"$DEFAULT_FILE")"
  fi
  emit_json "{\"removed\":$(json_string "$PROFILE"),\"default_profile\":$(json_string "$default_profile")}" "$OUTPUT"
}

operation_json() {
  local operation="$1"
  local extra="$2"
  tsv_to_json_rows "$PG_OUTPUT"
  printf '{"profile":%s,"mode":%s,"operation":%s%s,"row_count":%s,"rows":%s}' \
    "$(json_string "$PROFILE_NAME")" "$(json_string "${MODE:-direct}")" "$(json_string "$operation")" "$extra" "$ROW_COUNT" "$ROWS_JSON"
}

operation_json_from_rows() {
  local operation="$1"
  local extra="$2"
  local result="${PG_RESULT_JSON:-{\"row_count\":0,\"rows\":[]}"
  result="${result#\{}"
  printf '{"profile":%s,"mode":%s,"operation":%s%s,%s' \
    "$(json_string "$PROFILE_NAME")" "$(json_string "${MODE:-direct}")" "$(json_string "$operation")" "$extra" "$result"
}

cmd_schema() {
  local PROFILE="" SCHEMA="public" TABLE="" ALL_SCHEMAS=false OUTPUT=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --schema) SCHEMA="${2:-}"; shift 2 ;;
      --all-schemas) ALL_SCHEMAS=true; shift ;;
      --table) TABLE="${2:-}"; shift 2 ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown schema argument: $1" ;;
    esac
  done
  load_profile "$PROFILE"
  local sql
  if [[ -n "$TABLE" ]]; then
    local schema_name
    local table_name
    schema_name="$(schema_for_table "$SCHEMA" "$TABLE")"
    table_name="$(name_for_table "$TABLE")"
    sql="SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_schema = $(sql_literal "$schema_name") AND table_name = $(sql_literal "$table_name") ORDER BY ordinal_position"
    run_json_query "$sql"
    emit_json "$(operation_json_from_rows schema ",\"schema\":$(json_string "$schema_name"),\"table\":$(json_string "$table_name")")" "$OUTPUT"
  else
    if [[ "$ALL_SCHEMAS" == "true" ]]; then
      sql="SELECT table_schema, table_name, table_type FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema') ORDER BY table_schema, table_name"
    else
      sql="SELECT table_schema, table_name, table_type FROM information_schema.tables WHERE table_schema = $(sql_literal "$SCHEMA") ORDER BY table_schema, table_name"
    fi
    run_json_query "$sql"
    emit_json "$(operation_json_from_rows schema ",\"schema\":$(json_string "$SCHEMA"),\"all_schemas\":${ALL_SCHEMAS}")" "$OUTPUT"
  fi
}

cmd_select() {
  local PROFILE="" SCHEMA="public" TABLE="" COLUMNS="*" WHERE="" LIMIT="50" ORDER_BY="" DESC=false OUTPUT=""
  PARAM_ITEMS=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --schema) SCHEMA="${2:-}"; shift 2 ;;
      --table) TABLE="${2:-}"; shift 2 ;;
      --columns) COLUMNS="${2:-}"; shift 2 ;;
      --where) WHERE="${2:-}"; shift 2 ;;
      --param) PARAM_ITEMS+=("${2:-}"); shift 2 ;;
      --limit) LIMIT="${2:-}"; shift 2 ;;
      --order-by) ORDER_BY="${2:-}"; shift 2 ;;
      --desc) DESC=true; shift ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown select argument: $1" ;;
    esac
  done
  [[ -n "$TABLE" ]] || die "Missing --table"
  load_profile "$PROFILE"
  local col_sql="*"
  if [[ "$COLUMNS" != "*" ]]; then
    col_sql=""
    local old_ifs="$IFS" col
    IFS=,
    read -r -a col_parts <<<"$COLUMNS"
    IFS="$old_ifs"
    for col in "${col_parts[@]}"; do
      col="${col// /}"
      [[ -n "$col_sql" ]] && col_sql+=", "
      col_sql+="$(quote_ident "$col")"
    done
  fi
  local table_sql
  table_sql="$(qualify_table "$SCHEMA" "$TABLE")"
  local sql="SELECT ${col_sql} FROM ${table_sql}"
  [[ -n "$WHERE" ]] && sql+=" WHERE $(render_placeholders "$WHERE")"
  [[ -n "$ORDER_BY" ]] && sql+=" ORDER BY $(quote_ident "$ORDER_BY")"
  [[ "$DESC" == "true" ]] && sql+=" DESC"
  [[ -n "$LIMIT" ]] && sql+=" LIMIT $LIMIT"
  run_json_query "$sql"
  emit_json "$(operation_json_from_rows select ",\"schema\":$(json_string "$(schema_for_table "$SCHEMA" "$TABLE")"),\"table\":$(json_string "$(name_for_table "$TABLE")"),\"sql\":$(json_string "$sql")")" "$OUTPUT"
}

cmd_insert() {
  local PROFILE="" SCHEMA="public" TABLE="" EXECUTE=false OUTPUT=""
  local VALUES=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --schema) SCHEMA="${2:-}"; shift 2 ;;
      --table) TABLE="${2:-}"; shift 2 ;;
      --value) VALUES+=("${2:-}"); shift 2 ;;
      --execute) EXECUTE=true; shift ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown insert argument: $1" ;;
    esac
  done
  [[ -n "$TABLE" ]] || die "Missing --table"
  [[ ${#VALUES[@]} -gt 0 ]] || die "insert requires --value"
  load_profile "$PROFILE"
  readonly_guard
  local cols="" vals="" item key value first=true values_json="{"
  for item in "${VALUES[@]}"; do
    [[ "$item" == *=* ]] || die "Expected key=value, got: $item"
    key="${item%%=*}"; value="${item#*=}"
    [[ "$first" == false ]] && cols+=", " && vals+=", " && values_json+=","
    cols+="$(quote_ident "$key")"
    vals+="$(sql_literal "$value")"
    values_json+="\"$(json_escape "$key")\":$(json_string "$value")"
    first=false
  done
  values_json+="}"
  local table_sql
  table_sql="$(qualify_table "$SCHEMA" "$TABLE")"
  local sql="INSERT INTO ${table_sql} (${cols}) VALUES (${vals})"
  if [[ "$EXECUTE" != "true" ]]; then
    emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "$MODE"),\"operation\":\"insert\",\"dry_run\":true,\"schema\":$(json_string "$(schema_for_table "$SCHEMA" "$TABLE")"),\"table\":$(json_string "$(name_for_table "$TABLE")"),\"values\":${values_json},\"sql\":$(json_string "$sql"),\"message\":\"Pass --execute only after user confirmation.\"}" "$OUTPUT"
    return
  fi
  run_query "$sql"
  emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "$MODE"),\"operation\":\"insert\",\"dry_run\":false,\"schema\":$(json_string "$(schema_for_table "$SCHEMA" "$TABLE")"),\"table\":$(json_string "$(name_for_table "$TABLE")"),\"sql\":$(json_string "$sql")}" "$OUTPUT"
}

cmd_update() {
  local PROFILE="" SCHEMA="public" TABLE="" WHERE="" EXECUTE=false OUTPUT="" PREVIEW_LIMIT=20 ALLOW_FULL_TABLE=false
  local SETS=()
  PARAM_ITEMS=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --schema) SCHEMA="${2:-}"; shift 2 ;;
      --table) TABLE="${2:-}"; shift 2 ;;
      --set) SETS+=("${2:-}"); shift 2 ;;
      --where) WHERE="${2:-}"; shift 2 ;;
      --param) PARAM_ITEMS+=("${2:-}"); shift 2 ;;
      --preview-limit) PREVIEW_LIMIT="${2:-}"; shift 2 ;;
      --allow-full-table) ALLOW_FULL_TABLE=true; shift ;;
      --execute) EXECUTE=true; shift ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown update argument: $1" ;;
    esac
  done
  [[ -n "$TABLE" ]] || die "Missing --table"
  [[ ${#SETS[@]} -gt 0 ]] || die "update requires --set"
  [[ -n "$WHERE" || "$ALLOW_FULL_TABLE" == "true" ]] || die "update requires --where. Pass --allow-full-table only after explicit user confirmation."
  load_profile "$PROFILE"
  readonly_guard
  local set_sql="" set_json="{" first=true item key value
  for item in "${SETS[@]}"; do
    [[ "$item" == *=* ]] || die "Expected key=value, got: $item"
    key="${item%%=*}"; value="${item#*=}"
    [[ "$first" == false ]] && set_sql+=", " && set_json+=","
    set_sql+="$(quote_ident "$key") = $(sql_literal "$value")"
    set_json+="\"$(json_escape "$key")\":$(json_string "$value")"
    first=false
  done
  set_json+="}"
  local where_sql=""
  [[ -n "$WHERE" ]] && where_sql="$(render_placeholders "$WHERE")"
  local table_sql
  table_sql="$(qualify_table "$SCHEMA" "$TABLE")"
  local sql="UPDATE ${table_sql} SET ${set_sql}"
  [[ -n "$where_sql" ]] && sql+=" WHERE ${where_sql}"
  if [[ "$EXECUTE" != "true" ]]; then
    local preview_sql="SELECT * FROM ${table_sql}"
    [[ -n "$where_sql" ]] && preview_sql+=" WHERE ${where_sql}"
    preview_sql+=" LIMIT ${PREVIEW_LIMIT}"
    run_json_query "$preview_sql"
    emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "$MODE"),\"operation\":\"update\",\"dry_run\":true,\"schema\":$(json_string "$(schema_for_table "$SCHEMA" "$TABLE")"),\"table\":$(json_string "$(name_for_table "$TABLE")"),\"would_set\":${set_json},\"sql\":$(json_string "$sql"),\"preview\":${PG_RESULT_JSON},\"message\":\"Pass --execute only after user confirmation.\"}" "$OUTPUT"
    return
  fi
  run_query "$sql"
  emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "$MODE"),\"operation\":\"update\",\"dry_run\":false,\"schema\":$(json_string "$(schema_for_table "$SCHEMA" "$TABLE")"),\"table\":$(json_string "$(name_for_table "$TABLE")"),\"sql\":$(json_string "$sql")}" "$OUTPUT"
}

cmd_delete() {
  local PROFILE="" SCHEMA="public" TABLE="" WHERE="" EXECUTE=false OUTPUT="" PREVIEW_LIMIT=20 ALLOW_FULL_TABLE=false
  PARAM_ITEMS=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --schema) SCHEMA="${2:-}"; shift 2 ;;
      --table) TABLE="${2:-}"; shift 2 ;;
      --where) WHERE="${2:-}"; shift 2 ;;
      --param) PARAM_ITEMS+=("${2:-}"); shift 2 ;;
      --preview-limit) PREVIEW_LIMIT="${2:-}"; shift 2 ;;
      --allow-full-table) ALLOW_FULL_TABLE=true; shift ;;
      --execute) EXECUTE=true; shift ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown delete argument: $1" ;;
    esac
  done
  [[ -n "$TABLE" ]] || die "Missing --table"
  [[ -n "$WHERE" || "$ALLOW_FULL_TABLE" == "true" ]] || die "delete requires --where. Pass --allow-full-table only after explicit user confirmation."
  load_profile "$PROFILE"
  readonly_guard
  local where_sql=""
  [[ -n "$WHERE" ]] && where_sql="$(render_placeholders "$WHERE")"
  local table_sql
  table_sql="$(qualify_table "$SCHEMA" "$TABLE")"
  local sql="DELETE FROM ${table_sql}"
  [[ -n "$where_sql" ]] && sql+=" WHERE ${where_sql}"
  if [[ "$EXECUTE" != "true" ]]; then
    local preview_sql="SELECT * FROM ${table_sql}"
    [[ -n "$where_sql" ]] && preview_sql+=" WHERE ${where_sql}"
    preview_sql+=" LIMIT ${PREVIEW_LIMIT}"
    run_json_query "$preview_sql"
    emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "$MODE"),\"operation\":\"delete\",\"dry_run\":true,\"schema\":$(json_string "$(schema_for_table "$SCHEMA" "$TABLE")"),\"table\":$(json_string "$(name_for_table "$TABLE")"),\"sql\":$(json_string "$sql"),\"preview\":${PG_RESULT_JSON},\"message\":\"Pass --execute only after user confirmation.\"}" "$OUTPUT"
    return
  fi
  run_query "$sql"
  emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "$MODE"),\"operation\":\"delete\",\"dry_run\":false,\"schema\":$(json_string "$(schema_for_table "$SCHEMA" "$TABLE")"),\"table\":$(json_string "$(name_for_table "$TABLE")"),\"sql\":$(json_string "$sql")}" "$OUTPUT"
}

is_read_sql() {
  local sql
  sql="$(printf '%s' "$1" | sed 's/^[[:space:]]*//;s/(//')"
  [[ "$sql" =~ ^([Ss][Ee][Ll][Ee][Cc][Tt]|[Ss][Hh][Oo][Ww]|[Dd][Ee][Ss][Cc][Rr][Ii][Bb][Ee]|[Ee][Xx][Pp][Ll][Aa][Ii][Nn]) ]]
}

is_json_wrappable_read_sql() {
  local sql
  sql="$(printf '%s' "$1" | sed 's/^[[:space:]]*//;s/(//')"
  [[ "$sql" =~ ^([Ss][Ee][Ll][Ee][Cc][Tt]) ]]
}

cmd_raw_sql() {
  local PROFILE="" SQL="" EXECUTE=false ALLOW_RAW_WRITE=false OUTPUT=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --sql) SQL="${2:-}"; shift 2 ;;
      --execute) EXECUTE=true; shift ;;
      --allow-raw-write) ALLOW_RAW_WRITE=true; shift ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown raw-sql argument: $1" ;;
    esac
  done
  [[ -n "$SQL" ]] || die "Missing --sql"
  load_profile "$PROFILE"
  if ! is_read_sql "$SQL"; then
    readonly_guard
    if [[ "$EXECUTE" != "true" || "$ALLOW_RAW_WRITE" != "true" ]]; then
      emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "$MODE"),\"operation\":\"raw-sql\",\"dry_run\":true,\"sql\":$(json_string "$SQL"),\"message\":\"Raw write SQL was not executed. Pass both --execute and --allow-raw-write only after user confirmation.\"}" "$OUTPUT"
      return
    fi
  fi
  if is_json_wrappable_read_sql "$SQL"; then
    run_json_query "$SQL"
    emit_json "$(operation_json_from_rows raw-sql ",\"sql\":$(json_string "$SQL")")" "$OUTPUT"
  else
    run_query "$SQL"
    emit_json "$(operation_json raw-sql ",\"sql\":$(json_string "$SQL")")" "$OUTPUT"
  fi
}

main() {
  [[ $# -gt 0 ]] || { usage; exit 0; }
  local cmd="$1"
  shift
  case "$cmd" in
    configure) cmd_configure "$@" ;;
    list-profiles) cmd_list_profiles "$@" ;;
    remove-profile) cmd_remove_profile "$@" ;;
    schema) cmd_schema "$@" ;;
    select) cmd_select "$@" ;;
    insert) cmd_insert "$@" ;;
    update) cmd_update "$@" ;;
    delete) cmd_delete "$@" ;;
    raw-sql) cmd_raw_sql "$@" ;;
    -h|--help|help) usage ;;
    *) die "Unknown command: $cmd" ;;
  esac
}

main "$@"
