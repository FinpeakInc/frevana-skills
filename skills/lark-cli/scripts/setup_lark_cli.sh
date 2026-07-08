#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-check}"
if [[ $# -gt 0 ]]; then
  shift
fi

LANG_ARG=""
SUITE_ARG=""
DRY_RUN="0"
RECOMMEND="1"
SCOPE_ARGS=()
DOMAIN_ARGS=()
EXTRA_ARGS=()

usage() {
  cat <<'USAGE'
Usage:
  setup_lark_cli.sh check
  setup_lark_cli.sh install [--lang zh|en]
  setup_lark_cli.sh config-init [--suite lark|feishu] [--lang zh|en]
  setup_lark_cli.sh login [--no-recommend] [--scope SCOPE] [--domain DOMAIN]
  setup_lark_cli.sh status
  setup_lark_cli.sh setup [--suite lark|feishu] [--lang zh|en]

Actions:
  check        Print lark-cli availability and install paths.
  install      Run the official installer: npx @larksuite/cli@latest install.
  config-init  Run lark-cli config init --new with required --brand lark|feishu.
  login        Run lark-cli auth login, defaulting to --recommend.
  status       Run lark-cli auth status.
  setup        Check/install, then config-init, login, and status.

Product suite:
  --suite lark    Use the international Lark app/authorization link.
  --suite feishu  Use the Feishu app/authorization link.
  --brand VALUE   Alias for --suite.
                 Defaults to feishu when omitted.

Debugging:
  --dry-run       Print the command that would run without executing it.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --lang)
      [[ $# -ge 2 ]] || { echo "Missing value for --lang" >&2; exit 2; }
      LANG_ARG="$2"
      shift 2
      ;;
    --lang=*)
      LANG_ARG="${1#*=}"
      shift
      ;;
    --suite|--brand)
      [[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 2; }
      case "$2" in
        lark|feishu) SUITE_ARG="$2" ;;
        *) echo "--suite/--brand must be lark or feishu" >&2; exit 2 ;;
      esac
      shift 2
      ;;
    --suite=*|--brand=*)
      value="${1#*=}"
      case "$value" in
        lark|feishu) SUITE_ARG="$value" ;;
        *) echo "--suite/--brand must be lark or feishu" >&2; exit 2 ;;
      esac
      shift
      ;;
    --dry-run)
      DRY_RUN="1"
      shift
      ;;
    --no-recommend)
      RECOMMEND="0"
      shift
      ;;
    --scope)
      [[ $# -ge 2 ]] || { echo "Missing value for --scope" >&2; exit 2; }
      SCOPE_ARGS+=(--scope "$2")
      shift 2
      ;;
    --scope=*)
      SCOPE_ARGS+=(--scope "${1#*=}")
      shift
      ;;
    --domain)
      [[ $# -ge 2 ]] || { echo "Missing value for --domain" >&2; exit 2; }
      DOMAIN_ARGS+=(--domain "$2")
      shift 2
      ;;
    --domain=*)
      DOMAIN_ARGS+=(--domain "${1#*=}")
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    --)
      shift
      EXTRA_ARGS+=("$@")
      break
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    return 1
  fi
}

npm_prefix() {
  npm prefix -g 2>/dev/null || true
}

npm_root() {
  npm root -g 2>/dev/null || true
}

lark_bin() {
  command -v lark-cli 2>/dev/null || true
}

run_command() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf 'dry_run_command='
    printf '%q ' "$@"
    printf '\n'
    return 0
  fi

  "$@"
}

print_paths() {
  local prefix root bin package_dir native_bin
  prefix="$(npm_prefix)"
  root="$(npm_root)"
  bin="$(lark_bin)"
  package_dir=""
  native_bin=""

  if [[ -n "$root" ]]; then
    package_dir="$root/@larksuite/cli"
    if [[ "${OS:-}" == "Windows_NT" ]]; then
      native_bin="$package_dir/bin/lark-cli.exe"
    else
      native_bin="$package_dir/bin/lark-cli"
    fi
  fi

  echo "lark_cli_command=${bin:-missing}"
  echo "npm_global_prefix=${prefix:-unknown}"
  echo "npm_global_root=${root:-unknown}"
  echo "npm_package_dir=${package_dir:-unknown}"
  echo "native_binary=${native_bin:-unknown}"
}

check_lark_cli() {
  need_cmd npm
  print_paths
  if command -v lark-cli >/dev/null 2>&1; then
    lark-cli --version 2>/dev/null || true
    return 0
  fi
  return 1
}

install_lark_cli() {
  need_cmd npm
  need_cmd npx
  local args=("@larksuite/cli@latest" "install")
  if [[ -n "$LANG_ARG" ]]; then
    args+=(--lang "$LANG_ARG")
  fi
  run_command npx "${args[@]}"
}

require_lark_cli() {
  if ! command -v lark-cli >/dev/null 2>&1; then
    echo "lark-cli is not installed. Run: bash <skill-path>/scripts/setup_lark_cli.sh install" >&2
    exit 1
  fi
}

effective_suite() {
  if [[ -n "$SUITE_ARG" ]]; then
    printf '%s\n' "$SUITE_ARG"
  else
    printf 'feishu\n'
  fi
}

config_init() {
  require_lark_cli
  local suite
  suite="$(effective_suite)"
  local args=("config" "init" "--new")
  args+=(--brand "$suite")
  if [[ -n "$LANG_ARG" ]]; then
    args+=(--lang "$LANG_ARG")
  fi
  if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
    args+=("${EXTRA_ARGS[@]}")
  fi
  run_command lark-cli "${args[@]}"
}

login() {
  require_lark_cli
  local args=("auth" "login")
  if [[ "$RECOMMEND" == "1" && ${#SCOPE_ARGS[@]} -eq 0 && ${#DOMAIN_ARGS[@]} -eq 0 ]]; then
    args+=(--recommend)
  fi
  if [[ ${#SCOPE_ARGS[@]} -gt 0 ]]; then
    args+=("${SCOPE_ARGS[@]}")
  fi
  if [[ ${#DOMAIN_ARGS[@]} -gt 0 ]]; then
    args+=("${DOMAIN_ARGS[@]}")
  fi
  if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
    args+=("${EXTRA_ARGS[@]}")
  fi
  run_command lark-cli "${args[@]}"
}

status() {
  require_lark_cli
  local args=("auth" "status")
  if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
    args+=("${EXTRA_ARGS[@]}")
  fi
  run_command lark-cli "${args[@]}"
}

case "$ACTION" in
  check)
    check_lark_cli
    ;;
  install)
    install_lark_cli
    ;;
  config-init)
    config_init
    ;;
  login)
    login
    ;;
  status)
    status
    ;;
  setup)
    if ! command -v lark-cli >/dev/null 2>&1; then
      install_lark_cli
    fi
    config_init
    login
    status
    ;;
  --help|-h|help)
    usage
    ;;
  *)
    echo "Unknown action: $ACTION" >&2
    usage >&2
    exit 2
    ;;
esac
