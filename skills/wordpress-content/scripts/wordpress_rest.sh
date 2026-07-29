#!/usr/bin/env bash
set -euo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERBATIM_HELPER="$SCRIPT_DIR/wordpress_verbatim.py"

ACTION="status"
if [[ $# -gt 0 && "$1" != -* ]]; then
  ACTION="$1"
  shift
fi

URL_OVERRIDE=""
USERNAME_OVERRIDE=""
APP_PASSWORD_OVERRIDE=""
CONFIG_FILE_OVERRIDE=""
METHOD="GET"
ENDPOINT=""
DATA_FILE=""
BINARY_FILE=""
CONTENT_TYPE=""
FILENAME=""
OUTPUT_FILE=""
HEADER_FILE=""
BACKUP_FILE=""
SAVE_CONFIG="false"
EXECUTE="false"
DRY_RUN="false"

TEMP_AUTH_FILE=""
TEMP_RESPONSE_FILE=""
TEMP_VERIFY_FILE=""
TEMP_STATUS_FILE=""
WORDPRESS_SETUP_GUIDE="https://frevana.gitbook.io/frevana-docs/cms-integrations/wordpress-integration"
WORDPRESS_CONNECT_TIMEOUT="${WORDPRESS_CONNECT_TIMEOUT:-15}"
WORDPRESS_MAX_TIME="${WORDPRESS_MAX_TIME:-300}"
SETUP_GUIDE_PRINTED="false"
CREDENTIALS_CONFIGURED="false"
CREDENTIALS_VALID="false"

usage() {
  cat <<'USAGE'
Usage:
  wordpress_rest.sh configure [credential options]
  wordpress_rest.sh status [credential options]
  wordpress_rest.sh request --endpoint PATH [request options] [credential options]
  wordpress_rest.sh verbatim-create --endpoint COLLECTION --data-file JSON [--execute]
  wordpress_rest.sh verbatim-update --endpoint OBJECT --data-file JSON --backup FILE [--execute]
  wordpress_rest.sh clear-config [--config FILE]

Actions:
  configure     Resolve missing credentials interactively and save them.
  status        Validate credentials and report availability and source.
  request       Call a relative endpoint on the configured WordPress site.
  verbatim-create
                Create with the supplied JSON unchanged, then compare content.raw.
  verbatim-update
                Back up, update unchanged, then compare content.raw.
  clear-config  Remove the selected local config file.

Credential options:
  --url URL
  --username USERNAME
  --app-password PASSWORD
  --config FILE
  --save-config

Request options:
  --endpoint PATH       Relative site path beginning with /, usually /wp-json/...
  --method METHOD       GET by default
  --data-file FILE      JSON or other request body
  --binary-file FILE    Binary upload body
  --content-type TYPE   Request Content-Type
  --filename NAME       Content-Disposition attachment filename
  --output FILE         Save the response body
  --headers FILE        Save response headers
  --backup FILE         Required saved pre-update object for verbatim-update
  --execute             Perform POST, PUT, PATCH, or DELETE
  --dry-run             Print a redacted request plan without calling WordPress

Resolution order:
  1. explicit credential options
  2. WORDPRESS_URL, WORDPRESS_USERNAME, WORDPRESS_APP_PASSWORD
  3. local config file
  4. interactive prompt, when a terminal is available

Default config:
  ${WORDPRESS_CONFIG_FILE:-${XDG_CONFIG_HOME:-$HOME/.config}/wordpress-content/config}

First-time setup:
  https://frevana.gitbook.io/frevana-docs/cms-integrations/wordpress-integration

Timeout environment variables:
  WORDPRESS_CONNECT_TIMEOUT  Connection timeout in seconds (default: 15)
  WORDPRESS_MAX_TIME         Total request timeout in seconds (default: 300)

Writes are dry-run by default. GET, HEAD, and OPTIONS execute immediately.
USAGE
}

cleanup() {
  local path
  for path in \
    "$TEMP_AUTH_FILE" \
    "$TEMP_RESPONSE_FILE" \
    "$TEMP_VERIFY_FILE" \
    "$TEMP_STATUS_FILE"; do
    if [[ -n "$path" && -f "$path" ]]; then
      rm -f -- "$path"
    fi
  done
}
trap cleanup EXIT

while [[ $# -gt 0 ]]; do
  case "$1" in
    --url)
      [[ $# -ge 2 ]] || { echo "Missing value for --url" >&2; exit 2; }
      URL_OVERRIDE="$2"
      shift 2
      ;;
    --url=*)
      URL_OVERRIDE="${1#*=}"
      shift
      ;;
    --username)
      [[ $# -ge 2 ]] || { echo "Missing value for --username" >&2; exit 2; }
      USERNAME_OVERRIDE="$2"
      shift 2
      ;;
    --username=*)
      USERNAME_OVERRIDE="${1#*=}"
      shift
      ;;
    --app-password)
      [[ $# -ge 2 ]] || { echo "Missing value for --app-password" >&2; exit 2; }
      APP_PASSWORD_OVERRIDE="$2"
      shift 2
      ;;
    --app-password=*)
      APP_PASSWORD_OVERRIDE="${1#*=}"
      shift
      ;;
    --config)
      [[ $# -ge 2 ]] || { echo "Missing value for --config" >&2; exit 2; }
      CONFIG_FILE_OVERRIDE="$2"
      shift 2
      ;;
    --config=*)
      CONFIG_FILE_OVERRIDE="${1#*=}"
      shift
      ;;
    --save-config)
      SAVE_CONFIG="true"
      shift
      ;;
    --endpoint)
      [[ $# -ge 2 ]] || { echo "Missing value for --endpoint" >&2; exit 2; }
      ENDPOINT="$2"
      shift 2
      ;;
    --endpoint=*)
      ENDPOINT="${1#*=}"
      shift
      ;;
    --method)
      [[ $# -ge 2 ]] || { echo "Missing value for --method" >&2; exit 2; }
      METHOD="$2"
      shift 2
      ;;
    --method=*)
      METHOD="${1#*=}"
      shift
      ;;
    --data-file)
      [[ $# -ge 2 ]] || { echo "Missing value for --data-file" >&2; exit 2; }
      DATA_FILE="$2"
      shift 2
      ;;
    --binary-file)
      [[ $# -ge 2 ]] || { echo "Missing value for --binary-file" >&2; exit 2; }
      BINARY_FILE="$2"
      shift 2
      ;;
    --content-type)
      [[ $# -ge 2 ]] || { echo "Missing value for --content-type" >&2; exit 2; }
      CONTENT_TYPE="$2"
      shift 2
      ;;
    --filename)
      [[ $# -ge 2 ]] || { echo "Missing value for --filename" >&2; exit 2; }
      FILENAME="$2"
      shift 2
      ;;
    --output)
      [[ $# -ge 2 ]] || { echo "Missing value for --output" >&2; exit 2; }
      OUTPUT_FILE="$2"
      shift 2
      ;;
    --headers)
      [[ $# -ge 2 ]] || { echo "Missing value for --headers" >&2; exit 2; }
      HEADER_FILE="$2"
      shift 2
      ;;
    --backup)
      [[ $# -ge 2 ]] || { echo "Missing value for --backup" >&2; exit 2; }
      BACKUP_FILE="$2"
      shift 2
      ;;
    --execute)
      EXECUTE="true"
      shift
      ;;
    --dry-run)
      DRY_RUN="true"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

config_file() {
  local config_root
  if [[ -n "$CONFIG_FILE_OVERRIDE" ]]; then
    printf '%s\n' "$CONFIG_FILE_OVERRIDE"
  elif [[ -n "${WORDPRESS_CONFIG_FILE:-}" ]]; then
    printf '%s\n' "$WORDPRESS_CONFIG_FILE"
  else
    if [[ -n "${XDG_CONFIG_HOME:-}" ]]; then
      config_root="$XDG_CONFIG_HOME"
    elif [[ -n "${HOME:-}" ]]; then
      config_root="$HOME/.config"
    else
      echo "Set HOME, XDG_CONFIG_HOME, WORDPRESS_CONFIG_FILE, or --config FILE." >&2
      return 1
    fi
    printf '%s/wordpress-content/config\n' "$config_root"
  fi
}

validate_single_line() {
  local name="$1"
  local value="$2"
  if [[ "$value" == *$'\n'* || "$value" == *$'\r'* ]]; then
    echo "$name must be a single-line value" >&2
    return 1
  fi
}

CONFIG_URL=""
CONFIG_USERNAME=""
CONFIG_APP_PASSWORD=""

load_config() {
  local path line key value
  path="$(config_file)"
  [[ -r "$path" ]] || return 0

  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ -z "$line" || "$line" == \#* || "$line" != *=* ]] && continue
    key="${line%%=*}"
    value="${line#*=}"
    case "$value" in
      \"*\")
        value="${value#\"}"
        value="${value%\"}"
        ;;
      \'*\')
        value="${value#\'}"
        value="${value%\'}"
        ;;
    esac
    case "$key" in
      WORDPRESS_URL) CONFIG_URL="$value" ;;
      WORDPRESS_USERNAME) CONFIG_USERNAME="$value" ;;
      WORDPRESS_APP_PASSWORD) CONFIG_APP_PASSWORD="$value" ;;
    esac
  done < "$path"
}

URL_SOURCE="missing"
USERNAME_SOURCE="missing"
APP_PASSWORD_SOURCE="missing"
RESOLVED_URL=""
RESOLVED_USERNAME=""
RESOLVED_APP_PASSWORD=""

resolve_credentials() {
  load_config

  if [[ -n "$URL_OVERRIDE" ]]; then
    RESOLVED_URL="$URL_OVERRIDE"
    URL_SOURCE="input"
  elif [[ -n "${WORDPRESS_URL:-}" ]]; then
    RESOLVED_URL="$WORDPRESS_URL"
    URL_SOURCE="environment"
  elif [[ -n "$CONFIG_URL" ]]; then
    RESOLVED_URL="$CONFIG_URL"
    URL_SOURCE="config"
  fi

  if [[ -n "$USERNAME_OVERRIDE" ]]; then
    RESOLVED_USERNAME="$USERNAME_OVERRIDE"
    USERNAME_SOURCE="input"
  elif [[ -n "${WORDPRESS_USERNAME:-}" ]]; then
    RESOLVED_USERNAME="$WORDPRESS_USERNAME"
    USERNAME_SOURCE="environment"
  elif [[ -n "$CONFIG_USERNAME" ]]; then
    RESOLVED_USERNAME="$CONFIG_USERNAME"
    USERNAME_SOURCE="config"
  fi

  if [[ -n "$APP_PASSWORD_OVERRIDE" ]]; then
    RESOLVED_APP_PASSWORD="$APP_PASSWORD_OVERRIDE"
    APP_PASSWORD_SOURCE="input"
  elif [[ -n "${WORDPRESS_APP_PASSWORD:-}" ]]; then
    RESOLVED_APP_PASSWORD="$WORDPRESS_APP_PASSWORD"
    APP_PASSWORD_SOURCE="environment"
  elif [[ -n "$CONFIG_APP_PASSWORD" ]]; then
    RESOLVED_APP_PASSWORD="$CONFIG_APP_PASSWORD"
    APP_PASSWORD_SOURCE="config"
  fi
}

prompt_missing_credentials() {
  if [[ ! -t 0 ]]; then
    return 0
  fi

  if [[ -z "$RESOLVED_URL" || -z "$RESOLVED_USERNAME" || -z "$RESOLVED_APP_PASSWORD" ]]; then
    print_setup_guide
  fi

  if [[ -z "$RESOLVED_URL" ]]; then
    read -r -p "WordPress HTTPS URL: " RESOLVED_URL
    URL_SOURCE="prompt"
  fi
  if [[ -z "$RESOLVED_USERNAME" ]]; then
    read -r -p "WordPress username: " RESOLVED_USERNAME
    USERNAME_SOURCE="prompt"
  fi
  if [[ -z "$RESOLVED_APP_PASSWORD" ]]; then
    read -r -s -p "WordPress Application Password: " RESOLVED_APP_PASSWORD
    printf '\n' >&2
    APP_PASSWORD_SOURCE="prompt"
  fi
}

print_setup_guide() {
  if [[ "$SETUP_GUIDE_PRINTED" == "true" ]]; then
    return 0
  fi
  printf 'WordPress setup guide: %s\n' "$WORDPRESS_SETUP_GUIDE" >&2
  SETUP_GUIDE_PRINTED="true"
}

validate_credentials() {
  local missing="false" authority

  CREDENTIALS_CONFIGURED="false"
  CREDENTIALS_VALID="false"
  validate_single_line "WORDPRESS_URL" "$RESOLVED_URL"
  validate_single_line "WORDPRESS_USERNAME" "$RESOLVED_USERNAME"
  validate_single_line "WORDPRESS_APP_PASSWORD" "$RESOLVED_APP_PASSWORD"

  if [[ -z "$RESOLVED_URL" ]]; then
    echo "Missing WORDPRESS_URL" >&2
    missing="true"
  elif [[ "$RESOLVED_URL" != https://* ]]; then
    echo "WORDPRESS_URL must use HTTPS" >&2
    return 1
  elif [[ "$RESOLVED_URL" == *"?"* || "$RESOLVED_URL" == *"#"* || "$RESOLVED_URL" == *" "* || "$RESOLVED_URL" == *$'\t'* ]]; then
    echo "WORDPRESS_URL must not contain queries, fragments, or whitespace" >&2
    return 1
  else
    while [[ "$RESOLVED_URL" == */ ]]; do
      RESOLVED_URL="${RESOLVED_URL%/}"
    done
    authority="${RESOLVED_URL#https://}"
    authority="${authority%%/*}"
    if [[ -z "$authority" || "$authority" == *"@"* || "$authority" == :* ]]; then
      echo "WORDPRESS_URL must contain a host and must not embed credentials" >&2
      return 1
    fi
  fi

  if [[ -z "$RESOLVED_USERNAME" ]]; then
    echo "Missing WORDPRESS_USERNAME" >&2
    missing="true"
  fi
  if [[ -z "$RESOLVED_APP_PASSWORD" ]]; then
    echo "Missing WORDPRESS_APP_PASSWORD" >&2
    missing="true"
  fi

  if [[ "$missing" == "true" ]]; then
    print_setup_guide
    return 1
  fi

  CREDENTIALS_CONFIGURED="true"
  CREDENTIALS_VALID="not_checked"
}

save_config() {
  local path dir tmp dir_created="false"
  path="$(config_file)"
  dir="$(dirname "$path")"

  if [[ ! -d "$dir" ]]; then
    mkdir -p "$dir"
    dir_created="true"
  fi
  if [[ "$dir_created" == "true" ]]; then
    chmod 700 "$dir"
  fi
  tmp="$(mktemp "$dir/config.XXXXXX")"
  printf 'WORDPRESS_URL=%s\n' "$RESOLVED_URL" > "$tmp"
  printf 'WORDPRESS_USERNAME=%s\n' "$RESOLVED_USERNAME" >> "$tmp"
  printf 'WORDPRESS_APP_PASSWORD=%s\n' "$RESOLVED_APP_PASSWORD" >> "$tmp"
  chmod 600 "$tmp"
  mv "$tmp" "$path"
  chmod 600 "$path"
  printf 'Saved WordPress configuration to %s\n' "$path" >&2
}

print_status() {
  printf 'config_file=%s\n' "$(config_file)"
  printf 'wordpress_url=%s\n' "${RESOLVED_URL:-missing}"
  printf 'wordpress_url_source=%s\n' "$URL_SOURCE"
  printf 'wordpress_username=%s\n' "${RESOLVED_USERNAME:-missing}"
  printf 'wordpress_username_source=%s\n' "$USERNAME_SOURCE"
  if [[ -n "$RESOLVED_APP_PASSWORD" ]]; then
    printf 'wordpress_app_password=configured\n'
  else
    printf 'wordpress_app_password=missing\n'
  fi
  printf 'wordpress_app_password_source=%s\n' "$APP_PASSWORD_SOURCE"
  printf 'credentials_configured=%s\n' "$CREDENTIALS_CONFIGURED"
  printf 'credentials_valid=%s\n' "$CREDENTIALS_VALID"
  if [[ -z "$RESOLVED_URL" || -z "$RESOLVED_USERNAME" || -z "$RESOLVED_APP_PASSWORD" ]]; then
    printf 'setup_guide=%s\n' "$WORDPRESS_SETUP_GUIDE"
  fi
}

curl_config_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  printf '%s' "$value"
}

build_auth_file() {
  local auth_dir escaped_user escaped_password
  if [[ -n "$TEMP_AUTH_FILE" && -f "$TEMP_AUTH_FILE" ]]; then
    return 0
  fi
  auth_dir="${TMPDIR:-/tmp}"
  TEMP_AUTH_FILE="$(mktemp "$auth_dir/wordpress-content-curl.XXXXXX")"
  escaped_user="$(curl_config_escape "$RESOLVED_USERNAME")"
  escaped_password="$(curl_config_escape "$RESOLVED_APP_PASSWORD")"
  printf 'user = "%s:%s"\n' "$escaped_user" "$escaped_password" > "$TEMP_AUTH_FILE"
  chmod 600 "$TEMP_AUTH_FILE"
}

require_verbatim_helper() {
  command -v python3 >/dev/null 2>&1 || {
    echo "verbatim-create and verbatim-update require Python 3" >&2
    return 1
  }
  [[ -r "$VERBATIM_HELPER" ]] || {
    echo "Missing verbatim helper: $VERBATIM_HELPER" >&2
    return 1
  }
}

require_curl() {
  command -v curl >/dev/null 2>&1 || {
    echo "Missing required command: curl" >&2
    return 1
  }
}

validate_curl_timeouts() {
  local name value
  for name in WORDPRESS_CONNECT_TIMEOUT WORDPRESS_MAX_TIME; do
    if [[ "$name" == "WORDPRESS_CONNECT_TIMEOUT" ]]; then
      value="$WORDPRESS_CONNECT_TIMEOUT"
    else
      value="$WORDPRESS_MAX_TIME"
    fi
    if [[ ! "$value" =~ ^[0-9]+([.][0-9]+)?$ || "$value" =~ ^0+([.]0+)?$ ]]; then
      echo "$name must be a positive number of seconds" >&2
      return 1
    fi
  done
}

validate_endpoint() {
  local endpoint="$1"
  if [[ -z "$endpoint" || "$endpoint" != /* || "$endpoint" == *"://"* ]]; then
    echo "--endpoint must be a relative site path beginning with /" >&2
    return 1
  fi
  validate_single_line "endpoint" "$endpoint"
  if [[ "$endpoint" == *" "* || "$endpoint" == *$'\t'* ]]; then
    echo "--endpoint must URL-encode spaces and other query values" >&2
    return 1
  fi
}

ensure_distinct_files() {
  local first_label="$1"
  local first_path="$2"
  local second_label="$3"
  local second_path="$4"
  local path_status

  [[ -n "$first_path" && -n "$second_path" ]] || return 0
  require_verbatim_helper
  if python3 "$VERBATIM_HELPER" same-path "$first_path" "$second_path"; then
    printf '%s and %s must refer to different files\n' "$first_label" "$second_label" >&2
    return 1
  else
    path_status=$?
    if [[ "$path_status" -eq 1 ]]; then
      return 0
    fi
    return "$path_status"
  fi
}

allocate_verbatim_temp_files() {
  local temp_root="${TMPDIR:-/tmp}"
  TEMP_RESPONSE_FILE="$(mktemp "$temp_root/wordpress-content-response.XXXXXX")"
  TEMP_VERIFY_FILE="$(mktemp "$temp_root/wordpress-content-verify.XXXXXX")"
  chmod 600 "$TEMP_RESPONSE_FILE" "$TEMP_VERIFY_FILE"
}

json_request_to_file() {
  local method="$1"
  local endpoint="$2"
  local data_file="$3"
  local output_file="$4"
  local request_url="$RESOLVED_URL$endpoint"
  local curl_args=()

  require_curl
  validate_curl_timeouts
  build_auth_file
  curl_args=(
    --disable
    --fail-with-body
    --silent
    --show-error
    --connect-timeout "$WORDPRESS_CONNECT_TIMEOUT"
    --max-time "$WORDPRESS_MAX_TIME"
    --config "$TEMP_AUTH_FILE"
    --request "$method"
    --header "Content-Type: application/json"
    --output "$output_file"
  )
  if [[ -n "$data_file" ]]; then
    curl_args+=(--data-binary "@$data_file")
  fi
  curl "${curl_args[@]}" "$request_url"
}

check_remote_credentials() {
  local temp_root="${TMPDIR:-/tmp}"

  require_verbatim_helper
  TEMP_STATUS_FILE="$(mktemp "$temp_root/wordpress-content-status.XXXXXX")"
  chmod 600 "$TEMP_STATUS_FILE"
  if json_request_to_file GET \
      "/wp-json/wp/v2/users/me?context=edit&_fields=id,username" \
      "" \
      "$TEMP_STATUS_FILE" \
    && python3 "$VERBATIM_HELPER" extract-id "$TEMP_STATUS_FILE" >/dev/null; then
    CREDENTIALS_VALID="true"
    return 0
  fi

  CREDENTIALS_VALID="false"
  echo "WordPress authentication check failed" >&2
  return 1
}

emit_verbatim_result() {
  local source_file="$1"
  if [[ -n "$OUTPUT_FILE" ]]; then
    cp -- "$source_file" "$OUTPUT_FILE"
    printf 'Saved WordPress response to %s\n' "$OUTPUT_FILE" >&2
  else
    command cat -- "$source_file"
  fi
}

request_is_write() {
  case "$METHOD" in
    GET|HEAD|OPTIONS) return 1 ;;
    *) return 0 ;;
  esac
}

run_request() {
  local request_url is_write="false" helper_status
  local curl_args=()

  require_curl
  validate_curl_timeouts

  METHOD="$(printf '%s' "$METHOD" | tr '[:lower:]' '[:upper:]')"
  case "$METHOD" in
    GET|HEAD|OPTIONS|POST|PUT|PATCH|DELETE) ;;
    *) echo "Unsupported HTTP method: $METHOD" >&2; return 1 ;;
  esac

  validate_endpoint "$ENDPOINT"

  if [[ -n "$DATA_FILE" && -n "$BINARY_FILE" ]]; then
    echo "--data-file and --binary-file are mutually exclusive" >&2
    return 1
  fi
  if [[ -n "$DATA_FILE" && ! -r "$DATA_FILE" ]]; then
    echo "Data file is not readable: $DATA_FILE" >&2
    return 1
  fi
  if [[ -n "$BINARY_FILE" && ! -r "$BINARY_FILE" ]]; then
    echo "Binary file is not readable: $BINARY_FILE" >&2
    return 1
  fi
  ensure_distinct_files "--output" "$OUTPUT_FILE" "--data-file" "$DATA_FILE"
  ensure_distinct_files "--output" "$OUTPUT_FILE" "--binary-file" "$BINARY_FILE"
  ensure_distinct_files "--headers" "$HEADER_FILE" "--data-file" "$DATA_FILE"
  ensure_distinct_files "--headers" "$HEADER_FILE" "--binary-file" "$BINARY_FILE"
  ensure_distinct_files "--output" "$OUTPUT_FILE" "--headers" "$HEADER_FILE"

  request_url="$RESOLVED_URL$ENDPOINT"

  if request_is_write; then
    is_write="true"
  fi

  if [[ "$DRY_RUN" == "true" || ( "$EXECUTE" != "true" && "$is_write" == "true" ) ]]; then
    printf 'mode=dry_run\n'
    printf 'method=%s\n' "$METHOD"
    printf 'url=%s\n' "$request_url"
    printf 'credentials=redacted\n'
    printf 'data_file=%s\n' "${DATA_FILE:-none}"
    printf 'binary_file=%s\n' "${BINARY_FILE:-none}"
    printf 'content_type=%s\n' "${CONTENT_TYPE:-default}"
    return 0
  fi

  if [[ "$is_write" == "true" && -n "$DATA_FILE" && ( -z "$CONTENT_TYPE" || "$CONTENT_TYPE" == application/json* ) ]]; then
    require_verbatim_helper
    if python3 "$VERBATIM_HELPER" has-content "$DATA_FILE"; then
      echo "Generic request refuses executable writes containing content." >&2
      echo "Use verbatim-create or verbatim-update so the payload is submitted unchanged and content.raw can be checked." >&2
      return 1
    else
      helper_status=$?
      if [[ "$helper_status" -ne 1 ]]; then
        return "$helper_status"
      fi
    fi
  fi

  build_auth_file
  curl_args=(
    --disable
    --fail-with-body
    --silent
    --show-error
    --connect-timeout "$WORDPRESS_CONNECT_TIMEOUT"
    --max-time "$WORDPRESS_MAX_TIME"
    --config "$TEMP_AUTH_FILE"
    --request "$METHOD"
  )

  if [[ -n "$CONTENT_TYPE" ]]; then
    validate_single_line "content type" "$CONTENT_TYPE"
    curl_args+=(--header "Content-Type: $CONTENT_TYPE")
  elif [[ -n "$DATA_FILE" ]]; then
    curl_args+=(--header "Content-Type: application/json")
  fi
  if [[ -n "$FILENAME" ]]; then
    validate_single_line "filename" "$FILENAME"
    curl_args+=(--header "Content-Disposition: attachment; filename=$FILENAME")
  fi
  if [[ -n "$DATA_FILE" ]]; then
    curl_args+=(--data-binary "@$DATA_FILE")
  elif [[ -n "$BINARY_FILE" ]]; then
    curl_args+=(--data-binary "@$BINARY_FILE")
  fi
  if [[ -n "$OUTPUT_FILE" ]]; then
    curl_args+=(--output "$OUTPUT_FILE")
  fi
  if [[ -n "$HEADER_FILE" ]]; then
    curl_args+=(--dump-header "$HEADER_FILE")
  fi

  curl "${curl_args[@]}" "$request_url"
}

require_content_payload() {
  local helper_status
  if python3 "$VERBATIM_HELPER" has-content "$DATA_FILE"; then
    return 0
  else
    helper_status=$?
  fi
  if [[ "$helper_status" -eq 1 ]]; then
    echo "$DATA_FILE must contain a top-level string field named content" >&2
  fi
  return "$helper_status"
}

validate_verbatim_inputs() {
  require_verbatim_helper
  validate_endpoint "$ENDPOINT"
  if [[ "$ENDPOINT" == *"?"* || "$ENDPOINT" == *"#"* ]]; then
    echo "Verbatim actions require an endpoint without a query or fragment" >&2
    return 1
  fi
  if [[ -z "$DATA_FILE" || ! -r "$DATA_FILE" ]]; then
    echo "Verbatim actions require a readable --data-file JSON payload" >&2
    return 1
  fi
  if [[ -n "$BINARY_FILE" ]]; then
    echo "Verbatim actions do not accept --binary-file" >&2
    return 1
  fi
  ensure_distinct_files "--output" "$OUTPUT_FILE" "--data-file" "$DATA_FILE"
  ensure_distinct_files "--backup" "$BACKUP_FILE" "--data-file" "$DATA_FILE"
  ensure_distinct_files "--output" "$OUTPUT_FILE" "--backup" "$BACKUP_FILE"
  require_content_payload
}

run_verbatim_create() {
  local object_id object_endpoint

  validate_verbatim_inputs
  if [[ "$ENDPOINT" =~ /[0-9]+/?$ ]]; then
    echo "verbatim-create requires a collection endpoint; use verbatim-update for an object ID" >&2
    return 1
  fi
  allocate_verbatim_temp_files

  if [[ "$DRY_RUN" == "true" || "$EXECUTE" != "true" ]]; then
    printf 'mode=dry_run\n'
    printf 'action=verbatim_create\n'
    printf 'url=%s%s\n' "$RESOLVED_URL" "$ENDPOINT"
    printf 'payload=submitted_unchanged\n'
    printf 'verification=advisory\n'
    return 0
  fi

  json_request_to_file POST "$ENDPOINT" "$DATA_FILE" "$TEMP_RESPONSE_FILE"
  emit_verbatim_result "$TEMP_RESPONSE_FILE"
  if ! python3 "$VERBATIM_HELPER" verify-status "$DATA_FILE" "$TEMP_RESPONSE_FILE"; then
    printf 'Error: WordPress accepted the request but did not apply the requested publication status.\n' >&2
    return 1
  fi

  if ! object_id="$(python3 "$VERBATIM_HELPER" extract-id "$TEMP_RESPONSE_FILE")"; then
    printf 'Warning: WordPress accepted the request, but the response ID could not be read; skipped advisory content verification.\n' >&2
    return 0
  fi

  printf 'wordpress_object_id=%s\n' "$object_id" >&2
  object_endpoint="${ENDPOINT%/}/$object_id"
  if ! json_request_to_file GET "$object_endpoint?context=edit" "" "$TEMP_VERIFY_FILE"; then
    printf 'Warning: WordPress accepted the request, but the published object could not be fetched for advisory verification.\n' >&2
    return 0
  fi
  if ! python3 "$VERBATIM_HELPER" compare "$DATA_FILE" "$TEMP_VERIFY_FILE"; then
    printf 'Warning: WordPress accepted the request but changed or omitted content.raw; publication was not stopped or rolled back.\n' >&2
  fi
  if ! python3 "$VERBATIM_HELPER" verify-status "$DATA_FILE" "$TEMP_VERIFY_FILE"; then
    printf 'Error: the stored object does not have the requested publication status.\n' >&2
    return 1
  fi
}

run_verbatim_update() {
  validate_verbatim_inputs
  if [[ ! "$ENDPOINT" =~ /[0-9]+/?$ ]]; then
    echo "verbatim-update requires an object endpoint ending in a numeric ID" >&2
    return 1
  fi

  if [[ "$DRY_RUN" == "true" || "$EXECUTE" != "true" ]]; then
    printf 'mode=dry_run\n'
    printf 'action=verbatim_update\n'
    printf 'url=%s%s\n' "$RESOLVED_URL" "$ENDPOINT"
    printf 'payload=submitted_unchanged\n'
    printf 'verification=advisory\n'
    printf 'backup_file=%s\n' "${BACKUP_FILE:-required_for_execute}"
    return 0
  fi

  if [[ -z "$BACKUP_FILE" ]]; then
    echo "verbatim-update requires --backup FILE when --execute is used" >&2
    return 1
  fi
  allocate_verbatim_temp_files
  json_request_to_file GET "$ENDPOINT?context=edit" "" "$BACKUP_FILE"
  chmod 600 "$BACKUP_FILE"
  json_request_to_file POST "$ENDPOINT" "$DATA_FILE" "$TEMP_RESPONSE_FILE"
  printf 'backup_file=%s\n' "$BACKUP_FILE" >&2
  emit_verbatim_result "$TEMP_RESPONSE_FILE"
  if ! python3 "$VERBATIM_HELPER" verify-status "$DATA_FILE" "$TEMP_RESPONSE_FILE"; then
    printf 'Error: WordPress accepted the update but did not apply the requested status. The previous object is saved at %s.\n' "$BACKUP_FILE" >&2
    return 1
  fi

  if ! json_request_to_file GET "$ENDPOINT?context=edit" "" "$TEMP_VERIFY_FILE"; then
    printf 'Warning: WordPress accepted the update, but the object could not be fetched for advisory verification. The previous object is saved at %s.\n' "$BACKUP_FILE" >&2
    return 0
  fi
  if ! python3 "$VERBATIM_HELPER" compare "$DATA_FILE" "$TEMP_VERIFY_FILE"; then
    printf 'Warning: WordPress accepted the update but changed or omitted content.raw. The previous object is saved at %s; the update was not rolled back.\n' "$BACKUP_FILE" >&2
  fi
  if ! python3 "$VERBATIM_HELPER" verify-status "$DATA_FILE" "$TEMP_VERIFY_FILE"; then
    printf 'Error: the stored object does not have the requested status. The previous object is saved at %s.\n' "$BACKUP_FILE" >&2
    return 1
  fi
}

resolve_credentials

case "$ACTION" in
  configure)
    prompt_missing_credentials
    validate_credentials
    save_config
    if check_remote_credentials; then
      print_status
    else
      connection_status=$?
      print_status
      exit "$connection_status"
    fi
    ;;
  status)
    if validate_credentials; then
      if check_remote_credentials; then
        print_status
      else
        connection_status=$?
        print_status
        exit "$connection_status"
      fi
    else
      validation_status=$?
      print_status
      exit "$validation_status"
    fi
    ;;
  clear-config)
    selected_config="$(config_file)"
    if [[ -f "$selected_config" ]]; then
      rm -f -- "$selected_config"
      printf 'Removed WordPress configuration from %s\n' "$selected_config" >&2
    fi
    ;;
  request)
    prompt_missing_credentials
    validate_credentials
    if [[ "$SAVE_CONFIG" == "true" ]]; then
      save_config
    fi
    run_request
    ;;
  verbatim-create)
    prompt_missing_credentials
    validate_credentials
    if [[ "$SAVE_CONFIG" == "true" ]]; then
      save_config
    fi
    run_verbatim_create
    ;;
  verbatim-update)
    prompt_missing_credentials
    validate_credentials
    if [[ "$SAVE_CONFIG" == "true" ]]; then
      save_config
    fi
    run_verbatim_update
    ;;
  *)
    echo "Unknown action: $ACTION" >&2
    usage >&2
    exit 2
    ;;
esac
