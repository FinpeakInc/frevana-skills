#!/usr/bin/env bash

set -euo pipefail

DATA_DIR="${LOCAL_KNOWLEDGE_DATA_DIR:-${HOME}/.local/share/local-knowledge}"
VENV_DIR="${LOCAL_KNOWLEDGE_VENV_DIR:-${DATA_DIR}/venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PY_SCRIPT="${SCRIPT_DIR}/local_knowledge.py"
REQUIREMENTS_DIR="${LOCAL_KNOWLEDGE_REQUIREMENTS_DIR:-${SKILL_DIR}/requirements}"
BASE_REQUIREMENTS="${REQUIREMENTS_DIR}/base.txt"
DOCS_REQUIREMENTS="${REQUIREMENTS_DIR}/docs.txt"
MULTIMODAL_REQUIREMENTS="${REQUIREMENTS_DIR}/multimodal.txt"

usage() {
  cat <<'EOF'
Usage:
  local_knowledge.sh doctor [--install] [--with-docs] [--with-multimodal] [--mode text|multimodal] [--data-dir DIR] [--venv-dir DIR] [--output PATH]
  local_knowledge.sh index --path DIR [--mode text|multimodal] [--model MODEL] [--chunk-size N] [--chunk-overlap N] [--batch-size N] [--max-file-mb N] [--max-files N] [--data-dir DIR] [--output PATH]
  local_knowledge.sh search --path DIR --query TEXT [--mode text|multimodal] [--top-k N] [--model MODEL] [--auto-index] [--chunk-size N] [--chunk-overlap N] [--batch-size N] [--max-file-mb N] [--max-files N] [--data-dir DIR] [--output PATH]
  local_knowledge.sh ask --path DIR --question TEXT [--mode text|multimodal] [--top-k N] [--model MODEL] [--auto-index] [--chunk-size N] [--chunk-overlap N] [--batch-size N] [--max-file-mb N] [--max-files N] [--data-dir DIR] [--output PATH]
  local_knowledge.sh status --path DIR [--mode text|multimodal] [--data-dir DIR] [--output PATH]
  local_knowledge.sh delete --path DIR [--yes] [--mode text|multimodal] [--data-dir DIR] [--output PATH]

Environment:
  LOCAL_KNOWLEDGE_DATA_DIR   Runtime storage root. Default: ~/.local/share/local-knowledge
  LOCAL_KNOWLEDGE_VENV_DIR   Virtualenv path. Default: ~/.local/share/local-knowledge/venv
  LOCAL_KNOWLEDGE_REQUIREMENTS_DIR
                               Requirements directory. Default: <skill>/requirements
  PYTHON_BIN                 Python executable for bootstrap. Default: python3
EOF
}

die() {
  echo "$*" >&2
  exit 1
}

need_python() {
  command -v "$PYTHON_BIN" >/dev/null 2>&1 || die "python3 is required. Set PYTHON_BIN if needed."
}

venv_python() {
  printf '%s/bin/python' "$VENV_DIR"
}

create_venv() {
  need_python
  mkdir -p "$DATA_DIR"
  if [[ ! -x "$(venv_python)" ]]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi
}

install_deps() {
  local with_docs="$1"
  local with_multimodal="$2"
  create_venv
  [[ -f "$BASE_REQUIREMENTS" ]] || die "Missing requirements file: $BASE_REQUIREMENTS"
  "$(venv_python)" -m pip install --upgrade pip
  "$(venv_python)" -m pip install -r "$BASE_REQUIREMENTS"
  if [[ "$with_docs" == "true" ]]; then
    [[ -f "$DOCS_REQUIREMENTS" ]] || die "Missing requirements file: $DOCS_REQUIREMENTS"
    "$(venv_python)" -m pip install -r "$DOCS_REQUIREMENTS"
  fi
  if [[ "$with_multimodal" == "true" ]]; then
    [[ -f "$MULTIMODAL_REQUIREMENTS" ]] || die "Missing requirements file: $MULTIMODAL_REQUIREMENTS"
    "$(venv_python)" -m pip install -r "$MULTIMODAL_REQUIREMENTS"
  fi
}

run_python() {
  if [[ -x "$(venv_python)" ]]; then
    "$(venv_python)" "$PY_SCRIPT" "$@"
  else
    need_python
    "$PYTHON_BIN" "$PY_SCRIPT" "$@"
  fi
}

configure_paths_from_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --data-dir)
        [[ -n "${2:-}" ]] || die "--data-dir requires a value"
        DATA_DIR="$2"
        VENV_DIR="${LOCAL_KNOWLEDGE_VENV_DIR:-${DATA_DIR}/venv}"
        shift 2
        ;;
      --venv-dir)
        [[ -n "${2:-}" ]] || die "--venv-dir requires a value"
        VENV_DIR="$2"
        shift 2
        ;;
      *)
        shift
        ;;
    esac
  done
}

[[ $# -gt 0 ]] || { usage; exit 1; }

cmd="$1"
shift

case "$cmd" in
  -h|--help|help)
    usage
    ;;
  doctor)
    INSTALL=false
    WITH_DOCS=true
    WITH_MULTIMODAL=false
    REST=()
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --install) INSTALL=true; shift ;;
        --with-docs) WITH_DOCS=true; shift ;;
        --no-docs) WITH_DOCS=false; shift ;;
        --with-multimodal) WITH_MULTIMODAL=true; shift ;;
        --no-multimodal) WITH_MULTIMODAL=false; shift ;;
        --mode)
          [[ -n "${2:-}" ]] || die "--mode requires a value"
          REST+=("$1" "$2")
          shift 2
          ;;
        --output)
          [[ -n "${2:-}" ]] || die "--output requires a value"
          REST+=("$1" "$2")
          shift 2
          ;;
        --data-dir)
          [[ -n "${2:-}" ]] || die "--data-dir requires a value"
          DATA_DIR="$2"
          VENV_DIR="${LOCAL_KNOWLEDGE_VENV_DIR:-${DATA_DIR}/venv}"
          REST+=("$1" "$2")
          shift 2
          ;;
        --venv-dir)
          [[ -n "${2:-}" ]] || die "--venv-dir requires a value"
          VENV_DIR="$2"
          REST+=("$1" "$2")
          shift 2
          ;;
        *) die "Unknown doctor argument: $1" ;;
      esac
    done
    if [[ "$INSTALL" == "true" ]]; then
      install_deps "$WITH_DOCS" "$WITH_MULTIMODAL"
    fi
    run_python doctor --data-dir "$DATA_DIR" --venv-dir "$VENV_DIR" "${REST[@]}"
    ;;
  index|search|ask|status|delete)
    configure_paths_from_args "$@"
    run_python "$cmd" --data-dir "$DATA_DIR" "$@"
    ;;
  *)
    usage >&2
    die "Unknown command: $cmd"
    ;;
esac
