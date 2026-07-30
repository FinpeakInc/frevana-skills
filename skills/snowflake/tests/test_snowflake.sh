#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WRAPPER="${SCRIPT_DIR}/scripts/snowflake.sh"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

mkdir -p "$TEST_ROOT/bin"
cat >"$TEST_ROOT/bin/snow" <<'MOCK'
#!/usr/bin/env bash
if [[ "${1-}" == "--version" ]]; then
  echo "Snowflake CLI version 9.9.9"
  exit 0
fi
printf '[{"argv":'
printf '"'
printf '%s' "$*" | sed 's/\\/\\\\/g; s/"/\\"/g'
printf '"}]\n'
MOCK
chmod +x "$TEST_ROOT/bin/snow"

cat >"$TEST_ROOT/bin/uname" <<'MOCK_UNAME'
#!/usr/bin/env bash
printf '%s\n' "${MOCK_PLATFORM:-Darwin}"
MOCK_UNAME
chmod +x "$TEST_ROOT/bin/uname"

export PATH="$TEST_ROOT/bin:$PATH"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "expected output to contain: $needle"
}

check_output="$(bash "$WRAPPER" check)"
assert_contains "$check_output" "9.9.9"

config_info_home="$TEST_ROOT/config-info-home"
mkdir -p "$config_info_home"
config_info_output="$(HOME="$config_info_home" MOCK_PLATFORM=Darwin bash "$WRAPPER" config-info)"
assert_contains "$config_info_output" "$config_info_home/Library/Application Support/snowflake/config.toml"
assert_contains "$config_info_output" '"config_exists":false'

shared_config_home="$TEST_ROOT/shared-config-home"
shared_config_dir="$shared_config_home/Library/Application Support/snowflake"
mkdir -p "$shared_config_dir"
printf '[shared]\naccount = "example"\n' >"$shared_config_dir/connections.toml"
chmod 600 "$shared_config_dir/connections.toml"
shared_info_output="$(HOME="$shared_config_home" MOCK_PLATFORM=Darwin bash "$WRAPPER" config-info)"
assert_contains "$shared_info_output" '"connections_exists":true'
assert_contains "$shared_info_output" "$shared_config_dir/connections.toml"
if HOME="$shared_config_home" \
  MOCK_PLATFORM=Darwin \
  SNOWFLAKE_ACCOUNT=shared-account \
  SNOWFLAKE_USER=shared-user \
  SNOWFLAKE_PAT=shared-token \
  bash "$WRAPPER" setup-pat >"$TEST_ROOT/shared.out" 2>"$TEST_ROOT/shared.err"; then
  fail "setup-pat accepted a config directory with an active connections.toml"
fi
assert_contains "$(<"$TEST_ROOT/shared.err")" "Snowflake CLI would ignore a connection added to config.toml"
if HOME="$shared_config_home" \
  MOCK_PLATFORM=Darwin \
  bash "$WRAPPER" connection-remove \
    --name shared \
    --execute >"$TEST_ROOT/shared-remove.out" 2>"$TEST_ROOT/shared-remove.err"; then
  fail "connection-remove accepted a config directory with an active connections.toml"
fi
assert_contains "$(<"$TEST_ROOT/shared-remove.err")" "only edits config.toml"

INSTALL_ROOT="$TEST_ROOT/install"
mkdir -p "$INSTALL_ROOT/bin" "$INSTALL_ROOT/tool-bin"
export MOCK_UV_BIN="$INSTALL_ROOT/tool-bin"
export MOCK_UV_LOG="$INSTALL_ROOT/uv.log"
cat >"$INSTALL_ROOT/bin/uv" <<'MOCK_UV'
#!/usr/bin/env bash
set -euo pipefail
if [[ "$*" == "tool install snowflake-cli" ]]; then
  printf '%s\n' "$*" >>"$MOCK_UV_LOG"
  cat >"$MOCK_UV_BIN/snow" <<'MOCK_SNOW'
