---
name: snowflake
description: Use when the user wants to install or verify the official Snowflake CLI, configure or test PAT-authenticated Snowflake connections, execute Snowflake SQL, inspect databases and objects, create or drop Snowflake objects, run SQL files, or operate Snowflake workloads and applications through the `snow` command. Provides an AI-safe Bash wrapper with automatic CLI installation, owner-only PAT token files, JSON output, local-only SQL includes, dry-run previews, and explicit confirmation gates for DDL, DML, connection changes, and destructive operations.
---

# Snowflake CLI

Operate Snowflake through the official `snow` CLI. Use the bundled wrapper for common connection, SQL, and object workflows; use the official CLI directly only when the wrapper does not cover a specialized command.

## Requirements

- Require Python 3.10 or later for Snowflake CLI.
- Use the bundled wrapper for every operation. Before it runs a Snowflake command, it checks that `snow --help` succeeds and `snow --version` identifies Snowflake CLI; reject an unrelated or broken executable with the same name.
- If `snow` is missing, automatically run `uv tool install snowflake-cli`.
- `uv` is resolved automatically: the wrapper first searches common install locations (`~/.local/bin`, `~/.cargo/bin`, `/opt/homebrew/bin`, `${FREVANA_BIN_DIR}`, etc.). If missing, it auto-detects the environment and installs `uv` according to official Astral guidelines (PowerShell/winget/scoop on Windows; standalone installer `https://astral.sh/uv/install.sh` via `curl`/`wget` on macOS/Linux, with Homebrew, `pip`, and `cargo` fallbacks). Manual `uv` installation is only required if all installation methods are unavailable or blocked.
- After installation, resolve `snow` from `PATH` or the uv tool bin directory, symlink it to `${FREVANA_BIN_DIR}/snow` (`~/.frevana/bin/snow`), and verify it with `snow --help`.
- Run `scripts/snowflake.sh check` before the first operation to report the installed version.
- If `uv` cannot be resolved or installed and the executable cannot be found, stop with a clear setup error. Do not silently fall back to system `pip`.

## Safety Rules

- Never store passwords, OAuth secrets, tokens, private-key contents, or passphrases in this repository.
- Use PAT as the primary supported authentication flow for unattended AI processes.
- Require PAT token files to be regular, readable, non-empty, and owner-only with `0400` or `0600` permissions.
- During initial setup, allow connection fields and PAT to be sourced from environment variables. Persist the PAT only to an owner-only token file and write only its path to Snowflake configuration.
- Do not pass passwords, raw tokens, OAuth client secrets, or private-key contents on command lines.
- Keep Snowflake configuration files owner-readable/writable only (`0600`) on macOS and Linux.
- Run `connection-list` before inventing a connection name. Run `connection-test` before the first query.
- Prefer a least-privilege role and a dedicated warehouse for automation.
- Treat `-D/--variable` SQL template values as textual substitution, not bound parameters. Never interpolate untrusted values into SQL.
- The wrapper automatically executes clearly read-only SQL. It previews all other SQL and requires `--execute`.
- Use `--preview` for SQL from an untrusted source or SQL that calls UDFs, external functions, stored logic, or unfamiliar `SYSTEM$` functions, even when it begins with `SELECT`.
- The wrapper previews every SQL statement containing a `SYSTEM$` function because some system functions perform external or administrative side effects.
- After inspecting a mutation preview, obtain explicit user confirmation before rerunning it with `--execute`.
- Before `UPDATE`, `DELETE`, or `MERGE`, run a read-only query with the same predicate and verify the target count and current values. After execution, query the target again to verify the intended result.
- Use `--single-transaction` for multi-statement writes when Snowflake supports the statements in a transaction.
- Keep the wrapper's `--local-only` SQL protection enabled. Do not use remote `!source` or `!load` inputs without explicit user approval and inspection.
- Do not interpret `--local-only` as a general no-network or no-side-effect guarantee; it only blocks URL-based SQL include/load directives.
- Do not enable debug logging when queries or connection metadata may contain secrets.
- Treat `object-create`, `object-drop`, connection add/remove/default changes, application deploys, stage uploads, and service changes as mutations.

