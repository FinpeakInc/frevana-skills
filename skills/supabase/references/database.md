# Database operations

Set `SCRIPTS` to this skill's absolute scripts directory. Use `python3 "$SCRIPTS/supabase_db.py" cli --workdir "$PROJECT_DIR" -- <arguments>` for native DB commands below. Database shortcuts are on the same script, and project init/link on `supabase_project.py`. The legacy helper remains compatible. Before running a version-dependent command, inspect its `--help`. Use `--linked` or a supported `--db-url` when appropriate; flags differ by command.

## Connect, inspect and run SQL / CRUD

Resolve the actual project/environment first. A Management API login does not necessarily provide DB credentials. Obtain connection settings from that project's Dashboard Connect panel; do not fabricate a pooler hostname or reuse a connection URL from another project.

- Hosted DB: select the documented direct connection or session pooler according to network availability and tooling. Prefer direct/session connections for migrations and session-dependent SQL. Read the connection guide before selecting transaction pooling for such operations.
- Custom Postgres connection: use `--db-url` only where the command advertises support. Avoid passing credential-bearing URLs in logged argv; prefer protected `psql` profiles for ad hoc SQL.

For SQL, first check `db --help`. If this CLI exposes `db query`, inspect `db query --help` for its actual target and SQL-file flags. Do not assume every supported CLI version has it. When unavailable, use standard `psql`:

