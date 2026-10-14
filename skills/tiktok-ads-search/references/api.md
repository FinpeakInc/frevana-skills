# Frevana TikTok Ads Library task API

Default host: `https://ai-factory.frevana.com`. Authentication: `Authorization: Bearer <FREVANA_TOKEN>`. Do not use a TikTok Business access token here.

## Create

`POST /service/tiktok-ads/tasks` returns HTTP 202 with a task object and `client_task_id`. The script sends a stable client ID generated before the request if omitted. The server rejects unsupported fields and null parameter values.

| JSON field | CLI option | Contract / server default |
| --- | --- | --- |
| `client_task_id` | `--client-task-id` | Optional trimmed nonempty string, max 128 characters. Same ID + same normalized parameters returns the same task; changed parameters return 409. |
| `query` | `--query` | Optional trimmed nonempty string, max 256 characters. |
| `advertiser_name` | `--advertiser-name` | Optional trimmed nonempty string, max 256 characters; may combine with query. |
| `ad_ids` | repeat `--ad-id` | 1–100 unique strings of 1–32 decimal digits; excludes every search field below and query/advertiser. Keep IDs as strings. |
| `max_pages` | `--max-pages` | Integer 1–25, default 1. Search estimates at most 12 ads per page. |
| `start_date` | `--start-date` | Valid `YYYY-MM-DD`, default server UTC date one year earlier. |
| `end_date` | `--end-date` | Valid `YYYY-MM-DD`, default server UTC today. Start must not exceed end; end must not be in the future. Server validates the effective range including omitted defaults. |
| `timezone` | `--timezone` | Default `UTC`. Exact allowlist in [timezones.json](timezones.json). |
| `country` | `--country` | Default `all`; supported values below. |
| `sort_by` | `--sort-by` | `last_shown_date,desc` (default), `last_shown_date,asc`, `create_time,desc`, `create_time,asc`, `impression,desc`, `impression,asc`. |
| `quick_search` | `--quick-search true|false` | Boolean, default false. True skips detailed enrichment and can omit creative/advertiser/targeting fields. |

For search, require `query`, `advertiser_name`, or a specific country. An empty request or country `all` alone is invalid. Ad ID lookup sends only `ad_ids` plus `client_task_id`, with no implicit search defaults.

Countries: `all FR AT BE BG HR CY CZ DK EE FI DE GR HU IS IE IT LV LI LT LU MT NL NO PL PT RO SK SI ES SE CH GB`. Values are case-sensitive. `US` and `CN` are not supported filters.

Example requests:

```json
{"client_task_id":"caller-stable-search","query":"pikoya","country":"ES","max_pages":1}
```

```json
{"client_task_id":"caller-stable-detail","ad_ids":["1878055429367345"]}
```

Creation performs a credit preflight; actual usage settles later. Do not describe its initial estimate or upstream charge allowance as a guaranteed final price or hard cap.

## Status and polling

`GET /service/tiktok-ads/tasks/{task_id}` requires a UUID v4 owned by the authenticated user. The public response has **no `billing_status`**:

```json
{
  "task_id":"7af283fe-13aa-431d-a7cf-b58675701884",
  "status":"RUNNING",
  "result_available":false,
  "result_count":0,
  "error_code":null,
  "error_message":null,
  "next_poll_after_ms":5000
}
```

| Status | Action |
| --- | --- |
| `PENDING`, `RUNNING`, `SETTLING` | Continue after `next_poll_after_ms` (currently 5000). `SETTLING` includes billing pending/retry. |
| `READY` | Fetch result only when `result_available=true`; currently implies billing is complete. |
| `FAILED` | Stop and report error fields. |
| `REVIEW_REQUIRED` | Stop; manual reconciliation needed, including uncertain upstream triggering or billing review. Do not resubmit. |
| `RESULT_EXPIRED` | Stop; results are no longer available. |

`next_poll_after_ms=0` means automatic polling can stop. The helper defaults to a six-hour wait budget; `--timeout 0` disables this budget. Resuming `wait` does not create or charge for a replacement task. Creation transport/HTTP/response failures are not automatically retried.

## Result

`GET /service/tiktok-ads/tasks/{task_id}/result` streams a JSON array in stored item order. HTTP 409 means the result is unavailable (including pending/settling/review/failed); HTTP 410 means expired. HTTP 404 can mean a nonexistent or inaccessible task. Save/print only a successful JSON array; errors must not overwrite the requested output.

Items include `adId`; available detail fields may include `adTitle`, `adType`, `adLandingUrl`, `adVideoUrl`, `adVideoCover`, `adImageUrls`, `adStartDate`, `adEndDate`, `advertiserName`, `advertiserCountry`, `advertiserTtUser`, `adImpressions`, and targeting arrays. Details are optional; use returned values without reshaping, constructing URLs, or converting missing values into facts. Media URLs are not permanently hosted or archived by Frevana, so do not assume URLs are permanent Frevana-hosted assets.

The server limits stored results to 50 MiB and items to 1 MiB. The client rejects responses larger than 52 MiB and preserves successful response bytes when saving or printing. No `/items` endpoint is used by this skill.
