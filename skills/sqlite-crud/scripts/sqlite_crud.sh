#!/usr/bin/env bash

set -euo pipefail

CONFIG_DIR="${HOME}/.config/sqlite-crud"
PROFILE_DIR="${CONFIG_DIR}/profiles"
DEFAULT_FILE="${CONFIG_DIR}/default_profile"

usage() {
  cat <<'EOF'
Usage:
  sqlite_crud.sh configure --profile NAME --path DB_FILE [--readonly] [--default] [--test-connection] [--output PATH]
  sqlite_crud.sh list-profiles [--output PATH]
  sqlite_crud.sh remove-profile --profile NAME [--output PATH]
  sqlite_crud.sh schema [--profile NAME | --path DB_FILE] [--table TABLE] [--output PATH]
  sqlite_crud.sh select [--profile NAME | --path DB_FILE] --table TABLE [--columns COLUMNS] [--where SQL] [--param name=value ...] [--order-by COLUMN] [--desc] [--limit N] [--output PATH]
  sqlite_crud.sh insert [--profile NAME | --path DB_FILE] --table TABLE --value column=value [--value column=value ...] [--readonly] [--execute] [--output PATH]
  sqlite_crud.sh update [--profile NAME | --path DB_FILE] --table TABLE --value column=value [--value column=value ...] [--where SQL] [--param name=value ...] [--allow-full-table] [--readonly] [--execute] [--output PATH]
  sqlite_crud.sh delete [--profile NAME | --path DB_FILE] --table TABLE [--where SQL] [--param name=value ...] [--allow-full-table] [--readonly] [--execute] [--output PATH]
  sqlite_crud.sh raw-sql [--profile NAME | --path DB_FILE] --sql SQL [--readonly] [--execute] [--allow-raw-write] [--output PATH]

Only local SQLite database file paths are supported.
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
  [[ -n "${DB_PATH:-}" ]] || die "Profile is missing DB_PATH: $requested"
}

save_path_profile() {
  local db_path="$1"
  local readonly_value="${2:-false}"
  local profile="local"
  chmod_config
  if [[ -f "$DEFAULT_FILE" ]]; then
    profile="$(<"$DEFAULT_FILE")"
    safe_name "$profile" || profile="local"
  fi
  local path
  path="$(profile_path "$profile")"
  {
    write_kv DB_PATH "$db_path"
    write_kv READONLY "$readonly_value"
  } >"$path"
  chmod 600 "$path"
  printf '%s\n' "$profile" >"$DEFAULT_FILE"
  chmod 600 "$DEFAULT_FILE"
  PROFILE_NAME="$profile"
}

load_target() {
  local requested="${1-}"
  local path_override="${2-}"
  local readonly_override="${3:-false}"
  if [[ -n "$requested" && -n "$path_override" ]]; then
    die "Use either --profile or --path, not both."
  fi
  if [[ -n "$path_override" ]]; then
    [[ -f "$path_override" ]] || die "SQLite file not found: $path_override"
    save_path_profile "$path_override" "$readonly_override"
    DB_PATH="$path_override"
    READONLY="$readonly_override"
    return
  fi
  if [[ -z "$requested" && ! -f "$DEFAULT_FILE" ]]; then
    die "No profile specified and no default profile configured. Provide --path DB_FILE or run configure first."
  fi
  load_profile "$requested"
}

emit_json() {
  local json="$1"
  local output="${2-}"
  if [[ -z "$output" ]]; then
    mkdir -p out
    output="out/sqlite-crud-$(date -u +%Y%m%dT%H%M%SZ)-$$.json"
  else
    mkdir -p "$(dirname "$output")"
  fi
  printf '%s\n' "$json" >"$output"
  echo "Saved JSON to $output" >&2
  printf '%s\n' "$json"
}

readonly_guard() {
  if [[ "${READONLY:-false}" == "true" ]]; then
    die "This profile is readonly; write SQLite commands are blocked."
  fi
}

