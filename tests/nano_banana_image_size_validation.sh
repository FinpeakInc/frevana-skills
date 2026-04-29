#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

run_with_fake_curl() {
  local script_path="$1"
  local image_size="$2"
  local payload_capture_file="$3"
  local output=""
  local status=0
  local temp_dir=""

  temp_dir="$(mktemp -d)"

  cat > "$temp_dir/curl" <<'EOF'
#!/usr/bin/env bash

set -euo pipefail

output_file=""
payload_file=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --connect-timeout|--max-time|-w|-X|-H|-o|--data)
      if [[ "$1" == "-o" ]]; then
        output_file="${2:-}"
      elif [[ "$1" == "--data" ]]; then
        payload_file="${2:-}"
      fi
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

payload_file="${payload_file#@}"
cp "$payload_file" "$TEST_CAPTURE_PAYLOAD"
printf '%s\n' '{"generated_images":[{"image_url":"https://example.com/fake.png","mime_type":"image/png"}],"credits_consumed":1}' > "$output_file"
printf '200'
EOF
  chmod +x "$temp_dir/curl"

  set +e
  output="$(
    env FREVANA_TOKEN="test-token" \
      TEST_CAPTURE_PAYLOAD="$payload_capture_file" \
      PATH="$temp_dir:$PATH" \
      bash "$script_path" \
      --prompt "test prompt" \
      --image-size "$image_size" \
      2>&1
  )"
  status=$?
  set -e

  if [[ "$status" -ne 0 ]]; then
    echo "Expected success for $script_path with --image-size $image_size"
    echo "$output"
    rm -rf "$temp_dir"
    exit 1
  fi

  rm -rf "$temp_dir"
}

assert_normalized_image_size() {
  local script_path="$1"
  local raw_image_size="$2"
  local expected_image_size="$3"
  local payload_capture_file=""
  local actual_image_size=""

  payload_capture_file="$(mktemp)"
  run_with_fake_curl "$script_path" "$raw_image_size" "$payload_capture_file"

  actual_image_size="$(
    python3 - "$payload_capture_file" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(payload["config"]["imageConfig"]["imageSize"])
PY
  )"
  rm -f "$payload_capture_file"

  if [[ "$actual_image_size" != "$expected_image_size" ]]; then
    echo "Unexpected normalized image size for $script_path"
    echo "Input: $raw_image_size"
    echo "Expected: $expected_image_size"
    echo "Actual: $actual_image_size"
    exit 1
  fi
}

run_expect_failure() {
  local script_path="$1"
  local image_size="$2"
  local expected_message="$3"
  local output=""
  local status=0

  set +e
  output="$(
    env -u FREVANA_TOKEN \
      bash "$script_path" \
      --prompt "test prompt" \
      --image-size "$image_size" \
      2>&1
  )"
  status=$?
  set -e

  if [[ "$status" -eq 0 ]]; then
    echo "Expected failure for $script_path with --image-size $image_size"
    exit 1
  fi

  if [[ "$output" != *"$expected_message"* ]]; then
    echo "Unexpected output for $script_path with --image-size $image_size"
    echo "Expected to find: $expected_message"
    echo "Actual output:"
    echo "$output"
    exit 1
  fi
}

assert_normalized_image_size \
  "$ROOT_DIR/skills/nano-banana-2/scripts/generate_image.sh" \
  "1024" \
  "1K"

assert_normalized_image_size \
  "$ROOT_DIR/skills/nano-banana-2/scripts/generate_image.sh" \
  "1024x1024" \
  "1K"

assert_normalized_image_size \
  "$ROOT_DIR/skills/nano-banana-2/scripts/generate_image.sh" \
  "999" \
  "1K"

assert_normalized_image_size \
  "$ROOT_DIR/skills/nano-banana-2/scripts/generate_image.sh" \
  "1536" \
  "2K"

assert_normalized_image_size \
  "$ROOT_DIR/skills/nano-banana-2/scripts/generate_image.sh" \
  "1536x1024" \
  "2K"

assert_normalized_image_size \
  "$ROOT_DIR/skills/nano-banana-2/scripts/generate_image.sh" \
  "3072" \
  "4K"

assert_normalized_image_size \
  "$ROOT_DIR/skills/nano-banana-2/scripts/generate_image.sh" \
  "4k" \
  "4K"

assert_normalized_image_size \
  "$ROOT_DIR/skills/nano-banana-pro/scripts/generate_image.sh" \
  "1024" \
  "1K"

assert_normalized_image_size \
  "$ROOT_DIR/skills/nano-banana-pro/scripts/generate_image.sh" \
  "1024X1024" \
  "1K"

assert_normalized_image_size \
  "$ROOT_DIR/skills/nano-banana-pro/scripts/generate_image.sh" \
  "1536" \
  "2K"

assert_normalized_image_size \
  "$ROOT_DIR/skills/nano-banana-pro/scripts/generate_image.sh" \
  "3500x1200" \
  "4K"

assert_normalized_image_size \
  "$ROOT_DIR/skills/nano-banana-pro/scripts/generate_image.sh" \
  "4096" \
  "4K"

run_expect_failure \
  "$ROOT_DIR/skills/nano-banana-2/scripts/generate_image.sh" \
  "huge" \
  "Invalid value for --image-size: huge"

run_expect_failure \
  "$ROOT_DIR/skills/nano-banana-pro/scripts/generate_image.sh" \
  "huge" \
  "Invalid value for --image-size: huge"

echo "nano banana image-size validation checks passed"
