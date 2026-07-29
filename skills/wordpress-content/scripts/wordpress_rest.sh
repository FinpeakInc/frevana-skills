#!/usr/bin/env bash
set -euo pipefail

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
SAVE_CONFIG="false"
EXECUTE="false"
DRY_RUN="false"

TEMP_AUTH_FILE=""
WORDPRESS_SETUP_GUIDE="https://frevana.gitbook.io/frevana-docs/cms-integrations/wordpress-integration"
SETUP_GUIDE_PRINTED="false"

usage() {
  cat <<'USAGE'
Usage:
  wordpress_rest.sh configure [credential options]
  wordpress_rest.sh status [credential options]
  wordpress_rest.sh request --endpoint PATH [request options] [credential options]
  wordpress_rest.sh clear-config [--config FILE]

Actions:
  configure     Resolve missing credentials interactively and save them.
  status        Report whether each credential is available and its source.
  request       Call a relative endpoint on the configured WordPress site.
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

Writes are dry-run by default. GET, HEAD, and OPTIONS execute immediately.
USAGE
}

cleanup() {
  if [[ -n "$TEMP_AUTH_FILE" && -f "$TEMP_AUTH_FILE" ]]; then
    rm -f -- "$TEMP_AUTH_FILE"
  fi
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

  validate_single_line "WORDPRESS_URL" "$RESOLVED_URL"
  validate_single_line "WORDPRESS_USERNAME" "$RESOLVED_USERNAME"
  validate_single_line "WORDPRESS_APP_PASSWORD" "$RESOLVED_APP_PASSWORD"

  if [[ -z "$RESOLVED_URL" ]]; then
    echo "Missing WORDPRESS_URL" >&2
    missing="true"
  elif [[ "$RESOLVED_URL" != https://* ]]; then
    echo "WORDPRESS_URL must use HTTPS" >&2
    return 1
  else
    RESOLVED_URL="${RESOLVED_URL%/}"
    authority="${RESOLVED_URL#https://}"
    authority="${authority%%/*}"
    if [[ -z "$authority" || "$authority" == *"@"* ]]; then
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
}

save_config() {
  local path dir tmp
  path="$(config_file)"
  dir="$(dirname "$path")"

  mkdir -p "$dir"
  chmod 700 "$dir" 2>/dev/null || true
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
  auth_dir="${TMPDIR:-/tmp}"
  TEMP_AUTH_FILE="$(mktemp "$auth_dir/wordpress-content-curl.XXXXXX")"
  escaped_user="$(curl_config_escape "$RESOLVED_USERNAME")"
  escaped_password="$(curl_config_escape "$RESOLVED_APP_PASSWORD")"
  printf 'user = "%s:%s"\n' "$escaped_user" "$escaped_password" > "$TEMP_AUTH_FILE"
  chmod 600 "$TEMP_AUTH_FILE"
}

request_is_write() {
  case "$METHOD" in
    GET|HEAD|OPTIONS) return 1 ;;
    *) return 0 ;;
  esac
}

run_request() {
  local request_url is_write="false"
  local curl_args=()

  command -v curl >/dev/null 2>&1 || { echo "Missing required command: curl" >&2; return 1; }

  METHOD="$(printf '%s' "$METHOD" | tr '[:lower:]' '[:upper:]')"
  case "$METHOD" in
    GET|HEAD|OPTIONS|POST|PUT|PATCH|DELETE) ;;
    *) echo "Unsupported HTTP method: $METHOD" >&2; return 1 ;;
  esac

  if [[ -z "$ENDPOINT" || "$ENDPOINT" != /* || "$ENDPOINT" == *"://"* ]]; then
    echo "--endpoint must be a relative site path beginning with /" >&2
    return 1
  fi
  validate_single_line "endpoint" "$ENDPOINT"
  if [[ "$ENDPOINT" == *" "* || "$ENDPOINT" == *$'\t'* ]]; then
    echo "--endpoint must URL-encode spaces and other query values" >&2
    return 1
  fi

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

  build_auth_file
  curl_args=(--fail-with-body --silent --show-error --config "$TEMP_AUTH_FILE" --request "$METHOD")

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

resolve_credentials

case "$ACTION" in
  configure)
    prompt_missing_credentials
    validate_credentials
    save_config
    print_status
    ;;
  status)
    print_status
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
  *)
    echo "Unknown action: $ACTION" >&2
    usage >&2
    exit 2
    ;;
esac
