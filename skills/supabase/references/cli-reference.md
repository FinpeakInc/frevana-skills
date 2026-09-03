# Other Supabase resource entry points

Use Management API actions in [API capabilities](api-capabilities.md) for implemented cloud operations. This reference covers additional CLI/file workflows and service API entry points. The native entry is guarded, not arbitrary passthrough: unknown/local/container-dependent modes cannot execute until reviewed. Set `SCRIPTS` to the absolute scripts directory and inspect installed help when selecting a CLI route:

```bash
python3 "$SCRIPTS/supabase_resources.py" cli --workdir "$PROJECT_DIR" -- "$GROUP" --help
python3 "$SCRIPTS/supabase_resources.py" cli --workdir "$PROJECT_DIR" -- "$GROUP" "$OPERATION" --help
```

Verified on CLI 2.116.0 (2026-08-31): 21 resource/project/tool groups were traversed down to 88 leaf commands, with all 109 group/command `--help` calls succeeding through the capability scripts. This verifies command availability and parameter discovery, not account permissions or live resource access. New groups can be inspected through help; executing them requires review and an update to supabase_cli_policy.py.

Set `GROUP` and `OPERATION` to a group/operation below before running these examples. Read current help before choosing flags, especially `--experimental`, target selection and output format. Use an explicit project ref when supported, otherwise verify the workdir's linked project. Add `--profile NAME` before the separator for a different auth profile. Never assume `--local` is universal; Storage defaults/experimental requirements, for example, must be checked.

| User intent / resource | CLI entry and operations to discover | Required context / verification |
|---|---|---|
| Projects | `projects`: list, create, api-keys, delete | Use `supabase_project.py`; cloud actions now use explicit API commands, including `rename` (see projects.md). Inspect region/size/high-availability choices before creation. `api-keys --reveal` can expose full secret keys; never add it by default. |
| Cloud configuration | `config push` | Use `supabase_project.py`; `--project-ref` selects the target. Review local config differences before pushing; this version has no `config get/pull` readback command. |
| Edge Functions | `functions`: new, list, download, deploy, delete | Workdir, function name and remote ref; use supported `--use-api` for deploy/download to avoid Docker, and list after deploy/delete. If unavailable, use a documented Dashboard/API path or report that limit. Do not start a local `functions serve` runtime. Keep JWT verification enabled unless public access is intended. |
| Remote function secrets | `secrets`: list, set, unset | Project ref and names; use supported `set --env-file` with a private file rather than secrets in argv. Verify names/digests without values. |
| Storage objects | `storage`: ls, cp, mv, rm | Use `ss:///bucket/path` and explicit `--project-ref` or `--linked`; CLI 2.116.0 requires `--experimental`. `cp` and `mv` take source/destination paths. `rm` takes file paths and must include `--yes` in non-interactive execution; otherwise it can exit 0 after declining deletion. Inspect `--recursive` scope before directory operations and verify every write/delete with `storage ls`. |
| Storage bucket setup/seeding | `seed buckets`; supported config fields | Use `seed buckets --project-ref REF` for buckets declared in `[storage.buckets]`. Review config, bucket access and local paths; seeding is a write. For settings outside seed/config support or bucket deletion, use the documented Storage API/SDK rather than inventing `storage buckets` commands. |
| Preview branches | `branches`: create, list, get, update, pause, unpause, delete | Parent project and branch name/id; list/get to verify readiness. `create --with-data` clones production data and needs that scope; do not automatically add notify URLs or override status via update. `get` may reveal DB credentials. Branch pause does not pause the main project. |
| SSO providers | `sso`: add, list, show, info, update, remove | Project, provider id and SAML metadata (`--metadata-file` or `--metadata-url`). `update --domains` replaces domains; use add/remove-domains for scoped edits. Do not automatically skip URL validation. Verify with list/show/info. Ordinary Auth users/sessions use Auth Admin API/SDK, not SSO commands. |
| Custom API domains | `domains`: create, get, reverify, activate, delete | Project and hostname; inspect existing state/DNS requirements before changing DNS. API domains get reads status; mutations use this reviewed CLI entry. Verify domain status; potential paid feature. |
| Vanity subdomains | `vanity-subdomains`: check-availability, get, activate, delete | Project and desired subdomain; verify final state. Do not treat availability checks as activation permission. |
| Network bans | `network-bans`: get, remove | Project and affected IP; diagnose why banned before removing, then re-read. |
| Network restrictions | `network-restrictions`: get, update | Project and intended CIDRs; inspect `--db-allow-cidr` and `--append` (without append the list is replaced). Save current state and prevent operator lockout. Do not add `--bypass-cidr-checks` or allow-all CIDRs to hide an error. |
| DB SSL enforcement | `ssl-enforcement`: get, update | Project and intended setting; update exposes enable-db-ssl-enforcement and disable-db-ssl-enforcement. Verify client TLS compatibility, then read back with get. |
| Postgres server settings | `postgres-config`: get, update, delete | Inspect get first. Update takes `--config key=value`; `--replace-existing-overrides` replaces instead of merging. Delete takes named keys; update/delete expose `--no-restart`. Account for restart impact and read back. This is distinct from local config.toml. |
| Hosted physical backups / PITR | `backups`: list, restore | Discover flags with `backups list --help` / `backups restore --help`; verify `--project-ref`, available recovery times and plan support. Restore takes `--timestamp` in epoch seconds, not milliseconds. Restore needs exact target and data-loss authorization; distinct from logical `db dump`. |
| Project encryption keys | `encryption`: get-root-key, update-root-key | Inspect help and supported target. Key retrieval can expose secrets; never print raw key material. Rotation requires explicit scope and recovery planning. |
| Saved SQL snippets | `snippets`: list, download | Project and snippet id; downloading does not execute SQL. Review content and target separately before executing. |
| Service versions | `services` | Inspect versions using supported target flags; this is not a deploy/upgrade command. |
| Organizations | `orgs`: list, create | Organization selection/name; creating an org is distinct from creating a project. See projects.md. |
| Types and signing/JWT tools | `gen`: types, signing-key, bearer-jwt, keys | Use `supabase_db.py`. Installed help lists TypeScript/Go/Swift/Python; this wrapper currently permits only TypeScript execution without Docker. Types uses `--project-id` or `--linked` (not a universal --project-ref). signing-key creates private key material; bearer-jwt can specify role/sub and must not be used to bypass access controls. These are not Supabase account PATs. `gen keys` is deprecated in this release. |
| Database diagnostics and reports | `db lint`, `db advisors`, `inspect report`, `inspect db <metric>` | Use `supabase_db.py`; discover metrics with `inspect db --help`. On CLI 2.116.0, DB diagnostics with `--project-ref` also require an initialized/linked workdir and `--linked`. They create a temporary remote login role but do not start Docker. Protect SQL text and database metadata in exports. |
| Cloud DB test preparation | `test new` | Local test-file creation only when needed for an authorized cloud test workflow. `test db` is blocked; no Docker runner fallback or production fixture changes by default. |
| CLI utility/configuration | `bootstrap`, `completion`, `telemetry` | Help only in this skill until a mode is reviewed; bootstrap can create local resources and is blocked. |