## Common Workflow

Set the script path once:

```bash
SNOWFLAKE_SKILL="<skill-path>/scripts/snowflake.sh"
```

Inspect the installation, resolved configuration, and redacted connections:

```bash
bash "$SNOWFLAKE_SKILL" check
bash "$SNOWFLAKE_SKILL" config-info
bash "$SNOWFLAKE_SKILL" connection-list
```

`config-info` reports the resolved `config.toml`, the sibling `connections.toml`, whether each exists, and which file supplies connections. Snowflake CLI normally masks passwords in connection listings. Inspect output before sharing it outside the current process.

If a usable connection already exists, test it:

```bash
bash "$SNOWFLAKE_SKILL" connection-test --connection analytics
```

If normal testing reports connectivity problems, collect diagnostics into an absolute local directory:

```bash
bash "$SNOWFLAKE_SKILL" connection-test \
  --connection analytics \
  --enable-diag \
  --diag-log-path /absolute/path/snowflake-diag
```

Inspect diagnostic files for account, host, user, and network metadata before sharing them.

If no usable connection exists, run the PAT setup below. Successful setup tests the new connection automatically.

Inspect context before querying:

```bash
bash "$SNOWFLAKE_SKILL" query \
  --connection analytics \
  --sql "SELECT CURRENT_ACCOUNT(), CURRENT_USER(), CURRENT_ROLE(), CURRENT_WAREHOUSE(), CURRENT_DATABASE(), CURRENT_SCHEMA();"
```

## Manage Connections

### Configure PAT authentication

Before configuration:

- Confirm PAT is enabled for the Snowflake account and allowed by the user's authentication policy.
- Confirm the user satisfies Snowflake's PAT network-policy requirements.
- Prefer a service user with a PAT restricted to the least-privilege role required by the AI process.
- Generate the PAT in Snowsight or through a separate authorized administrator session. The token secret is only displayed once.
- Save only the token secret in a file outside this repository and run `chmod 600 /secure/path/snowflake.pat`.

The shortest initial setup needs only three environment variables:

```bash
export SNOWFLAKE_ACCOUNT=myorg-myaccount
export SNOWFLAKE_USER=svc_analytics
export SNOWFLAKE_PAT='<token secret>'

bash "$SNOWFLAKE_SKILL" setup-pat
bash "$SNOWFLAKE_SKILL" setup-pat --execute
unset SNOWFLAKE_PAT
```

This creates a connection named `default`, marks it as the default, persists only the protected PAT file path in Snowflake configuration, and immediately runs `snow connection test`. When `--output result.json` is supplied, save the test result as `result.test.json`.

Set optional context only when needed:

```bash
export SNOWFLAKE_DEFAULT_CONNECTION_NAME=analytics
export SNOWFLAKE_ACCOUNT=myorg-myaccount
export SNOWFLAKE_USER=svc_analytics
export SNOWFLAKE_ROLE=ANALYST
export SNOWFLAKE_WAREHOUSE=AI_WH
export SNOWFLAKE_DATABASE=ANALYTICS
export SNOWFLAKE_SCHEMA=PUBLIC
export SNOWFLAKE_PAT='<token secret>'
```

`SNOWFLAKE_CONNECTION_NAME` remains a skill-specific compatibility alias, but prefer the official `SNOWFLAKE_DEFAULT_CONNECTION_NAME`. Command-line values take precedence during setup. For connection `analytics`, the wrapper then checks official connection-specific variables such as `SNOWFLAKE_CONNECTIONS_ANALYTICS_ACCOUNT`, `SNOWFLAKE_CONNECTIONS_ANALYTICS_USER`, `SNOWFLAKE_CONNECTIONS_ANALYTICS_ROLE`, and `SNOWFLAKE_CONNECTIONS_ANALYTICS_TOKEN` before generic `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_ROLE`, and `SNOWFLAKE_TOKEN`. Infer connection-specific variables only for connection names containing letters, digits, and underscores; names containing dots or hyphens use explicit command options or generic variables to avoid ambiguous environment-variable mappings.

Preview and execute:

```bash
bash "$SNOWFLAKE_SKILL" setup-pat
bash "$SNOWFLAKE_SKILL" setup-pat --execute
unset SNOWFLAKE_PAT
```

