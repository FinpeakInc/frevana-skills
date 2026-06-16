#!/usr/bin/env bash

set -euo pipefail

CONFIG_DIR="${HOME}/.config/mysql-crud"
PROFILE_DIR="${CONFIG_DIR}/profiles"
DEFAULT_FILE="${CONFIG_DIR}/default_profile"

usage() {
  cat <<'EOF'
Usage:
  mysql_crud.sh configure --profile NAME --mode direct|ssh-tunnel|ssh-remote [options]
  mysql_crud.sh list-profiles [--output PATH]
  mysql_crud.sh remove-profile --profile NAME [--output PATH]
  mysql_crud.sh schema [--profile NAME] [--table TABLE] [--output PATH]
  mysql_crud.sh select [--profile NAME] --table TABLE [--columns c1,c2] [--where "id = :id"] [--param id=1] [--limit 50] [--output PATH]
  mysql_crud.sh insert [--profile NAME] --table TABLE --value col=value [--execute] [--output PATH]
  mysql_crud.sh update [--profile NAME] --table TABLE --set col=value --where "id = :id" [--param id=1] [--execute] [--output PATH]
  mysql_crud.sh delete [--profile NAME] --table TABLE --where "id = :id" [--param id=1] [--execute] [--output PATH]
  mysql_crud.sh raw-sql [--profile NAME] --sql "SELECT 1" [--execute] [--output PATH]

Common configure options:
  --readonly
  --default
  --url mysql://user:password@host:3306/database
  --mysql-host HOST --mysql-port 3306 --mysql-database DB --mysql-user USER [--mysql-password PASS]
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
    if [[ -z "$out" ]]; then
      out="\`${part}\`"
    else
      out="${out}.\`${part}\`"
    fi
  done
  printf '%s' "$out"
}

