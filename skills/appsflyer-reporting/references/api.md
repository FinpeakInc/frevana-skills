# AppsFlyer Reporting API Reference

## Master API

### Last update

```text
GET https://hq1.appsflyer.com/api/master-agg-data/lastupdate
```

Use Bearer authentication. The response can be JSON or plain text depending on content negotiation.

Official reference: <https://dev.appsflyer.com/hc/reference/master-lastupdate>

### Master report

```text
GET https://hq1.appsflyer.com/api/master-agg-data/v4/app/{app_id}
```

Required query parameters:

- `from`: lower LTV attribution date, `YYYY-MM-DD`
- `to`: upper LTV attribution date, `YYYY-MM-DD`; maximum inclusive range is 31 days. Do not concatenate separately aggregated Master reports into one result.
- `groupings`: comma-separated dimensions
- `kpis`: comma-separated KPI selections

Use API field names for groupings, not dashboard display labels. Common values include `app_id`, `pid`, `af_prt`, `c`, `af_adset`, `af_ad`, `af_channel`, `af_siteid`, `af_keywords`, `is_primary`, `af_c_id`, `af_adset_id`, `af_ad_id`, `install_time`, `attributed_touch_type`, and `geo`.

Optional filters exposed by the wrapper:

- calculated KPI query entries whose names begin with `calculated_kpi_`
- `pid`: media source
- `c`: campaign
- `af_prt`: agency
- `af_channel`: channel
- `af_siteid`: publisher/site ID
- `geo`: country
- `currency`: `preferred` or `USD`
- `timezone`: `preferred`
- `format=json`: request JSON instead of the default CSV

Master data is calculated daily and is generally available within 24–48 hours. Master API is not available to agencies and partners.

Official references:

- <https://dev.appsflyer.com/hc/reference/overview-9>
- <https://dev.appsflyer.com/hc/reference/master_api_get>

## Aggregate Pull API

Base endpoint form:

```text
GET https://hq1.appsflyer.com/api/agg-data/export/app/{app_id}/{report}/v5
```

Report mapping:

| CLI name | API report path | Grouping summary |
|---|---|---|
| `partners` | `partners_report` | Media source and campaign |
| `partners-daily` | `partners_by_date_report` | Date, media source, and campaign |
| `daily` | `daily_report` | Date, media source, and campaign; excludes in-app events |
| `geo` | `geo_report` | Geo, media source, and campaign |
| `geo-daily` | `geo_by_date_report` | Date, geo, media source, and campaign |

Required query parameters:

- `from`: `YYYY-MM-DD`
- `to`: `YYYY-MM-DD`

Optional parameters exposed by the wrapper:

- `media_source`
- `category`: `standard`, `facebook`, or `organic`
- `attribution_touch_type=impression`
- `currency`: `preferred` or `USD`
- `reattr=true`
- `timezone`: the exact app timezone, such as `Europe/Paris`

When filtering a media source, pass the matching category. For example, use both `media_source=facebook` and `category=facebook`; use `category=standard` for most other sources. AppsFlyer's prose mentions a Twitter category but the current endpoint enum omits it, so the wrapper does not advertise or send `category=twitter` without a future verified API update.

Aggregate Pull reports return CSV. The wrapper's JSON output is a local conversion of the merged CSV. Long-range splitting is enabled only for `daily`, `partners-daily`, and `geo-daily`; non-daily `partners` and `geo` requests remain one aggregate API call.

Official references:

- <https://dev.appsflyer.com/hc/reference/overview-11>
- <https://dev.appsflyer.com/hc/reference/get_app-id-partners-by-date-report-v5-1>
- <https://dev.appsflyer.com/hc/reference/get_app-id-daily-report-v5-1>
- <https://dev.appsflyer.com/hc/reference/get_app-id-geo-by-date-report-v5-1>

## Authentication and freshness notice

Send the AppsFlyer API V2 token only as:

```text
Authorization: Bearer <token>
```

AppsFlyer states that all API V2 tokens generated before March 10, 2026 at 19:00 UTC were revoked. Regenerate older tokens before diagnosing valid requests as malformed.
