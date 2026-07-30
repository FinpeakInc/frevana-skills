# Official Snowflake CLI Reference

Use this reference only when the common wrapper does not cover the requested workflow.

## Primary documentation

- Introduction: https://docs.snowflake.com/en/developer-guide/snowflake-cli/introduction/introduction
- Installation: https://docs.snowflake.com/en/developer-guide/snowflake-cli/installation/installation
- Configuration: https://docs.snowflake.com/en/developer-guide/snowflake-cli/connecting/configure-cli
- Connections: https://docs.snowflake.com/en/developer-guide/snowflake-cli/connecting/configure-connections
- Programmatic access tokens: https://docs.snowflake.com/en/user-guide/programmatic-access-tokens
- SQL execution: https://docs.snowflake.com/en/developer-guide/snowflake-cli/sql/execute-sql
- Command reference: https://docs.snowflake.com/en/developer-guide/snowflake-cli/command-reference/overview

Check the live documentation and `snow <group> --help` because command groups and options change between releases.

## Connection behavior

Snowflake CLI reads connection parameters in this precedence order:

1. command-line connection parameters
2. connection-specific environment variables
3. `config.toml` or `connections.toml`
4. generic Snowflake environment variables

For example, a command-line `--user` wins over `SNOWFLAKE_CONNECTIONS_ANALYTICS_USER`; that connection-specific variable wins over the stored connection; the stored value wins over generic `SNOWFLAKE_USER`.

If both configuration files exist, connections in `connections.toml` take precedence over connections in `config.toml`. CLI-specific settings, including `default_connection_name`, remain in `config.toml`.

The official `snow connection remove` example removes a connection from `config.toml`. Do not use it to manage an active `connections.toml`; edit that shared file through a separate reviewed workflow. `snow connection set-default` still targets the CLI-only default setting in `config.toml`.

Resolve `config.toml` in this order:

1. the file passed with `--config-file`
2. the directory selected by `SNOWFLAKE_HOME`
3. `~/.snowflake/config.toml` when `~/.snowflake` exists
4. the operating-system default:
   - Linux: `${XDG_CONFIG_HOME:-$HOME/.config}/snowflake/config.toml`
   - Windows: `%USERPROFILE%\AppData\Local\snowflake\config.toml`
   - macOS: `~/Library/Application Support/snowflake/config.toml`

Require `0600` permissions for `config.toml` on Linux and macOS.

Use PAT as the primary authentication method currently supported by this skill:

- `PROGRAMMATIC_ACCESS_TOKEN` plus a token file

Set `authenticator = "PROGRAMMATIC_ACCESS_TOKEN"` and `token_file_path` in the Snowflake connection. The account and authentication policy must allow PAT. Network-policy requirements apply by default. Prefer a service user and restrict the PAT to a least-privilege role.

Snowflake CLI also recognizes generic connection environment variables including `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_DATABASE`, `SNOWFLAKE_SCHEMA`, `SNOWFLAKE_ROLE`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_AUTHENTICATOR`, `SNOWFLAKE_TOKEN`, and `SNOWFLAKE_TOKEN_FILE_PATH`.

This skill's `setup-pat` workflow snapshots initial environment values into persistent connection configuration. It stores the PAT in a separate owner-only file and writes only `token_file_path` to Snowflake configuration.

The simplest setup uses `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, and either `SNOWFLAKE_PAT` or official `SNOWFLAKE_TOKEN`. It names the connection `default`, makes it the default, and tests it after saving. `SNOWFLAKE_DEFAULT_CONNECTION_NAME` selects another name. For a named connection containing only letters, digits, and underscores, connection-specific `SNOWFLAKE_CONNECTIONS_<NAME>_*` values take precedence over generic values during setup. Do not infer these variables for names containing dots or hyphens because lossy shell-name normalization can bind multiple connections to the same environment variable.

Run the official connection lifecycle in this order:

1. `snow connection list`
2. `snow connection add --no-interactive`
3. `snow connection test --connection <name>`

Use `--enable-diag` and an absolute `--diag-log-path` with `snow connection test` only when normal testing reports connectivity problems.

The official `snow object create --json` interface accepts JSON text rather than a file path; even the official file example expands file contents into the command argument. Keep wrapper JSON definitions small and non-sensitive. Use protected DDL files with `snow sql --filename` when command-line exposure is unacceptable.

Generate and rotate PAT secrets outside the PAT-authenticated session used by the same user. Snowflake displays a newly generated or rotated secret only once.

Other authentication methods can be added later:

- `SNOWFLAKE_JWT` plus a private-key file
- `WORKLOAD_IDENTITY` for AWS, Azure, GCP, or OIDC automation
- `OAUTH` plus a token file

Use `EXTERNALBROWSER` only when an interactive browser is available. Use `USERNAME_PASSWORD_MFA` only when account policy and MFA caching support the automation model.

## SQL behavior

- Use `snow sql -q` for a query and `snow sql -f` for files.
- Use `--format JSON_EXT` for native JSON values.
- Use `--enhanced-exit-codes` to distinguish argument errors (`2`) from SQL execution errors (`5`).
- Use `--local-only` to reject URL-based `!source` and `!load`.
- Use `--single-transaction` for an all-or-nothing multi-statement unit when supported.
- Prefer the standard `<% variable_name %>` template syntax.
- Use `;>` only when the user explicitly requests asynchronous execution and persist the returned query ID.
- Retrieve an asynchronous result with `!result <query-id>`.
- Abort a running query with `!abort <query-id>` only after confirming the target query ID.
- Treat every `SYSTEM$...` function call as potentially side-effecting and require preview/confirmation rather than relying on a `SELECT` prefix.

## Command groups

Inspect the current help before invocation:

```bash
snow --help
snow <group> --help
snow <group> <command> --help
```

Common groups include:

- `connection`: add, list, test, set-default, remove
- `sql`: execute SQL strings, files, stdin, templates, and asynchronous queries
- `object`: create, list, describe, and drop supported Snowflake objects
- `stage`: list, copy, upload, download, and remove staged files
- `snowpark`: build and deploy functions and procedures
- `streamlit`: deploy, list, share, and manage Streamlit apps
- `app`: develop and deploy Snowflake Native Apps
- `notebook`: deploy and manage notebooks
- `git`: manage Snowflake Git repository clones
- `spcs`: manage compute pools, services, registries, and images
- `cortex`: invoke supported Cortex workflows

Treat any command that changes a local project, a connection file, a Snowflake object, staged data, deployed code, grants, compute state, or service state as a mutation.