## When there is no dedicated subcommand

Some capabilities are outside Management API and need CLI or an official service API. Do not directly modify Supabase-managed tables to imitate a supported service API.

| Requested operation | Route |
|---|---|
| Project rename/pause/restore/restart | Bundled project API actions; no CLI name mutation substitute |
| Cron jobs / queue management | DB `query` with documented pg_cron / PGMQ SQL; consuming/acknowledging messages requires --write and authorization |
| RLS/grants/extensions | Read-only SQL inspection; scoped reviewed migrations for persistent changes |
| Realtime | API service config; SQL for publications/policies; client/API for subscriptions, broadcast and presence |
| Ordinary Auth users/sessions/invitations | Official Auth Admin API/SDK with separate authorized credentials, not auth table writes |
| Invoke functions / retrieve logs | Official function invocation or Management logging API/Dashboard; CLI functions serve is local and blocked. These are extension entry points, not currently wrapped API actions |
| Storage bucket deletion/settings beyond config/seed | Official Storage API/SDK; object storage rm is not bucket administration |
| Hosted PITR | DB backups/restore-pitr API actions; inspect plan/window and explicit destructive authorization |

Examples for discovering operation-specific parameters without acting on resources:

```bash
python3 "$SCRIPTS/supabase_resources.py" cli --no-install -- storage cp --help
python3 "$SCRIPTS/supabase_resources.py" cli --no-install -- sso update --help
python3 "$SCRIPTS/supabase_resources.py" cli --no-install -- network-restrictions update --help
python3 "$SCRIPTS/supabase_resources.py" cli --no-install -- backups restore --help
python3 "$SCRIPTS/supabase_db.py" cli --no-install -- gen bearer-jwt --help
python3 "$SCRIPTS/supabase_db.py" cli --no-install -- inspect db --help
```

Refresh installed help and the current official documentation before declaring an operation unsupported. Use supported remote/server-side modes before another interface, explain the exact limitation when switching, and report account/plan restrictions without silently substituting another resource.

For mutations, inspect first, reuse the user's existing authorization for the exact scope, execute, and verify. Avoid blind retries of create/upload/deploy when completion is uncertain. Deletion, credential rotation, access changes and billable resource creation need authorization covering their consequences. The native entry point does not add or enforce these authorizations for you.

Sources:
- [Official CLI groups and flags](https://supabase.com/docs/reference/cli/introduction)
- [Management API](https://supabase.com/docs/reference/api/introduction)
- [Storage](https://supabase.com/docs/guides/storage)
- [Auth Admin API](https://supabase.com/docs/reference/javascript/auth-admin-listusers)
- [Cron SQL interface](https://supabase.com/docs/guides/cron)
- [Queues](https://supabase.com/docs/guides/queues)
- [Realtime](https://supabase.com/docs/guides/realtime)
