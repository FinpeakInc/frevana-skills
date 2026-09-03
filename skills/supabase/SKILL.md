---
name: supabase
description: Manage Supabase cloud projects, databases, and resources through bundled scripts. Use for project creation, renaming, configuration, or deletion; SQL queries and table data changes; schema, migrations, diagnostics, and types; and Functions, Storage, Secrets, branches, domains, and network settings. Trigger for requests to rename a Supabase project, query or modify database data, deploy functions, or manage other hosted Supabase resources. Reuse or guide configuration of a personal access token (PAT). Cloud management uses the Management API; repository migrations and file deployment use the CLI. Cloud resources only; no Docker dependency.
---

# Supabase cloud operations

Use this skill for Supabase resource operations even when the user does not mention the skill, CLI, API, scripts, or token. An action request asks you to execute through the matching bundled script, not merely explain commands or send the user to the Dashboard. Ask only for required inputs still unresolved after safe discovery.

## Choose the operation, then its transport

The script entry describes the resource/action. Management API is the default for supported cloud operations. CLI handles repository migrations, file deployment/transfer, diagnostics, and additional reviewed remote modes. Do not switch interfaces simply because authentication, permissions, SQL, or networking failed. Never automatically replay a possibly applied write.

| User intent | Bundled entry and default route |
|---|---|
| 修改项目名称、创建/查看/删除/暂停/恢复项目 | `supabase_project.py list/get/create/rename/delete/pause/restore/restart` — Management API; `organizations` for organization discovery |
| 查询/修改表数据、查看表结构 | `supabase_db.py query/tables` — Management API; query defaults to server-side `read_only=true`, writes require `--write` |
| TypeScript 类型、迁移历史、云端备份 | `supabase_db.py types/migrations/backups/restore-pitr` — Management API |
| Apply standalone reviewed schema SQL | `supabase_db.py query --write` — API for ordinary PAT users; restricted `migration-apply` only for confirmed selected-partner OAuth access and without an existing repository migration workflow |
| Deploy existing repository migrations | `supabase_db.py cli -- migration ...` / `supabase_db.py cli -- db push --linked`; keep existing files/history; never apply the same migration through both interfaces |
| DB diagnostics / advisors | `supabase_db.py cli -- db lint --linked --project-ref REF ...`, `supabase_db.py cli -- db advisors --linked --project-ref REF ...`, or `supabase_db.py cli -- inspect db METRIC --linked --project-ref REF`; initialize/link the selected workdir first. The HTTP metadata/advisors endpoints are deprecated/experimental, not defaults |
| Functions list/get/delete, Secrets, branches | `supabase_resources.py functions/secrets/branches ACTION` — implemented API actions |
| Service configuration, bucket listing, domain/network reads | `supabase_resources.py config/storage/domains/network-restrictions ACTION` — API; this does not imply full service API coverage |
| Deploy/download function source, Storage files, further cloud resources | `supabase_resources.py cli -- ...` — inspect installed help and read [CLI resources](references/cli-reference.md) before execution. Functions deploy/download requires `--use-api`; Storage object paths use `ss:///bucket/path` and the installed version may require `--experimental` |
| PAT setup or CLI installation | `supabase_auth.py status/verify`; `supabase_setup.py check` only if a CLI task needs it |

Set `SCRIPTS` to this skill's absolute scripts directory. API actions require an explicit `--project-ref` where applicable; they never infer one from a link, ambient workdir, or prior task. `--workdir` resolves input/output files only. API actions do not require `init`, `link`, CLI installation, a DB password (except project creation), or Docker.

Always invoke native CLI operations through the owning bundled wrapper; never call the `supabase` binary directly. Use `supabase_project.py cli -- ...` for project/org/config/link groups, `supabase_db.py cli -- ...` for db/migration/inspect/gen/test/seed groups, and `supabase_resources.py cli -- ...` for Functions, Storage objects, Secrets, branches, domains, networking and other reviewed resource groups. The wrapper choice is part of the operation contract because it enforces cloud targets and blocks Docker/local modes.

## Authentication and target resolution