sql_literal() {
  local s="${1-}"
  s=${s//\\/\\\\}
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
    output="out/mysql-crud-$(date -u +%Y%m%dT%H%M%SZ)-$$.json"
  else
    mkdir -p "$(dirname "$output")"
  fi
  printf '%s\n' "$json" >"$output"
  echo "Saved JSON to $output" >&2
  printf '%s\n' "$json"
}

parse_url_to_mysql_vars() {
  local url="$1"
  [[ "$url" =~ ^mysql://([^:/@]+)(:([^@]*))?@([^:/]+)(:([0-9]+))?/([^?]+) ]] || die "Unsupported MySQL URL format. Prefer explicit --mysql-* fields."
  MYSQL_USER="${BASH_REMATCH[1]}"
  MYSQL_PASSWORD="${BASH_REMATCH[3]-}"
  MYSQL_HOST="${BASH_REMATCH[4]}"
  MYSQL_PORT="${BASH_REMATCH[6]:-3306}"
  MYSQL_DATABASE="${BASH_REMATCH[7]}"
}

mysql_args() {
  if [[ -n "${URL:-}" && -z "${MYSQL_HOST:-}" ]]; then
    parse_url_to_mysql_vars "$URL"
  fi
  [[ -n "${MYSQL_USER:-}" ]] || die "MySQL user is missing in profile."
  [[ -n "${MYSQL_DATABASE:-}" ]] || die "MySQL database is missing in profile."
  MYSQL_HOST="${MYSQL_HOST:-127.0.0.1}"
  MYSQL_PORT="${MYSQL_PORT:-3306}"
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
      if [[ "${vals[$i]-}" == "NULL" ]]; then
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

run_local_mysql() {
  local sql="$1"
  mysql_args
  local tmp
  tmp="$(mktemp)"
  local status=0
  MYSQL_PWD="${MYSQL_PASSWORD:-}" mysql --batch --raw --default-character-set=utf8mb4 \
    -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u "$MYSQL_USER" "$MYSQL_DATABASE" \
    -e "$sql" >"$tmp" || status=$?
  if [[ $status -ne 0 ]]; then
    rm -f "$tmp"
    return "$status"
  fi
  MYSQL_OUTPUT="$(<"$tmp")"
  rm -f "$tmp"
}

run_remote_mysql() {
  local sql="$1"
  ssh_target_and_opts
  local remote_cmd="SQL=$(shell_quote "$sql")"
  remote_cmd+=" REMOTE_CWD=$(shell_quote "${REMOTE_CWD:-}")"
  remote_cmd+=" ENV_FILE=$(shell_quote "${ENV_FILE:-}")"
  remote_cmd+=" ENV_KEY=$(shell_quote "${ENV_KEY:-DATABASE_URL}")"
  remote_cmd+=" URL=$(shell_quote "${URL:-}")"
  remote_cmd+=" MYSQL_HOST=$(shell_quote "${MYSQL_HOST:-}")"
  remote_cmd+=" MYSQL_PORT=$(shell_quote "${MYSQL_PORT:-3306}")"
  remote_cmd+=" MYSQL_DATABASE=$(shell_quote "${MYSQL_DATABASE:-}")"
  remote_cmd+=" MYSQL_USER=$(shell_quote "${MYSQL_USER:-}")"
  remote_cmd+=" MYSQL_PASSWORD=$(shell_quote "${MYSQL_PASSWORD:-}")"
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
  if [[ "$url" =~ ^mysql://([^:/@]+)(:([^@]*))?@([^:/]+)(:([0-9]+))?/([^?]+) ]]; then
    MYSQL_USER="${BASH_REMATCH[1]}"
    MYSQL_PASSWORD="${BASH_REMATCH[3]-}"
    MYSQL_HOST="${BASH_REMATCH[4]}"
    MYSQL_PORT="${BASH_REMATCH[6]:-3306}"
    MYSQL_DATABASE="${BASH_REMATCH[7]}"
  else
    echo "Unsupported MySQL URL format in remote env." >&2
    exit 2
  fi
}

if [[ -z "${MYSQL_HOST:-}" ]]; then
  if [[ -z "${URL:-}" ]]; then
    [[ -n "${ENV_FILE:-}" ]] || { echo "Missing ENV_FILE or URL." >&2; exit 2; }
    [[ -f "$ENV_FILE" ]] || { echo "Env file not found: $ENV_FILE" >&2; exit 2; }
    URL="$(grep -E "^${ENV_KEY:-DATABASE_URL}=" "$ENV_FILE" | tail -n 1 | sed 's/^[^=]*=//' | sed "s/^['\"]//;s/['\"]$//")"
  fi
  [[ -n "$URL" ]] || { echo "DATABASE_URL not found." >&2; exit 2; }
  parse_url "$URL"
fi

MYSQL_HOST="${MYSQL_HOST:-127.0.0.1}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
MYSQL_PWD="${MYSQL_PASSWORD:-}" mysql --batch --raw --default-character-set=utf8mb4 \
  -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u "$MYSQL_USER" "$MYSQL_DATABASE" \
  -e "$SQL"
REMOTE
  if [[ $status -ne 0 ]]; then
    rm -f "$tmp"
    return "$status"
  fi
  MYSQL_OUTPUT="$(<"$tmp")"
  rm -f "$tmp"
}

run_query() {
  local sql="$1"
  case "${MODE:-direct}" in
    direct)
      command -v mysql >/dev/null 2>&1 || die "mysql client is required for direct mode."
      run_local_mysql "$sql"
      ;;
    ssh-remote)
      command -v ssh >/dev/null 2>&1 || die "ssh is required for ssh-remote mode."
      run_remote_mysql "$sql"
      ;;
    ssh-tunnel)
      command -v ssh >/dev/null 2>&1 || die "ssh is required for ssh-tunnel mode."
      command -v mysql >/dev/null 2>&1 || die "mysql client is required for ssh-tunnel mode."
      mysql_args
      ssh_target_and_opts
      local local_port
      local_port="$(find_free_port)"
      ssh -N -L "127.0.0.1:${local_port}:${MYSQL_HOST}:${MYSQL_PORT}" -o ExitOnForwardFailure=yes "${SSH_OPTS[@]}" "$SSH_TARGET" &
      local tunnel_pid=$!
      trap 'kill "$tunnel_pid" >/dev/null 2>&1 || true' RETURN
      sleep 1
      MYSQL_HOST="127.0.0.1" MYSQL_PORT="$local_port" run_local_mysql "$sql"
      ;;
    *)
      die "Unsupported mode: ${MODE:-}"
      ;;
  esac
}

find_free_port() {
  local port
  for port in $(seq 43000 43100); do
    if ! (echo >/dev/tcp/127.0.0.1/"$port") >/dev/null 2>&1; then
      echo "$port"
      return
    fi
  done
  die "Could not find a free local tunnel port."
}

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
  local op="$1"
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
  if [[ -n "${MYSQL_HOST:-}${MYSQL_DATABASE:-}${MYSQL_USER:-}" ]]; then
    json+=",\"mysql\":{\"host\":$(json_string "${MYSQL_HOST:-127.0.0.1}"),\"port\":${MYSQL_PORT:-3306},\"database\":$(json_string "${MYSQL_DATABASE:-}"),\"user\":$(json_string "${MYSQL_USER:-}")"
    [[ -n "${MYSQL_PASSWORD:-}" ]] && json+=",\"password\":\"****\""
    json+="}"
  fi
  json+="}"
  printf '%s' "$json"
}

