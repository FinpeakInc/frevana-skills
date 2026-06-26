#!/usr/bin/env bash

set -euo pipefail

DEFAULT_API_BASE_URL="https://ai-factory.frevana.com"
API_BASE_URL="${FREVANA_API_BASE_URL:-$DEFAULT_API_BASE_URL}"
API_PATH="/service/google-short-videos"
CONNECT_TIMEOUT="10"
MAX_TIME="600"

usage() {
  cat <<'EOF'
Usage:
  search_google_short_videos.sh --q VALUE [options] [--output /path/to/result.json] [--token "bearer token"]

Request options:
  --q                          string parameter
  --location                   string parameter
  --uule                       string parameter
  --google-domain              string parameter
  --gl                         string parameter
  --hl                         string parameter
  --lr                         string parameter
  --device                     string parameter
  --start                      int parameter
  --tbs                        string parameter
  --safe                       string parameter
  --nfpr                       int parameter
  --filter                     int parameter
  --no-cache                   bool parameter
  --async                      bool parameter
  --zero-trace                 bool parameter

Runtime options:
  --output                   Optional file path for saving returned JSON
  --token                    Optional Bearer token override for this run
  -h, --help                 Show this help message
EOF
}

fail() { echo "$1" >&2; exit 1; }

OUTPUT_PATH=""
TOKEN_OVERRIDE=""
PAYLOAD_ARGS=()

while [[ $# -gt 0 ]]; do
  if [[ "$1" == --*=* ]]; then
    set -- "${1%%=*}" "${1#*=}" "${@:2}"
  fi

  case "$1" in
    --output)
      OUTPUT_PATH="${2:-}"
      shift 2
      ;;
    --token)
      TOKEN_OVERRIDE="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --*)
      OPTION="${1#--}"
      OPTION="${OPTION//-/_}"
      if [[ -z "${2:-}" ]]; then
        fail "Missing value for $1"
      fi
      PAYLOAD_ARGS+=("$OPTION=${2:-}")
      shift 2
      ;;
    *)
      fail "Unknown argument: $1"
      ;;
  esac
done

command -v curl >/dev/null 2>&1 || fail "curl is required but was not found in PATH."
command -v python3 >/dev/null 2>&1 || fail "python3 is required but was not found in PATH."

TOKEN="${TOKEN_OVERRIDE:-${FREVANA_TOKEN:-}}"
if [[ -z "$TOKEN" && -t 0 ]]; then
  read -r -s -p "FREVANA_TOKEN not found. Please enter your Frevana Bearer token: " TOKEN
  echo >&2
fi
[[ -n "$TOKEN" ]] || fail "FREVANA_TOKEN is not set. In non-interactive runs, set FREVANA_TOKEN or pass --token explicitly."

PAYLOAD_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
RESULT_FILE="$(mktemp)"
cleanup() { rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE" "$RESULT_FILE"; }
trap cleanup EXIT

python3 - "$PAYLOAD_FILE" '{"q":"q","location":"location","uule":"uule","google_domain":"google_domain","google-domain":"google_domain","gl":"gl","hl":"hl","lr":"lr","device":"device","start":"start","tbs":"tbs","safe":"safe","nfpr":"nfpr","filter":"filter","no_cache":"no_cache","no-cache":"no_cache","async":"async","zero_trace":"zero_trace","zero-trace":"zero_trace"}' '{"q":"string","location":"string","uule":"string","google_domain":"string","gl":"string","hl":"string","lr":"string","device":"string","start":"int","tbs":"string","safe":"string","nfpr":"int","filter":"int","no_cache":"bool","async":"bool","zero_trace":"bool"}' '["q"]' '[]' "${PAYLOAD_ARGS[@]}" <<'PY'
import json
import sys
from pathlib import Path

payload_path = Path(sys.argv[1])
aliases = json.loads(sys.argv[2])
types = json.loads(sys.argv[3])
required = json.loads(sys.argv[4])
required_any = json.loads(sys.argv[5])
raw_args = sys.argv[6:]

payload = {}

def parse_bool(value, key):
    lowered = value.lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise SystemExit(f"Invalid --{key.replace('_', '-')} value: expected true or false")

for item in raw_args:
    if "=" not in item:
        raise SystemExit(f"Invalid argument payload: {item}")
    raw_key, value = item.split("=", 1)
    key = aliases.get(raw_key)
    if not key:
        allowed = ", ".join(f"--{name.replace('_', '-')}" for name in sorted(types))
        raise SystemExit(f"Unknown argument: --{raw_key.replace('_', '-')}. Allowed options: {allowed}")
    kind = types[key]
    try:
        if kind == "int":
            payload[key] = int(value)
        elif kind == "float":
            payload[key] = float(value)
        elif kind == "bool":
            payload[key] = parse_bool(value, key)
        else:
            payload[key] = value
    except ValueError:
        raise SystemExit(f"Invalid --{key.replace('_', '-')} value: expected {kind}")

missing = [key for key in required if key not in payload or payload[key] == ""]
if missing:
    raise SystemExit("Missing required argument(s): " + ", ".join(f"--{key.replace('_', '-')}" for key in missing))
if required_any and not any(payload.get(key) not in (None, "") for key in required_any):
    raise SystemExit("One of these arguments is required: " + ", ".join(f"--{key.replace('_', '-')}" for key in required_any))

payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
PY

HTTP_CODE="$(curl -sS --connect-timeout "$CONNECT_TIMEOUT" --max-time "$MAX_TIME" -o "$RESPONSE_FILE" -w "%{http_code}" -X POST "$API_BASE_URL$API_PATH" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" --data @"$PAYLOAD_FILE")"
if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "Google Short Videos Search API request failed with HTTP $HTTP_CODE" >&2
  cat "$RESPONSE_FILE" >&2
  exit 1
fi
[[ -s "$RESPONSE_FILE" ]] || fail "Google Short Videos Search API returned an empty response body."

python3 - "$RESPONSE_FILE" "$RESULT_FILE" <<'PY'
import json
import sys
from pathlib import Path
raw = Path(sys.argv[1]).read_text(encoding="utf-8")
try:
    json.loads(raw)
except json.JSONDecodeError as exc:
    print(f"API returned non-JSON response: {exc}", file=sys.stderr)
    print(raw, file=sys.stderr)
    sys.exit(1)
Path(sys.argv[2]).write_text(raw, encoding="utf-8")
PY

if [[ -n "$OUTPUT_PATH" ]]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  cp "$RESULT_FILE" "$OUTPUT_PATH"
fi
cat "$RESULT_FILE"
