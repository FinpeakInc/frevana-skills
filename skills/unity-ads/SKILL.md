---
name: unity-ads
description: Query and safely manage Unity Ads through the official Monetization Stats API, Advertising Statistics API v2, and Advertising Management API v1. Use when the user wants Unity Ads monetization revenue or inventory reports; Unity Acquire acquisition or SKAN reports; app, campaign, budget, bid, targeting, creative, or creative-pack inspection; or previewed and explicitly confirmed Unity Ads management changes.
---

# Unity Ads

Use one wrapper with three internally routed modules. Do not construct ad hoc Unity Ads URLs.

## Requirements

- Require Python 3.9 or newer.
- Run all commands through `scripts/unity_ads.sh`.
- Keep API hosts fixed to `monetization.api.unity.com` and `services.api.unity.com`.
- Read credentials from environment variables or owner-only secret files. Never print credentials.
- Use the current official API documentation as the source of truth when a payload schema changes.

## Route the request

- Route publisher revenue, views, starts, availability, and ad-request data to `monetization report`.
- Route advertiser acquisition and SKAdNetwork performance to `reporting report`.
- Route apps, campaigns, budgets, bids, targeting, creatives, and creative packs to `management`.
- Keep Unity SDK and LevelPlay integration work outside this skill.

Read only the relevant reference before using a module:

- [references/monetization.md](references/monetization.md)
- [references/acquire-reporting.md](references/acquire-reporting.md)
- [references/acquire-management.md](references/acquire-management.md)

## Authentication

For monetization reports, require:

```text
UNITY_ADS_MONETIZATION_API_KEY
UNITY_ADS_MONETIZATION_ORG_ID
```

For Acquire reporting and management, use either:

```text
UNITY_ADS_SERVICE_ACCOUNT_KEY_ID
UNITY_ADS_SERVICE_ACCOUNT_SECRET
UNITY_ADS_ORGANIZATION_ID
```

or a Unity service-account bearer token:

```text
UNITY_ADS_SERVICE_ACCOUNT_BEARER_TOKEN
UNITY_ADS_ORGANIZATION_ID
```

Command-line IDs override environment IDs. Secret-file options override secret environment variables. Do not pass secrets directly on the command line.

## Workflow

1. Check runtime and credential presence without exposing values:

   ```bash
   bash <skill-path>/scripts/unity_ads.sh check
   ```

2. Select the smallest module and action.
3. Execute GET reports and reads directly.
4. For a management mutation, identify exact organization, app, campaign, and resource IDs. Put the JSON payload in an owner-only file.
5. Run the mutation without `--execute` to retrieve current state when applicable and print a preview.
6. Obtain explicit user confirmation for the shown targets and payload.
7. Rerun with `--execute`; let the script compare the requested fields with a verification GET.
8. Return a concise summary and the saved output path. Do not paste large reports unless requested.

## Reports

Query monetization statistics:

```bash
bash <skill-path>/scripts/unity_ads.sh monetization report \
  --start 2026-08-01T00:00:00Z \
  --end 2026-08-08T00:00:00Z \
  --fields revenue_sum,view_count,adrequest_count \
  --group-by game,country,platform \
  --scale day \
  --format json
```

Query Acquire statistics:

```bash
bash <skill-path>/scripts/unity_ads.sh reporting report \
  --report acquisitions \
  --start 2026-08-01T00:00:00Z \
  --end 2026-08-08T00:00:00Z \
  --scale day \
  --metrics clicks,installs,spend,cpi \
  --breakdowns app,campaign,country \
  --eof-marker
```

Use `--report skan` for SKAdNetwork reporting. Reports stream to owner-only temporary files and are atomically moved under `./out/` by default. Add `--stdout` only when the user explicitly requests the complete body.

## Management reads

List supported actions:

```bash
bash <skill-path>/scripts/unity_ads.sh management list-actions
bash <skill-path>/scripts/unity_ads.sh management describe --action get-budget
```

List campaigns:

```bash
bash <skill-path>/scripts/unity_ads.sh management call \
  --action list-campaigns \
  --app-id 5eb26a338a232100e4bb5893
```

Call another documented Management API path relative to the organization:

```bash
bash <skill-path>/scripts/unity_ads.sh management call \
  --method GET \
  --path apps/5eb26a338a232100e4bb5893/campaigns
```

Reject absolute URLs, query strings embedded in paths, path traversal, and paths outside the selected organization.

## Management writes

Preview a campaign budget update:

```bash
bash <skill-path>/scripts/unity_ads.sh management call \
  --action update-budget \
  --app-id 5eb26a338a232100e4bb5893 \
  --campaign-id 5eb26a338a232100e4bb6361 \
  --body-file /secure/path/budget.json
```

After explicit confirmation, repeat the exact command with `--execute`.

For a documented action not in the built-in action table, provide `--method`, `--path`, and `--body-file`. For `PATCH`, `PUT`, and `DELETE`, also provide `--current-path`. For every mutation provide `--verify-path`; use `--verify-mode absent` when deletion should produce `404`. For list updates containing null deletion values, also provide the comma-separated identity fields through `--verify-keys`.

Safety rules:

- Treat every non-GET request as a mutation.
- Preview mutations by default. Require `--execute` for network writes.
- Read current state before `PATCH`, `PUT`, or `DELETE`.
- Require a GET verification after every successful mutation and compare the requested fields with the returned state.
- Do not automatically retry a mutation.
- Explain that deleting an app also deletes its campaigns, bids, and creative packs and cannot be recovered.
- Do not upload creative binaries through generic JSON calls. Add a schema-aware multipart action first.
- Treat reports, source-app identifiers, targeting, attribution URLs, and campaign data as sensitive.

## Failure handling

- Treat `204` from reporting as a successful empty report.
- Retry GET-only `429` and `5xx` responses with bounded exponential backoff; honor numeric `Retry-After`.
- Treat `401` as invalid credentials and `403` as missing organization access or role.
- Mention that Management API access must be enabled by Unity when a properly authorized service account still receives access errors.
- Split high-cardinality Acquire reports by day when they time out or risk incomplete output.
- Use `--eof-marker` for large CSV Acquire reports and verify the marker before claiming the download is complete.
- Strip authentication headers from every cross-origin redirect and reject HTTPS downgrades.
- Never include authorization headers, credentials, or a full secret-bearing request in error output.