Resolve PAT input in this order:

1. Reuse an existing `--token-file`.
2. Reuse `SNOWFLAKE_CONNECTIONS_<NAME>_TOKEN_FILE_PATH` or `SNOWFLAKE_TOKEN_FILE_PATH`.
3. Read a raw token from `--token-env`, `SNOWFLAKE_CONNECTIONS_<NAME>_TOKEN`, `SNOWFLAKE_PAT`, or `SNOWFLAKE_TOKEN`, then persist it to a new owner-only file.

By default, store a new PAT in a `pat` subdirectory beside Snowflake CLI's selected configuration file with `0600` permissions. Respect the same location precedence: `--config-file`, `SNOWFLAKE_HOME`, an existing `~/.snowflake` directory, then the platform default. `SNOWFLAKE_PAT_DIR` overrides only the PAT directory. Never overwrite an existing PAT file.

Create a missing PAT directory with `0700`. Never change permissions on an existing directory; require it to be owned by the current user, not be a symlink, and not be group- or world-writable.

The wrapper invokes official `snow connection add --no-interactive`. Snowflake CLI writes the connection—including `authenticator = "PROGRAMMATIC_ACCESS_TOKEN"` and `token_file_path`—to its selected configuration. The PAT itself is not written into TOML. Use `--no-default` only when the new connection must not become the default, and `--skip-test` only when connectivity cannot be tested yet.

When no higher-precedence location applies, the official `config.toml` paths are:

- Linux: `${XDG_CONFIG_HOME:-$HOME/.config}/snowflake/config.toml`
- Windows: `%USERPROFILE%\AppData\Local\snowflake\config.toml`
- macOS: `~/Library/Application Support/snowflake/config.toml`

If `~/.snowflake` already exists, Snowflake CLI uses `~/.snowflake/config.toml` before those platform defaults.

If multiple Snowflake developer tools share connections, put them in `connections.toml` beside `config.toml`. When both files exist, Snowflake CLI reads connections from `connections.toml` and ignores connection definitions in `config.toml`; CLI-only settings such as `default_connection_name` remain in `config.toml`.

Because the official `snow connection add` flow writes to `config.toml`, `setup-pat` stops if an active sibling `connections.toml` exists instead of creating an ignored connection. In that case, add a reviewed `[connection-name]` entry to the shared `connections.toml`, or use `--config-file` in an isolated directory intended for Snowflake CLI only.

Preview the PAT connection:

```bash
bash "$SNOWFLAKE_SKILL" connection-add-pat \
  --name analytics \
  --account myorg-myaccount \
  --user svc_analytics \
  --token-file /secure/path/snowflake.pat \
  --role ANALYST \
  --warehouse AI_WH \
  --database ANALYTICS \
  --schema PUBLIC
```

The wrapper sets `PROGRAMMATIC_ACCESS_TOKEN` automatically and passes the file as `token_file_path`. It never reads or prints the token value. After reviewing the preview and receiving explicit confirmation, rerun with `--execute`:

```bash
bash "$SNOWFLAKE_SKILL" connection-add-pat \
  --name analytics \
  --account myorg-myaccount \
  --user svc_analytics \
  --token-file /secure/path/snowflake.pat \
  --role ANALYST \
  --warehouse AI_WH \
  --database ANALYTICS \
  --schema PUBLIC \
  --execute
```

Immediately run `connection-test --connection analytics`. If the token is role-restricted, keep `--role` consistent with that restriction.

Use the generic `connection-add` command only for future or advanced authentication methods. It applies the same `0400`/`0600`, regular-file, non-symlink checks to token and private-key files; selecting `PROGRAMMATIC_ACCESS_TOKEN` also enforces all PAT requirements.

Set or remove a connection with the same preview/execute flow:

```bash
bash "$SNOWFLAKE_SKILL" connection-set-default --name analytics
bash "$SNOWFLAKE_SKILL" connection-remove --name obsolete
```

When `connections.toml` is active, `connection-set-default` remains valid because the default name belongs in `config.toml`, but the wrapper refuses `connection-remove`: the official command removes only from `config.toml`. Remove a reviewed connection section directly from `connections.toml` instead.

