#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="${FREVANA_API_BASE_URL:-https://ai-factory.frevana.com}"
API_PATH="/service/amazon/related-keywords"
CONNECT_TIMEOUT="10"
MAX_TIME="600"

usage() {
  cat <<'EOF'
Usage:
  search_amazon_related_keywords.sh --keyword "wireless earbuds" [options]

Options:
  --keyword                    Seed keyword. It is normalized to lowercase
  --location-name              Full DataForSEO location name. Defaults to United States
  --location-code              DataForSEO location code
  --language-name              Full DataForSEO language name. Defaults to English
  --language-code              DataForSEO language code
  --limit                      Results per request, from 1 to 1000. Defaults to 1000
  --offset                     Starting result offset, minimum 0. Defaults to 0
  --tag                        User-defined task identifier, maximum 255 characters
  --depth                      Related-keyword search depth, from 0 to 4. Defaults to 4
  --include-seed-keyword       Include data for the seed keyword. API default: false
  --include_seed_keyword       Alias for --include-seed-keyword
  --ignore-synonyms            Exclude highly similar keywords. API default: false
  --ignore_synonyms            Alias for --ignore-synonyms
  --output                     Output JSON path. Defaults to ./out/amazon-related-keywords-<timestamp>-<pid>.json
  --token                      Optional Bearer token override for this run
  -h, --help                   Show this help message
EOF
}

fail() {
  echo "$1" >&2
  exit 1
}

KEYWORD=""
LOCATION_NAME=""
LOCATION_CODE=""
LANGUAGE_NAME=""
LANGUAGE_CODE=""
LIMIT="1000"
OFFSET="0"
TAG=""
DEPTH="4"
INCLUDE_SEED_KEYWORD=""
IGNORE_SYNONYMS=""
OUTPUT_PATH=""
TOKEN_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --keyword)
      KEYWORD="${2:-}"
      shift 2
      ;;
    --location-name|--location_name)
      LOCATION_NAME="${2:-}"
      shift 2
      ;;
    --location-code|--location_code)
      LOCATION_CODE="${2:-}"
      shift 2
      ;;
    --language-name|--language_name)
      LANGUAGE_NAME="${2:-}"
      shift 2
      ;;
    --language-code|--language_code)
      LANGUAGE_CODE="${2:-}"
      shift 2
      ;;
    --limit)
      LIMIT="${2:-}"
      shift 2
      ;;
    --offset)
      OFFSET="${2:-}"
      shift 2
      ;;
    --tag)
      TAG="${2:-}"
      shift 2
      ;;
    --depth)
      DEPTH="${2:-}"
      shift 2
      ;;
    --include-seed-keyword|--include_seed_keyword)
      INCLUDE_SEED_KEYWORD="${2:-}"
      shift 2
      ;;
    --ignore-synonyms|--ignore_synonyms)
      IGNORE_SYNONYMS="${2:-}"
      shift 2
      ;;
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
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

[[ -n "$KEYWORD" ]] || fail "Missing required argument: --keyword"

command -v curl >/dev/null 2>&1 || fail "curl is required but was not found in PATH."
command -v python3 >/dev/null 2>&1 || fail "python3 is required but was not found in PATH."

TOKEN="${TOKEN_OVERRIDE:-${FREVANA_TOKEN:-}}"
if [[ -z "$TOKEN" && -t 0 ]]; then
  read -r -s -p "FREVANA_TOKEN not found. Please enter your Frevana Bearer token: " TOKEN
  echo >&2
fi
[[ -n "$TOKEN" ]] || fail "FREVANA_TOKEN is not set. In non-interactive runs, set FREVANA_TOKEN or pass --token explicitly."

if [[ -z "$OUTPUT_PATH" ]]; then
  OUTPUT_PATH="out/amazon-related-keywords-$(date -u +%Y%m%dT%H%M%SZ)-$$.json"
fi

PAYLOAD_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
RESULT_FILE="$(mktemp)"
cleanup() {
  rm -f "$PAYLOAD_FILE" "$RESPONSE_FILE" "$RESULT_FILE"
}
trap cleanup EXIT

