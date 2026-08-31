# Other Supabase resource entry points

This skill exposes native CLI capabilities, not just its shortcuts. Set `SCRIPTS` to its absolute scripts directory. Use the resource entry below (project/DB tasks have dedicated `supabase_project.py` / `supabase_db.py` entries):

```bash
python3 "$SCRIPTS/supabase_resources.py" cli --workdir "$PROJECT_DIR" -- "$GROUP" --help
python3 "$SCRIPTS/supabase_resources.py" cli --workdir "$PROJECT_DIR" -- "$GROUP" "$OPERATION" --help
```

Set `GROUP` and `OPERATION` to a group/operation below before running these examples. Read current help before choosing flags, especially `--experimental`, target selection and output format. Use an explicit project ref when supported, otherwise verify the workdir's linked project. Add `--profile NAME` before the separator for a different auth profile. Never assume `--local` is universal; Storage defaults/experimental requirements, for example, must be checked.

| User intent / resource | CLI entry and operations to discover | Required context / verification |
|---|---|---|
| Edge Functions | `functions`: new, list, download, serve, deploy, delete | Workdir, function name and remote ref; list after deploy/delete. Keep JWT verification enabled unless public access is intended. |
| Remote function secrets | `secrets`: list, set, unset | Project ref and names; use supported `set --env-file` with a private file rather than secrets in argv. Verify names/digests without values. |
| Storage objects | `storage`: ls, cp, mv, rm | Target project, bucket/object path and source/destination; inspect help for `ss:///` paths, local/linked targeting and experimental flags. Verify object listing after mutation. |
| Storage bucket setup/seeding | `seed buckets`; supported config fields | Review config, bucket access and local paths. Seed is a write. CLI object commands are not a complete bucket-settings API; use documented Storage API/SDK when needed. |
| Preview branches | `branches`: create, list, get, update, pause, unpause, delete | Parent project and branch name/id; list/get to verify readiness. `get` may reveal DB credentials. Do not confuse branch pause with main-project pause. |
| SSO providers | `sso`: add, list, show, info, update, remove | Project, provider id, SAML metadata/domains; verify provider state. Ordinary Auth users/sessions require Auth Admin API/SDK, not SSO commands. |
| Custom API domains | `domains`: create, get, reverify, activate, delete | Project and hostname; inspect existing state/DNS requirements before changing DNS. Verify domain status; potential paid feature. |
| Vanity subdomains | `vanity-subdomains`: check-availability, get, activate, delete | Project and desired subdomain; verify final state. Do not treat availability checks as activation permission. |
| Network bans | `network-bans`: get, remove | Project and affected IP; diagnose why banned before removing, then re-read. |
| Network restrictions | `network-restrictions`: get, update | Project, intended IPv4/IPv6 CIDRs; save current state and prevent operator lockout. Do not broaden access to all IPs as a troubleshooting shortcut. |
| DB SSL enforcement | `ssl-enforcement`: get, update | Project and intended setting; verify clients support required TLS, then read back. |
| Postgres server settings | `postgres-config`: get, update, delete | Project, exact settings/values and impact/restart requirements; inspect current overrides, update only the requested values, read back. This is distinct from local `config.toml`. |
| Saved SQL snippets | `snippets`: list, download | Project and snippet id; downloading does not execute SQL. Review content and target separately before executing. |
| Service versions | `services` | Inspect versions using supported target flags; this is not a deploy/upgrade command. |
| Organizations | `orgs`: list, create | Organization selection/name; creating an org is distinct from creating a project. See projects.md. |
| DB tests / seed / code generation | `test`, `seed`, `gen` | Chosen DB/workdir and output path; see database.md. Do not run data-changing tests on production by default. |
| CLI utility/configuration | `bootstrap`, `completion`, `telemetry` | Discover via help; bootstrap creates local resources, telemetry changes CLI preferences. Only act when requested. |

The installed CLI may not expose every resource for every release/account. If the requested operation is missing, follow the official Management API, Auth Admin API, Storage API or SQL documentation as appropriate; don't invent CLI subcommands for main-project pause/restore, user management, Realtime, Cron, Queues or other products. Report account/plan restrictions rather than silently substituting a different resource.

For mutations, inspect first, reuse the user's existing authorization for the exact scope, execute, and verify. Avoid blind retries of create/upload/deploy when completion is uncertain. Deletion, credential rotation, access changes and billable resource creation need authorization covering their consequences. The native entry point does not add or enforce these authorizations for you.

Sources:
- [Official CLI groups and flags](https://supabase.com/docs/reference/cli/introduction)
- [Management API](https://supabase.com/docs/reference/api/introduction)
- [Storage](https://supabase.com/docs/guides/storage)
- [Auth Admin API](https://supabase.com/docs/reference/javascript/admin-api)
