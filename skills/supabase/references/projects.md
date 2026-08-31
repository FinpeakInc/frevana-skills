# Projects, authentication and configuration

Set `SCRIPTS` to this skill's absolute scripts directory. Use `python3 "$SCRIPTS/supabase_project.py" cli --workdir "$PROJECT_DIR" -- <arguments>` for native project/org/config commands below, or the selected installed CLI directly. Use `supabase_setup.py check` for installation and `supabase_auth.py status|verify` for PAT checks. The legacy helper remains compatible. `PROJECT_DIR` must exist; account-only commands can use the caller's current directory without `init` or Docker.

## Installation and CLI choice

Run `python3 "$SCRIPTS/supabase_setup.py" check --workdir "$PROJECT_DIR"` as the bootstrap step. It resolves a project/ancestor `node_modules/.bin/supabase`, then PATH, then its managed installation, and verifies `--version`. Existing binaries are reused without upgrades or reinstallation. Python 3 is needed only for the helper.

When no binary exists, the helper **automatically installs and continues**, without another confirmation:

1. With npm and Node.js 20+, globally install the official `supabase` package with `npm install -g --no-audit --no-fund supabase@latest` and symlink the binary to `~/.frevana/bin/supabase` (override using `FREVANA_BIN_DIR`). Application manifests, lockfiles and local node_modules are not changed.
2. If that npm runtime is unavailable but Homebrew exists, run `brew install supabase/tap/supabase`, resolve the installed formula's binary, and symlink to `~/.frevana/bin/supabase`.
3. Verify the installed binary with `--version` before executing the requested command. Installer output goes to stderr, preserving command JSON/file output. A failed install/version check stops the operation; never report success or run the pending DB write.

The helper makes one bounded installation attempt (up to five minutes), without switching sources or looping after failure. If no supported manager/runtime is available, bootstrap an appropriate official runtime/package manager using the host's supported installation mechanism, then retry. Respect OS/admin/sandbox prompts rather than bypassing them. Do not treat a network/proxy failure as absence of the package. Existing but broken CLI installations are diagnosed, not blindly reinstalled. Explicit `--no-install` keeps diagnostics offline.

If the app requires a particular CLI version, honor its existing installed dependency or install that declared version using its package manager before normal use; don't silently upgrade its dependency to match the managed cache. Project installs use a pinned dev dependency and direct usage is `npx supabase ...`.

The official installation guide documents npm dev dependencies and Homebrew/Scoop/release binaries. Use those routes rather than depending on a global npm installation. On Windows use the native CLI or the helper in WSL; private file modes assume Unix. An agent plugin is a separate optional dependency: when the requested task needs it and it is missing, follow [automatic plugin setup](plugin-setup.md).