export KEYWORD LOCATION_NAME LOCATION_CODE LANGUAGE_NAME LANGUAGE_CODE
export LIMIT OFFSET TAG DEPTH INCLUDE_SEED_KEYWORD IGNORE_SYNONYMS

CURRENT_OFFSET="$OFFSET"

while true; do
  export OFFSET="$CURRENT_OFFSET"

  python3 - "$PAYLOAD_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path

payload_path = Path(sys.argv[1])


def env(name):
    return os.environ.get(name, "").strip()


def parse_int(name, label, minimum, maximum=None):
    raw = env(name)
    try:
        value = int(raw)
    except ValueError:
        print(f"{label} must be an integer.", file=sys.stderr)
        sys.exit(1)
    if value < minimum or (maximum is not None and value > maximum):
        if maximum is None:
            message = f"{label} must be at least {minimum}."
        else:
            message = f"{label} must be between {minimum} and {maximum}."
        print(message, file=sys.stderr)
        sys.exit(1)
    return value


def parse_bool(name, label):
    raw = env(name).lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    print(f"{label} must be true or false.", file=sys.stderr)
    sys.exit(1)


keyword = env("KEYWORD")
if not keyword:
    print("--keyword must contain a non-empty value.", file=sys.stderr)
    sys.exit(1)

location_name = env("LOCATION_NAME")
location_code = env("LOCATION_CODE")
if location_name and location_code:
    print("Use only one of --location-name or --location-code.", file=sys.stderr)
    sys.exit(1)
if not location_name and not location_code:
    location_name = "United States"

language_name = env("LANGUAGE_NAME")
language_code = env("LANGUAGE_CODE")
if language_name and language_code:
    print("Use only one of --language-name or --language-code.", file=sys.stderr)
    sys.exit(1)
if not language_name and not language_code:
    language_name = "English"

tag = env("TAG")
if len(tag) > 255:
    print("--tag must not exceed 255 characters.", file=sys.stderr)
    sys.exit(1)

payload = {
    "keyword": keyword.lower(),
    "limit": parse_int("LIMIT", "--limit", 1, 1000),
    "offset": parse_int("OFFSET", "--offset", 0),
    "depth": parse_int("DEPTH", "--depth", 0, 4),
}

if location_name:
    payload["location_name"] = location_name
else:
    payload["location_code"] = parse_int("LOCATION_CODE", "--location-code", 0)

if language_name:
    payload["language_name"] = language_name
else:
    payload["language_code"] = language_code

if tag:
    payload["tag"] = tag
if env("INCLUDE_SEED_KEYWORD"):
    payload["include_seed_keyword"] = parse_bool(
        "INCLUDE_SEED_KEYWORD", "--include-seed-keyword"
    )
if env("IGNORE_SYNONYMS"):
    payload["ignore_synonyms"] = parse_bool("IGNORE_SYNONYMS", "--ignore-synonyms")

payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
PY

  HTTP_CODE="$(
    curl -sS \
      --connect-timeout "$CONNECT_TIMEOUT" \
      --max-time "$MAX_TIME" \
      -o "$RESPONSE_FILE" \
      -w "%{http_code}" \
      -X POST "$API_BASE_URL$API_PATH" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      --data @"$PAYLOAD_FILE"
  )"

  if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
    echo "Amazon related keywords API request at offset $CURRENT_OFFSET failed with HTTP $HTTP_CODE" >&2
    cat "$RESPONSE_FILE" >&2
    exit 1
  fi

  [[ -s "$RESPONSE_FILE" ]] || fail "Amazon related keywords API returned an empty response body at offset $CURRENT_OFFSET."

  PAGE_INFO="$(
    python3 - "$RESPONSE_FILE" "$RESULT_FILE" "$CURRENT_OFFSET" "$LIMIT" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

response_path = Path(sys.argv[1])
result_path = Path(sys.argv[2])
current_offset = int(sys.argv[3])
limit = int(sys.argv[4])
raw = response_path.read_text(encoding="utf-8")