Use `--config-file /secure/path/config.toml` when the user selects a non-default configuration file.

## Execute SQL

Run a read-only query and save JSON automatically:

```bash
bash "$SNOWFLAKE_SKILL" query \
  --connection analytics \
  --sql "SELECT * FROM ANALYTICS.PUBLIC.EVENTS LIMIT 20"
```

Use Snowflake CLI standard templates:

```bash
bash "$SNOWFLAKE_SKILL" query \
  --connection analytics \
  --sql "SELECT * FROM <% table_name %> LIMIT <% row_limit %>" \
  --variable table_name=ANALYTICS.PUBLIC.EVENTS \
  --variable row_limit=20
```

Only use template variables for trusted identifiers and values. For user-supplied data, construct safe SQL literals or use a controlled stored procedure.

Run a SQL file:

```bash
bash "$SNOWFLAKE_SKILL" query \
  --connection analytics \
  --file /absolute/path/query.sql
```

Write SQL is previewed:

```bash
bash "$SNOWFLAKE_SKILL" query \
  --connection analytics \
  --sql "UPDATE ANALYTICS.PUBLIC.JOBS SET STATUS = 'DONE' WHERE ID = 42"
```

Before asking for confirmation, query `ID = 42` and verify it identifies exactly the intended row and current status. After explicit confirmation:

```bash
bash "$SNOWFLAKE_SKILL" query \
  --connection analytics \
  --sql "UPDATE ANALYTICS.PUBLIC.JOBS SET STATUS = 'DONE' WHERE ID = 42" \
  --execute
```

Query `ID = 42` again after execution and report the verified state. For multi-statement writes, also pass `--single-transaction` when appropriate.

## Inspect and Manage Objects

List and describe objects:

```bash
bash "$SNOWFLAKE_SKILL" object-list --connection analytics --type table
bash "$SNOWFLAKE_SKILL" object-describe \
  --connection analytics \
  --type table \
  --identifier ANALYTICS.PUBLIC.EVENTS
```

Create an object from a reviewed JSON definition:

```bash
bash "$SNOWFLAKE_SKILL" object-create \
  --connection analytics \
  --type warehouse \
  --definition-file /absolute/path/warehouse.json
```

Snowflake CLI accepts object JSON only as `--json TEXT`, so execution necessarily exposes non-secret JSON in the child process arguments. The wrapper limits definitions to 32768 bytes and rejects secret objects or sensitive-looking fields. For larger definitions or any object containing credentials, tokens, private keys, or secret values, write reviewed DDL to a protected SQL file and use `query --file` instead.

Drop an object:

```bash
bash "$SNOWFLAKE_SKILL" object-drop \
  --connection analytics \
  --type warehouse \
  --identifier AI_WH
```

Both commands require preview, explicit confirmation, and then `--execute`.

## Output Contract

- Default command format is `JSON_EXT`.
- Successful live commands print Snowflake CLI JSON to stdout.
- The same output is saved to a uniquely reserved `./out/snowflake-<UTC timestamp>-<pid>-<random>.json` unless `--output` is provided.
- Saved outputs are regular, non-symlink files owned by the current user with `0600` permissions. Reject unsafe explicit output targets before running the Snowflake command.
- Mutation previews print JSON with `"dry_run": true` and do not contact Snowflake.
- Snowflake enhanced exit codes are preserved: `0` success, `2` command-parameter error, `5` SQL execution error, and `1` other errors.

## Specialized Commands

Read [references/official-cli.md](references/official-cli.md) before using Native Apps, Streamlit, Snowpark, stages, notebooks, Cortex, Git repositories, data pipelines, or Snowpark Container Services.

For specialized commands:

1. Inspect `snow <group> --help` and the exact subcommand help.
2. Prefer list, status, describe, validate, and diff operations first.
3. Request explicit confirmation before deploy, create, alter, drop, upload, execute, or service lifecycle commands.
4. Pass `--format JSON_EXT` and `--enhanced-exit-codes` when supported.
5. Do not claim success until the command exits successfully and any asynchronous resource reaches the intended state.