#!/usr/bin/env bash
if [[ "${1-}" == "--version" ]]; then
  echo "Snowflake CLI version 8.8.8"
fi
MOCK_SNOW
  chmod +x "$MOCK_UV_BIN/snow"
  exit 0
fi
if [[ "$*" == "tool dir --bin" ]]; then
  printf '%s\n' "$MOCK_UV_BIN"
  exit 0
fi
exit 2
MOCK_UV
chmod +x "$INSTALL_ROOT/bin/uv"

install_output="$(PATH="$INSTALL_ROOT/bin:/usr/bin:/bin" bash "$WRAPPER" check)"
assert_contains "$install_output" "8.8.8"
assert_contains "$(<"$MOCK_UV_LOG")" "tool install snowflake-cli"

BAD_SNOW_ROOT="$TEST_ROOT/bad-snow"
mkdir -p "$BAD_SNOW_ROOT"
cat >"$BAD_SNOW_ROOT/snow" <<'BAD_SNOW'
#!/usr/bin/env bash
if [[ "${1-}" == "--version" ]]; then
  echo "unrelated snow utility"
fi
exit 0
BAD_SNOW
chmod +x "$BAD_SNOW_ROOT/snow"
if PATH="$BAD_SNOW_ROOT:/usr/bin:/bin" \
  bash "$WRAPPER" check >"$TEST_ROOT/bad-snow.out" 2>"$TEST_ROOT/bad-snow.err"; then
  fail "check accepted an unrelated executable named snow"
fi
assert_contains "$(<"$TEST_ROOT/bad-snow.err")" "not a working Snowflake CLI"

list_output="$(bash "$WRAPPER" connection-list --output "$TEST_ROOT/list.json")"
assert_contains "$list_output" "connection list --format JSON_EXT --enhanced-exit-codes"
[[ -s "$TEST_ROOT/list.json" ]] || fail "connection-list did not save output"
list_mode="$(stat -f '%Lp' "$TEST_ROOT/list.json" 2>/dev/null || stat -c '%a' "$TEST_ROOT/list.json")"
[[ "$list_mode" == "600" ]] || fail "explicit output file mode is not 600"

output_target="$TEST_ROOT/output-target.json"
output_link="$TEST_ROOT/output-link.json"
printf 'preserve\n' >"$output_target"
chmod 600 "$output_target"
ln -s "$output_target" "$output_link"
if bash "$WRAPPER" connection-list \
  --output "$output_link" >"$TEST_ROOT/output-link.out" 2>"$TEST_ROOT/output-link.err"; then
  fail "connection-list accepted a symlink output"
fi
assert_contains "$(<"$TEST_ROOT/output-link.err")" "not a symlink"
[[ "$(<"$output_target")" == "preserve" ]] || fail "symlink output target was modified"

diag_allowlist="$TEST_ROOT/allowlist.json"
printf '{}\n' >"$diag_allowlist"
diag_output="$(bash "$WRAPPER" connection-test \
  --connection demo \
  --enable-diag \
  --diag-log-path "$TEST_ROOT/diag" \
  --diag-allowlist-path "$diag_allowlist" \
  --output "$TEST_ROOT/diag.json")"
assert_contains "$diag_output" "--enable-diag"
assert_contains "$diag_output" "--diag-log-path $TEST_ROOT/diag"
assert_contains "$diag_output" "--diag-allowlist-path $diag_allowlist"

readonly_output="$(bash "$WRAPPER" query --connection demo --sql "SELECT 1" --output "$TEST_ROOT/query.json")"
assert_contains "$readonly_output" "sql --query SELECT 1 --connection demo"
assert_contains "$readonly_output" "--local-only"
[[ -s "$TEST_ROOT/query.json" ]] || fail "read-only query did not save output"

readonly_preview="$(bash "$WRAPPER" query --sql "SELECT external_udf(1)" --preview)"
assert_contains "$readonly_preview" '"dry_run":true'