quote_identifier() {
  local ident="$1"
  [[ "$ident" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || die "Invalid identifier: $ident"
  printf '"%s"' "$ident"
}

trim_spaces() {
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s' "$s"
}

quote_columns() {
  local columns="${1:-*}"
  if [[ -z "$columns" || "$columns" == "*" ]]; then
    printf '*'
    return
  fi
  local out="" first=true part col
  IFS=',' read -r -a parts <<<"$columns"
  for part in "${parts[@]}"; do
    col="$(trim_spaces "$part")"
    [[ -n "$col" ]] || die "Empty column in --columns"
    [[ "$first" == false ]] && out+=", "
    out+="$(quote_identifier "$col")"
    first=false
  done
  printf '%s' "$out"
}

sql_literal() {
  local value="${1-}"
  value=${value//\'/\'\'}
  printf "'%s'" "$value"
}

split_assignment() {
  local pair="$1"
  [[ "$pair" == *=* ]] || die "Expected name=value: $pair"
  ASSIGN_NAME="${pair%%=*}"
  ASSIGN_VALUE="${pair#*=}"
  [[ "$ASSIGN_NAME" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || die "Invalid name: $ASSIGN_NAME"
}

apply_params() {
  local sql="$1"
  local pair name value literal
  for pair in "${PARAMS[@]:-}"; do
    split_assignment "$pair"
    name="$ASSIGN_NAME"
    value="$ASSIGN_VALUE"
    literal="$(sql_literal "$value")"
    sql="${sql//:${name}/$literal}"
  done
  if [[ "$sql" =~ :[A-Za-z_][A-Za-z0-9_]* ]]; then
    die "Unresolved SQL parameter in --where: $sql"
  fi
  printf '%s' "$sql"
}

run_sqlite_json() {
  local sql="$1"
  command -v sqlite3 >/dev/null 2>&1 || die "sqlite3 is required."
  [[ -f "$DB_PATH" ]] || die "SQLite file not found: $DB_PATH"
  local tmp status=0
  tmp="$(mktemp)"
  sqlite3 -readonly -json "$DB_PATH" "$sql" >"$tmp" || status=$?
  if [[ $status -ne 0 ]]; then
    rm -f "$tmp"
    return "$status"
  fi
  SQLITE_OUTPUT="$(<"$tmp")"
  rm -f "$tmp"
}

run_sqlite_write() {
  local sql="$1"
  command -v sqlite3 >/dev/null 2>&1 || die "sqlite3 is required."
  [[ -f "$DB_PATH" ]] || die "SQLite file not found: $DB_PATH"
  local tmp status=0
  tmp="$(mktemp)"
  sqlite3 -json "$DB_PATH" "$sql; SELECT changes() AS changes;" >"$tmp" || status=$?
  if [[ $status -ne 0 ]]; then
    rm -f "$tmp"
    return "$status"
  fi
  SQLITE_OUTPUT="$(<"$tmp")"
  rm -f "$tmp"
}

profile_json() {
  local profile="$1"
  local path
  path="$(profile_path "$profile")"
  # shellcheck disable=SC1090
  source "$path"
  printf '{"path":%s,"readonly":%s}' "$(json_string "${DB_PATH:-}")" "${READONLY:-false}"
}

cmd_configure() {
  local PROFILE="" DB_PATH="" READONLY=false DEFAULT=false TEST_CONNECTION=false OUTPUT=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --path) DB_PATH="${2:-}"; shift 2 ;;
      --readonly) READONLY=true; shift ;;
      --default) DEFAULT=true; shift ;;
      --test-connection) TEST_CONNECTION=true; shift ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown configure argument: $1" ;;
    esac
  done
  [[ -n "$PROFILE" ]] || die "Missing --profile"
  [[ -n "$DB_PATH" ]] || die "Missing --path"
  [[ -f "$DB_PATH" ]] || die "SQLite file not found: $DB_PATH"
  if [[ "$TEST_CONNECTION" == "true" ]]; then
    PROFILE_NAME="$PROFILE"
    run_sqlite_json "SELECT 1 AS ok" >/dev/null
  fi
  chmod_config
  local path
  path="$(profile_path "$PROFILE")"
  {
    write_kv DB_PATH "$DB_PATH"
    write_kv READONLY "$READONLY"
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
  if [[ -f "$DEFAULT_FILE" && "$(<"$DEFAULT_FILE")" == "$PROFILE" ]]; then
    rm -f "$DEFAULT_FILE"
  fi
  emit_json "{\"removed\":$(json_string "$PROFILE")}" "$OUTPUT"
}

cmd_schema() {
  local PROFILE="" DB_PATH_OVERRIDE="" TABLE="" OUTPUT=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --path) DB_PATH_OVERRIDE="${2:-}"; shift 2 ;;
      --table) TABLE="${2:-}"; shift 2 ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown schema argument: $1" ;;
    esac
  done
  load_target "$PROFILE" "$DB_PATH_OVERRIDE"
  local sql table_sql
  if [[ -n "$TABLE" ]]; then
    table_sql="$(quote_identifier "$TABLE")"
    sql="PRAGMA table_info(${table_sql})"
    run_sqlite_json "$sql"
    emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"operation\":\"schema\",\"db_path\":$(json_string "$DB_PATH"),\"table\":$(json_string "$TABLE"),\"columns\":${SQLITE_OUTPUT:-[]}}" "$OUTPUT"
  else
    sql="SELECT name, type FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY name"
    run_sqlite_json "$sql"
    emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"operation\":\"schema\",\"db_path\":$(json_string "$DB_PATH"),\"tables\":${SQLITE_OUTPUT:-[]}}" "$OUTPUT"
  fi
}