1. Reuse `SUPABASE_ACCESS_TOKEN`. `supabase_auth.py status` reports presence only. If missing, guide the user to [Access Tokens](https://supabase.com/dashboard/account/tokens) and the host's secure environment settings; never request the token in chat or put it in argv/source files. When the host presents a secure credential input, use this exact English label: `Supabase Access Token (create one at https://supabase.com/dashboard/account/tokens)`. The variable must reach the actual helper process. Helpers do not load `.env` automatically or persist tokens.
2. With a known ref, use `supabase_auth.py verify --project-ref REF` or the intended read operation. Only enumerate projects when needed to resolve an ambiguous target. `verify` without ref checks the project-list permission; this does not prove every read/write permission. A fine-grained token may allow DB/config access without project enumeration; test the intended read capability instead of demanding unrelated permissions.
3. PAT is the default, not OAuth. `--profile` is CLI-only and rejected by API actions. Reuse a saved CLI account only when selected by the user; never switch accounts after a PAT failure. Service APIs have separate credentials; do not forward the PAT to arbitrary hosts or use administrative SQL as a substitute for Auth/Storage APIs.
4. For CLI operations only, reuse the installed/pinned CLI. If absent, automatically install using `supabase_setup.py` and continue under the existing bootstrap authorization, respecting host approval boundaries. Plugin setup is optional and only for an actual missing capability; see [plugin setup](references/plugin-setup.md). API-only work must not trigger either installation.

## Execute and verify

State the resolved target and intended change before a write. Existing authorization for that exact action applies; do not repeatedly ask for confirmation. Inspection does not authorize changes. Deletion, destructive reset, PITR restore, paid provisioning and cloning production data require corresponding scope. `--confirm-project-ref` is an execution safeguard for project deletion/PITR, not a replacement for authorization.

Use each operation's help and [capability table](references/api-capabilities.md) for inputs, transport, prerequisites, write behavior and verification. Read API schemas from the official endpoint reference when constructing JSON files; do not invent fields. Known script operations do not need CLI discovery on every call.

- `--dry-run` is only a local plan or read/preflight unless otherwise stated. It never sends the mutation. SQL previews do not execute SQL or prove server validity; do not simulate arbitrary SQL with a rollback transaction.
- SQL reads and writes use reviewed files passed with `--file`; never put SQL in argv. Use optional JSON parameter files for bindings. Preview affected rows with a separate read, keep predicates/transactions scoped, and inspect `RETURNING` or follow-up reads. Administrative SQL is not an end-user RLS test.
- API helpers use HTTPS on the fixed official Management API host, disable redirects and automatic retries, and sanitize failures. A timeout after writing is ambiguous; read state before any retry. 401/403/429 are errors to diagnose, not reasons to bypass controls or change transport.
- Only report verified success when the evidence supports it. Creation, pause/restore/restart and PITR return `accepted` with observations; continue bounded read checks without resubmitting writes. Secret set verifies names only, not the saved value. An accepted migration still needs schema/behavior verification.
- API read results and CLI stdout are not interchangeable formats. Native CLI output remains raw. `types` extracts the TypeScript source. API writes return small status summaries; protect SQL/user data, credentials, and config output from chat/logs.
- Helper `--output FILE` writes privately and atomically on success. A failure preserves the existing file. Native CLI file flags do not inherit that guarantee. Keep sensitive outputs outside source control.

## Cloud-only scope; no Docker dependency

This skill operates hosted Supabase resources, not local/self-hosted environments. Never install, start or request Docker, start a local Supabase stack, or move a Docker-dependent workflow to another runner as a fallback. Local SQL files, migration files, function source, init/link metadata and result files are allowed only to support the requested cloud operation. The shared CLI gate blocks local/custom DB modes, unreviewed commands, container-dependent dump/diff/pull/test/schema flows, and Functions deployment without `--use-api`. Remote flags alone do not prove absence of Docker dependencies. CLI help remains available even for blocked commands; do not bypass the gate by directly invoking the same blocked local command. To enable a new mode, first verify the installed version/implementation and update its reviewed capability rule.

For a requested logical export/restore, use a narrowly scoped PostgreSQL client connected to the selected cloud database only when needed. For unsupported diff/tests, use a verified container-free cloud route or report the capability as unsupported; do not introduce Docker or a local database server. Do not install clients during normal onboarding. Hosted backups are not equivalent to a logical dump or a complete backup of Storage files. If no appropriate route is available, state the uncompleted capability rather than claim success.

## Help and references

```bash
python3 "$SCRIPTS/supabase_project.py" --help
python3 "$SCRIPTS/supabase_project.py" rename --help
python3 "$SCRIPTS/supabase_db.py" query --help
python3 "$SCRIPTS/supabase_resources.py" config --help
# Helper help before --; actual CLI help after --:
python3 "$SCRIPTS/supabase_resources.py" cli --no-install -- --help
python3 "$SCRIPTS/supabase_resources.py" cli --no-install -- functions deploy --help
```

Helper help is offline and needs no token/CLI. Native help can install a missing CLI unless `--no-install` is supplied. `--no-install` never means offline/read-only. Follow installed root → group → operation help, including nested groups. Never infer absence from a bundled legacy binary or an incomplete documentation scrape.

- [API capabilities](references/api-capabilities.md): registered routes, JSON inputs, verification and gaps.
- [Projects and authentication](references/projects.md): PAT injection, project actions, optional CLI setup.
- [Database operations](references/database.md): SQL, migration ownership, backup/restore, RLS and diagnostics.
- [CLI resources](references/cli-reference.md): additional remote commands and service API entry points.

Legacy `supabase_helper.sh` / `.py` and `gen-types`, `migration-new`, `db-lint`, `inspect`, `init`, `link` retain their CLI behavior. Prefer API `types` for new TypeScript requests. Legacy native execution now shares the cloud/Docker guard; it is not an unrestricted escape hatch. Python helpers use only the standard library.
