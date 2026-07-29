#!/usr/bin/env bash
set -euo pipefail

TEST_DIR="$(mktemp -d "${TMPDIR:-/tmp}/wordpress-content-test.XXXXXX")"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORDPRESS_SCRIPT="$SCRIPT_DIR/../scripts/wordpress_rest.sh"
trap 'rm -rf -- "$TEST_DIR"' EXIT

export TEST_DIR
export TEST_PAYLOAD="$TEST_DIR/publish.json"
export TEST_META_PAYLOAD="$TEST_DIR/meta.json"
export TEST_USER_RESPONSE="$TEST_DIR/user.json"
export TEST_CREATE_RESPONSE="$TEST_DIR/create.json"
export TEST_DRAFT_RESPONSE="$TEST_DIR/draft.json"
export TEST_MATCH_RESPONSE="$TEST_DIR/match.json"
export TEST_MISMATCH_RESPONSE="$TEST_DIR/mismatch.json"
export TEST_GENERIC_RESPONSE="$TEST_DIR/generic.json"

printf '%s\n' \
  '{"title":"Original","content":"<p>Keep  two spaces.</p>","status":"publish"}' \
  > "$TEST_PAYLOAD"
cp "$TEST_PAYLOAD" "$TEST_DIR/publish-before.json"
printf '%s\n' '{"title":"Updated","excerpt":"Summary"}' > "$TEST_META_PAYLOAD"
printf '%s\n' '{"id":7,"username":"editor"}' > "$TEST_USER_RESPONSE"
printf '%s\n' \
  '{"id":42,"content":{"raw":"<p>Keep  two spaces.</p>"},"status":"publish"}' \
  > "$TEST_CREATE_RESPONSE"
printf '%s\n' \
  '{"id":42,"content":{"raw":"<p>Keep  two spaces.</p>"},"status":"draft"}' \
  > "$TEST_DRAFT_RESPONSE"
cp "$TEST_CREATE_RESPONSE" "$TEST_MATCH_RESPONSE"
printf '%s\n' \
  '{"id":42,"content":{"raw":"<p>Keep two spaces.</p>"},"status":"publish"}' \
  > "$TEST_MISMATCH_RESPONSE"
printf '%s\n' '{"id":42,"title":{"raw":"Updated"}}' > "$TEST_GENERIC_RESPONSE"

curl() {
  local first="${1:-}"
  local method="GET"
  local output=""
  local data=""
  local url=""
  local connect_timeout=""
  local max_time=""

  [[ "$first" == "--disable" ]] || {
    echo "curl must begin with --disable" >&2
    return 90
  }
  shift

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --request)
        method="$2"
        shift 2
        ;;
      --output)
        output="$2"
        shift 2
        ;;
      --data-binary)
        data="$2"
        shift 2
        ;;
      --connect-timeout)
        connect_timeout="$2"
        shift 2
        ;;
      --max-time)
        max_time="$2"
        shift 2
        ;;
      --config|--header|--dump-header)
        shift 2
        ;;
      --fail-with-body|--silent|--show-error)
        shift
        ;;
      *)
        url="$1"
        shift
        ;;
    esac
  done

  [[ -n "$connect_timeout" && -n "$max_time" ]] || {
    echo "curl timeouts are required" >&2
    return 91
  }

  case "$TEST_SCENARIO" in
    status_ok)
      [[ "$method" == "GET" && "$url" == *"/wp-json/wp/v2/users/me?"* ]]
      cp "$TEST_USER_RESPONSE" "$output"
      ;;
    status_fail)
      return 22
      ;;
    create_match)
      if [[ "$method" == "POST" ]]; then
        [[ "$data" == "@$TEST_PAYLOAD" ]]
        cp "$TEST_CREATE_RESPONSE" "$output"
      else
        cp "$TEST_MATCH_RESPONSE" "$output"
      fi
      ;;
    create_mismatch)
      if [[ "$method" == "POST" ]]; then
        [[ "$data" == "@$TEST_PAYLOAD" ]]
        cp "$TEST_CREATE_RESPONSE" "$output"
      else
        cp "$TEST_MISMATCH_RESPONSE" "$output"
      fi
      ;;
    status_mismatch)
      [[ "$method" == "POST" && "$data" == "@$TEST_PAYLOAD" ]]
      cp "$TEST_DRAFT_RESPONSE" "$output"
      ;;
    generic_update)
      [[ "$method" == "POST" && "$data" == "@$TEST_META_PAYLOAD" ]]
      cp "$TEST_GENERIC_RESPONSE" "$output"
      ;;
    *)
      echo "Unexpected test scenario: $TEST_SCENARIO" >&2
      return 92
      ;;
  esac
}
export -f curl