cte_output="$(bash "$WRAPPER" query --sql "WITH x AS (SELECT 1) SELECT * FROM x" --output "$TEST_ROOT/cte.json")"
assert_contains "$cte_output" "--query WITH x AS"

write_preview="$(bash "$WRAPPER" query --sql "UPDATE jobs SET status = 'done'")"
assert_contains "$write_preview" '"dry_run":true'
assert_contains "$write_preview" '"action":"query"'

multi_statement_preview="$(bash "$WRAPPER" query --sql "SELECT 1; DROP TABLE jobs")"
assert_contains "$multi_statement_preview" '"dry_run":true'

cancel_preview="$(bash "$WRAPPER" query --sql "SELECT SYSTEM\$CANCEL_QUERY('query-id')")"
assert_contains "$cancel_preview" '"dry_run":true'

system_send_preview="$(bash "$WRAPPER" query --sql "SELECT SYSTEM\$SEND_EMAIL('integration', 'a@example.com', 'subject', 'body')")"
assert_contains "$system_send_preview" '"dry_run":true'

write_output="$(bash "$WRAPPER" query --sql "UPDATE jobs SET status = 'done'" --execute --output "$TEST_ROOT/write.json")"
assert_contains "$write_output" "UPDATE jobs"
[[ -s "$TEST_ROOT/write.json" ]] || fail "executed write did not save output"

connection_preview="$(bash "$WRAPPER" connection-add --name demo --account org-account --user service)"
assert_contains "$connection_preview" '"dry_run":true'
assert_contains "$connection_preview" "--no-interactive"

pat_file="$TEST_ROOT/snowflake.pat"
printf 'test-pat-secret-that-must-not-appear\n' >"$pat_file"
chmod 600 "$pat_file"
pat_preview="$(bash "$WRAPPER" connection-add-pat \
  --name pat-demo \
  --account org-account \
  --user service \
  --token-file "$pat_file" \
  --role AI_ROLE)"
assert_contains "$pat_preview" '"action":"connection-add-pat"'
assert_contains "$pat_preview" "--authenticator PROGRAMMATIC_ACCESS_TOKEN"
assert_contains "$pat_preview" "--token-file-path"
[[ "$pat_preview" != *"test-pat-secret"* ]] || fail "PAT secret leaked into preview"

pat_output="$(bash "$WRAPPER" connection-add-pat \
  --name pat-demo \
  --account org-account \
  --user service \
  --token-file "$pat_file" \
  --execute \
  --output "$TEST_ROOT/pat.json")"
assert_contains "$pat_output" "--authenticator PROGRAMMATIC_ACCESS_TOKEN"
assert_contains "$pat_output" "--token-file-path"

setup_pat_file="$TEST_ROOT/persisted/setup.pat"
setup_preview="$(SNOWFLAKE_CONNECTION_NAME=env-demo \
  SNOWFLAKE_ACCOUNT=env-account \
  SNOWFLAKE_USER=env-user \
  SNOWFLAKE_ROLE=env-role \
  SNOWFLAKE_WAREHOUSE=env-warehouse \
  SNOWFLAKE_DATABASE=env-database \
  SNOWFLAKE_SCHEMA=env-schema \
  SNOWFLAKE_PAT=environment-pat-secret \
  bash "$WRAPPER" setup-pat --token-file "$setup_pat_file")"
assert_contains "$setup_preview" '"action":"setup-pat"'
assert_contains "$setup_preview" "SNOWFLAKE_PAT"
assert_contains "$setup_preview" "--authenticator PROGRAMMATIC_ACCESS_TOKEN"
[[ "$setup_preview" != *"environment-pat-secret"* ]] || fail "environment PAT leaked into preview"
[[ ! -e "$setup_pat_file" ]] || fail "setup-pat preview wrote a token file"

