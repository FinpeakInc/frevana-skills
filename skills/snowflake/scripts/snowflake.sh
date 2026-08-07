#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  snowflake.sh check
  snowflake.sh config-info [--config-file PATH]
  snowflake.sh setup-pat [--name NAME] [--account ACCOUNT] [--user USER] [--token-env ENV_NAME] [--token-file PATH] [connection options] [--no-default] [--skip-test] [--execute]
  snowflake.sh connection-list [--all] [--config-file PATH] [--output PATH]
  snowflake.sh connection-test [--connection NAME] [--enable-diag --diag-log-path PATH] [--diag-allowlist-path PATH] [--config-file PATH] [--output PATH]
  snowflake.sh connection-add-pat --name NAME --account ACCOUNT --user USER --token-file PATH [connection options] [--execute]
  snowflake.sh connection-add --name NAME [connection options] [--execute]
  snowflake.sh connection-set-default --name NAME [--execute]
  snowflake.sh connection-remove --name NAME [--execute]
  snowflake.sh query (--sql SQL | --file PATH) [query options] [--execute]
  snowflake.sh object-list --type TYPE [context options]
  snowflake.sh object-describe --type TYPE --identifier IDENTIFIER [context options]
  snowflake.sh object-create --type TYPE --definition-file PATH [context options] [--execute]
  snowflake.sh object-drop --type TYPE --identifier IDENTIFIER [context options] [--execute]

Common options:
  --connection NAME       Snowflake CLI connection name
  --config-file PATH      Alternate Snowflake CLI config.toml
  --output PATH           Save command JSON to this path
  --format JSON|JSON_EXT  Snowflake CLI output format (default: JSON_EXT)

Query options:
  --database NAME --schema NAME --role NAME --warehouse NAME
  --variable key=value    Standard Snowflake CLI template variable; repeatable
  --env key=value         snowflake.yml ctx.env override; repeatable
  --templating MODE       STANDARD, NONE, LEGACY, JINJA, or ALL (default: STANDARD)
  --single-transaction
  --preview               Preview even SQL classified as read-only
  --execute               Required for SQL not classified as read-only

Connection-add options:
  --account NAME --user NAME --role NAME --warehouse NAME
  --database NAME --schema NAME --authenticator NAME
  --private-key-file PATH --token-file PATH --token-file-path PATH
  --workload-identity-provider AWS|AZURE|GCP|OIDC
  --default

PAT is the primary authentication flow. connection-add-pat always sets
authenticator=PROGRAMMATIC_ACCESS_TOKEN and requires an owner-only token file
with permissions 0400 or 0600.

setup-pat reads connection fields from SNOWFLAKE_* environment variables and
reads the PAT from SNOWFLAKE_PAT, falling back to SNOWFLAKE_TOKEN. It stores the
secret in an owner-only file, writes only token_file_path to Snowflake config,
sets the connection as default, and tests it. The default connection name is "default".

Passwords, raw tokens, OAuth client secrets, private-key contents, and MFA passcodes
are intentionally not accepted. Supply secrets through protected files or environment variables.
EOF
}

die() {
  echo "$*" >&2
  exit 2
}

require_value() {
  local option="$1"
  local value="${2-}"
  [[ -n "$value" ]] || die "Missing value for ${option}"
}

safe_name() {
  [[ "$1" =~ ^[A-Za-z0-9_.-]+$ ]]
}

valid_format() {
  [[ "$1" == "JSON" || "$1" == "JSON_EXT" ]]
}

valid_templating() {
  [[ "$1" == "STANDARD" || "$1" == "NONE" || "$1" == "LEGACY" || "$1" == "JINJA" || "$1" == "ALL" ]]
}

valid_wif_provider() {
  [[ "$1" == "AWS" || "$1" == "AZURE" || "$1" == "GCP" || "$1" == "OIDC" ]]
}

file_mode() {
  local path="$1"
  local mode=""
  mode="$(stat -f '%Lp' "$path" 2>/dev/null || true)"
  if [[ -z "$mode" ]]; then
    mode="$(stat -c '%a' "$path" 2>/dev/null || true)"
  fi
  printf '%s' "$mode"
}

file_owner_id() {
  local path="$1"
  local owner_id=""
  owner_id="$(stat -f '%u' "$path" 2>/dev/null || true)"
  if [[ -z "$owner_id" ]]; then
    owner_id="$(stat -c '%u' "$path" 2>/dev/null || true)"
  fi
  printf '%s' "$owner_id"
}

validate_protected_file() {
  local path="$1"
  local label="$2"
  [[ -f "$path" && ! -L "$path" ]] || die "$label not found, not a regular file, or is a symlink: $path"
  [[ -r "$path" ]] || die "$label is not readable: $path"
  [[ -s "$path" ]] || die "$label is empty: $path"

  local mode
  mode="$(file_mode "$path")"
  [[ -n "$mode" ]] || die "Unable to verify $label permissions: $path"
  case "$mode" in
    400|600) ;;
    *) die "$label permissions must be 0400 or 0600; found ${mode} for $path" ;;
  esac
}

validate_pat_file() {
  validate_protected_file "$1" "PAT token file"
}

