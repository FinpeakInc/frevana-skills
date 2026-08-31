---
name: supabase
description: Guide users to configure a Supabase personal access token (PAT), then operate cloud projects and databases with the official CLI, including project selection, linking, cloud configuration, SQL, migrations, backups, diagnostics, and types. Also routes Storage, Edge Functions, Secrets, branches, SSO, domains, and network settings to their CLI entry points.
---

# Supabase cloud projects and databases

Use the official Supabase CLI for cloud project/resource management and remote database lifecycle operations. Use SQL through a supported CLI command or `psql` for database queries and CRUD. The primary onboarding path is a personal access token (PAT) in `SUPABASE_ACCESS_TOKEN`, not browser OAuth. This skill does not require Docker, a Supabase MCP connection or Frevana credentials.

## Token-first authentication

For remote operations, guide the user through token setup before selecting or changing resources:

1. Run `python3 scripts/supabase_auth.py status` from the skill directory (or use its absolute path) to check whether `SUPABASE_ACCESS_TOKEN` is available to the agent/helper process, reporting only configured/missing. Never print its value or dump the environment. CLI installation/help do not require an account token.
2. If missing, direct the user to [Supabase Access Tokens](https://supabase.com/dashboard/account/tokens) to create a PAT under an account with the required organization/project permissions. Have them configure `SUPABASE_ACCESS_TOKEN` using the host's secure environment/secret settings or a hidden terminal prompt. Do not ask them to paste the token into chat.
3. Follow [token configuration and verification](references/projects.md#configure-a-token-and-select-the-project) to ensure the variable reaches the actual CLI process. The helper inherits environment variables; it does not read `.env` files automatically or save tokens itself.
4. Run `supabase_auth.py verify --workdir DIR`, which requires the PAT and uses a read-only `projects list`, then match the intended project. A set variable or successful `check` is not proof of authentication. If authentication fails, help fix the token/access rather than automatically launching `supabase login` or an OAuth flow.

Use an existing saved CLI login only if the user chooses that path. Browser login/OAuth is a fallback when explicitly requested or required by the selected platform; it must not block the normal token-based CLI workflow. Request a database password separately only for an operation that requires one; PAT, DB password and project API keys are different credentials.

## Start with the target

1. Determine whether the user wants account/project management or an existing cloud DB.
2. Resolve the caller's application directory (`--workdir`), CLI auth profile if needed, organization/project ref, and database target. Ask only for inputs still missing after safe discovery. Never treat the skill repository's own `supabase/config.toml` as the user's target.
3. Check the CLI once with the helper. Reuse an installed project/PATH/managed CLI; if missing, automatically install it and verify the version before continuing. Do not ask again for permission to install a missing CLI or a needed Supabase agent plugin: this bootstrap is part of the workflow. Reuse existing installations and respect environment-enforced approval boundaries. Discover supported commands/flags with `--help`; the installed version takes precedence over examples.
4. Before a write, state the resolved project/DB and intended change. Existing explicit authorization applies; do not ask again for the same operation. A request to inspect does not authorize changes. Destructive resets/deletions require authorization covering the exact target and data loss.
5. Execute, then verify the requested state using a read operation. Distinguish command success from a resource that is still provisioning. Never report a live verification when only mocks/local checks ran.

Read the relevant reference:

- [Projects and authentication](references/projects.md): install, PAT configuration/verification, optional login/profiles, organizations, create/select/link/delete projects, cloud configuration.
- [Database operations](references/database.md): connection setup, SQL/CRUD, migrations, backup/restore, RLS, lint, diagnostics, types, pgTAP.
- [Agent plugin setup](references/plugin-setup.md): detect the active agent's Supabase plugin and install it automatically only when needed.
- [Other CLI resources](references/cli-reference.md): Storage, Functions, Secrets, branching, SSO, domains, network/SSL/Postgres settings, snippets and services.

## Scripts by capability

Set `SCRIPTS` to this skill's absolute `scripts/` directory and `PROJECT_DIR` to the caller's existing application directory. Prefer the smallest matching entry:

| Capability | Script | Commands / native groups |
|---|---|---|
| CLI discovery and automatic installation | [supabase_setup.py](scripts/supabase_setup.py) | `check`; verifies installation, not account access |
| Token authentication | [supabase_auth.py](scripts/supabase_auth.py) | `status` (presence only), `verify` (read-only project listing); never persists tokens or starts OAuth |
| Projects and configuration | [supabase_project.py](scripts/supabase_project.py) | `init`, `link REF`, `cli -- projects/orgs/config/unlink ...` |
| Database | [supabase_db.py](scripts/supabase_db.py) | `gen-types`, `migration-new`, `db-lint`, `inspect`; `cli -- db/migration/inspect/gen/test/seed ...` |
| Other resources / native fallback | [supabase_resources.py](scripts/supabase_resources.py) | `cli -- storage/functions/secrets/branches/...`; preserves all native CLI capabilities |

`supabase_common.py` owns shared parsing, execution and atomic file output; it is not a user command. `supabase_helper.sh` / `supabase_helper.py` remain compatibility dispatchers for all previous commands. Capability implementations are shared with the old entry, not duplicated. Plugin installation remains the host-aware workflow in [plugin-setup.md](references/plugin-setup.md); it is not a CLI-resource command.

```bash
python3 "$SCRIPTS/supabase_setup.py" check --workdir "$PROJECT_DIR"
python3 "$SCRIPTS/supabase_auth.py" status
python3 "$SCRIPTS/supabase_auth.py" verify --workdir "$PROJECT_DIR"
python3 "$SCRIPTS/supabase_project.py" init --workdir "$PROJECT_DIR"
python3 "$SCRIPTS/supabase_project.py" link "$PROJECT_REF" --workdir "$PROJECT_DIR"
python3 "$SCRIPTS/supabase_project.py" cli --workdir "$PROJECT_DIR" -- config push --help
python3 "$SCRIPTS/supabase_db.py" gen-types --workdir "$PROJECT_DIR" --output types/database.ts
python3 "$SCRIPTS/supabase_db.py" cli --workdir "$PROJECT_DIR" -- db push --linked --dry-run
python3 "$SCRIPTS/supabase_resources.py" cli --workdir "$PROJECT_DIR" -- storage --help
```

Project/DB native entries expect their command group immediately after `--`; put CLI flags after the group/subcommand or use the unrestricted resource/compatibility entry for other layouts. `auth verify` is specifically a PAT check; for a user-selected saved CLI login, use the project entry's native `projects list` instead.

## Shared execution contract

Requires Python 3 (standard library only). If Supabase CLI is missing, commands that invoke it automatically install it via npm global install (`npm install -g supabase@latest`, Node.js 20+), or Homebrew if that runtime is unavailable, and symlink the binary to `~/.frevana/bin/supabase`. See projects.md for locations and failure handling. `--no-install` is available for explicitly offline/read-only diagnostics; do not use it for the normal setup flow. Help and token-presence checks never install or connect. Set `HELPER` to `scripts/supabase_helper.sh` only when using the compatible legacy examples below.

Shortcuts: `check`, `init`, `gen-types`, `migration-new`, `db-lint`, `inspect`, `link`. See `<command> --help` for each command's accepted options. Unknown options and invalid targets fail before execution. DB shortcuts operate on the linked remote target.

Existing callers can keep using the original explicit native CLI entry point:

```bash
bash "$HELPER" cli --workdir "$PROJECT_DIR" -- projects list
bash "$HELPER" cli --workdir "$PROJECT_DIR" --profile staging -- db push --help
bash "$HELPER" cli --workdir "$PROJECT_DIR" -- db push --linked --dry-run
bash "$HELPER" cli --workdir "$PROJECT_DIR" -- storage --help
```

- Before `--`: helper options `--workdir`, `--profile`, `--output FILE`, `--no-install`.
- After `--`: exact Supabase arguments; nothing is silently dropped. Supabase validates these flags. This entry point preserves native capabilities, prompts and side effects; it is **not an authorization filter**. Follow the target/authorization rules above, including for native reset/delete commands.
- `--workdir` belongs before the separator. It is also passed explicitly to the CLI, overriding ambient `SUPABASE_WORKDIR`.
- Helper output paths are relative to `--workdir`. Files are written privately and replaced atomically only after exit code 0. Existing output survives failures. Native `-f/--file` flags are owned by Supabase and do not get this protection.
- Native `--output json` is a format flag, distinct from helper `--output FILE`. Not every command supports structured output; inspect its help first. Saved stdout is not rewritten.
- Native `projects api-keys`, branch connection details, SQL output and debug logs may contain secrets or user data. Never paste raw secrets into chat or logs.
- Dependency installation is automatic when missing; cloud commands never receive an automatic `--yes`, retry or login. Pass native CLI `--yes` only when supported and the operation is already authorized; it does not supply missing inputs or make an operation safe.

## Verification and boundaries

Summarize the selected target, requested changes, verification result, and any file outputs. Do not print passwords, PATs, service-role/secret keys, or credential-bearing connection strings. Use environment variables, CLI credential storage or protected local files for credentials; never put real secrets in examples or tracked files.

CLI command availability changes. If a resource is absent, inspect `--version`/`--help`, then consult the [official reference](https://supabase.com/docs/reference/cli/introduction). Offer an appropriate version upgrade or a documented Management API/SDK/SQL route within the user's scope; do not invent a command or claim CLI coverage for every Supabase product.