try:
    page = json.loads(raw)
except json.JSONDecodeError as exc:
    print(f"Amazon related keywords API returned non-JSON response: {exc}", file=sys.stderr)
    print(raw, file=sys.stderr)
    sys.exit(1)


def collect_result_objects(value):
    results = []
    if not isinstance(value, dict):
        return results

    tasks = value.get("tasks")
    if isinstance(tasks, list):
        for task in tasks:
            if isinstance(task, dict) and isinstance(task.get("result"), list):
                results.extend(
                    item for item in task["result"] if isinstance(item, dict)
                )

    result = value.get("result")
    if isinstance(result, list):
        results.extend(item for item in result if isinstance(item, dict))

    nested_data = value.get("data")
    if isinstance(nested_data, dict):
        results.extend(collect_result_objects(nested_data))

    if isinstance(value.get("items"), list):
        results.append(value)

    return results


result_objects = collect_result_objects(page)
item_lists = [
    result["items"]
    for result in result_objects
    if isinstance(result.get("items"), list)
]
if not item_lists:
    print(
        "Amazon related keywords response did not contain a recognized items array; "
        "cannot safely continue automatic pagination.",
        file=sys.stderr,
    )
    sys.exit(1)

items = [item for item_list in item_lists for item in item_list]
returned_count = len(items)
total_counts = [
    result["total_count"]
    for result in result_objects
    if isinstance(result.get("total_count"), int)
]
total_count = max(total_counts) if total_counts else None
page_hash = hashlib.sha256(
    json.dumps(items, ensure_ascii=False, sort_keys=True).encode("utf-8")
).hexdigest()

if result_path.exists() and result_path.stat().st_size:
    aggregate = json.loads(result_path.read_text(encoding="utf-8"))
else:
    aggregate = {
        "pagination": {
            "start_offset": current_offset,
            "limit": limit,
            "page_count": 0,
            "items_count": 0,
            "total_count": total_count,
            "page_item_hashes": [],
        },
        "pages": [],
    }

pagination = aggregate["pagination"]
if returned_count and page_hash in pagination["page_item_hashes"]:
    print(
        "Amazon related keywords API returned a duplicate page; "
        "stopping to avoid an infinite pagination loop.",
        file=sys.stderr,
    )
    sys.exit(1)

pagination["page_item_hashes"].append(page_hash)
pagination["page_count"] += 1
pagination["items_count"] += returned_count
if total_count is not None:
    pagination["total_count"] = total_count
pagination["last_offset"] = current_offset
aggregate["pages"].append(page)

result_path.write_text(
    json.dumps(aggregate, ensure_ascii=False),
    encoding="utf-8",
)
print(f"{returned_count}|{'' if total_count is None else total_count}")
PY
  )"

  IFS='|' read -r RETURNED_COUNT TOTAL_COUNT <<< "$PAGE_INFO"
  echo "Fetched $RETURNED_COUNT Amazon related keyword items at offset $CURRENT_OFFSET" >&2

  if [[ "$RETURNED_COUNT" -lt "$LIMIT" ]]; then
    break
  fi
  if [[ -n "$TOTAL_COUNT" && $((CURRENT_OFFSET + RETURNED_COUNT)) -ge "$TOTAL_COUNT" ]]; then
    break
  fi

  CURRENT_OFFSET=$((CURRENT_OFFSET + LIMIT))
done

python3 - "$RESULT_FILE" <<'PY'
import json
import sys
from pathlib import Path

result_path = Path(sys.argv[1])
aggregate = json.loads(result_path.read_text(encoding="utf-8"))
pagination = aggregate["pagination"]
pagination.pop("page_item_hashes", None)
pagination["next_offset"] = None
result_path.write_text(
    json.dumps(aggregate, ensure_ascii=False),
    encoding="utf-8",
)
PY

mkdir -p "$(dirname "$OUTPUT_PATH")"
cp "$RESULT_FILE" "$OUTPUT_PATH"
echo "Saved Amazon related keywords JSON to $OUTPUT_PATH" >&2

cat "$RESULT_FILE"
