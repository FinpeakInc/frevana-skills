#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_PATH="$SCRIPT_DIR/../scripts/search_google_forums.sh"

assert_status() {
  local expected="$1"
  shift
  set +e
  "$@" >/tmp/google_forums_test_stdout.$$ 2>/tmp/google_forums_test_stderr.$$
  local actual="$?"
  set -e
  if [[ "$actual" != "$expected" ]]; then
    echo "Expected exit status $expected, got $actual for: $*" >&2
    echo "stderr:" >&2
    cat /tmp/google_forums_test_stderr.$$ >&2
    rm -f /tmp/google_forums_test_stdout.$$ /tmp/google_forums_test_stderr.$$
    exit 1
  fi
  rm -f /tmp/google_forums_test_stdout.$$ /tmp/google_forums_test_stderr.$$
}

assert_output_contains() {
  local expected="$1"
  shift
  set +e
  "$@" >/tmp/google_forums_test_stdout.$$ 2>/tmp/google_forums_test_stderr.$$
  local status="$?"
  set -e
  if [[ "$status" != 0 ]]; then
    echo "Expected command to pass, got $status for: $*" >&2
    cat /tmp/google_forums_test_stderr.$$ >&2
    rm -f /tmp/google_forums_test_stdout.$$ /tmp/google_forums_test_stderr.$$
    exit 1
  fi
  if ! grep -Fq -- "$expected" /tmp/google_forums_test_stdout.$$; then
    echo "Expected stdout to contain: $expected" >&2
    cat /tmp/google_forums_test_stdout.$$ >&2
    rm -f /tmp/google_forums_test_stdout.$$ /tmp/google_forums_test_stderr.$$
    exit 1
  fi
  rm -f /tmp/google_forums_test_stdout.$$ /tmp/google_forums_test_stderr.$$
}

assert_output_contains "--start-date" bash "$SCRIPT_PATH" --help
assert_status 1 bash "$SCRIPT_PATH" --gl us
assert_status 1 bash "$SCRIPT_PATH" --q "vibe coding" --device tv
assert_status 1 bash "$SCRIPT_PATH" --q "vibe coding" --start -1
assert_status 1 bash "$SCRIPT_PATH" --q "vibe coding" --start nope
