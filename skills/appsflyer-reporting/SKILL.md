---
name: appsflyer-reporting
description: Query AppsFlyer reporting APIs for Master API campaign KPIs, Master data freshness, and Aggregate Pull API partner, daily, and geo reports. Use when the user asks for AppsFlyer LTV, activity, retention, cohort, Protect360, installs, revenue, media-source, campaign, country, or daily aggregated performance data, or wants AppsFlyer reports exported as CSV or JSON.
---

# AppsFlyer Reporting

Use the bundled read-only CLI for AppsFlyer Master API and Aggregate Pull API reports.

## Requirements

- Require Python 3.9 or newer.
- Require `APPSFLYER_API_TOKEN` in the environment.
- Require AppsFlyer subscription access to the requested report and app.
- Never print, quote, save, or pass the token on the command line.
- Use `scripts/appsflyer_reporting.sh`; do not construct ad hoc AppsFlyer URLs.

AppsFlyer revoked API V2 tokens generated before March 10, 2026 at 19:00 UTC. If a previously working token receives `401`, tell the user to regenerate it in AppsFlyer before retrying.

## Workflow

1. Select `master-last-update`, `master-report`, or `pull`.
2. Collect the required app ID, dates, groupings, and KPIs. Do not guess them.
3. Route freshness, custom KPI, retention, cohort, and Protect360 requests to Master API. Route fixed daily, partner, and geo aggregates to Pull API; use Pull `daily` for ordinary daily performance requests.
4. Keep Master reports within 31 inclusive days. Let the script split and merge only date-grouped Pull reports; never merge independently aggregated Master, `partners`, or `geo` chunks.
5. Return a concise summary and the saved output path. Do not paste a large report unless requested.
6. Preserve the raw report unless the user explicitly chooses Pull API `--format json`, which performs a local CSV-to-JSON conversion.

## Commands

### Check Master data freshness

```bash
bash <skill-path>/scripts/appsflyer_reporting.sh master-last-update
```

### Get a Master report

```bash
bash <skill-path>/scripts/appsflyer_reporting.sh master-report \
  --app-id com.example.app \
  --from 2026-08-01 \
  --to 2026-08-31 \
  --groupings install_time,pid,c \
  --kpis installs,revenue \
  --format json
```

Master Report checks `master-last-update` first and writes the freshness value to stderr. Use `--skip-last-update` only when that extra request is undesirable. Master API accepts at most 31 inclusive days; run separate reports for longer periods.

Add a calculated KPI with a name that starts with `calculated_kpi_`:

```bash
bash <skill-path>/scripts/appsflyer_reporting.sh master-report \
  --app-id com.example.app \
  --from 2026-08-01 \
  --to 2026-08-07 \
  --groupings install_time,pid \
  --kpis installs,revenue \
  --calculated-kpi 'calculated_kpi_revenue_per_install=revenue/installs'
```

### Get an Aggregate Pull report

```bash
bash <skill-path>/scripts/appsflyer_reporting.sh pull \
  --report partners-daily \
  --app-id com.example.app \
  --from 2026-08-01 \
  --to 2026-08-31 \
  --media-source facebook \
  --category facebook
```

Supported Pull report names:

- `partners`
- `partners-daily`
- `daily`
- `geo`
- `geo-daily`

Use `--format json` to convert the returned CSV rows into a JSON array locally. Aggregate Pull API itself returns CSV. Only `daily`, `partners-daily`, and `geo-daily` are split and merged across long ranges because they include a date dimension; `partners` and `geo` are sent as one aggregate request.

## Output and errors

- Save every successful response under `./out/` by default; use `--output` to select a path.
- Print the saved path to stderr. Add `--stdout` only when the user explicitly requests the complete report on stdout.
- Validate that report responses have a compatible CSV or JSON content type.
- Keep CSV headers once when merging safe, date-grouped Pull chunks.
- Merge JSON arrays, or objects containing a `data` array, across chunks.
- Retry `429` and `5xx` responses with bounded exponential backoff and honor numeric `Retry-After` values.
- Sanitize API error text and never include the token or full request URL.
- Treat `401` as invalid/revoked credentials or account suspension, `404` as an invalid app ID or unavailable subscription feature, and other non-2xx responses as failures.

For endpoint and parameter details, read [references/api.md](references/api.md).