cmd_configure() {
  local PROFILE="" MODE="" READONLY=false DEFAULT=false URL=""
  local SSH_ALIAS="" SSH_HOST="" SSH_USER="" SSH_KEY=""
  local REMOTE_CWD="" ENV_FILE="" ENV_KEY="DATABASE_URL"
  local MYSQL_HOST="" MYSQL_PORT="3306" MYSQL_DATABASE="" MYSQL_USER="" MYSQL_PASSWORD=""
  local OUTPUT=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --mode) MODE="${2:-}"; shift 2 ;;
      --readonly) READONLY=true; shift ;;
      --default) DEFAULT=true; shift ;;
      --url) URL="${2:-}"; shift 2 ;;
      --ssh-alias) SSH_ALIAS="${2:-}"; shift 2 ;;
      --ssh-host) SSH_HOST="${2:-}"; shift 2 ;;
      --ssh-user) SSH_USER="${2:-}"; shift 2 ;;
      --ssh-key) SSH_KEY="${2:-}"; shift 2 ;;
      --remote-cwd) REMOTE_CWD="${2:-}"; shift 2 ;;
      --env-file) ENV_FILE="${2:-}"; shift 2 ;;
      --env-key) ENV_KEY="${2:-}"; shift 2 ;;
      --mysql-host) MYSQL_HOST="${2:-}"; shift 2 ;;
      --mysql-port) MYSQL_PORT="${2:-}"; shift 2 ;;
      --mysql-database) MYSQL_DATABASE="${2:-}"; shift 2 ;;
      --mysql-user) MYSQL_USER="${2:-}"; shift 2 ;;
      --mysql-password) MYSQL_PASSWORD="${2:-}"; shift 2 ;;
      --prompt-mysql-password) read -r -s -p "MySQL password: " MYSQL_PASSWORD; echo >&2; shift ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown configure argument: $1" ;;
    esac
  done
  [[ -n "$PROFILE" ]] || die "Missing --profile"
  [[ "$MODE" =~ ^(direct|ssh-tunnel|ssh-remote)$ ]] || die "Missing or invalid --mode"
  if [[ "$MODE" == "direct" && -z "$URL$MYSQL_HOST$MYSQL_DATABASE$MYSQL_USER" ]]; then
    die "direct mode requires --url or mysql connection fields."
  fi
  if [[ "$MODE" == "ssh-tunnel" ]]; then
    [[ -n "$SSH_ALIAS$SSH_HOST" ]] || die "ssh-tunnel requires --ssh-alias or --ssh-host."
    [[ -n "$MYSQL_HOST$MYSQL_DATABASE$MYSQL_USER" ]] || die "ssh-tunnel requires mysql connection fields."
  fi
  if [[ "$MODE" == "ssh-remote" ]]; then
    [[ -n "$SSH_ALIAS$SSH_HOST" ]] || die "ssh-remote requires --ssh-alias or --ssh-host."
    [[ -n "$ENV_FILE$URL$MYSQL_HOST$MYSQL_DATABASE$MYSQL_USER" ]] || die "ssh-remote requires --env-file, --url, or mysql connection fields."
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
    write_kv MYSQL_HOST "$MYSQL_HOST"
    write_kv MYSQL_PORT "$MYSQL_PORT"
    write_kv MYSQL_DATABASE "$MYSQL_DATABASE"
    write_kv MYSQL_USER "$MYSQL_USER"
    write_kv MYSQL_PASSWORD "$MYSQL_PASSWORD"
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
  tsv_to_json_rows "$MYSQL_OUTPUT"
  printf '{"profile":%s,"mode":%s,"operation":%s%s,"row_count":%s,"rows":%s}' \
    "$(json_string "$PROFILE_NAME")" "$(json_string "${MODE:-direct}")" "$(json_string "$operation")" "$extra" "$ROW_COUNT" "$ROWS_JSON"
}