setup_output="$(SNOWFLAKE_CONNECTION_NAME=env-demo \
  SNOWFLAKE_ACCOUNT=env-account \
  SNOWFLAKE_USER=env-user \
  SNOWFLAKE_ROLE=env-role \
  SNOWFLAKE_WAREHOUSE=env-warehouse \
  SNOWFLAKE_DATABASE=env-database \
  SNOWFLAKE_SCHEMA=env-schema \
  SNOWFLAKE_PAT=environment-pat-secret \
  bash "$WRAPPER" setup-pat \
    --token-file "$setup_pat_file" \
    --execute \
    --output "$TEST_ROOT/setup.json")"
assert_contains "$setup_output" "--connection-name env-demo"
assert_contains "$setup_output" "--account env-account"
assert_contains "$setup_output" "--user env-user"
assert_contains "$setup_output" "--token-file-path $setup_pat_file"
[[ "$setup_output" != *"environment-pat-secret"* ]] || fail "environment PAT leaked into command output"
[[ "$(<"$setup_pat_file")" == "environment-pat-secret" ]] || fail "setup-pat did not persist the PAT"
file_mode_for_test="$(stat -f '%Lp' "$setup_pat_file" 2>/dev/null || stat -c '%a' "$setup_pat_file")"
[[ "$file_mode_for_test" == "600" ]] ||
  fail "setup-pat token file mode is not 600"

minimal_home="$TEST_ROOT/minimal-home"
mkdir -p "$minimal_home"
minimal_output="$(HOME="$minimal_home" \
  MOCK_PLATFORM=Darwin \
  SNOWFLAKE_ACCOUNT=minimal-account \
  SNOWFLAKE_USER=minimal-user \
  SNOWFLAKE_PAT=minimal-pat-secret \
  bash "$WRAPPER" setup-pat --execute --output "$TEST_ROOT/minimal.json")"
minimal_pat="$minimal_home/Library/Application Support/snowflake/pat/default.pat"
[[ -f "$minimal_pat" ]] || fail "minimal setup-pat did not persist the default connection PAT"
assert_contains "$minimal_output" "--connection-name default"
assert_contains "$minimal_output" "--default"
assert_contains "$minimal_output" "connection test --connection default"
[[ -f "$TEST_ROOT/minimal.test.json" ]] || fail "minimal setup-pat did not save its connection test"
[[ "$minimal_output" != *"minimal-pat-secret"* ]] || fail "minimal setup PAT leaked into command output"

connection_env_pat="$TEST_ROOT/connection-env.pat"
connection_env_output="$(SNOWFLAKE_DEFAULT_CONNECTION_NAME=team_prod \
  SNOWFLAKE_CONNECTIONS_TEAM_PROD_ACCOUNT=specific-account \
  SNOWFLAKE_CONNECTIONS_TEAM_PROD_USER=specific-user \
  SNOWFLAKE_CONNECTIONS_TEAM_PROD_ROLE=specific-role \
  SNOWFLAKE_CONNECTIONS_TEAM_PROD_TOKEN=specific-pat-secret \
  SNOWFLAKE_ACCOUNT=generic-account \
  SNOWFLAKE_USER=generic-user \
  bash "$WRAPPER" setup-pat \
    --token-file "$connection_env_pat" \
    --skip-test \
    --execute \
    --output "$TEST_ROOT/connection-env.json")"
assert_contains "$connection_env_output" "--connection-name team_prod"
assert_contains "$connection_env_output" "--account specific-account"
assert_contains "$connection_env_output" "--user specific-user"
assert_contains "$connection_env_output" "--role specific-role"
[[ "$connection_env_output" != *"connection test"* ]] || fail "setup-pat --skip-test ran a connection test"
[[ "$(<"$connection_env_pat")" == "specific-pat-secret" ]] ||
  fail "setup-pat did not read the connection-specific token environment variable"

