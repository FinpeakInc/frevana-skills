#!/usr/bin/env bash

set -euo pipefail

export BACKLINKS_API_NAME="Backlinks Referring Networks"
export BACKLINKS_API_METHOD="POST"
export BACKLINKS_API_PATH="/service/backlinks/referring-networks"
export BACKLINKS_ALLOWED_FIELDS="target network_address_type limit offset internal_list_limit backlinks_status_type filters order_by backlinks_filters include_subdomains include_indirect_links exclude_internal_backlinks rank_scale tag"
export BACKLINKS_REQUIRED_FIELDS="target"
export BACKLINKS_OUTPUT_PREFIX="backlinks-referring-networks"

API_BASE_URL="${FREVANA_API_BASE_URL:-https://ai-factory.frevana.com}"
CONNECT_TIMEOUT="10"
MAX_TIME="600"

fail() {
  echo "$1" >&2
  exit 1
}

usage_common() {
  cat <<'EOF'
Common options:
  --output                         Optional file path for saving returned JSON
  --token                          Optional Bearer token override for this run
  --target                         Domain, subdomain, or webpage target
  --targets                        Comma-separated target list for bulk APIs
  --targets-json                   JSON object/array for intersection or bulk APIs
  --exclude-targets                Comma-separated exclude target list
  --exclude-targets-json           JSON array of exclude targets
  --filters-json                   JSON array filters
  --backlinks-filters-json         JSON array backlinks_filters
  --order-by                       Comma-separated order_by values
  --mode                           Backlinks grouping mode
  --custom-mode-json               JSON custom_mode object/array
  --limit                          Numeric limit
  --offset                         Numeric offset
  --internal-list-limit            Numeric internal_list_limit
  --search-after-token             search_after_token value
  --network-address-type           network_address_type value
  --backlinks-status-type          backlinks_status_type value
  --include-subdomains             true|false
  --include-indirect-links         true|false
  --exclude-internal-backlinks     true|false
  --exclude-large-domains          true|false
  --main-domain                    true|false
  --intersection-mode              intersection_mode value
  --rank-scale                     rank_scale value
  --date-from                      yyyy-mm-dd
  --date-to                        yyyy-mm-dd
  --group-range                    day|week|month|year
  --tag                            User-defined task identifier
  -h, --help                       Show help
EOF
}

require_var() {
  local name="$1"
  [[ -n "${!name:-}" ]] || fail "Internal script error: $name is required."
}

require_var BACKLINKS_API_NAME
require_var BACKLINKS_API_PATH
BACKLINKS_API_METHOD="${BACKLINKS_API_METHOD:-POST}"
BACKLINKS_ALLOWED_FIELDS="${BACKLINKS_ALLOWED_FIELDS:-}"
BACKLINKS_REQUIRED_FIELDS="${BACKLINKS_REQUIRED_FIELDS:-}"
BACKLINKS_OUTPUT_PREFIX="${BACKLINKS_OUTPUT_PREFIX:-backlinks}"
BACKLINKS_TARGETS_SHAPE="${BACKLINKS_TARGETS_SHAPE:-array}"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  echo "Usage: $(basename "$0") [options]"
  echo
  usage_common
  exit 0
fi