wordpress() {
  bash "$WORDPRESS_SCRIPT" "$@" \
    --url "https://example.com" \
    --username "editor" \
    --app-password "secret"
}

export TEST_SCENARIO="status_ok"
wordpress status > "$TEST_DIR/status-ok.stdout" 2> "$TEST_DIR/status-ok.stderr"
grep -q '^credentials_configured=true$' "$TEST_DIR/status-ok.stdout"
grep -q '^credentials_valid=true$' "$TEST_DIR/status-ok.stdout"

export TEST_SCENARIO="status_fail"
if wordpress status > "$TEST_DIR/status-fail.stdout" 2> "$TEST_DIR/status-fail.stderr"; then
  echo "status must fail when remote authentication fails" >&2
  exit 1
fi
grep -q '^credentials_valid=false$' "$TEST_DIR/status-fail.stdout"

export TEST_SCENARIO="create_match"
wordpress verbatim-create \
  --endpoint "/wp-json/wp/v2/posts" \
  --data-file "$TEST_PAYLOAD" \
  --output "$TEST_DIR/create-match.json" \
  --execute 2> "$TEST_DIR/create-match.stderr"
grep -q 'content_match=true' "$TEST_DIR/create-match.stderr"
cmp "$TEST_PAYLOAD" "$TEST_DIR/publish-before.json"

export TEST_SCENARIO="create_mismatch"
wordpress verbatim-create \
  --endpoint "/wp-json/wp/v2/posts" \
  --data-file "$TEST_PAYLOAD" \
  --output "$TEST_DIR/create-mismatch.json" \
  --execute 2> "$TEST_DIR/create-mismatch.stderr"
grep -q 'content_match=false' "$TEST_DIR/create-mismatch.stderr"
grep -q 'publication was not stopped or rolled back' "$TEST_DIR/create-mismatch.stderr"

export TEST_SCENARIO="status_mismatch"
if wordpress verbatim-create \
  --endpoint "/wp-json/wp/v2/posts" \
  --data-file "$TEST_PAYLOAD" \
  --output "$TEST_DIR/status-mismatch.json" \
  --execute 2> "$TEST_DIR/status-mismatch.stderr"; then
  echo "publication must fail when WordPress does not apply status=publish" >&2
  exit 1
fi
grep -q 'did not apply the requested publication status' "$TEST_DIR/status-mismatch.stderr"

export TEST_SCENARIO="generic_update"
wordpress request \
  --method POST \
  --endpoint "/wp-json/wp/v2/posts/42" \
  --data-file "$TEST_META_PAYLOAD" \
  --output "$TEST_DIR/generic-update.json" \
  --execute
cmp "$TEST_GENERIC_RESPONSE" "$TEST_DIR/generic-update.json"

if wordpress request \
  --method POST \
  --endpoint "/wp-json/wp/v2/posts/42" \
  --data-file "$TEST_META_PAYLOAD" \
  --output "$TEST_META_PAYLOAD" \
  --execute > "$TEST_DIR/path-conflict.stdout" 2> "$TEST_DIR/path-conflict.stderr"; then
  echo "request must reject an output path that aliases its payload" >&2
  exit 1
fi
grep -q -- '--output and --data-file must refer to different files' "$TEST_DIR/path-conflict.stderr"

if wordpress verbatim-update \
  --endpoint "/wp-json/wp/v2/posts/42" \
  --data-file "$TEST_PAYLOAD" \
  --backup "$TEST_DIR/shared.json" \
  --output "$TEST_DIR/shared.json" > "$TEST_DIR/backup-conflict.stdout" 2> "$TEST_DIR/backup-conflict.stderr"; then
  echo "verbatim-update must reject an output path that aliases its backup" >&2
  exit 1
fi
grep -q -- '--output and --backup must refer to different files' "$TEST_DIR/backup-conflict.stderr"

echo "wordpress_rest tests passed"
