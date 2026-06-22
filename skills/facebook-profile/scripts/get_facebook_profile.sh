#!/usr/bin/env bash

set -euo pipefail

DEFAULT_API_BASE_URL="https://ai-factory.frevana.com"
API_BASE_URL="${FREVANA_API_BASE_URL:-$DEFAULT_API_BASE_URL}"
FACEBOOK_PROFILE_PATH="/service/facebook-profile"
CONNECT_TIMEOUT="10"
MAX_TIME="600"

usage() {
  cat <<'EOF'
Usage:
  get_facebook_profile.sh --profile-id PROFILE_ID [--output /path/to/result.json] [--token "bearer token"]

Options:
  --profile-id, --profile_id  Required Facebook profile ID or username
  --output                    Optional file path for saving returned JSON
  --token                     Optional Bearer token override for this run
  -h, --help                  Show this help message
EOF
}

PROFILE_ID=""; OUTPUT_PATH=""; TOKEN_OVERRIDE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile-id|--profile_id) PROFILE_ID="${2:-}"; shift 2 ;;
    --output) OUTPUT_PATH="${2:-}"; shift 2 ;;
    --token) TOKEN_OVERRIDE="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done

[[ -n "$PROFILE_ID" ]] || { echo "Missing required argument: --profile-id" >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "curl is required but was not found in PATH." >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is required but was not found in PATH." >&2; exit 1; }
TOKEN="${TOKEN_OVERRIDE:-${FREVANA_TOKEN:-}}"
if [[ -z "$TOKEN" && -t 0 ]]; then read -r -s -p "FREVANA_TOKEN not found. Please enter your Frevana Bearer token: " TOKEN; echo >&2; fi
[[ -n "$TOKEN" ]] || { echo "FREVANA_TOKEN is not set. In non-interactive runs, set FREVANA_TOKEN or pass --token explicitly." >&2; exit 1; }

PAYLOAD_FILE="$(mktemp)"; RESPONSE_FILE="$(mktemp)"; RESULT_FILE="$(mktemp)"
cleanup() { rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE" "$RESULT_FILE"; }
trap cleanup EXIT
export PROFILE_ID
python3 - "$PAYLOAD_FILE" <<'PY'
import json, os, sys
from pathlib import Path
Path(sys.argv[1]).write_text(json.dumps({"profile_id": os.environ["PROFILE_ID"]}, ensure_ascii=False), encoding="utf-8")
PY

HTTP_CODE="$(curl -sS --connect-timeout "$CONNECT_TIMEOUT" --max-time "$MAX_TIME" -o "$RESPONSE_FILE" -w "%{http_code}" -X POST "$API_BASE_URL$FACEBOOK_PROFILE_PATH" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" --data @"$PAYLOAD_FILE")"
if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then echo "Facebook profile API request failed with HTTP $HTTP_CODE" >&2; cat "$RESPONSE_FILE" >&2; exit 1; fi
[[ -s "$RESPONSE_FILE" ]] || { echo "Facebook profile API returned an empty response body." >&2; exit 1; }
python3 - "$RESPONSE_FILE" "$RESULT_FILE" <<'PY'
import json, sys
from pathlib import Path
raw = Path(sys.argv[1]).read_text(encoding="utf-8")
try: json.loads(raw)
except json.JSONDecodeError as exc: print(f"Facebook profile API returned non-JSON response: {exc}", file=sys.stderr); print(raw, file=sys.stderr); sys.exit(1)
Path(sys.argv[2]).write_text(raw, encoding="utf-8")
PY
if [[ -n "$OUTPUT_PATH" ]]; then mkdir -p "$(dirname "$OUTPUT_PATH")"; cp "$RESULT_FILE" "$OUTPUT_PATH"; fi
cat "$RESULT_FILE"