TARGET=""
TARGETS=""
TARGETS_JSON=""
EXCLUDE_TARGETS=""
EXCLUDE_TARGETS_JSON=""
FILTERS_JSON=""
BACKLINKS_FILTERS_JSON=""
ORDER_BY=""
MODE=""
CUSTOM_MODE_JSON=""
LIMIT=""
OFFSET=""
INTERNAL_LIST_LIMIT=""
SEARCH_AFTER_TOKEN=""
NETWORK_ADDRESS_TYPE=""
BACKLINKS_STATUS_TYPE=""
INCLUDE_SUBDOMAINS=""
INCLUDE_INDIRECT_LINKS=""
EXCLUDE_INTERNAL_BACKLINKS=""
EXCLUDE_LARGE_DOMAINS=""
MAIN_DOMAIN=""
INTERSECTION_MODE=""
RANK_SCALE=""
DATE_FROM=""
DATE_TO=""
GROUP_RANGE=""
TAG=""
OUTPUT_PATH=""
TOKEN_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="${2:-}"; shift 2 ;;
    --targets) TARGETS="${2:-}"; shift 2 ;;
    --targets-json|--targets_json) TARGETS_JSON="${2:-}"; shift 2 ;;
    --exclude-targets|--exclude_targets) EXCLUDE_TARGETS="${2:-}"; shift 2 ;;
    --exclude-targets-json|--exclude_targets_json) EXCLUDE_TARGETS_JSON="${2:-}"; shift 2 ;;
    --filters-json|--filters_json) FILTERS_JSON="${2:-}"; shift 2 ;;
    --backlinks-filters-json|--backlinks_filters_json) BACKLINKS_FILTERS_JSON="${2:-}"; shift 2 ;;
    --order-by|--order_by) ORDER_BY="${2:-}"; shift 2 ;;
    --mode) MODE="${2:-}"; shift 2 ;;
    --custom-mode-json|--custom_mode_json) CUSTOM_MODE_JSON="${2:-}"; shift 2 ;;
    --limit) LIMIT="${2:-}"; shift 2 ;;
    --offset) OFFSET="${2:-}"; shift 2 ;;
    --internal-list-limit|--internal_list_limit) INTERNAL_LIST_LIMIT="${2:-}"; shift 2 ;;
    --search-after-token|--search_after_token) SEARCH_AFTER_TOKEN="${2:-}"; shift 2 ;;
    --network-address-type|--network_address_type) NETWORK_ADDRESS_TYPE="${2:-}"; shift 2 ;;
    --backlinks-status-type|--backlinks_status_type) BACKLINKS_STATUS_TYPE="${2:-}"; shift 2 ;;
    --include-subdomains|--include_subdomains) INCLUDE_SUBDOMAINS="${2:-}"; shift 2 ;;
    --include-indirect-links|--include_indirect_links) INCLUDE_INDIRECT_LINKS="${2:-}"; shift 2 ;;
    --exclude-internal-backlinks|--exclude_internal_backlinks) EXCLUDE_INTERNAL_BACKLINKS="${2:-}"; shift 2 ;;
    --exclude-large-domains|--exclude_large_domains) EXCLUDE_LARGE_DOMAINS="${2:-}"; shift 2 ;;
    --main-domain|--main_domain) MAIN_DOMAIN="${2:-}"; shift 2 ;;
    --intersection-mode|--intersection_mode) INTERSECTION_MODE="${2:-}"; shift 2 ;;
    --rank-scale|--rank_scale) RANK_SCALE="${2:-}"; shift 2 ;;
    --date-from|--date_from) DATE_FROM="${2:-}"; shift 2 ;;
    --date-to|--date_to) DATE_TO="${2:-}"; shift 2 ;;
    --group-range|--group_range) GROUP_RANGE="${2:-}"; shift 2 ;;
    --tag) TAG="${2:-}"; shift 2 ;;
    --output) OUTPUT_PATH="${2:-}"; shift 2 ;;
    --token) TOKEN_OVERRIDE="${2:-}"; shift 2 ;;
    -h|--help) usage_common; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage_common >&2; exit 1 ;;
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

if [[ -z "$OUTPUT_PATH" ]]; then
  OUTPUT_PATH="out/${BACKLINKS_OUTPUT_PREFIX}-$(date -u +%Y%m%dT%H%M%SZ)-$$.json"
fi

PAYLOAD_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
RESULT_FILE="$(mktemp)"
cleanup() {
  rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE" "$RESULT_FILE"
}
trap cleanup EXIT

export BACKLINKS_ALLOWED_FIELDS BACKLINKS_REQUIRED_FIELDS BACKLINKS_TARGETS_SHAPE
export TARGET TARGETS TARGETS_JSON EXCLUDE_TARGETS EXCLUDE_TARGETS_JSON FILTERS_JSON BACKLINKS_FILTERS_JSON ORDER_BY
export MODE CUSTOM_MODE_JSON LIMIT OFFSET INTERNAL_LIST_LIMIT SEARCH_AFTER_TOKEN NETWORK_ADDRESS_TYPE BACKLINKS_STATUS_TYPE
export INCLUDE_SUBDOMAINS INCLUDE_INDIRECT_LINKS EXCLUDE_INTERNAL_BACKLINKS EXCLUDE_LARGE_DOMAINS MAIN_DOMAIN INTERSECTION_MODE
export RANK_SCALE DATE_FROM DATE_TO GROUP_RANGE TAG

if [[ "$BACKLINKS_API_METHOD" == "POST" ]]; then
  python3 - "$PAYLOAD_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path

payload_path = Path(sys.argv[1])
allowed = set(os.environ.get("BACKLINKS_ALLOWED_FIELDS", "").split())
required = [item for item in os.environ.get("BACKLINKS_REQUIRED_FIELDS", "").split() if item]

def env(name):
    return os.environ.get(name, "").strip()

def ensure_allowed(field):
    if field not in allowed:
        print(f"This API does not support field: {field}", file=sys.stderr)
        sys.exit(1)

def parse_bool(raw, label):
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    print(f"Invalid {label} value: expected true or false.", file=sys.stderr)
    sys.exit(1)

def parse_int(raw, label):
    try:
        return int(raw)
    except ValueError:
        print(f"{label} must be an integer.", file=sys.stderr)
        sys.exit(1)

def parse_json(raw, label):
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"{label} must be valid JSON: {exc}", file=sys.stderr)
        sys.exit(1)

def split_csv(raw):
    return [item.strip() for item in raw.split(",") if item.strip()]

payload = {}

string_fields = {
    "target": "TARGET",
    "mode": "MODE",
    "search_after_token": "SEARCH_AFTER_TOKEN",
    "network_address_type": "NETWORK_ADDRESS_TYPE",
    "backlinks_status_type": "BACKLINKS_STATUS_TYPE",
    "intersection_mode": "INTERSECTION_MODE",
    "rank_scale": "RANK_SCALE",
    "date_from": "DATE_FROM",
    "date_to": "DATE_TO",
    "group_range": "GROUP_RANGE",
    "tag": "TAG",
}
for field, var in string_fields.items():
    if env(var):
        ensure_allowed(field)
        payload[field] = env(var)