cmd_schema() {
  local PROFILE="" TABLE="" OUTPUT=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --table) TABLE="${2:-}"; shift 2 ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown schema argument: $1" ;;
    esac
  done
  load_profile "$PROFILE"
  local sql
  if [[ -n "$TABLE" ]]; then
    sql="SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY, COLUMN_DEFAULT, EXTRA FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = $(sql_literal "$TABLE") ORDER BY ORDINAL_POSITION"
    run_query "$sql"
    emit_json "$(operation_json schema ",\"table\":$(json_string "$TABLE")")" "$OUTPUT"
  else
    sql="SELECT TABLE_NAME, TABLE_TYPE FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() ORDER BY TABLE_NAME"
    run_query "$sql"
    emit_json "$(operation_json schema "")" "$OUTPUT"
  fi
}

cmd_select() {
  local PROFILE="" TABLE="" COLUMNS="*" WHERE="" LIMIT="50" ORDER_BY="" DESC=false OUTPUT=""
  PARAM_ITEMS=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
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
  local sql="SELECT ${col_sql} FROM $(quote_ident "$TABLE")"
  [[ -n "$WHERE" ]] && sql+=" WHERE $(render_placeholders "$WHERE")"
  [[ -n "$ORDER_BY" ]] && sql+=" ORDER BY $(quote_ident "$ORDER_BY")"
  [[ "$DESC" == "true" ]] && sql+=" DESC"
  [[ -n "$LIMIT" ]] && sql+=" LIMIT $LIMIT"
  run_query "$sql"
  emit_json "$(operation_json select ",\"table\":$(json_string "$TABLE"),\"sql\":$(json_string "$sql")")" "$OUTPUT"
}

cmd_insert() {
  local PROFILE="" TABLE="" EXECUTE=false OUTPUT=""
  local VALUES=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
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
  readonly_guard insert
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
  local sql="INSERT INTO $(quote_ident "$TABLE") (${cols}) VALUES (${vals})"
  if [[ "$EXECUTE" != "true" ]]; then
    emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "$MODE"),\"operation\":\"insert\",\"dry_run\":true,\"table\":$(json_string "$TABLE"),\"values\":${values_json},\"sql\":$(json_string "$sql"),\"message\":\"Pass --execute only after user confirmation.\"}" "$OUTPUT"
    return
  fi
  run_query "$sql"
  emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "$MODE"),\"operation\":\"insert\",\"dry_run\":false,\"table\":$(json_string "$TABLE"),\"sql\":$(json_string "$sql")}" "$OUTPUT"
}