valid_env_name() {
  [[ "$1" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]
}

connection_env_name() {
  local connection_name="$1"
  local field="$2"
  [[ "$connection_name" =~ ^[A-Za-z0-9_]+$ ]] || return 1
  local normalized_name
  normalized_name="$(printf '%s' "$connection_name" | tr '[:lower:]' '[:upper:]')"
  printf 'SNOWFLAKE_CONNECTIONS_%s_%s' "$normalized_name" "$field"
}

connection_env_value() {
  local env_name
  env_name="$(connection_env_name "$1" "$2" 2>/dev/null || true)"
  [[ -n "$env_name" ]] || return 0
  printenv "$env_name" 2>/dev/null || true
}

default_snowflake_config_dir() {
  if [[ -n "${SNOWFLAKE_HOME:-}" ]]; then
    printf '%s' "$SNOWFLAKE_HOME"
    return
  fi

  if [[ -d "$HOME/.snowflake" ]]; then
    printf '%s' "$HOME/.snowflake"
    return
  fi

  case "$(uname -s)" in
    Darwin)
      printf '%s' "$HOME/Library/Application Support/snowflake"
      ;;
    Linux)
      printf '%s' "${XDG_CONFIG_HOME:-$HOME/.config}/snowflake"
      ;;
    CYGWIN*|MINGW*|MSYS*)
      local windows_config_dir="${LOCALAPPDATA:-${USERPROFILE:-}/AppData/Local}"
      [[ -n "$windows_config_dir" ]] ||
        die "Unable to determine the Windows Snowflake configuration directory"
      if command -v cygpath >/dev/null 2>&1; then
        windows_config_dir="$(cygpath -u "$windows_config_dir")"
      fi
      [[ "$windows_config_dir" == /* ]] ||
        die "Windows paths require a POSIX-compatible shell with cygpath"
      printf '%s/snowflake' "$windows_config_dir"
      ;;
    *)
      die "Unsupported platform for automatic Snowflake configuration path; use --token-file"
      ;;
  esac
}

resolve_config_file() {
  local config_file="${1-}"
  if [[ -n "$config_file" ]]; then
    if [[ "$config_file" == /* ]]; then
      printf '%s' "$config_file"
    else
      printf '%s/%s' "$PWD" "$config_file"
    fi
    return
  fi
  printf '%s/config.toml' "$(default_snowflake_config_dir)"
}

default_pat_file() {
  local connection_name="$1"
  local config_file="${2-}"
  local pat_dir=""

  if [[ -n "${SNOWFLAKE_PAT_DIR:-}" ]]; then
    pat_dir="$SNOWFLAKE_PAT_DIR"
  else
    pat_dir="$(dirname "$(resolve_config_file "$config_file")")/pat"
  fi

  printf '%s/%s.pat' "$pat_dir" "$connection_name"
}

validate_pat_env() {
  local env_name="$1"
  valid_env_name "$env_name" || die "Invalid PAT environment variable name: $env_name"
  [[ -n "$(printenv "$env_name" 2>/dev/null || true)" ]] ||
    die "PAT environment variable is missing or empty: $env_name"
}

store_pat_from_env() {
  local env_name="$1"
  local target_path="$2"
  [[ "$target_path" == /* ]] || die "Persisted PAT token file path must be absolute: $target_path"
  [[ ! -e "$target_path" ]] ||
    die "PAT token file already exists: $target_path. Refusing to overwrite it during initial setup."

  local target_dir
  target_dir="$(dirname "$target_path")"
  if [[ -e "$target_dir" ]]; then
    [[ -d "$target_dir" && ! -L "$target_dir" ]] ||
      die "PAT token directory must be a real directory, not a symlink: $target_dir"
    local target_dir_owner
    target_dir_owner="$(file_owner_id "$target_dir")"
    [[ -n "$target_dir_owner" && "$target_dir_owner" == "$(id -u)" ]] ||
      die "PAT token directory must be owned by the current user: $target_dir"
    local target_dir_mode
    target_dir_mode="$(file_mode "$target_dir")"
    [[ -n "$target_dir_mode" ]] || die "Unable to verify PAT token directory permissions: $target_dir"
    (( (8#$target_dir_mode & 8#22) == 0 )) ||
      die "PAT token directory must not be group- or world-writable: $target_dir"
  else
    (umask 077; mkdir -p "$target_dir")
    chmod 700 "$target_dir"
  fi

  local pat_value
  pat_value="$(printenv "$env_name")"
  local temp_path
  temp_path="$(mktemp "${target_path}.tmp.XXXXXX")"
  chmod 600 "$temp_path"
  printf '%s\n' "$pat_value" >"$temp_path"
  unset pat_value
  mv "$temp_path" "$target_path"
  chmod 600 "$target_path"
  validate_pat_file "$target_path"
}

json_escape() {
  local value="${1-}"
  value=${value//\\/\\\\}
  value=${value//\"/\\\"}
  value=${value//$'\n'/\\n}
  value=${value//$'\r'/\\r}
  value=${value//$'\t'/\\t}
  printf '%s' "$value"
}

shell_join() {
  local result=""
  local arg
  for arg in "$@"; do
    if [[ -n "$result" ]]; then
      result+=" "
    fi
    printf -v arg '%q' "$arg"
    result+="$arg"
  done
  printf '%s' "$result"
}

preview() {
  local action="$1"
  shift
  local command_text
  command_text="$(shell_join "$@")"
  printf '{"dry_run":true,"action":"%s","command":"%s","next":"Review the preview, obtain explicit confirmation, then rerun with --execute."}\n' \
    "$(json_escape "$action")" "$(json_escape "$command_text")"
}

verify_snow_binary() {
  local binary="$1"
  "$binary" --help >/dev/null 2>&1 || return 1
  local version_output
  version_output="$("$binary" --version 2>/dev/null)" || return 1
  printf '%s' "$version_output" | grep -Eqi 'Snowflake CLI'
}

# Directory where Frevana-managed binaries (uv, etc.) are installed.
FREVANA_BIN_DIR="${FREVANA_BIN_DIR:-$HOME/.frevana/bin}"

resolve_uv() {
  # Return the path to uv. Check PATH first, then FREVANA_BIN_DIR, then common locations.
  if command -v uv >/dev/null 2>&1; then
    printf '%s' "$(command -v uv)"
    return 0
  fi
  if [[ -x "${FREVANA_BIN_DIR}/uv" ]]; then
    printf '%s' "${FREVANA_BIN_DIR}/uv"
    return 0
  fi
  local candidate
  for candidate in \
    "$HOME/.frevana/python/bin/uv" \
    "$HOME/.local/bin/uv" \
    "$HOME/.cargo/bin/uv" \
    "/opt/homebrew/bin/uv" \
    "/usr/local/bin/uv" \
    "/usr/bin/uv"; do
    if [[ -x "$candidate" ]]; then
      printf '%s' "$candidate"
      return 0
    fi
  done
  return 1
}

install_uv() {
  local target_dir="${FREVANA_BIN_DIR}"
  (umask 077; mkdir -p "$target_dir")

  # Detect OS environment
  local os_type
  os_type="$(uname -s 2>/dev/null || echo "Unknown")"

  # ── 1. Windows Environment (MSYS, MINGW, Cygwin) ──────────────────────────
  case "$os_type" in
    *MINGW*|*MSYS*|*CYGWIN*)
      if command -v powershell >/dev/null 2>&1; then
        echo "Installing uv via official PowerShell installer..." >&2
        powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex" >&2 && return 0
      fi
      if command -v winget >/dev/null 2>&1; then
        echo "Installing uv via winget..." >&2
        winget install --id=astral-sh.uv -e >&2 && return 0
      fi
      if command -v scoop >/dev/null 2>&1; then
        echo "Installing uv via scoop..." >&2
        scoop install main/uv >&2 && return 0
      fi
      ;;
  esac

  # ── 2. Official Standalone Installer (macOS / Linux) ─────────────────────
  # Recommended primary method per Astral docs (https://docs.astral.sh/uv/getting-started/installation/)
  if command -v curl >/dev/null 2>&1; then
    echo "Installing uv into ${target_dir} via official installer (curl)..." >&2
    if curl -LsSf https://astral.sh/uv/install.sh | \
      UV_INSTALL_DIR="$target_dir" INSTALLER_NO_MODIFY_PATH=1 sh >&2; then
      hash -r 2>/dev/null || true
      if [[ -x "${target_dir}/uv" ]]; then
        echo "uv installed at: ${target_dir}/uv" >&2
        return 0
      fi
    fi
  elif command -v wget >/dev/null 2>&1; then
    echo "Installing uv into ${target_dir} via official installer (wget)..." >&2
    if wget -qO- https://astral.sh/uv/install.sh | \
      UV_INSTALL_DIR="$target_dir" INSTALLER_NO_MODIFY_PATH=1 sh >&2; then
      hash -r 2>/dev/null || true
      if [[ -x "${target_dir}/uv" ]]; then
        echo "uv installed at: ${target_dir}/uv" >&2
        return 0
      fi
    fi
  fi

  # ── 3. Homebrew Fallback (macOS / Linux) ──────────────────────────────────
  if command -v brew >/dev/null 2>&1; then
    echo "Installing uv via Homebrew..." >&2
    if brew install uv >&2; then
      hash -r 2>/dev/null || true
      local brew_uv
      brew_uv="$(command -v uv 2>/dev/null || true)"
      if [[ -n "$brew_uv" && -x "$brew_uv" ]]; then
        ln -sf "$brew_uv" "${target_dir}/uv" 2>/dev/null || true
        echo "uv installed via Homebrew at: ${brew_uv}" >&2
        return 0
      fi
    fi
  fi

  # ── 4. pip / pip3 Fallback ───────────────────────────────────────────────
  local PIP_BIN=""
  if [[ -x "${target_dir}/pip" ]];  then PIP_BIN="${target_dir}/pip"
  elif [[ -x "${target_dir}/pip3" ]]; then PIP_BIN="${target_dir}/pip3"
  elif command -v pip >/dev/null 2>&1;  then PIP_BIN="pip"
  elif command -v pip3 >/dev/null 2>&1; then PIP_BIN="pip3"
  fi

  if [[ -n "$PIP_BIN" ]]; then
    echo "Installing uv via ${PIP_BIN} install uv..." >&2
    if "$PIP_BIN" install --quiet uv >&2; then
      hash -r 2>/dev/null || true

      local real_pip pip_bin_dir uv_in_py_bin
      real_pip="$(readlink -f "$PIP_BIN" 2>/dev/null || realpath "$PIP_BIN" 2>/dev/null || true)"
      if [[ -n "$real_pip" ]]; then
        pip_bin_dir="$(dirname "$real_pip")"
        uv_in_py_bin="${pip_bin_dir}/uv"
      fi

      if [[ -x "${target_dir}/uv" ]]; then
        echo "uv installed at: ${target_dir}/uv" >&2
        return 0
      fi

      if [[ -n "${uv_in_py_bin:-}" && -x "$uv_in_py_bin" ]]; then
        ln -sf "$uv_in_py_bin" "${target_dir}/uv"
        echo "uv installed at: ${target_dir}/uv -> ${uv_in_py_bin}" >&2
        return 0
      fi

      if command -v uv >/dev/null 2>&1; then
        echo "uv installed at: $(command -v uv)" >&2
        return 0
      fi
    fi
  fi

  # ── 5. Cargo Fallback (Rust) ──────────────────────────────────────────────
  if command -v cargo >/dev/null 2>&1; then
    echo "Installing uv via cargo..." >&2
    if cargo install --locked uv --root "$target_dir" >&2; then
      hash -r 2>/dev/null || true
      if [[ -x "${target_dir}/bin/uv" ]]; then
        ln -sf "${target_dir}/bin/uv" "${target_dir}/uv" 2>/dev/null || true
        echo "uv installed via cargo at: ${target_dir}/uv" >&2
        return 0
      fi
    fi
  fi

  echo "Failed to install uv automatically. All methods (standalone installer, Homebrew, pip, cargo) were unavailable or failed." >&2
  echo "Please install uv manually (https://docs.astral.sh/uv/getting-started/installation/), then retry." >&2
  return 127
}

ensure_snow() {
  if [[ -x "${FREVANA_BIN_DIR}/snow" ]] && verify_snow_binary "${FREVANA_BIN_DIR}/snow"; then
    SNOW_BIN="${FREVANA_BIN_DIR}/snow"
    return
  fi

  if command -v snow >/dev/null 2>&1; then
    if verify_snow_binary "snow"; then
      SNOW_BIN="$(command -v snow)"
      (umask 077; mkdir -p "$FREVANA_BIN_DIR")
      local real_snow
      real_snow="$(readlink -f "$SNOW_BIN" 2>/dev/null || realpath "$SNOW_BIN" 2>/dev/null || printf '%s' "$SNOW_BIN")"
      if [[ -n "$real_snow" && "$real_snow" != "${FREVANA_BIN_DIR}/snow" && -x "$real_snow" ]]; then
        ln -sf "$real_snow" "${FREVANA_BIN_DIR}/snow" 2>/dev/null || true
      fi
      return
    fi
    die "A command named 'snow' exists but is not a working Snowflake CLI executable"
  fi

  # Resolve uv; install it automatically if missing.
  local UV_BIN
  UV_BIN="$(resolve_uv 2>/dev/null || true)"
  if [[ -z "$UV_BIN" ]]; then
    install_uv
    UV_BIN="$(resolve_uv 2>/dev/null || true)"
    if [[ -z "$UV_BIN" ]]; then
      echo "uv installation did not produce a usable uv binary." >&2
      echo "Install uv manually (https://docs.astral.sh/uv/getting-started/installation/), then retry." >&2
      exit 127
    fi
  fi

  echo "Snowflake CLI executable 'snow' was not found. Installing with: uv tool install snowflake-cli" >&2
  "$UV_BIN" tool install snowflake-cli 1>&2
  hash -r 2>/dev/null || true

  if command -v snow >/dev/null 2>&1; then
    SNOW_BIN="$(command -v snow)"
  else
    local uv_bin_dir
    uv_bin_dir="$("$UV_BIN" tool dir --bin 2>/dev/null || true)"
    if [[ -z "$uv_bin_dir" ]]; then
      # Fallback: derive bin dir from uv tool dir (tools dir lives at <uv_data>/tools,
      # bin dir is typically <uv_data>/../../bin → ~/.local/bin on Linux/macOS).
      local uv_tools_dir
      uv_tools_dir="$("$UV_BIN" tool dir 2>/dev/null || true)"
      if [[ -n "$uv_tools_dir" ]]; then
        uv_bin_dir="$(dirname "$(dirname "$uv_tools_dir")")/bin"
      fi
    fi
    if [[ -z "$uv_bin_dir" ]]; then
      uv_bin_dir="$HOME/.local/bin"
    fi
    if [[ -x "${uv_bin_dir}/snow" ]]; then
      SNOW_BIN="${uv_bin_dir}/snow"
    else
      echo "Snowflake CLI was installed, but 'snow' is not available on PATH." >&2
      echo "Run '$UV_BIN tool update-shell', restart the shell, and retry." >&2
      exit 127
    fi
  fi

  verify_snow_binary "$SNOW_BIN" ||
    die "Installed 'snow' executable failed Snowflake CLI verification"

  (umask 077; mkdir -p "${FREVANA_BIN_DIR}")
  local real_snow
  real_snow="$(readlink -f "$SNOW_BIN" 2>/dev/null || realpath "$SNOW_BIN" 2>/dev/null || printf '%s' "$SNOW_BIN")"
  if [[ -n "$real_snow" && "$real_snow" != "${FREVANA_BIN_DIR}/snow" && -x "$real_snow" ]]; then
    ln -sf "$real_snow" "${FREVANA_BIN_DIR}/snow" 2>/dev/null || true
  fi

  echo "Snowflake CLI installation verified." >&2
}

default_output() {
  mkdir -p out
  local output_prefix="out/snowflake-$(date -u +%Y%m%dT%H%M%SZ)-$$"
  local candidate=""
  local attempt=0
  while (( attempt < 100 )); do
    candidate="${output_prefix}-${RANDOM}-${RANDOM}.json"
    if (umask 077; set -C; : >"$candidate") 2>/dev/null; then
      printf '%s' "$candidate"
      return
    fi
    attempt=$((attempt + 1))
  done
  die "Unable to reserve a unique Snowflake output file"
}

prepare_explicit_output() {
  local output="$1"
  mkdir -p "$(dirname "$output")"
  if [[ -e "$output" ]]; then
    [[ -f "$output" && ! -L "$output" ]] ||
      die "Output path must be a regular file and not a symlink: $output"
    local output_owner
    output_owner="$(file_owner_id "$output")"
    [[ -n "$output_owner" && "$output_owner" == "$(id -u)" ]] ||
      die "Existing output file must be owned by the current user: $output"
  else
    (umask 077; set -C; : >"$output") 2>/dev/null ||
      die "Unable to reserve output file: $output"
  fi
  chmod 600 "$output"
}

run_and_save() {
  local output="$1"
  local generated_output=false
  shift
  if [[ -z "$output" ]]; then
    output="$(default_output)"
    generated_output=true
  else
    prepare_explicit_output "$output"
  fi

  local temp_file
  temp_file="$(mktemp)"
  local status=0
  "$@" >"$temp_file" || status=$?
  if [[ -s "$temp_file" ]]; then
    cp "$temp_file" "$output"
    chmod 600 "$output"
    cat "$temp_file"
    echo "Saved output to $output" >&2
  elif [[ "$generated_output" == true ]]; then
    rm -f "$output"
  fi
  rm -f "$temp_file"
  return "$status"
}

add_global_config() {
  SNOW_CMD=("$SNOW_BIN")
  if [[ -n "${CONFIG_FILE:-}" ]]; then
    SNOW_CMD+=(--config-file "$CONFIG_FILE")
  fi
}

add_context_options() {
  [[ -z "${CONNECTION:-}" ]] || SNOW_CMD+=(--connection "$CONNECTION")
  [[ -z "${DATABASE:-}" ]] || SNOW_CMD+=(--database "$DATABASE")
  [[ -z "${SCHEMA_NAME:-}" ]] || SNOW_CMD+=(--schema "$SCHEMA_NAME")
  [[ -z "${ROLE:-}" ]] || SNOW_CMD+=(--role "$ROLE")
  [[ -z "${WAREHOUSE:-}" ]] || SNOW_CMD+=(--warehouse "$WAREHOUSE")
}

is_read_only_sql() {
  local sql="$1"
  local normalized
  normalized="$(printf '%s' "$sql" |
    sed -E 's/--.*$//g' |
    tr '\n\r\t' '   ' |
    sed -E 's/^[[:space:]]+//; s/[[:space:]]+/ /g' |
    tr '[:lower:]' '[:upper:]')"

  [[ -n "$normalized" ]] || return 1

  if printf '%s' "$normalized" | grep -Eq '(^|[^A-Z_])(INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|DROP|TRUNCATE|COPY|PUT|GET|REMOVE|GRANT|REVOKE|CALL|EXECUTE|BEGIN|COMMIT|ROLLBACK|UNDROP)([^A-Z_]|$)'; then
    return 1
  fi

  if printf '%s' "$normalized" | grep -Eq 'SYSTEM[$][A-Z0-9_]+'; then
    return 1
  fi

  printf '%s' "$normalized" | grep -Eq '^(SELECT|SHOW|DESCRIBE|DESC|EXPLAIN|WITH)([[:space:](;]|$)|^!(QUERIES|RESULT)([[:space:]]|$)'
}

read_sql_file() {
  local path="$1"
  [[ -f "$path" ]] || die "SQL file not found: $path"
  [[ -r "$path" ]] || die "SQL file is not readable: $path"
  SQL_CONTENT="$(<"$path")"
}

validate_object_definition() {
  local object_type="$1"
  local path="$2"
  object_type="$(printf '%s' "$object_type" | tr '[:upper:]' '[:lower:]')"
  local size_bytes
  size_bytes="$(wc -c <"$path" | tr -d '[:space:]')"
  [[ "$size_bytes" =~ ^[0-9]+$ ]] || die "Unable to determine object definition size: $path"
  (( size_bytes <= 32768 )) ||
    die "Object definition exceeds the safe 32768-byte command-line limit; use reviewed DDL with query --file"
  [[ "$object_type" != "secret" ]] ||
    die "Creating secret objects from JSON is disabled because Snowflake CLI exposes --json in process arguments; use reviewed DDL with query --file"
  if grep -Eiq '"[^"]*(password|passphrase|private[_-]?key|token|secret[_-]?(string|value)?|credential)[^"]*"[[:space:]]*:' "$path"; then
    die "Object definition appears to contain sensitive fields that would be exposed in process arguments; use reviewed DDL with query --file"
  fi
}

COMMAND="${1-}"
[[ -n "$COMMAND" ]] || {
  usage
  exit 2
}
shift

case "$COMMAND" in
  check)
    [[ $# -eq 0 ]] || die "check does not accept options"
    ensure_snow
    "$SNOW_BIN" --help >/dev/null
    "$SNOW_BIN" --version
    ;;

  connection-list)
    CONFIG_FILE=""
    OUTPUT=""
    INCLUDE_ALL=false
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --all) INCLUDE_ALL=true; shift ;;
        --config-file) require_value "$1" "${2-}"; CONFIG_FILE="$2"; shift 2 ;;
        --output) require_value "$1" "${2-}"; OUTPUT="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) die "Unknown connection-list option: $1" ;;
      esac
    done
    ensure_snow
    add_global_config
    SNOW_CMD+=(connection list)
    [[ "$INCLUDE_ALL" == true ]] && SNOW_CMD+=(--all)
    SNOW_CMD+=(--format JSON_EXT --enhanced-exit-codes)
    run_and_save "$OUTPUT" "${SNOW_CMD[@]}"
    ;;

  config-info)
    CONFIG_FILE=""
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --config-file) require_value "$1" "${2-}"; CONFIG_FILE="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) die "Unknown config-info option: $1" ;;
      esac
    done
    ensure_snow
    RESOLVED_CONFIG_FILE="$(resolve_config_file "$CONFIG_FILE")"
    RESOLVED_CONFIG_DIR="$(dirname "$RESOLVED_CONFIG_FILE")"
    RESOLVED_CONNECTIONS_FILE="$RESOLVED_CONFIG_DIR/connections.toml"
    CONFIG_EXISTS=false
    CONNECTIONS_EXISTS=false
    [[ -f "$RESOLVED_CONFIG_FILE" ]] && CONFIG_EXISTS=true
    [[ -f "$RESOLVED_CONNECTIONS_FILE" ]] && CONNECTIONS_EXISTS=true
    CONNECTION_SOURCE="$RESOLVED_CONFIG_FILE"
    [[ "$CONNECTIONS_EXISTS" == true ]] && CONNECTION_SOURCE="$RESOLVED_CONNECTIONS_FILE"
    printf '{"config_file":"%s","config_exists":%s,"connections_file":"%s","connections_exists":%s,"connection_source":"%s"}\n' \
      "$(json_escape "$RESOLVED_CONFIG_FILE")" \
      "$CONFIG_EXISTS" \
      "$(json_escape "$RESOLVED_CONNECTIONS_FILE")" \
      "$CONNECTIONS_EXISTS" \
      "$(json_escape "$CONNECTION_SOURCE")"
    ;;

  connection-test)
    CONFIG_FILE=""
    OUTPUT=""
    CONNECTION=""
    ENABLE_DIAG=false
    DIAG_LOG_PATH=""
    DIAG_ALLOWLIST_PATH=""
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --connection) require_value "$1" "${2-}"; CONNECTION="$2"; safe_name "$CONNECTION" || die "Invalid connection name"; shift 2 ;;
        --enable-diag) ENABLE_DIAG=true; shift ;;
        --diag-log-path) require_value "$1" "${2-}"; DIAG_LOG_PATH="$2"; shift 2 ;;
        --diag-allowlist-path) require_value "$1" "${2-}"; DIAG_ALLOWLIST_PATH="$2"; shift 2 ;;
        --config-file) require_value "$1" "${2-}"; CONFIG_FILE="$2"; shift 2 ;;
        --output) require_value "$1" "${2-}"; OUTPUT="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) die "Unknown connection-test option: $1" ;;
      esac
    done
    ensure_snow
    add_global_config
    SNOW_CMD+=(connection test)
    [[ -z "$CONNECTION" ]] || SNOW_CMD+=(--connection "$CONNECTION")
    if [[ "$ENABLE_DIAG" == true ]]; then
      [[ -n "$DIAG_LOG_PATH" ]] || die "--enable-diag requires --diag-log-path"
      [[ "$DIAG_LOG_PATH" == /* ]] || die "--diag-log-path must be absolute"
      SNOW_CMD+=(--enable-diag --diag-log-path "$DIAG_LOG_PATH")
      if [[ -n "$DIAG_ALLOWLIST_PATH" ]]; then
        [[ "$DIAG_ALLOWLIST_PATH" == /* ]] || die "--diag-allowlist-path must be absolute"
        [[ -f "$DIAG_ALLOWLIST_PATH" ]] || die "Diagnostic allowlist file not found: $DIAG_ALLOWLIST_PATH"
        SNOW_CMD+=(--diag-allowlist-path "$DIAG_ALLOWLIST_PATH")
      fi
    else
      [[ -z "$DIAG_LOG_PATH" ]] || die "--diag-log-path requires --enable-diag"
      [[ -z "$DIAG_ALLOWLIST_PATH" ]] || die "--diag-allowlist-path requires --enable-diag"
    fi
    SNOW_CMD+=(--format JSON_EXT --enhanced-exit-codes)
    run_and_save "$OUTPUT" "${SNOW_CMD[@]}"
    ;;

  setup-pat|connection-add|connection-add-pat)
    CONFIG_FILE=""
    OUTPUT=""
    NAME=""
    ACCOUNT=""
    USER_NAME=""
    ROLE=""
    WAREHOUSE=""
    DATABASE=""
    SCHEMA_NAME=""
    AUTHENTICATOR=""
    PRIVATE_KEY_FILE=""
    TOKEN_FILE_PATH=""
    PAT_ENV_NAME=""
    WIF_PROVIDER=""
    MAKE_DEFAULT=false
    SKIP_TEST=false
    STORE_PAT=false
    EXECUTE=false
    PAT_MODE=false
    SETUP_PAT_MODE=false
    if [[ "$COMMAND" == "setup-pat" ]]; then
      PAT_MODE=true
      SETUP_PAT_MODE=true
      NAME="${SNOWFLAKE_DEFAULT_CONNECTION_NAME:-${SNOWFLAKE_CONNECTION_NAME:-default}}"
      MAKE_DEFAULT=true
    elif [[ "$COMMAND" == "connection-add-pat" ]]; then
      PAT_MODE=true
    fi
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --name) require_value "$1" "${2-}"; NAME="$2"; safe_name "$NAME" || die "Invalid connection name"; shift 2 ;;
        --account) require_value "$1" "${2-}"; ACCOUNT="$2"; shift 2 ;;
        --user) require_value "$1" "${2-}"; USER_NAME="$2"; shift 2 ;;
        --role) require_value "$1" "${2-}"; ROLE="$2"; shift 2 ;;
        --warehouse) require_value "$1" "${2-}"; WAREHOUSE="$2"; shift 2 ;;
        --database) require_value "$1" "${2-}"; DATABASE="$2"; shift 2 ;;
        --schema) require_value "$1" "${2-}"; SCHEMA_NAME="$2"; shift 2 ;;
        --authenticator) require_value "$1" "${2-}"; AUTHENTICATOR="$(printf '%s' "$2" | tr '[:lower:]' '[:upper:]')"; shift 2 ;;
        --private-key-file) require_value "$1" "${2-}"; PRIVATE_KEY_FILE="$2"; shift 2 ;;
        --token-file|--token-file-path) require_value "$1" "${2-}"; TOKEN_FILE_PATH="$2"; shift 2 ;;
        --token-env) require_value "$1" "${2-}"; PAT_ENV_NAME="$2"; shift 2 ;;
        --workload-identity-provider) require_value "$1" "${2-}"; WIF_PROVIDER="$(printf '%s' "$2" | tr '[:lower:]' '[:upper:]')"; valid_wif_provider "$WIF_PROVIDER" || die "Invalid workload identity provider"; shift 2 ;;
        --default) MAKE_DEFAULT=true; shift ;;
        --no-default) MAKE_DEFAULT=false; shift ;;
        --skip-test) SKIP_TEST=true; shift ;;
        --config-file) require_value "$1" "${2-}"; CONFIG_FILE="$2"; shift 2 ;;
        --output) require_value "$1" "${2-}"; OUTPUT="$2"; shift 2 ;;
        --execute) EXECUTE=true; shift ;;
        --password|--token|--oauth-client-secret|--private-key|--mfa-passcode)
          die "$1 is intentionally unsupported; use protected files or environment variables"
          ;;
        -h|--help) usage; exit 0 ;;
        *) die "Unknown ${COMMAND} option: $1" ;;
      esac
    done
    if [[ "$SETUP_PAT_MODE" != true ]]; then
      [[ "$SKIP_TEST" == false ]] || die "--skip-test is only supported by setup-pat"
    fi
    if [[ "$COMMAND" == "connection-add" && "$AUTHENTICATOR" == "PROGRAMMATIC_ACCESS_TOKEN" ]]; then
      PAT_MODE=true
    fi
    ADD_CONFIG_FILE="$(resolve_config_file "$CONFIG_FILE")"
    ADD_CONNECTIONS_FILE="$(dirname "$ADD_CONFIG_FILE")/connections.toml"
    [[ ! -f "$ADD_CONNECTIONS_FILE" ]] ||
      die "connections.toml is active at $ADD_CONNECTIONS_FILE. Snowflake CLI would ignore a connection added to config.toml. Add the shared connection to connections.toml or use --config-file in a directory without connections.toml."
    [[ -n "$NAME" ]] || die "${COMMAND} requires --name"
    if [[ "$PAT_MODE" == true ]]; then
      if [[ "$SETUP_PAT_MODE" == true ]]; then
        ACCOUNT="${ACCOUNT:-$(connection_env_value "$NAME" ACCOUNT)}"
        ACCOUNT="${ACCOUNT:-${SNOWFLAKE_ACCOUNT:-}}"
        USER_NAME="${USER_NAME:-$(connection_env_value "$NAME" USER)}"
        USER_NAME="${USER_NAME:-${SNOWFLAKE_USER:-}}"
        ROLE="${ROLE:-$(connection_env_value "$NAME" ROLE)}"
        ROLE="${ROLE:-${SNOWFLAKE_ROLE:-}}"
        WAREHOUSE="${WAREHOUSE:-$(connection_env_value "$NAME" WAREHOUSE)}"
        WAREHOUSE="${WAREHOUSE:-${SNOWFLAKE_WAREHOUSE:-}}"
        DATABASE="${DATABASE:-$(connection_env_value "$NAME" DATABASE)}"
        DATABASE="${DATABASE:-${SNOWFLAKE_DATABASE:-}}"
        SCHEMA_NAME="${SCHEMA_NAME:-$(connection_env_value "$NAME" SCHEMA)}"
        SCHEMA_NAME="${SCHEMA_NAME:-${SNOWFLAKE_SCHEMA:-}}"
      fi
      [[ -n "$ACCOUNT" ]] || die "${COMMAND} requires --account or SNOWFLAKE_ACCOUNT"
      [[ -n "$USER_NAME" ]] || die "${COMMAND} requires --user or SNOWFLAKE_USER"
      if [[ "$SETUP_PAT_MODE" == true ]]; then
        CONNECTION_TOKEN_FILE_ENV="$(connection_env_name "$NAME" TOKEN_FILE_PATH 2>/dev/null || true)"
        if [[ -z "$TOKEN_FILE_PATH" && -n "$CONNECTION_TOKEN_FILE_ENV" && -n "$(printenv "$CONNECTION_TOKEN_FILE_ENV" 2>/dev/null || true)" ]]; then
          TOKEN_FILE_PATH="$(printenv "$CONNECTION_TOKEN_FILE_ENV")"
        elif [[ -z "$TOKEN_FILE_PATH" && -n "${SNOWFLAKE_TOKEN_FILE_PATH:-}" ]]; then
          TOKEN_FILE_PATH="$SNOWFLAKE_TOKEN_FILE_PATH"
        fi

        if [[ -z "$TOKEN_FILE_PATH" ]]; then
          TOKEN_FILE_PATH="$(default_pat_file "$NAME" "$CONFIG_FILE")"
        fi
        [[ "$TOKEN_FILE_PATH" == /* ]] || die "setup-pat --token-file must be an absolute path"

        if [[ -e "$TOKEN_FILE_PATH" ]]; then
          validate_pat_file "$TOKEN_FILE_PATH"
        else
          if [[ -z "$PAT_ENV_NAME" ]]; then
            CONNECTION_TOKEN_ENV="$(connection_env_name "$NAME" TOKEN 2>/dev/null || true)"
            if [[ -n "$CONNECTION_TOKEN_ENV" && -n "$(printenv "$CONNECTION_TOKEN_ENV" 2>/dev/null || true)" ]]; then
              PAT_ENV_NAME="$CONNECTION_TOKEN_ENV"
            elif [[ -n "${SNOWFLAKE_PAT:-}" ]]; then
              PAT_ENV_NAME="SNOWFLAKE_PAT"
            elif [[ -n "${SNOWFLAKE_TOKEN:-}" ]]; then
              PAT_ENV_NAME="SNOWFLAKE_TOKEN"
            else
              PAT_ENV_NAME="SNOWFLAKE_PAT"
            fi
          fi
          validate_pat_env "$PAT_ENV_NAME"
          STORE_PAT=true
        fi
      else
        [[ -n "$TOKEN_FILE_PATH" ]] || die "${COMMAND} requires --token-file"
      fi
      [[ -z "$AUTHENTICATOR" || "$AUTHENTICATOR" == "PROGRAMMATIC_ACCESS_TOKEN" ]] ||
        die "${COMMAND} does not accept another authenticator"
      [[ -z "$PRIVATE_KEY_FILE" ]] || die "${COMMAND} does not accept --private-key-file"
      [[ -z "$WIF_PROVIDER" ]] || die "${COMMAND} does not accept --workload-identity-provider"
      AUTHENTICATOR="PROGRAMMATIC_ACCESS_TOKEN"
      if [[ "$SETUP_PAT_MODE" != true ]]; then
        validate_pat_file "$TOKEN_FILE_PATH"
      fi
    fi
    if [[ -n "$TOKEN_FILE_PATH" && "$PAT_MODE" != true ]]; then
      validate_protected_file "$TOKEN_FILE_PATH" "Token file"
    fi
    if [[ -n "$PRIVATE_KEY_FILE" ]]; then
      validate_protected_file "$PRIVATE_KEY_FILE" "Private key file"
    fi
    ensure_snow
    if [[ "$SETUP_PAT_MODE" == true && "$STORE_PAT" == true && "$EXECUTE" == true ]]; then
      store_pat_from_env "$PAT_ENV_NAME" "$TOKEN_FILE_PATH"
    fi
    add_global_config
    SNOW_CMD+=(connection add --connection-name "$NAME" --no-interactive)
    [[ -z "$ACCOUNT" ]] || SNOW_CMD+=(--account "$ACCOUNT")
    [[ -z "$USER_NAME" ]] || SNOW_CMD+=(--user "$USER_NAME")
    [[ -z "$ROLE" ]] || SNOW_CMD+=(--role "$ROLE")
    [[ -z "$WAREHOUSE" ]] || SNOW_CMD+=(--warehouse "$WAREHOUSE")
    [[ -z "$DATABASE" ]] || SNOW_CMD+=(--database "$DATABASE")
    [[ -z "$SCHEMA_NAME" ]] || SNOW_CMD+=(--schema "$SCHEMA_NAME")
    [[ -z "$AUTHENTICATOR" ]] || SNOW_CMD+=(--authenticator "$AUTHENTICATOR")
    [[ -z "$PRIVATE_KEY_FILE" ]] || SNOW_CMD+=(--private-key-file "$PRIVATE_KEY_FILE")
    [[ -z "$TOKEN_FILE_PATH" ]] || SNOW_CMD+=(--token-file-path "$TOKEN_FILE_PATH")
    [[ -z "$WIF_PROVIDER" ]] || SNOW_CMD+=(--workload-identity-provider "$WIF_PROVIDER")
    [[ "$MAKE_DEFAULT" == true ]] && SNOW_CMD+=(--default)
    SNOW_CMD+=(--format JSON_EXT --enhanced-exit-codes)
    if [[ "$EXECUTE" != true ]]; then
      if [[ "$SETUP_PAT_MODE" == true ]]; then
        if [[ "$STORE_PAT" == true ]]; then
          SETUP_TOKEN_ACTION="read PAT from ${PAT_ENV_NAME} and store it at ${TOKEN_FILE_PATH} with mode 0600"
        else
          SETUP_TOKEN_ACTION="reuse protected PAT file ${TOKEN_FILE_PATH}"
        fi
        if [[ "$SKIP_TEST" == true ]]; then
          preview "$COMMAND" "$SETUP_TOKEN_ACTION" "then run" "${SNOW_CMD[@]}"
        else
          preview "$COMMAND" \
            "$SETUP_TOKEN_ACTION" \
            "then run" \
            "${SNOW_CMD[@]}" \
            "and test connection ${NAME}"
        fi
      else
        preview "$COMMAND" "${SNOW_CMD[@]}"
      fi
      exit 0
    fi
    run_and_save "$OUTPUT" "${SNOW_CMD[@]}"
    if [[ "$SETUP_PAT_MODE" == true && "$SKIP_TEST" != true ]]; then
      TEST_OUTPUT=""
      if [[ -n "$OUTPUT" ]]; then
        if [[ "$OUTPUT" == *.json ]]; then
          TEST_OUTPUT="${OUTPUT%.json}.test.json"
        else
          TEST_OUTPUT="${OUTPUT}.test.json"
        fi
      fi
      add_global_config
      SNOW_CMD+=(connection test --connection "$NAME" --format JSON_EXT --enhanced-exit-codes)
      run_and_save "$TEST_OUTPUT" "${SNOW_CMD[@]}"
    fi
    ;;

  connection-set-default|connection-remove)
    CONFIG_FILE=""
    OUTPUT=""
    NAME=""
    EXECUTE=false
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --name) require_value "$1" "${2-}"; NAME="$2"; safe_name "$NAME" || die "Invalid connection name"; shift 2 ;;
        --config-file) require_value "$1" "${2-}"; CONFIG_FILE="$2"; shift 2 ;;
        --output) require_value "$1" "${2-}"; OUTPUT="$2"; shift 2 ;;
        --execute) EXECUTE=true; shift ;;
        -h|--help) usage; exit 0 ;;
        *) die "Unknown ${COMMAND} option: $1" ;;
      esac
    done
    [[ -n "$NAME" ]] || die "${COMMAND} requires --name"
    if [[ "$COMMAND" == "connection-remove" ]]; then
      REMOVE_CONFIG_FILE="$(resolve_config_file "$CONFIG_FILE")"
      REMOVE_CONNECTIONS_FILE="$(dirname "$REMOVE_CONFIG_FILE")/connections.toml"
      [[ ! -f "$REMOVE_CONNECTIONS_FILE" ]] ||
        die "connections.toml is active at $REMOVE_CONNECTIONS_FILE. Snowflake CLI connection remove only edits config.toml; remove the reviewed entry from connections.toml instead."
    fi
    ensure_snow
    add_global_config
    if [[ "$COMMAND" == "connection-set-default" ]]; then
      SNOW_CMD+=(connection set-default "$NAME")
    else
      SNOW_CMD+=(connection remove "$NAME")
    fi
    SNOW_CMD+=(--format JSON_EXT --enhanced-exit-codes)
    if [[ "$EXECUTE" != true ]]; then
      preview "$COMMAND" "${SNOW_CMD[@]}"
      exit 0
    fi
    run_and_save "$OUTPUT" "${SNOW_CMD[@]}"
    ;;

  query)
    CONFIG_FILE=""
    OUTPUT=""
    CONNECTION=""
    DATABASE=""
    SCHEMA_NAME=""
    ROLE=""
    WAREHOUSE=""
    SQL=""
    SQL_FILE=""
    FORMAT="JSON_EXT"
    TEMPLATING="STANDARD"
    SINGLE_TRANSACTION=false
    PREVIEW_ONLY=false
    EXECUTE=false
    VARIABLES=()
    ENV_OVERRIDES=()
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --sql) require_value "$1" "${2-}"; SQL="$2"; shift 2 ;;
        --file) require_value "$1" "${2-}"; SQL_FILE="$2"; shift 2 ;;
        --connection) require_value "$1" "${2-}"; CONNECTION="$2"; safe_name "$CONNECTION" || die "Invalid connection name"; shift 2 ;;
        --config-file) require_value "$1" "${2-}"; CONFIG_FILE="$2"; shift 2 ;;
        --database) require_value "$1" "${2-}"; DATABASE="$2"; shift 2 ;;
        --schema) require_value "$1" "${2-}"; SCHEMA_NAME="$2"; shift 2 ;;
        --role) require_value "$1" "${2-}"; ROLE="$2"; shift 2 ;;
        --warehouse) require_value "$1" "${2-}"; WAREHOUSE="$2"; shift 2 ;;
        --variable) require_value "$1" "${2-}"; [[ "$2" == *=* ]] || die "--variable requires key=value"; VARIABLES+=("$2"); shift 2 ;;
        --env) require_value "$1" "${2-}"; [[ "$2" == *=* ]] || die "--env requires key=value"; ENV_OVERRIDES+=("$2"); shift 2 ;;
        --templating) require_value "$1" "${2-}"; TEMPLATING="$(printf '%s' "$2" | tr '[:lower:]' '[:upper:]')"; valid_templating "$TEMPLATING" || die "Invalid templating mode"; shift 2 ;;
        --format) require_value "$1" "${2-}"; FORMAT="$(printf '%s' "$2" | tr '[:lower:]' '[:upper:]')"; valid_format "$FORMAT" || die "Invalid format"; shift 2 ;;
        --single-transaction) SINGLE_TRANSACTION=true; shift ;;
        --preview) PREVIEW_ONLY=true; shift ;;
        --output) require_value "$1" "${2-}"; OUTPUT="$2"; shift 2 ;;
        --execute) EXECUTE=true; shift ;;
        -h|--help) usage; exit 0 ;;
        *) die "Unknown query option: $1" ;;
      esac
    done
    [[ -n "$SQL" || -n "$SQL_FILE" ]] || die "query requires exactly one of --sql or --file"
    [[ -z "$SQL" || -z "$SQL_FILE" ]] || die "query accepts only one of --sql or --file"
    if [[ -n "$SQL_FILE" ]]; then
      read_sql_file "$SQL_FILE"
    else
      SQL_CONTENT="$SQL"
    fi
    ensure_snow
    add_global_config
    SNOW_CMD+=(sql)
    if [[ -n "$SQL_FILE" ]]; then
      SNOW_CMD+=(--filename "$SQL_FILE")
    else
      SNOW_CMD+=(--query "$SQL")
    fi
    add_context_options
    local_item=""
    if [[ ${#VARIABLES[@]} -gt 0 ]]; then
      for local_item in "${VARIABLES[@]}"; do SNOW_CMD+=(--variable "$local_item"); done
    fi
    if [[ ${#ENV_OVERRIDES[@]} -gt 0 ]]; then
      for local_item in "${ENV_OVERRIDES[@]}"; do SNOW_CMD+=(--env "$local_item"); done
    fi
    SNOW_CMD+=(--enable-templating "$TEMPLATING" --local-only)
    [[ "$SINGLE_TRANSACTION" == true ]] && SNOW_CMD+=(--single-transaction)
    SNOW_CMD+=(--format "$FORMAT" --enhanced-exit-codes)
    if [[ "$PREVIEW_ONLY" == true ]] || { ! is_read_only_sql "$SQL_CONTENT" && [[ "$EXECUTE" != true ]]; }; then
      preview "query" "${SNOW_CMD[@]}"
      exit 0
    fi
    run_and_save "$OUTPUT" "${SNOW_CMD[@]}"
    ;;

  object-list|object-describe|object-create|object-drop)
    CONFIG_FILE=""
    OUTPUT=""
    CONNECTION=""
    DATABASE=""
    SCHEMA_NAME=""
    ROLE=""
    WAREHOUSE=""
    TYPE=""
    IDENTIFIER=""
    DEFINITION_FILE=""
    FORMAT="JSON_EXT"
    EXECUTE=false
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --type) require_value "$1" "${2-}"; TYPE="$2"; safe_name "$TYPE" || die "Invalid object type"; shift 2 ;;
        --identifier) require_value "$1" "${2-}"; IDENTIFIER="$2"; shift 2 ;;
        --definition-file) require_value "$1" "${2-}"; DEFINITION_FILE="$2"; shift 2 ;;
        --connection) require_value "$1" "${2-}"; CONNECTION="$2"; safe_name "$CONNECTION" || die "Invalid connection name"; shift 2 ;;
        --config-file) require_value "$1" "${2-}"; CONFIG_FILE="$2"; shift 2 ;;
        --database) require_value "$1" "${2-}"; DATABASE="$2"; shift 2 ;;
        --schema) require_value "$1" "${2-}"; SCHEMA_NAME="$2"; shift 2 ;;
        --role) require_value "$1" "${2-}"; ROLE="$2"; shift 2 ;;
        --warehouse) require_value "$1" "${2-}"; WAREHOUSE="$2"; shift 2 ;;
        --format) require_value "$1" "${2-}"; FORMAT="$(printf '%s' "$2" | tr '[:lower:]' '[:upper:]')"; valid_format "$FORMAT" || die "Invalid format"; shift 2 ;;
        --output) require_value "$1" "${2-}"; OUTPUT="$2"; shift 2 ;;
        --execute) EXECUTE=true; shift ;;
        -h|--help) usage; exit 0 ;;
        *) die "Unknown ${COMMAND} option: $1" ;;
      esac
    done
    [[ -n "$TYPE" ]] || die "${COMMAND} requires --type"
    ensure_snow
    add_global_config
    case "$COMMAND" in
      object-list)
        SNOW_CMD+=(object list "$TYPE")
        ;;
      object-describe)
        [[ -n "$IDENTIFIER" ]] || die "object-describe requires --identifier"
        SNOW_CMD+=(object describe "$TYPE" "$IDENTIFIER")
        ;;
      object-create)
        [[ -n "$DEFINITION_FILE" ]] || die "object-create requires --definition-file"
        [[ -f "$DEFINITION_FILE" && -r "$DEFINITION_FILE" ]] || die "Definition file is not readable: $DEFINITION_FILE"
        validate_object_definition "$TYPE" "$DEFINITION_FILE"
        OBJECT_DEFINITION="$(<"$DEFINITION_FILE")"
        [[ -n "$OBJECT_DEFINITION" ]] || die "Definition file is empty"
        SNOW_CMD+=(object create "$TYPE" --json "$OBJECT_DEFINITION")
        ;;
      object-drop)
        [[ -n "$IDENTIFIER" ]] || die "object-drop requires --identifier"
        SNOW_CMD+=(object drop "$TYPE" "$IDENTIFIER")
        ;;
    esac
    add_context_options
    SNOW_CMD+=(--format "$FORMAT" --enhanced-exit-codes)
    if [[ "$COMMAND" == "object-create" || "$COMMAND" == "object-drop" ]]; then
      if [[ "$EXECUTE" != true ]]; then
        PREVIEW_CMD=("${SNOW_CMD[@]}")
        if [[ "$COMMAND" == "object-create" ]]; then
          for ((preview_index = 0; preview_index < ${#PREVIEW_CMD[@]}; preview_index++)); do
            if [[ "${PREVIEW_CMD[$preview_index]}" == "--json" ]]; then
              PREVIEW_CMD[$((preview_index + 1))]="@${DEFINITION_FILE} (definition content redacted from preview)"
              break
            fi
          done
        fi
        preview "$COMMAND" "${PREVIEW_CMD[@]}"
        exit 0
      fi
    fi
    run_and_save "$OUTPUT" "${SNOW_CMD[@]}"
    ;;

  -h|--help|help)
    usage
    ;;

  *)
    die "Unknown command: $COMMAND"
    ;;
esac