cmd_select() {
  local PROFILE="" DB_PATH_OVERRIDE="" TABLE="" COLUMNS="*" WHERE="" ORDER_BY="" DESC=false LIMIT="20" OUTPUT=""
  PARAMS=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --path) DB_PATH_OVERRIDE="${2:-}"; shift 2 ;;
      --table) TABLE="${2:-}"; shift 2 ;;
      --columns) COLUMNS="${2:-}"; shift 2 ;;
      --where) WHERE="${2:-}"; shift 2 ;;
      --param) PARAMS+=("${2:-}"); shift 2 ;;
      --order-by) ORDER_BY="${2:-}"; shift 2 ;;
      --desc) DESC=true; shift ;;
      --limit) LIMIT="${2:-}"; shift 2 ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown select argument: $1" ;;
    esac
  done
  [[ -n "$TABLE" ]] || die "Missing --table"
  [[ "$LIMIT" =~ ^[0-9]+$ ]] || die "--limit must be a non-negative integer"
  load_target "$PROFILE" "$DB_PATH_OVERRIDE"
  local table_sql columns_sql where_sql sql
  table_sql="$(quote_identifier "$TABLE")"
  columns_sql="$(quote_columns "$COLUMNS")"
  sql="SELECT ${columns_sql} FROM ${table_sql}"
  if [[ -n "$WHERE" ]]; then
    where_sql="$(apply_params "$WHERE")"
    sql+=" WHERE ${where_sql}"
  fi
  if [[ -n "$ORDER_BY" ]]; then
    sql+=" ORDER BY $(quote_identifier "$ORDER_BY")"
    [[ "$DESC" == "true" ]] && sql+=" DESC"
  fi
  sql+=" LIMIT ${LIMIT}"
  run_sqlite_json "$sql"
  emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"operation\":\"select\",\"db_path\":$(json_string "$DB_PATH"),\"table\":$(json_string "$TABLE"),\"where\":$(json_string "$WHERE"),\"limit\":$LIMIT,\"rows\":${SQLITE_OUTPUT:-[]}}" "$OUTPUT"
}