1. Configure connection fields through existing `PGSERVICE`/`PGSERVICEFILE`, or `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, and appropriate TLS settings. Use the caller's approved host, role and CA/SSL configuration.
2. Supply credentials via a private `PGPASSFILE` (0600) or a protected password prompt; don't echo/commit passwords or put them into shell history. Profiles should name environments clearly. Confirm the profile mapping before connecting.
3. For inspection, use an actual read-only session and stop on SQL errors:

```bash
# SQL_FILE is a reviewed file; connection/profile variables are already configured.
PGOPTIONS='-c default_transaction_read_only=on' psql -X -v ON_ERROR_STOP=1 --file "$SQL_FILE"
```

Start by checking `current_database()`, `current_user`, `inet_server_addr()` and `version()`, then inspect requested tables with explicit columns and bounded results. Don't dump customer data by default.

For INSERT/UPDATE/DELETE, review predicates and expected row counts in a read-only query first. Execute only the authorized SQL using `psql -X -v ON_ERROR_STOP=1 --single-transaction --file "$SQL_FILE"` when the statements support transactions. Use `RETURNING`/follow-up queries to verify affected rows. Don't pretend a keyword/regex SQL classifier establishes read-only safety. `TRUNCATE`, broad deletes and other destructive operations need explicit scope. Prefer migrations for persistent schema changes; SQL access remains available for ordinary queries and data operations.

Sources: [connections](https://supabase.com/docs/guides/database/connecting-to-postgres), [psql](https://www.postgresql.org/docs/current/app-psql.html).

## Migrate existing or new schemas

1. Inspect the app's existing migrations, config, link and `migration list --linked` before modifying history. For an existing remote DB without local history, use `db pull` to establish a reviewed baseline; do not push an empty/new template blindly.
2. Preserve the project's schema workflow. If it uses declarative schema paths, edit those files and generate a diff. Otherwise run `migration new NAME` and write the migration. Do not hand-invent timestamps or rewrite already-applied migrations.
3. Review generated SQL: publication changes, Storage buckets and security-invoker views may not be captured completely. Do not equate an empty diff with verification of all resources.
4. Run relevant DB tests, lint and RLS/privilege checks below. For remote deployment, verify the link, run `db push --linked --dry-run`, inspect planned migrations, then `db push --linked` under the existing authorization.
5. Verify `migration list --linked` and the changed schema/behavior. A migration can partially fail depending on its SQL; inspect actual state before retrying. `migration repair`, squash and down require deliberate history/state reconciliation, not an automatic response to mismatch errors.

**Remote reset:** native `db reset --linked` or `--db-url` can drop user-created objects in the remote DB. It is not a routine migration/deployment method. Require exact target/data-loss authorization and a recovery plan. Do not automatically add `--yes`.

Sources: [migrations](https://supabase.com/docs/reference/cli/introduction#supabase-migration), [db reset](https://supabase.com/docs/reference/cli/introduction#supabase-db-reset).

## Backup and restore

Inspect `db dump --help`. By default dumps exclude data/custom roles and Supabase-managed schemas; a schema-only dump is not a full backup. Keep sensitive exports outside tracked directories. Example with atomic helper stdout saving:

```bash
python3 "$SCRIPTS/supabase_db.py" cli --workdir "$PROJECT_DIR" --output "$BACKUP_DIR/schema.sql" -- db dump --linked
python3 "$SCRIPTS/supabase_db.py" cli --workdir "$PROJECT_DIR" --output "$BACKUP_DIR/data.sql" -- db dump --linked --data-only
python3 "$SCRIPTS/supabase_db.py" cli --workdir "$PROJECT_DIR" --output "$BACKUP_DIR/roles.sql" -- db dump --linked --role-only
```

Use a private absolute `BACKUP_DIR`. Check each exit status and output; don't claim these files include Storage object contents, all managed schemas, or a consistent cross-file snapshot. For production recovery requirements use a suitable verified backup/PITR/export strategy.

Restore only into the expressly chosen destination. Review roles, ownership, grants and statement compatibility, then use the documented restore workflow with `psql`/`pg_restore` appropriate to the backup format. Verify restoration in an isolated target when practical. Do not restore over a linked production DB just to test a dump.

Sources: [dump](https://supabase.com/docs/reference/cli/introduction#supabase-db-dump), [backup restoration](https://supabase.com/docs/guides/platform/migrating-within-supabase/backup-restore).

## Lint, RLS and privileges are different checks

- `db lint` uses `plpgsql_check` for database code/schema errors. It does not establish RLS coverage, policy correctness, or index efficiency. Helper `db-lint` defaults to `--fail-on error`; inspect warnings too. Use native help if an older CLI does not expose this flag.
- Inspect RLS and policies separately via SQL (`pg_class.relrowsecurity`, `pg_namespace`, `pg_policies`) for **all exposed schemas**, not just `public`. Review role/schema/table privileges. Enable RLS for exposed tables and define policies for the real ownership/access model; don't default to public SELECT.
- RLS alone does not grant API access. New tables may require explicit GRANTs to intended roles under the project's Data API settings. Grant only requested access, and keep RLS in place.
- Verify both allowed and denied operations as the actual anon/authenticated roles and relevant JWT context or client session. Tests as `postgres`/service-role can bypass RLS and are not sufficient.
- Review view security-invoker behavior and privileged functions if changed. If the CLI provides advisors, inspect its help before using it; otherwise use documented Dashboard/API checks. Do not invent `db advisors` on an unsupported version.

Sources: [lint](https://supabase.com/docs/reference/cli/introduction#supabase-db-lint), [securing the Data API](https://supabase.com/docs/guides/api/securing-your-api), [RLS](https://supabase.com/docs/guides/database/postgres/row-level-security).

## Diagnostics, types and tests

- `inspect db --help` discovers metrics; use `table-record-counts`, `index-usage`, `locks`, `cache-hit`, `long-running-queries`, `vacuum-stats` as supported. Helper `inspect METRIC --target linked --output FILE` saves raw stdout, which may contain sensitive SQL text.
- Helper `gen-types --target local|linked --schema public --output types/database.ts` writes only after success. Native `gen types --help` exposes additional languages/targets.
- `test db --help` / `test new --help` provide pgTAP entry points. Run tests against the chosen local/disposable DB unless remote test execution is explicitly intended. Test fixtures may mutate data.
- For errors/timeouts, inspect exit status and targeted logs; fetch [monitoring/debugging guidance](https://supabase.com/docs/guides/monitoring-and-debugging) before diagnosing provider behavior. Don't loop resets, repair migration history, or disable RLS to hide a failure.
