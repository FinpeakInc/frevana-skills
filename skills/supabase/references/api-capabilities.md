# Implemented capabilities and transport selection

Verified against [Management API reference](https://supabase.com/docs/reference/api/introduction) on 2026-08-31. This is a capability map, not a promise that every Supabase endpoint is wrapped. API actions below require Python 3 + a PAT, no CLI or Docker. No caller-defined URL/API base is accepted. `--profile` is rejected for API actions. `--workdir` only resolves files; it does not choose an API target.

## Projects: supabase_project.py

| Action | API path after /v1 | Required input | Effect and verification |
|---|---|---|---|
| list | GET /projects | PAT with list permission | Read; returns array, not an auth test for every write |
| organizations | GET /organizations | PAT with organization read | Read; array |
| get | GET /projects/{ref} | --project-ref | Read; verifies response ref/name |
| create | POST /projects | --name, --organization-slug, --config-file; password environment | Write; optional dry-run is local preview. Returns accepted/ref; GET readback is not readiness proof |
| rename | PATCH /projects/{ref} | --project-ref, --name; optional --expect-name | Read → scoped write → readback. Dry-run reads only; same name skips write |
| delete | DELETE /projects/{ref} | --project-ref and matching --confirm-project-ref | Destructive; pre-read; only 404 readback proves deletion |
| pause / restore / restart | POST /projects/{ref}/{action} | --project-ref | Pre-read, write, read status; accepted does not mean completed |

Create config: choose exactly one `region_selection` (current schema) or `region` (legacy deprecated field), optionally `desired_instance_size`/`high_availability`. Use the exact current [create schema](https://supabase.com/docs/reference/api/v1-create-a-project) and user-selected region/capacity. Do not silently enable paid features. Password defaults to the `SUPABASE_DB_PASSWORD` environment value and is never printed. `--db-password-env` names an alternate environment variable, not the password itself.

## Database: supabase_db.py

| Action | API path after /v1/projects/{ref} | Required input | Effect and verification |
|---|---|---|---|
| query | POST /database/query | --project-ref, --file; optional --parameters-file | Server-side read_only=true by default; --write permits authorized mutations. Returns provider rows unchanged |
| tables | POST /database/query | --project-ref; --schema defaults public | Read-only parameterized information_schema query, no deprecated metadata API |
| types | GET /types/typescript | --project-ref; --schema defaults public | included_schemas query parameter; extracts types string; --output writes source atomically |
| migrations | GET /database/migrations | --project-ref | Read history |
| migration-apply | POST /database/migrations | --project-ref, --file, --name, --partner-api-access; optional --rollback-file | Restricted to selected partner OAuth apps; rejects ordinary execution without the explicit eligibility assertion and rejects existing workdir supabase/migrations/*.sql. Accepted + history readback; verify actual schema separately |
| backups | GET /database/backups | --project-ref | Read hosted backup inventory; not an export |
| restore-pitr | POST /database/backups/restore-pitr | --project-ref, matching --confirm-project-ref, --timestamp | Destructive; timestamp in Unix seconds, plan/backup availability required. Accepted is not recovery validation |

`query --dry-run` and `migration-apply --dry-run` never submit SQL, not even in a rollback transaction. They are local plans and do not validate syntax/access/schema. A parameters file is a JSON array; preserve SQL bindings rather than interpolating literals. No SQL regex classifier is used for read-only enforcement. Administrative queries do not emulate a user's JWT/RLS privileges.

The [SQL API](https://supabase.com/docs/reference/api/v1-run-a-query) is Beta. [Apply migration](https://supabase.com/docs/reference/api/v1-apply-a-migration) accepts optional rollback SQL but is available only to selected partner OAuth apps. Ordinary PAT users should submit reviewed standalone schema SQL through `query --write`; `--partner-api-access` is an eligibility assertion, not a way to obtain access. The helper does not infer rollback or automatically undo failures. `migration-apply` is not an alternative way to push a repository migration already tracked/applied by CLI. The deprecated [database context](https://supabase.com/docs/reference/api/v1-get-database-metadata) and [advisors](https://supabase.com/docs/reference/api/v1-get-performance-advisors) HTTP endpoints are deliberately not defaults; use tables/query and the existing CLI diagnostic interface (which may itself rely on provider APIs).

## Other resources: supabase_resources.py

Syntax is `RESOURCE ACTION --project-ref REF [options]`; use `RESOURCE --help` for available actions. All writes support read/preflight `--dry-run`. JSON body files must follow the selected official schema. The server validates config field types; the wrapper only limits the endpoint/service and requires a nonempty object. No schema discovery or PATCH happens just because a field appeared in external output.

| Resource/actions | Endpoint suffix after /v1/projects/{ref} | Input / result |
|---|---|---|
| functions list/get/delete | /functions, /functions/{slug} | --slug for get/delete; deletion verified via list |
| secrets list/set/unset | /secrets | set body: array of {name,value}; unset body: array of names. Lists show names only; set verifies presence, not values |
| branches list/create | /branches | create --body-file with branch_name, optional git_branch/persistent/region/desired_instance_size/with_data. Creating/cloning requires authorization; accepted is not ready |
| storage buckets | /storage/buckets | Lists buckets only; object transfer/deletion uses CLI |
| config get/update --service auth | /config/auth (GET/PATCH) | --body-file for update; GET exposes only safe known values and other field names, never provider secrets |
| config get/update --service storage | /config/storage (GET/PATCH) | --body-file; external provider credentials are redacted |
| config get/update --service realtime | /config/realtime (GET/PATCH) | Service config, not subscriptions |
| config get/update --service rest | /postgrest (GET/PATCH) | Data API config, not table CRUD |
| config get/update --service postgres | /config/database/postgres (GET/PUT) | Account for restart/connection impact. Compare only requested fields on readback |
| domains get | /custom-hostname | Beta; read DNS/activation state. Mutation entry remains reviewed CLI domains commands |
| network-restrictions get | /network-restrictions | Beta; mutation entry remains reviewed CLI with CIDR/lockout review |

Examples (input files already reviewed, target resolved):

```bash
python3 "$SCRIPTS/supabase_db.py" query --project-ref "$PROJECT_REF" --file "$SQL_FILE"
python3 "$SCRIPTS/supabase_db.py" query --project-ref "$PROJECT_REF" --file "$SQL_FILE" --write
python3 "$SCRIPTS/supabase_db.py" types --project-ref "$PROJECT_REF" --output types/database.ts
python3 "$SCRIPTS/supabase_resources.py" functions list --project-ref "$PROJECT_REF"
python3 "$SCRIPTS/supabase_resources.py" config update --service auth --project-ref "$PROJECT_REF" --body-file "$CONFIG_FILE" --dry-run
python3 "$SCRIPTS/supabase_resources.py" secrets set --project-ref "$PROJECT_REF" --body-file "$PRIVATE_SECRETS_FILE"
```

## CLI-only and additional entry points

| Workflow | Entry | Requirements |
|---|---|---|
| Repository migrations | project init/link; db migration-new; cli -- migration ... / db push --linked | Existing application workdir/link, installed CLI; DB password only if the chosen CLI needs it |
| Diagnostics | db-lint, inspect; cli -- db advisors --linked --project-ref REF ... | Installed CLI and initialized/linked workdir; CLI 2.116.0 requires `--linked` alongside `--project-ref`; no local containers |
| Function source deployment/download | cli -- functions deploy/download ... --use-api --project-ref REF | CLI handles files; API flag is mandatory |
| Storage files | cli -- storage ls/cp/mv/rm ... --project-ref REF or --linked | Reviewed object paths/recursive scope; native flags from installed help |
| Other branch operations, SSO, domains/network mutations, encryption, snippets | cli -- GROUP ACTION ... | Only reviewed command families, exact target, operation-specific help; no invented flags |
| Logical DB export/import | documented native client connected to the selected cloud DB | Separate DB credentials and compatible client tooling, no Docker/local server; never pretend hosted backup listing is a dump |
| Auth users, Storage bucket admin beyond config/seed, Realtime subscriptions | official service API/SDK references in cli-reference.md | Separate credentials; these are extension entry points, not implemented Management API commands |

Shared CLI policy lives in `supabase_cli_policy.py`. `--help` stays available for all commands; execution rejects unknown families/modes and local/custom DB URL flags. The gate does not prove authorization or catch every change in a future CLI implementation; honor project pins and verify version-dependent behavior. Do not bypass it through a raw binary. New capabilities should extend the corresponding script/registry after doc/help verification, not introduce arbitrary HTTP passthrough.

The selected collection APIs document full-list responses and expose no cursor arguments in these wrappers. They do not synthesize pagination or follow response links. When adding a paginated endpoint, explicitly implement its documented cursor/limit and same-host bounds. Errors never trigger automatic retries. Preserve Retry-After/rate-limit semantics during manual read retries; uncertain writes require readback first.