cmd_update() {
  local PROFILE="" TABLE="" WHERE="" EXECUTE=false OUTPUT="" PREVIEW_LIMIT=20 ALLOW_FULL_TABLE=false
  local SETS=()
  PARAM_ITEMS=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
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
  readonly_guard update
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
  local sql="UPDATE $(quote_ident "$TABLE") SET ${set_sql}"
  [[ -n "$where_sql" ]] && sql+=" WHERE ${where_sql}"
  if [[ "$EXECUTE" != "true" ]]; then
    local preview_sql="SELECT * FROM $(quote_ident "$TABLE")"
    [[ -n "$where_sql" ]] && preview_sql+=" WHERE ${where_sql}"
    preview_sql+=" LIMIT ${PREVIEW_LIMIT}"
    run_query "$preview_sql"
    tsv_to_json_rows "$MYSQL_OUTPUT"
    emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "$MODE"),\"operation\":\"update\",\"dry_run\":true,\"table\":$(json_string "$TABLE"),\"would_set\":${set_json},\"sql\":$(json_string "$sql"),\"preview\":{\"row_count\":${ROW_COUNT},\"rows\":${ROWS_JSON}},\"message\":\"Pass --execute only after user confirmation.\"}" "$OUTPUT"
    return
  fi
  run_query "$sql"
  emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "$MODE"),\"operation\":\"update\",\"dry_run\":false,\"table\":$(json_string "$TABLE"),\"sql\":$(json_string "$sql")}" "$OUTPUT"
}

cmd_delete() {
  local PROFILE="" TABLE="" WHERE="" EXECUTE=false OUTPUT="" PREVIEW_LIMIT=20 ALLOW_FULL_TABLE=false
  PARAM_ITEMS=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
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
  readonly_guard delete
  local where_sql=""
  [[ -n "$WHERE" ]] && where_sql="$(render_placeholders "$WHERE")"
  local sql="DELETE FROM $(quote_ident "$TABLE")"
  [[ -n "$where_sql" ]] && sql+=" WHERE ${where_sql}"
  if [[ "$EXECUTE" != "true" ]]; then
    local preview_sql="SELECT * FROM $(quote_ident "$TABLE")"
    [[ -n "$where_sql" ]] && preview_sql+=" WHERE ${where_sql}"
    preview_sql+=" LIMIT ${PREVIEW_LIMIT}"
    run_query "$preview_sql"
    tsv_to_json_rows "$MYSQL_OUTPUT"
    emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "$MODE"),\"operation\":\"delete\",\"dry_run\":true,\"table\":$(json_string "$TABLE"),\"sql\":$(json_string "$sql"),\"preview\":{\"row_count\":${ROW_COUNT},\"rows\":${ROWS_JSON}},\"message\":\"Pass --execute only after user confirmation.\"}" "$OUTPUT"
    return
  fi
  run_query "$sql"
  emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "$MODE"),\"operation\":\"delete\",\"dry_run\":false,\"table\":$(json_string "$TABLE"),\"sql\":$(json_string "$sql")}" "$OUTPUT"
}

is_read_sql() {
  local sql
  sql="$(printf '%s' "$1" | sed 's/^[[:space:]]*//;s/(//')"
  [[ "$sql" =~ ^([Ss][Ee][Ll][Ee][Cc][Tt]|[Ss][Hh][Oo][Ww]|[Dd][Ee][Ss][Cc][Rr][Ii][Bb][Ee]|[Dd][Ee][Ss][Cc]|[Ee][Xx][Pp][Ll][Aa][Ii][Nn]|[Ww][Ii][Tt][Hh]) ]]
}

cmd_raw_sql() {
  local PROFILE="" SQL="" EXECUTE=false OUTPUT=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --sql) SQL="${2:-}"; shift 2 ;;
      --execute) EXECUTE=true; shift ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown raw-sql argument: $1" ;;
    esac
  done
  [[ -n "$SQL" ]] || die "Missing --sql"
  load_profile "$PROFILE"
  if ! is_read_sql "$SQL"; then
    readonly_guard raw-sql
    if [[ "$EXECUTE" != "true" ]]; then
      emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"mode\":$(json_string "$MODE"),\"operation\":\"raw-sql\",\"dry_run\":true,\"sql\":$(json_string "$SQL"),\"message\":\"Raw write SQL was not executed. Pass --execute only after user confirmation.\"}" "$OUTPUT"
      return
    fi
  fi
  run_query "$SQL"
  emit_json "$(operation_json raw-sql ",\"sql\":$(json_string "$SQL")")" "$OUTPUT"
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
