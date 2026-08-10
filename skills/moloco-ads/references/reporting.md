# Analytics, reports, and logs

## Choosing an API

- Use `analytics-overview` for synchronous dashboard-style summaries.
- Use `analytics-detail` for synchronous filtered analysis. It supports comprehensive dimensions and metrics but returns no more than 10,000 rows.
- Use `analytics-skadnetwork` for SKAdNetwork-specific metrics and conversion dimensions.
- Use Report API for daily or periodic bulk export. It is asynchronous, supports CSV and JSON, returns up to 4 million rows, and does not support filters.
- Use Log API only when Moloco has enabled it for the account. It exports event-level data asynchronously.

## Analytics payloads

The CLI can build the common payload from:

- `--ad-account-id`
- `--from` and `--to`
- `--dimensions`
- `--metrics`
- optional `--timezone`
- optional `--limit` up to 10,000

For filters or advanced fields, supply an object through `--payload-file`. Explicit flags override the same top-level fields in that file. Both start and end dates are inclusive; the CLI rejects ranges over 184 days.

Always use the exact enum values in the current API reference. Common values include `DATE`, `CAMPAIGN_ID`, `CAMPAIGN_TITLE`, `CREATIVE_ID`, `IMPRESSIONS`, `CLICKS`, `INSTALLS`, `SPEND`, and `REVENUE`, but availability differs across the three Analytics endpoints.

## Report API

Report dimensions currently include:

- `DATE`
- `APP_OR_SITE`
- `CAMPAIGN`
- `AD_GROUP`
- `CREATIVE_GROUP`
- `CREATIVE`
- `EXCHANGE`
- `SUB_PUBLISHER`
- `TRAFFIC`
- `SKAN`

Optional metrics currently include `VIDEO_PLAY_PROGRESS`, `ENGAGED_VIEWS`, and `ENGAGED_CLICKS`. Default report metrics such as impressions, clicks, installs, spend, and revenue are returned without listing them as optional metrics.

The report lifecycle is `ACCEPTED` → `READY` or `FAILED`. Download URLs expire in one hour. Use the URL returned by the status endpoint and never derive or persist the storage hostname.

## Log API

Current log types:

- `IMP`
- `CLICK`
- `CONVERSION`
- `SKAN_CONVERSION`
- `ENGAGED_VIEW`

The CLI supports `CSV` and `AVRO`. Although the current Create Log schema also enumerates `PARQUET`, the documented Log Status response exposes download locations only for CSV and AVRO. Do not request PARQUET until Moloco documents a corresponding status/download field. Availability can depend on the account and API version. A status response can contain multiple file URLs, so the CLI preserves each part as a separate file.

Unless `skip_compression` is enabled, Moloco can return compressed files such as `.csv.gz`. The CLI preserves the compression suffix instead of decompressing or renaming the payload.

The log lifecycle is `ACCEPTED` → `READY` or `FAILED`. Download URLs expire in one hour. The CLI strips these URLs from displayed and saved status results.