build_insert_sql() {
  local table="$1"
  shift
  local cols="" vals="" first=true pair col value
  [[ $# -gt 0 ]] || die "At least one --value is required"
  for pair in "$@"; do
    split_assignment "$pair"
    col="$ASSIGN_NAME"
    value="$ASSIGN_VALUE"
    [[ "$first" == false ]] && cols+=", " && vals+=", "
    cols+="$(quote_identifier "$col")"
    vals+="$(sql_literal "$value")"
    first=false
  done
  printf 'INSERT INTO %s (%s) VALUES (%s)' "$(quote_identifier "$table")" "$cols" "$vals"
}

build_update_set_sql() {
  local first=true pair col value out=""
  [[ $# -gt 0 ]] || die "At least one --value is required"
  for pair in "$@"; do
    split_assignment "$pair"
    col="$ASSIGN_NAME"
    value="$ASSIGN_VALUE"
    [[ "$first" == false ]] && out+=", "
    out+="$(quote_identifier "$col") = $(sql_literal "$value")"
    first=false
  done
  printf '%s' "$out"
}

cmd_insert() {
  local PROFILE="" DB_PATH_OVERRIDE="" TABLE="" EXECUTE=false OUTPUT="" ONE_TIME_READONLY=false
  VALUES=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --path) DB_PATH_OVERRIDE="${2:-}"; shift 2 ;;
      --table) TABLE="${2:-}"; shift 2 ;;
      --value) VALUES+=("${2-}"); shift 2 ;;
      --readonly) ONE_TIME_READONLY=true; shift ;;
      --execute) EXECUTE=true; shift ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown insert argument: $1" ;;
    esac
  done
  [[ -n "$TABLE" ]] || die "Missing --table"
  load_target "$PROFILE" "$DB_PATH_OVERRIDE" "$ONE_TIME_READONLY"
  readonly_guard
  local sql
  sql="$(build_insert_sql "$TABLE" "${VALUES[@]}")"
  if [[ "$EXECUTE" != "true" ]]; then
    emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"operation\":\"insert\",\"dry_run\":true,\"db_path\":$(json_string "$DB_PATH"),\"table\":$(json_string "$TABLE"),\"sql\":$(json_string "$sql"),\"message\":\"Pass --execute only after user confirmation.\"}" "$OUTPUT"
    return
  fi
  run_sqlite_write "$sql"
  emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"operation\":\"insert\",\"dry_run\":false,\"db_path\":$(json_string "$DB_PATH"),\"table\":$(json_string "$TABLE"),\"result\":${SQLITE_OUTPUT:-[]}}" "$OUTPUT"
}

cmd_update() {
  local PROFILE="" DB_PATH_OVERRIDE="" TABLE="" WHERE="" ALLOW_FULL_TABLE=false EXECUTE=false OUTPUT="" ONE_TIME_READONLY=false
  VALUES=()
  PARAMS=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --path) DB_PATH_OVERRIDE="${2:-}"; shift 2 ;;
      --table) TABLE="${2:-}"; shift 2 ;;
      --value) VALUES+=("${2-}"); shift 2 ;;
      --where) WHERE="${2:-}"; shift 2 ;;
      --param) PARAMS+=("${2:-}"); shift 2 ;;
      --allow-full-table) ALLOW_FULL_TABLE=true; shift ;;
      --readonly) ONE_TIME_READONLY=true; shift ;;
      --execute) EXECUTE=true; shift ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown update argument: $1" ;;
    esac
  done
  [[ -n "$TABLE" ]] || die "Missing --table"
  if [[ -z "$WHERE" && "$ALLOW_FULL_TABLE" != "true" ]]; then
    die "Refusing update without --where. Pass --allow-full-table only after explicit confirmation."
  fi
  load_target "$PROFILE" "$DB_PATH_OVERRIDE" "$ONE_TIME_READONLY"
  readonly_guard
  local sql set_sql where_sql
  set_sql="$(build_update_set_sql "${VALUES[@]}")"
  sql="UPDATE $(quote_identifier "$TABLE") SET ${set_sql}"
  if [[ -n "$WHERE" ]]; then
    where_sql="$(apply_params "$WHERE")"
    sql+=" WHERE ${where_sql}"
  fi
  if [[ "$EXECUTE" != "true" ]]; then
    emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"operation\":\"update\",\"dry_run\":true,\"db_path\":$(json_string "$DB_PATH"),\"table\":$(json_string "$TABLE"),\"where\":$(json_string "$WHERE"),\"sql\":$(json_string "$sql"),\"message\":\"Pass --execute only after user confirmation.\"}" "$OUTPUT"
    return
  fi
  run_sqlite_write "$sql"
  emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"operation\":\"update\",\"dry_run\":false,\"db_path\":$(json_string "$DB_PATH"),\"table\":$(json_string "$TABLE"),\"result\":${SQLITE_OUTPUT:-[]}}" "$OUTPUT"
}