ambiguous_name_pat="$TEST_ROOT/ambiguous-name.pat"
ambiguous_name_preview="$(SNOWFLAKE_DEFAULT_CONNECTION_NAME=team-prod \
  SNOWFLAKE_CONNECTIONS_TEAM_PROD_ACCOUNT=colliding-account \
  SNOWFLAKE_CONNECTIONS_TEAM_PROD_USER=colliding-user \
  SNOWFLAKE_CONNECTIONS_TEAM_PROD_TOKEN=colliding-token \
  SNOWFLAKE_ACCOUNT=generic-account \
  SNOWFLAKE_USER=generic-user \
  SNOWFLAKE_PAT=generic-token \
  bash "$WRAPPER" setup-pat --token-file "$ambiguous_name_pat" --skip-test)"
assert_contains "$ambiguous_name_preview" "--account generic-account"
assert_contains "$ambiguous_name_preview" "--user generic-user"
[[ "$ambiguous_name_preview" != *"colliding-account"* ]] ||
  fail "ambiguous connection name consumed a colliding connection-specific variable"

reused_pat="$TEST_ROOT/reused.pat"
printf 'reused-pat-secret\n' >"$reused_pat"
chmod 600 "$reused_pat"
reuse_preview="$(SNOWFLAKE_ACCOUNT=reuse-account \
  SNOWFLAKE_USER=reuse-user \
  SNOWFLAKE_TOKEN_FILE_PATH="$reused_pat" \
  bash "$WRAPPER" setup-pat)"
assert_contains "$reuse_preview" "protected"
assert_contains "$reuse_preview" "PAT"
assert_contains "$reuse_preview" "$reused_pat"
[[ "$reuse_preview" != *"reused-pat-secret"* ]] || fail "reused PAT leaked into preview"

mac_home="$TEST_ROOT/mac-home"
mkdir -p "$mac_home"
mac_default_output="$(HOME="$mac_home" \
  MOCK_PLATFORM=Darwin \
  SNOWFLAKE_CONNECTION_NAME=mac-default \
  SNOWFLAKE_ACCOUNT=env-account \
  SNOWFLAKE_USER=env-user \
  SNOWFLAKE_PAT=mac-pat-secret \
  bash "$WRAPPER" setup-pat --execute --output "$TEST_ROOT/mac-default.json")"
mac_default_pat="$mac_home/Library/Application Support/snowflake/pat/mac-default.pat"
[[ -f "$mac_default_pat" ]] || fail "setup-pat did not use the official macOS configuration directory"
[[ "$mac_default_output" != *"mac-pat-secret"* ]] || fail "macOS default PAT leaked into command output"

linux_home="$TEST_ROOT/linux-home"
linux_xdg="$TEST_ROOT/linux-xdg"
mkdir -p "$linux_home"
linux_default_output="$(HOME="$linux_home" \
  XDG_CONFIG_HOME="$linux_xdg" \
  MOCK_PLATFORM=Linux \
  SNOWFLAKE_CONNECTION_NAME=linux-default \
  SNOWFLAKE_ACCOUNT=env-account \
  SNOWFLAKE_USER=env-user \
  SNOWFLAKE_PAT=linux-pat-secret \
  bash "$WRAPPER" setup-pat --execute --output "$TEST_ROOT/linux-default.json")"
linux_default_pat="$linux_xdg/snowflake/pat/linux-default.pat"
[[ -f "$linux_default_pat" ]] || fail "setup-pat did not use the Linux XDG configuration directory"
[[ "$linux_default_output" != *"linux-pat-secret"* ]] || fail "Linux default PAT leaked into command output"

custom_config="$TEST_ROOT/custom-config/config.toml"
custom_config_output="$(HOME="$linux_home" \
  MOCK_PLATFORM=Linux \
  SNOWFLAKE_CONNECTION_NAME=custom-config \
  SNOWFLAKE_ACCOUNT=env-account \
  SNOWFLAKE_USER=env-user \
  SNOWFLAKE_PAT=custom-config-pat-secret \
  bash "$WRAPPER" setup-pat \
    --config-file "$custom_config" \
    --execute \
    --output "$TEST_ROOT/custom-config.json")"
