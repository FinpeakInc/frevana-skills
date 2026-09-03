# Projects and PAT authentication

Set `SCRIPTS` to the absolute skill scripts directory. Project cloud actions use the Management API with `SUPABASE_ACCESS_TOKEN`; they never create `supabase/` or require CLI installation. Use the caller's existing `--workdir` only to resolve files. Never use the skill repository as an application project.

## Configure a token and select the project

Reuse an existing PAT. If absent, direct the user to [Access Tokens](https://supabase.com/dashboard/account/tokens) and configure `SUPABASE_ACCESS_TOKEN` through the host's secure environment/secret settings. It must reach the helper process: exporting in another terminal does not update an already running agent. Helpers do not load `.env` or save tokens. Never ask for credentials in chat, print them, or pass them as command arguments. A private env file requires the host's trusted loader, mode 0600 and exclusion from source control; do not source untrusted shell content.

```bash
python3 "$SCRIPTS/supabase_auth.py" status
# Known project: no need to enumerate other projects.
python3 "$SCRIPTS/supabase_auth.py" verify --project-ref "$PROJECT_REF"
# Otherwise resolve the target from cloud discovery:
python3 "$SCRIPTS/supabase_project.py" list
python3 "$SCRIPTS/supabase_project.py" organizations
python3 "$SCRIPTS/supabase_project.py" get --project-ref "$PROJECT_REF"
```

Verification is a read-only API request, no CLI/bootstrap/login. A presence check proves no permissions; a successful read proves only that permission. If a fine-grained PAT lacks project enumeration but grants the intended DB/config operation, use that operation's read path instead. Diagnose 401/403/network errors without switching accounts or upgrading permissions automatically. PAT, database password and project service keys are different credentials.

If explicitly requested, a saved CLI login/profile remains available for CLI tasks. API actions reject `--profile` and always use the environment PAT. Interactive CLI login is optional, never a prerequisite; use the reviewed native login mode only when the user requests it, relay its URL if shown, and keep credential storage private.

## Create, rename and manage projects

Use `supabase_project.py COMMAND --help` to inspect the exact inputs. Available cloud commands: `list`, `get`, `organizations`, `create`, `rename`, `delete`, `pause`, `restore`, `restart`.

Creation requires `--name`, `--organization-slug`, `--config-file` and a DB password in `SUPABASE_DB_PASSWORD` (or the variable named by `--db-password-env`). The reviewed config JSON accepts `region_selection` or legacy `region`, optional `desired_instance_size` and `high_availability`. Consult the current [create schema](https://supabase.com/docs/reference/api/v1-create-a-project) for the region-selection union; do not guess its shape or paid capacity. The password is inserted only inside the request, never in argv or output. Dry-run previews the plan without provisioning or requiring a DB password.

```bash
python3 "$SCRIPTS/supabase_project.py" create --name "$PROJECT_NAME" --organization-slug "$ORG_SLUG" --config-file "$CONFIG_FILE" --dry-run
python3 "$SCRIPTS/supabase_project.py" create --name "$PROJECT_NAME" --organization-slug "$ORG_SLUG" --config-file "$CONFIG_FILE"
```

Creation returns `accepted`, the new ref and observed status. Read the returned ref until ready; never repeat creation after an uncertain timeout. Creating a project can incur charges.

## Rename a cloud project

Route 修改 Supabase 项目名称 / 项目改名 here. Resolve only the missing target/new name, then execute under the existing authorization:

```bash
python3 "$SCRIPTS/supabase_project.py" rename --project-ref "$PROJECT_REF" --name "$NEW_NAME" --dry-run
python3 "$SCRIPTS/supabase_project.py" rename --project-ref "$PROJECT_REF" --name "$NEW_NAME" --expect-name "$CURRENT_NAME"
```

The helper GETs the exact target, PATCHes only `name`, then GETs to verify. `--expect-name` rejects a stale observed name before writing but is not an atomic lock. Already named projects need no write. This changes only the cloud display name, not the project ref/URLs, database name, local link or local `project_id`.

Project deletion additionally requires `--confirm-project-ref` matching the expressly authorized ref. `--dry-run` performs only preflight reads. Only an explicit readback 404 proves absence; permission/network failures never do. Pause/restore/restart return accepted status and a readback observation, not verified completion. Monitor with `get` and do not resubmit the write.

Sources: [Management API authentication](https://supabase.com/docs/reference/api/introduction), [get project](https://supabase.com/docs/reference/api/v1-get-project), [rename](https://supabase.com/docs/reference/api/v1-update-a-project).

## Repository initialization, linking and config files

Only initialize/link the caller's application when its repository migration/deployment workflow needs that state. Do not create anything at the skill repository root. Preserve existing files. `supabase_project.py init --workdir DIR` is idempotent; `link REF --workdir DIR` uses the CLI. Check its link before remote writes. `unlink` detaches local state without deleting the cloud project. Local `config.toml` `project_id` is not the cloud project name.

For a targeted cloud setting use `supabase_resources.py config get/update --service ...`; for an explicit request to deploy the repository config file use native `config push --project-ref REF` after reviewing the diff. Do not silently push unrelated settings. Read back the relevant service configuration through the API.

## Installation and CLI choice

Run `python3 "$SCRIPTS/supabase_setup.py" check --workdir "$PROJECT_DIR"` only when the selected operation needs the CLI. It resolves a project/ancestor `node_modules/.bin/supabase`, then PATH, then an existing launcher in `~/.frevana/bin`, and verifies `--version`. Existing binaries are reused without upgrades or reinstallation. Python 3 is needed only for the helper.

When no binary exists, the helper **automatically installs and continues**, without another confirmation:

1. With npm and Node.js 20+, globally install the official `supabase` package with `npm install -g --no-audit --no-fund supabase@latest` and attempt to create an optional launcher in `~/.frevana/bin` (override using `FREVANA_BIN_DIR`). Application manifests, lockfiles and local node_modules are not changed.
2. If that npm runtime is unavailable, select the first available fallback: Scoop (`scoop install supabase`), Winget (`winget install --id=Supabase.CLI -e` with agreement flags), or Homebrew (`brew install supabase/tap/supabase`). Resolve and verify the installed binary before continuing.
3. Verify the installed binary with `--version` before executing the requested command. Installer output goes to stderr, preserving command JSON/file output. A failed install/version check stops the operation; never report success or run the pending DB write.

The helper makes one bounded installation attempt (up to five minutes), without switching sources or looping after failure. If no supported manager/runtime is available, bootstrap an appropriate official runtime/package manager using the host's supported installation mechanism, then retry. Respect OS/admin/sandbox prompts rather than bypassing them. Do not treat a network/proxy failure as absence of the package. Existing but broken CLI installations are diagnosed, not blindly reinstalled. `check --no-install` never installs or writes a shared launcher; native CLI telemetry can still write its own state. On other commands, `--no-install` does not disable network access or resource mutations. Discovery never exports a project-pinned CLI into the shared launcher. New installs create the launcher only if absent (a symlink on Unix, a `.cmd` shim on Windows); existing files, directories and dangling symlinks remain untouched. If launcher creation fails, report the warning and use the verified installed binary directly.

If the app requires a particular CLI version, honor its existing installed dependency or install that declared version using its package manager before normal use; don't silently upgrade its dependency to match the global installation. Project installs use a pinned dev dependency and direct usage is `npx supabase ...`.

The helper uses the global npm route shown on the [Supabase docs home](https://supabase.com/docs); the local-development guide also documents project dependencies and native package-manager installs. Reuse an existing project dependency, but do not create one merely to bootstrap this skill. On Windows use the native CLI or the helper in WSL; private file modes assume Unix. An agent plugin is a separate optional dependency: when the requested task needs it and it is missing, follow [automatic plugin setup](plugin-setup.md).

Sources: [installation](https://supabase.com/docs/guides/local-development/cli/getting-started), [CLI releases](https://github.com/supabase/cli/releases).

For restricted-environment help checks, CLI 2.116.0 may write telemetry state even before displaying help. A telemetry permission error does not mean a subcommand is absent. This version supports `SUPABASE_HOME` and `SUPABASE_TELEMETRY_DISABLED=1`: for isolated, credential-free help only, point `SUPABASE_HOME` at a fresh temporary directory and disable telemetry for that subprocess. Do not change the user's HOME, overwrite credential files, or carry the temporary profile into authenticated operations. Verify these settings against the installed version before reuse.