number_fields = {
    "limit": "LIMIT",
    "offset": "OFFSET",
    "internal_list_limit": "INTERNAL_LIST_LIMIT",
}
for field, var in number_fields.items():
    if env(var):
        ensure_allowed(field)
        payload[field] = parse_int(env(var), f"--{field.replace('_', '-')}")

bool_fields = {
    "include_subdomains": "INCLUDE_SUBDOMAINS",
    "include_indirect_links": "INCLUDE_INDIRECT_LINKS",
    "exclude_internal_backlinks": "EXCLUDE_INTERNAL_BACKLINKS",
    "exclude_large_domains": "EXCLUDE_LARGE_DOMAINS",
    "main_domain": "MAIN_DOMAIN",
}
for field, var in bool_fields.items():
    if env(var):
        ensure_allowed(field)
        payload[field] = parse_bool(env(var), f"--{field.replace('_', '-')}")

json_fields = {
    "filters": "FILTERS_JSON",
    "backlinks_filters": "BACKLINKS_FILTERS_JSON",
    "custom_mode": "CUSTOM_MODE_JSON",
}
for field, var in json_fields.items():
    if env(var):
        ensure_allowed(field)
        payload[field] = parse_json(env(var), f"--{field.replace('_', '-')}-json")

if env("ORDER_BY"):
    ensure_allowed("order_by")
    payload["order_by"] = split_csv(env("ORDER_BY"))

targets_shape = os.environ.get("BACKLINKS_TARGETS_SHAPE", "array").strip() or "array"

if env("TARGETS_JSON"):
    ensure_allowed("targets")
    value = parse_json(env("TARGETS_JSON"), "--targets-json")
    if targets_shape == "object" and not isinstance(value, dict):
        print("--targets-json must be a JSON object for this API.", file=sys.stderr)
        sys.exit(1)
    if targets_shape == "array" and not isinstance(value, list):
        print("--targets-json must be a JSON array for this API.", file=sys.stderr)
        sys.exit(1)
    payload["targets"] = value
elif env("TARGETS"):
    ensure_allowed("targets")
    values = split_csv(env("TARGETS"))
    if targets_shape == "object":
        payload["targets"] = {str(index + 1): value for index, value in enumerate(values)}
    else:
        payload["targets"] = values

if env("EXCLUDE_TARGETS_JSON"):
    ensure_allowed("exclude_targets")
    value = parse_json(env("EXCLUDE_TARGETS_JSON"), "--exclude-targets-json")
    if not isinstance(value, list):
        print("--exclude-targets-json must be a JSON array.", file=sys.stderr)
        sys.exit(1)
    payload["exclude_targets"] = value
elif env("EXCLUDE_TARGETS"):
    ensure_allowed("exclude_targets")
    payload["exclude_targets"] = split_csv(env("EXCLUDE_TARGETS"))

missing = [field for field in required if field not in payload]
if missing:
    print("Missing required field(s): " + ", ".join(missing), file=sys.stderr)
    sys.exit(1)

payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
PY
fi

if [[ "$BACKLINKS_API_METHOD" == "GET" ]]; then
  HTTP_CODE="$(curl -sS --connect-timeout "$CONNECT_TIMEOUT" --max-time "$MAX_TIME" -o "$RESPONSE_FILE" -w "%{http_code}" -X GET "$API_BASE_URL$BACKLINKS_API_PATH" -H "Authorization: Bearer $TOKEN")"
else
  HTTP_CODE="$(curl -sS --connect-timeout "$CONNECT_TIMEOUT" --max-time "$MAX_TIME" -o "$RESPONSE_FILE" -w "%{http_code}" -X POST "$API_BASE_URL$BACKLINKS_API_PATH" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" --data @"$PAYLOAD_FILE")"
fi

if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "$BACKLINKS_API_NAME request failed with HTTP $HTTP_CODE" >&2
  cat "$RESPONSE_FILE" >&2
  exit 1
fi

[[ -s "$RESPONSE_FILE" ]] || fail "$BACKLINKS_API_NAME returned an empty response body."

python3 - "$RESPONSE_FILE" "$RESULT_FILE" "$BACKLINKS_API_NAME" <<'PY'
import json
import sys
from pathlib import Path

response_path = Path(sys.argv[1])
result_path = Path(sys.argv[2])
api_name = sys.argv[3]
raw = response_path.read_text(encoding="utf-8")

try:
    json.loads(raw)
except json.JSONDecodeError as exc:
    print(f"{api_name} returned non-JSON response: {exc}", file=sys.stderr)
    print(raw, file=sys.stderr)
    sys.exit(1)

result_path.write_text(raw, encoding="utf-8")
PY

mkdir -p "$(dirname "$OUTPUT_PATH")"
cp "$RESULT_FILE" "$OUTPUT_PATH"
echo "Saved $BACKLINKS_API_NAME JSON to $OUTPUT_PATH" >&2
cat "$RESULT_FILE"