custom_config_pat="$TEST_ROOT/custom-config/pat/custom-config.pat"
[[ -f "$custom_config_pat" ]] || fail "setup-pat did not place the PAT beside --config-file"
assert_contains "$custom_config_output" "--config-file $custom_config"

existing_pat_dir="$TEST_ROOT/existing-pat-dir"
mkdir -p "$existing_pat_dir"
chmod 750 "$existing_pat_dir"
existing_dir_token="$existing_pat_dir/preserved.pat"
existing_dir_output="$(SNOWFLAKE_ACCOUNT=dir-account \
  SNOWFLAKE_USER=dir-user \
  SNOWFLAKE_PAT=dir-token \
  bash "$WRAPPER" setup-pat \
    --name preserved-dir \
    --token-file "$existing_dir_token" \
    --skip-test \
    --execute \
    --output "$TEST_ROOT/existing-dir.json")"
assert_contains "$existing_dir_output" "--connection-name preserved-dir"
existing_dir_mode="$(stat -f '%Lp' "$existing_pat_dir" 2>/dev/null || stat -c '%a' "$existing_pat_dir")"
[[ "$existing_dir_mode" == "750" ]] || fail "setup-pat changed an existing PAT directory mode"

unsafe_pat_dir="$TEST_ROOT/unsafe-pat-dir"
mkdir -p "$unsafe_pat_dir"
chmod 770 "$unsafe_pat_dir"
if SNOWFLAKE_ACCOUNT=unsafe-dir-account \
  SNOWFLAKE_USER=unsafe-dir-user \
  SNOWFLAKE_PAT=unsafe-dir-token \
  bash "$WRAPPER" setup-pat \
    --name unsafe-dir \
    --token-file "$unsafe_pat_dir/token.pat" \
    --skip-test \
    --execute >"$TEST_ROOT/unsafe-dir.out" 2>"$TEST_ROOT/unsafe-dir.err"; then
  fail "setup-pat accepted a group-writable PAT directory"
fi
assert_contains "$(<"$TEST_ROOT/unsafe-dir.err")" "must not be group- or world-writable"

default_output_root="$TEST_ROOT/default-output"
default_output_token="$TEST_ROOT/default-output.pat"
mkdir -p "$default_output_root"
(
  cd "$default_output_root"
  SNOWFLAKE_ACCOUNT=output-account \
    SNOWFLAKE_USER=output-user \
    SNOWFLAKE_PAT=output-token \
    bash "$WRAPPER" setup-pat \
      --name output-test \
      --token-file "$default_output_token" \
      --execute >/dev/null
)
default_output_count="$(find "$default_output_root/out" -maxdepth 1 -type f -name '*.json' | wc -l | tr -d '[:space:]')"
[[ "$default_output_count" == "2" ]] || fail "setup-pat default outputs were not saved to two unique files"
while IFS= read -r default_output_file; do
  default_output_mode="$(stat -f '%Lp' "$default_output_file" 2>/dev/null || stat -c '%a' "$default_output_file")"
  [[ "$default_output_mode" == "600" ]] || fail "default output file mode is not 600"
done < <(find "$default_output_root/out" -maxdepth 1 -type f -name '*.json')

chmod 644 "$pat_file"
if bash "$WRAPPER" connection-add-pat \
  --name unsafe-pat \
  --account org-account \
  --user service \
  --token-file "$pat_file" >"$TEST_ROOT/pat-unsafe.out" 2>"$TEST_ROOT/pat-unsafe.err"; then
  fail "connection-add-pat accepted an unsafe token file"
fi
assert_contains "$(<"$TEST_ROOT/pat-unsafe.err")" "permissions must be 0400 or 0600"