cmd_delete() {
  local PROFILE="" DB_PATH_OVERRIDE="" TABLE="" WHERE="" ALLOW_FULL_TABLE=false EXECUTE=false OUTPUT="" ONE_TIME_READONLY=false
  PARAMS=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --path) DB_PATH_OVERRIDE="${2:-}"; shift 2 ;;
      --table) TABLE="${2:-}"; shift 2 ;;
      --where) WHERE="${2:-}"; shift 2 ;;
      --param) PARAMS+=("${2:-}"); shift 2 ;;
      --allow-full-table) ALLOW_FULL_TABLE=true; shift ;;
      --readonly) ONE_TIME_READONLY=true; shift ;;
      --execute) EXECUTE=true; shift ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown delete argument: $1" ;;
    esac
  done
  [[ -n "$TABLE" ]] || die "Missing --table"
  if [[ -z "$WHERE" && "$ALLOW_FULL_TABLE" != "true" ]]; then
    die "Refusing delete without --where. Pass --allow-full-table only after explicit confirmation."
  fi
  load_target "$PROFILE" "$DB_PATH_OVERRIDE" "$ONE_TIME_READONLY"
  readonly_guard
  local sql where_sql
  sql="DELETE FROM $(quote_identifier "$TABLE")"
  if [[ -n "$WHERE" ]]; then
    where_sql="$(apply_params "$WHERE")"
    sql+=" WHERE ${where_sql}"
  fi
  if [[ "$EXECUTE" != "true" ]]; then
    emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"operation\":\"delete\",\"dry_run\":true,\"db_path\":$(json_string "$DB_PATH"),\"table\":$(json_string "$TABLE"),\"where\":$(json_string "$WHERE"),\"sql\":$(json_string "$sql"),\"message\":\"Pass --execute only after user confirmation.\"}" "$OUTPUT"
    return
  fi
  run_sqlite_write "$sql"
  emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"operation\":\"delete\",\"dry_run\":false,\"db_path\":$(json_string "$DB_PATH"),\"table\":$(json_string "$TABLE"),\"result\":${SQLITE_OUTPUT:-[]}}" "$OUTPUT"
}

is_read_sql() {
  local sql="$1"
  sql="$(trim_spaces "$sql")"
  sql="$(printf '%s' "$sql" | tr '[:lower:]' '[:upper:]')"
  case "$sql" in
    SELECT\ *|PRAGMA\ *|EXPLAIN\ *)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

cmd_raw_sql() {
  local PROFILE="" DB_PATH_OVERRIDE="" SQL="" EXECUTE=false ALLOW_RAW_WRITE=false OUTPUT="" ONE_TIME_READONLY=false
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --path) DB_PATH_OVERRIDE="${2:-}"; shift 2 ;;
      --sql) SQL="${2:-}"; shift 2 ;;
      --readonly) ONE_TIME_READONLY=true; shift ;;
      --execute) EXECUTE=true; shift ;;
      --allow-raw-write) ALLOW_RAW_WRITE=true; shift ;;
      --output) OUTPUT="${2:-}"; shift 2 ;;
      *) die "Unknown raw-sql argument: $1" ;;
    esac
  done
  [[ -n "$SQL" ]] || die "Missing --sql"
  load_target "$PROFILE" "$DB_PATH_OVERRIDE" "$ONE_TIME_READONLY"
  if is_read_sql "$SQL"; then
    run_sqlite_json "$SQL"
    emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"operation\":\"raw-sql\",\"dry_run\":false,\"db_path\":$(json_string "$DB_PATH"),\"sql\":$(json_string "$SQL"),\"rows\":${SQLITE_OUTPUT:-[]}}" "$OUTPUT"
    return
  fi
  readonly_guard
  if [[ "$EXECUTE" != "true" || "$ALLOW_RAW_WRITE" != "true" ]]; then
    emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"operation\":\"raw-sql\",\"dry_run\":true,\"db_path\":$(json_string "$DB_PATH"),\"sql\":$(json_string "$SQL"),\"message\":\"Raw write SQL was not executed. Pass both --execute and --allow-raw-write only after user confirmation.\"}" "$OUTPUT"
    return
  fi
  run_sqlite_write "$SQL"
  emit_json "{\"profile\":$(json_string "$PROFILE_NAME"),\"operation\":\"raw-sql\",\"dry_run\":false,\"db_path\":$(json_string "$DB_PATH"),\"sql\":$(json_string "$SQL"),\"result\":${SQLITE_OUTPUT:-[]}}" "$OUTPUT"
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