Sources: [installation](https://supabase.com/docs/guides/local-development/cli/getting-started), [CLI releases](https://github.com/supabase/cli/releases).

## Configure a token and select the project

**Default to PAT configuration. Do not launch browser login/OAuth as the normal onboarding step.** CLI installation and help do not need cloud account credentials.

1. Run `python3 "$SCRIPTS/supabase_auth.py" status` to check only whether `SUPABASE_ACCESS_TOKEN` is nonempty in the environment that will run the scripts. Do not log its value, prefix, suffix or length, and do not read out raw credential files. If already configured, go directly to verification.
2. If missing, give the user the [Access Tokens page](https://supabase.com/dashboard/account/tokens). Ask them to create a personal access token using the intended Supabase account, give it a purpose-specific name and appropriate expiry/access where supported, then store it securely. The account/token must have access to the target organization and permission for the requested operation. A project `anon`, publishable or `service_role` key is not a PAT.
3. Prefer the current host's secure environment/secret configuration for `SUPABASE_ACCESS_TOKEN`. The variable must reach the agent/helper process. Setting it in a separate terminal does not retroactively update an already-running desktop agent; use the host's environment injection or start a new session with the variable configured.
4. If the user runs the helper themselves, this **Bash terminal** example reads the token without putting its value in the command text/history. `SCRIPTS` and `PROJECT_DIR` must already point to the skill scripts directory and selected working directory. Run only in a user-controlled terminal with shell tracing disabled:

```bash
set +x
read -r -s -p 'Supabase PAT: ' SUPABASE_ACCESS_TOKEN
printf '\n'
export SUPABASE_ACCESS_TOKEN
python3 "$SCRIPTS/supabase_auth.py" verify --workdir "$PROJECT_DIR"
```

Do not request the token in chat, pass it with `--token`, embed it in an executable command, or save it to tracked files. For persistence, prefer a secret manager/environment injection. If an explicitly chosen private env file is used, restrict it to the current user (0600), exclude it from version control, and use the host's supported env loader. The helper and native CLI are not assumed to auto-load a project `.env`; merely writing a file is not completed configuration. Do not `source` an untrusted env file as shell code. Token values are never stored by this helper.

5. Verify the configured PAT with `supabase_auth.py verify --workdir DIR`, which executes `projects list` (use the project entry for `orgs list` when needed). Missing PAT fails before CLI installation or login; a CLI failure is returned without a saved-account/OAuth fallback. Do not use CLI `check` or `--version` as an auth test. A failed token must not silently fall back to another saved account. Explain invalid/revoked/expired token errors, distinguish permission denial from network/proxy errors, and have the user correct the corresponding setting. An empty project list does not prove token invalidity; check organization/account selection. Successful listing does not prove authorization for every write.
6. Match the requested organization/project from the returned list. Ask only if selection is ambiguous. For local files/migrations, initialize the caller's app directory if needed, then `supabase_project.py link REF --workdir DIR`. Prompt separately for `SUPABASE_DB_PASSWORD` only if this operation needs it; this DB password is not the PAT. Use the protected prompt or documented environment option, never echo the password.
7. Verify link selection from the CLI's project listing and local `supabase/.temp/project-ref` if present. This is CLI-managed, version-dependent state, not a config to edit. Keep it ignored. Local `config.toml` `project_id` is different from the cloud project ref.

For multiple environments use explicit workdirs and the intended token injection. Recheck the current link before each remote write; don't reuse a ref from a previous conversation. `unlink` detaches local state without deleting the cloud project.

### Optional saved login / OAuth

If the user explicitly chooses an existing CLI login/profile, reuse it. If they request interactive login instead of token configuration, use the native fallback `supabase_resources.py cli --workdir DIR -- login` and relay an authorization URL when shown. Keep credential storage private; the CLI may fall back from OS credential storage to a plaintext token file. `--profile NAME` selects a CLI auth profile, not a cloud project. Avoid mixing a saved profile with a different environment PAT; confirm the intended identity using project/account discovery.

For MCP-only workflows, prefer PAT authentication when the client supports environment-backed authorization headers; see [plugin authentication](plugin-setup.md). Only use browser OAuth when the user selects it or the platform requires it. CLI token configuration does not require a plugin OAuth connection.

Source: [CLI token authentication](https://supabase.com/docs/reference/cli/introduction#supabase-login).

## Create and delete projects

For creation, resolve project name, organization, region and any size/billing choice. Don't guess the organization or paid capacity. Inspect `projects create --help` for the installed release, then use:

```bash
python3 "$SCRIPTS/supabase_project.py" cli --workdir "$PROJECT_DIR" -- projects create "$PROJECT_NAME" --org-id "$ORG_ID" --region "$REGION"
```

Supply a database password using the CLI's protected interactive prompt when required. If the installed release has no secure noninteractive credential input, stop at that browser/terminal step rather than placing a real password in argv. `--yes` does not solve missing creation parameters.

After creation, run `projects list` and capture the returned ref. If not ready, perform bounded read checks; do not repeat `projects create` after an uncertain timeout. Check whether the resource already exists before retrying. Link it only if the task needs local deployment. Creating projects can incur charges.

For deletion, inspect `projects delete --help`, identify the exact ref/name and data-loss scope, check existing authorization and backup requirements, then `projects delete "$PROJECT_REF"`. Verify absence from `projects list`. Never infer deletion permission from cleanup of a local workdir.

`projects api-keys --project-ref REF` is available when keys are required, but its output can contain privileged keys. Save to a protected secret store/file as needed, not chat or source files.

Source: [projects](https://supabase.com/docs/reference/cli/introduction#supabase-projects).

## Configure a cloud project

`supabase/config.toml` controls local services. Editing it or running `link` does **not** by itself apply those changes to the cloud. For cloud-supported configuration:

1. Read the current local config and the current remote settings through the Dashboard or documented Management API if needed. Do not invent a `config pull` command.
2. Edit only the requested settings. Consult the config reference and installed `config push --help`; not every local-only setting is remotely applicable.
3. Review the proposed changes and any unrelated differences in the file. A generated default config is not an authoritative snapshot of an existing production project. Do not push it wholesale if unrelated remote settings may be reset.
4. Once the scope is authorized, run:

```bash
python3 "$SCRIPTS/supabase_project.py" cli --workdir "$PROJECT_DIR" -- config push --project-ref "$PROJECT_REF"
```

5. Inspect the command's applied changes and read the affected settings back via the supported API/Dashboard. If readback is unavailable, report that limit instead of claiming it was verified.

Use config for supported Auth/API/Storage settings. Use `postgres-config`, `network-restrictions`, `network-bans` and `ssl-enforcement` for their dedicated operations; see [resource entry points](cli-reference.md). SSO commands manage identity providers, not arbitrary Auth users. General user administration belongs to the documented Auth Admin API/SDK.

Sources: [config push](https://supabase.com/docs/reference/cli/introduction#supabase-config-push), [config fields](https://supabase.com/docs/guides/local-development/cli/config), [Management API](https://supabase.com/docs/reference/api/introduction).
