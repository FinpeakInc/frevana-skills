# Database operations

Set `SCRIPTS` to this skill's absolute scripts directory. Use explicit cloud project refs for API actions. The operation map and exact paths are in [API capabilities](api-capabilities.md). CLI is retained for repository workflows and diagnostics; API is the default for ad hoc SQL, table inspection, TypeScript generation, migration history and hosted backup management.

## SQL and data changes

```bash
python3 "$SCRIPTS/supabase_db.py" tables --project-ref "$PROJECT_REF" --schema public
python3 "$SCRIPTS/supabase_db.py" query --project-ref "$PROJECT_REF" --file "$SQL_FILE"
python3 "$SCRIPTS/supabase_db.py" query --project-ref "$PROJECT_REF" --file "$SQL_FILE" --parameters-file "$PARAMETERS_FILE"
# Only for reviewed, already-authorized SQL writes:
python3 "$SCRIPTS/supabase_db.py" query --project-ref "$PROJECT_REF" --file "$SQL_FILE" --write
```

The [SQL API](https://supabase.com/docs/reference/api/v1-run-a-query) is Beta. Default requests include `read_only=true`, including queries calling functions. `--write` disables that restriction only for the authorized operation. Files prevent SQL/parameter literals entering process arguments; keep sensitive files private and outside source control. `--dry-run` is a local plan: it never executes SQL or validates it against the database. Do not substitute a regex SQL classifier or execute arbitrary statements under a pretend rollback preview.

Before INSERT/UPDATE/DELETE, read the intended rows and estimate the effect using the same predicate. Keep transactions and batches scoped; not every SQL statement supports a transaction. Verify `RETURNING`/actual rows after the write, not just HTTP success. Do not retry uncertain writes through CLI or another account. API helpers return provider rows unchanged, so the agent must interpret actual outcomes. Limit result size and avoid unnecessary customer-data exports.

For schema inspection use parameterized information_schema/pg_catalog SQL rather than the deprecated `/database/context` endpoint. Use reviewed migrations for persistent table, index, grant and RLS changes. Cron/Queues can use their documented SQL APIs, but dequeuing/acknowledging is a mutation even when phrased as a read.

## Migration ownership

For a repository already using `supabase/migrations`, preserve its migration files, versions and history. Inspect the link and history, create a migration with the CLI, review its SQL, preview pending changes, then deploy under existing authorization:

```bash
python3 "$SCRIPTS/supabase_db.py" migration-new "$MIGRATION_NAME" --workdir "$PROJECT_DIR"
python3 "$SCRIPTS/supabase_db.py" cli --workdir "$PROJECT_DIR" -- migration list --linked
python3 "$SCRIPTS/supabase_db.py" cli --workdir "$PROJECT_DIR" -- db push --linked --dry-run
python3 "$SCRIPTS/supabase_db.py" cli --workdir "$PROJECT_DIR" -- db push --linked
```

Verify migration history and changed schema/behavior. The CLI may need a separate DB password; request it only then. Do not replay the same migration through API, change applied files, or automatically repair/squash history. The API `migrations` action is a read and can inspect the same remote history.

For ordinary PAT-based standalone cloud work without a repository migration workflow, use `query --write` with reviewed schema SQL. The separate [migration API](https://supabase.com/docs/reference/api/v1-apply-a-migration) is available only to selected partner OAuth apps. An eligible integration may use `migration-apply --project-ref REF --file FILE --name NAME --partner-api-access`, optionally with `--rollback-file FILE`; the flag asserts already-confirmed eligibility and cannot grant it. The helper rejects a workdir containing existing `supabase/migrations/*.sql`; do not evade this check by changing workdir. The returned status is accepted, not proof of schema correctness. Optional rollback SQL does not make every migration reversible; never infer undo SQL or invoke rollback automatically.

For missing baselines, recover original migrations or use `migration fetch --linked` after inspecting help and preserving local files. This recovers recorded history, not every unrecorded Dashboard edit. Native schema-only export is an alternative when necessary; reconcile dependencies, managed schemas, grants and already-applied history deliberately. Never replay a baseline over existing objects.

## Cloud operations only; no Docker dependency

The scripts block local stack commands, `--local`/`--db-url`, `db pull/diff/dump/start/schema`, `test db`, and unreviewed modes before execution. CLI `--help` remains available. Merely using a remote target or a preview flag does not remove container dependencies. Do not bypass this policy through the native binary or install/start Docker. Preserve declarative schema files, but do not claim automatic diff generation when the available engine requires local containers.

Do not redirect unsupported diff/test operations to Docker on another runner. Use a verified container-free cloud workflow, or a scoped native PostgreSQL client connected to the cloud database for an explicitly requested export/import. Local database development and self-hosting are outside this skill. Do not provision paid infrastructure implicitly. If no suitable route exists, report that capability as unperformed. New Docker-free CLI modes require implementation/version review and an explicit policy update before execution.

## Hosted backup versus logical export

`backups --project-ref REF` reads hosted backup inventory. `restore-pitr --project-ref REF --confirm-project-ref REF --timestamp SECONDS` requests destructive recovery; resolve the exact project/time, available recovery window, plan entitlement, authorization and recovery plan first. `--dry-run` does not initiate or validate recovery. A successful request is accepted, not proof of completed restoration. Read project status and validate restored data without resubmitting the restore. See [PITR endpoint](https://supabase.com/docs/reference/api/v1-restore-pitr-backup).

Hosted backups are not an on-demand logical dump or a complete backup of Storage files. For a requested logical export, use compatible native `pg_dump` or an existing authorized container-free cloud export workflow; install only the required client tools when missing. Do not start a database server. A PAT is not a DB password: obtain the actual selected project's connection settings, prefer direct/session connections as required, and preserve TLS settings. Use a private `PGPASSFILE` or protected prompt, never credential-bearing URLs in logged argv. The script CLI gate intentionally rejects `--db-url`; native-client work is a separate documented workflow, not an escape to a local Supabase stack.

Write exports to a unique private directory (umask 077), stage partial output and publish only on exit 0. Scope schemas/tables explicitly, use a compatible server/client major version, preserve dependencies and record excluded resources. Independent exports need not share one snapshot. Inspect archives with `pg_restore --list`; restore only to the authorized destination with reviewed ownership, grants, privileges and RLS. Do not overwrite production merely to test a backup. See [pg_dump](https://www.postgresql.org/docs/current/app-pgdump.html) and [Supabase restore guidance](https://supabase.com/docs/guides/platform/migrating-within-supabase/backup-restore).

## Diagnostics, types and RLS

Use CLI `db advisors --linked --project-ref REF`, `db-lint` or `inspect METRIC` with an initialized and linked remote workdir. CLI 2.116.0 rejects `--project-ref` for these diagnostics unless `--linked` is also present. The HTTP advisors endpoints are deprecated/experimental; avoiding direct dependence does not guarantee the CLI uses a different provider backend. Inspect installed help and report failures without claiming equivalent checks ran. `db lint` checks database code; it does not establish RLS coverage or index efficiency. See [CLI reference](https://supabase.com/docs/reference/cli/introduction).

Inspect RLS/policies and grants separately across all exposed schemas, not only public. RLS does not grant privileges. Review view security-invoker behavior and privileged functions when changed. Administrative SQL/service-role execution is not an end-user access test: verify both allowed and denied operations using the intended role/JWT context. Never modify auth/storage managed tables to imitate supported service APIs.

Use `types --project-ref REF --schema public --output types/database.ts` for API TypeScript generation. The helper validates the `types` response and saves only source text, atomically. Old `gen-types` retains linked CLI behavior for compatibility; other languages can be discovered through CLI `gen types --help`, but execution remains blocked until a Docker-free implementation is reviewed. SQL/diagnostic output may be sensitive.

DB fixtures, extension setup and tests may mutate data; use an expressly authorized disposable/remote test target, not production by default. Verify actual TAP/assertion results; successful SQL execution alone does not prove tests passed.
