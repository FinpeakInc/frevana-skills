---
name: moloco-ads
description: Query, analyze, export, and safely manage Moloco Ads through the official Moloco Ads API. Use whenever the user mentions Moloco Ads, Moloco campaign performance, spend, impressions, clicks, installs, revenue, ROAS, Analytics, Report API, Log API, campaigns, ad groups, creatives, products, tracking links, audiences, customer sets, or wants to inspect, create, update, pause, enable, or delete a Moloco Ads resource. Do not use for Moloco Commerce Media (MCM) or Moloco Publisher SDK workflows.
---

# Moloco Ads

Use the bundled CLI as the single entry point for Moloco Ads authentication, analytics, asynchronous reports and logs, and campaign entity management. This skill targets Moloco Ads at `https://api.moloco.cloud/cm/v1`; it does not target Moloco Commerce Media.

## Requirements

- Require Python 3.10 or newer.
- Run commands through `scripts/moloco_ads.sh`; do not construct ad hoc Moloco requests.
- Read the API key only from `MOLOCO_ADS_API_KEY`. Never accept it as a command-line argument or print it.
- Default to API version `v1.10`. Use `MOLOCO_ADS_API_VERSION` only when the user's Moloco organization has standardized on another currently supported version.
- Let the CLI exchange the API key for a 16-hour access token and cache it locally with owner-only permissions. Never expose the cached token.

## Safety rules

- Keep the API origin fixed to `https://api.moloco.cloud` and paths under `/cm/v1/`.
- Use only the built-in resource allowlist. Do not add an arbitrary URL or raw-path escape hatch during a request.
- Execute analytics, report generation, log generation, status checks, downloads, and GET resource reads directly because they retrieve data.
- Preview entity create, update, and delete operations by default. Require the user to confirm exact IDs, query parameters, and payload before rerunning with `--execute`.
- Before entity update or delete, let the CLI retrieve the current object. Update output includes the before and after objects.
- Do not automatically retry entity mutations, report creation, or log creation. They can consume budget, change delivery, create duplicates, or consume limited daily quota.
- Never forward the Moloco bearer token or API-version header to report/log storage URLs. Do not print returned pre-signed URLs.
- Treat reports, logs, tracking URLs, audiences, customer sets, and identifiers as sensitive. Saved output files use mode `0600`.
- Confirm budgets, bids, schedules, countries, targeting, tracking links, creative assignments, and `enabling_state` before executing a campaign-related write.

## Workflow

1. Check local readiness:

   ```bash
   bash <skill-path>/scripts/moloco_ads.sh check
   ```

2. Select the smallest command matching the request. Use `list-actions` and `describe` when routing is unclear.
3. Collect required IDs and use API field names from the official documentation. Do not translate dashboard labels into guessed enum values.
4. Execute reads directly. For entity writes, show the preview, obtain confirmation, and rerun with `--execute`.
5. Return a concise summary and the saved output path. Do not paste large reports or logs unless requested.

## Analytics

Use Analytics for synchronous, filtered data. `analytics-detail` is capped at 10,000 rows and all supported Analytics date ranges are limited to 184 inclusive days.

```bash
bash <skill-path>/scripts/moloco_ads.sh analytics-detail \
  --ad-account-id ad_account_123 \
  --from 2026-08-01 \
  --to 2026-08-07 \
  --dimensions DATE,CAMPAIGN_ID,CAMPAIGN_TITLE \
  --metrics IMPRESSIONS,CLICKS,SPEND
```

Commands:

- `analytics-overview`
- `analytics-detail`
- `analytics-skadnetwork`

Use `--payload-file` for filters, ordering, conversion-event fields, or other documented request fields. Explicit flags override the corresponding fields in the payload file.

Read [references/reporting.md](references/reporting.md) before selecting dimensions, metrics, filters, or report behavior.

## Asynchronous reports

Use Report API for scheduled or large exports. A single report is limited to 31 inclusive days.

```bash
bash <skill-path>/scripts/moloco_ads.sh report-create \
  --ad-account-id ad_account_123 \
  --from 2026-08-01 \
  --to 2026-08-07 \
  --dimensions DATE,CAMPAIGN,CREATIVE \
  --format csv \
  --wait
```

Without `--wait`, return the report ID immediately. Continue later with:

```bash
bash <skill-path>/scripts/moloco_ads.sh report-status --report-id report_123
bash <skill-path>/scripts/moloco_ads.sh report-download --report-id report_123 --format json --wait
```

## Log data

Moloco disables Log API by default. Use these commands only after the user confirms Moloco has enabled it for the account:

```bash
bash <skill-path>/scripts/moloco_ads.sh log-create \
  --ad-account-id ad_account_123 \
  --date 2026-08-09 \
  --type IMP \
  --format CSV
```

Commands:

- `log-create`
- `log-status`
- `log-download`

Read [references/reporting.md](references/reporting.md) for supported log types and formats.

## Entity reads and writes

Supported resources:

- `ad-accounts`
- `products`
- `campaigns`
- `ad-groups`
- `creative-groups`
- `creatives`
- `audience-targets`
- `customer-sets`
- `tracking-links`

List and read:

```bash
bash <skill-path>/scripts/moloco_ads.sh list \
  --resource campaigns \
  --ad-account-id ad_account_123 \
  --product-id product_123

bash <skill-path>/scripts/moloco_ads.sh get \
  --resource campaign \
  --id campaign_123
```

Preview and execute a write:

```bash
bash <skill-path>/scripts/moloco_ads.sh update \
  --resource campaign \
  --id campaign_123 \
  --payload-file /secure/path/campaign-update.json

bash <skill-path>/scripts/moloco_ads.sh update \
  --resource campaign \
  --id campaign_123 \
  --payload-file /secure/path/campaign-update.json \
  --execute
```

Use `--params-file` for documented query fields not covered by common flags. Read [references/campaign-management.md](references/campaign-management.md) before preparing a write payload.

## Output and failures

- Save successful API responses under `./out/` by default; use `--output` to select a file.
- Use `--stdout` only when the user explicitly requests the complete JSON response.
- Report and log downloads are saved directly in their original format.
- Retry safe reads and Analytics requests on `429` and `5xx` with bounded backoff, honoring `Retry-After` or `X-Rate-Limit-Reset` when possible.
- On `401`, refresh the cached access token once. Retry only safe reads; for a write or export-creation request, stop after refreshing and ask the user to rerun it deliberately.
- On `403`, verify the API key's workplace, ad-account role, and requested resource.
- On `429`, report the relevant quota and wait for user direction before creating another report or log.
- Treat Moloco error payloads as authoritative, but redact credentials from all error output.

For the endpoint map, versioning, quotas, and source links, read [references/api-capabilities.md](references/api-capabilities.md).