if bash "$WRAPPER" connection-add \
  --name unsafe-generic-pat \
  --account org-account \
  --user service \
  --authenticator PROGRAMMATIC_ACCESS_TOKEN \
  --token-file "$pat_file" >"$TEST_ROOT/generic-pat-unsafe.out" 2>"$TEST_ROOT/generic-pat-unsafe.err"; then
  fail "generic connection-add bypassed PAT file permission checks"
fi
assert_contains "$(<"$TEST_ROOT/generic-pat-unsafe.err")" "permissions must be 0400 or 0600"

chmod 600 "$pat_file"
lowercase_auth_preview="$(bash "$WRAPPER" connection-add \
  --name lowercase-auth \
  --account org-account \
  --user service \
  --authenticator programmatic_access_token \
  --token-file "$pat_file")"
assert_contains "$lowercase_auth_preview" "--authenticator PROGRAMMATIC_ACCESS_TOKEN"
chmod 644 "$pat_file"

private_key_file="$TEST_ROOT/private-key.p8"
printf 'private-key-placeholder\n' >"$private_key_file"
chmod 644 "$private_key_file"
if bash "$WRAPPER" connection-add \
  --name unsafe-key \
  --account org-account \
  --user service \
  --authenticator SNOWFLAKE_JWT \
  --private-key-file "$private_key_file" >"$TEST_ROOT/private-key-unsafe.out" 2>"$TEST_ROOT/private-key-unsafe.err"; then
  fail "connection-add accepted an unsafe private key file"
fi
assert_contains "$(<"$TEST_ROOT/private-key-unsafe.err")" "Private key file permissions must be 0400 or 0600"

if bash "$WRAPPER" connection-add --name demo --password secret >"$TEST_ROOT/forbidden.out" 2>"$TEST_ROOT/forbidden.err"; then
  fail "connection-add accepted a password argument"
fi
assert_contains "$(<"$TEST_ROOT/forbidden.err")" "intentionally unsupported"

definition_file="$TEST_ROOT/warehouse.json"
printf '{"name":"AI_WH"}\n' >"$definition_file"
object_preview="$(bash "$WRAPPER" object-create \
  --type warehouse \
  --definition-file "$definition_file" \
  --config-file "$TEST_ROOT/object-config.toml" \
  --connection object-connection \
  --database object-database \
  --schema object-schema \
  --role object-role \
  --warehouse object-warehouse)"
assert_contains "$object_preview" '"dry_run":true'
assert_contains "$object_preview" "definition"
assert_contains "$object_preview" "redacted"
assert_contains "$object_preview" "--config-file"
assert_contains "$object_preview" "object-connection"
assert_contains "$object_preview" "object-database"
assert_contains "$object_preview" "object-schema"
assert_contains "$object_preview" "object-role"
assert_contains "$object_preview" "object-warehouse"
[[ "$object_preview" != *"AI_WH"* ]] || fail "object definition leaked into preview"

sensitive_definition="$TEST_ROOT/sensitive-object.json"
printf '{"name":"unsafe","password":"must-not-reach-argv"}\n' >"$sensitive_definition"
if bash "$WRAPPER" object-create \
  --type service \
  --definition-file "$sensitive_definition" \
  --execute >"$TEST_ROOT/sensitive.out" 2>"$TEST_ROOT/sensitive.err"; then
  fail "object-create accepted a definition containing a sensitive field"
fi
assert_contains "$(<"$TEST_ROOT/sensitive.err")" "sensitive fields"

large_definition="$TEST_ROOT/large-object.json"
dd if=/dev/zero bs=32769 count=1 2>/dev/null | tr '\0' 'x' >"$large_definition"
if bash "$WRAPPER" object-create \
  --type warehouse \
  --definition-file "$large_definition" \
  --execute >"$TEST_ROOT/large.out" 2>"$TEST_ROOT/large.err"; then
  fail "object-create accepted an oversized definition"
fi
assert_contains "$(<"$TEST_ROOT/large.err")" "32768-byte"

echo "All snowflake wrapper tests passed."
