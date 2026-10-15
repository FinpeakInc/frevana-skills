# Frevana Firecrawl API contract

Snapshot of Server DTOs and service on 2026-10-15, using firecrawl SDK 4.46.0. These are Frevana endpoints, not direct provider APIs. Supported routes are POST under `/service/web/`; bearer JWT comes exclusively from FREVANA_TOKEN. No independent Extract, Agent, Browser, Monitor, Parse, paper-index or sitemap-crawl endpoint is exposed.

## Requests

Use `--json` or `@file` for advanced options. Required URL/query can instead be supplied using `--url` / `--query`; do not provide the same field twice. `run` selects the execution mode as described in SKILL.md. `--mode async` still waits; `start` submits and returns. For job operations supply `--job-id` and optional pagination JSON only.

### MapRequestDto

| Field | Server type |
| --- | --- |
| `url` | `string` |
| `search` | `string` |
| `sitemap` | `'include' | 'skip' | 'only'` |
| `includeSubdomains` | `boolean` |
| `ignoreQueryParameters` | `boolean` |
| `limit` | `number` |
| `timeout` | `number` |
| `location` | `LocationDto` |
| `threatProtection` | `ThreatProtectionDto` |
| `auditMetadata` | `AuditMetadataDto` |

## Shared option details

- `formats` supports string shorthand or objects with `type` and relevant configuration. JSON: `{"type":"json","prompt":"Extract fields","schema":{"type":"object","properties":{"name":{"type":"string"}}}}`. Schema keys are caller-defined and must be preserved. Screenshots: `{"type":"screenshot","fullPage":true}`. `changeTracking` compares snapshots; it does not schedule monitoring.
- `actions` are ordered scrape-time actions (wait/click/write/press/scroll/screenshot/scrape/executeJavascript/pdf). They do not create persistent browser sessions.
- `parsers` accepts pdf/image parser options; it does not upload local files.
- `headers` means target-site headers, not Frevana authentication. Do not print these in diagnostics. `webhook.headers`, `webhook.metadata`, and JSON Schema are dynamic dictionaries.
- Scrape `timeout`: 1000..300000 milliseconds. `waitFor`: 0..60000 milliseconds. Map/Search timeout is milliseconds. Crawl top-level timeout is seconds (default 120, max 300); pollInterval is seconds (default 2); nested scrapeOptions.timeout remains milliseconds. Async start excludes top-level timeout (and crawl pollInterval).
- `limit` is a positive integer; omission uses server/provider defaults. maxAge/minAge are milliseconds. Crawl maxDiscoveryDepth and delay may be zero. Do not conflate `maxAge=0` (fresh capture) with an unspecified cache preference.
- Status pagination: autoPaginate boolean (server default true); maxPages = additional pages after the first, maxResults = document cap, maxWaitTime = seconds. These may be zero. The exposed DTO has no skip/cursor field: never invent one or send provider `next` to an arbitrary host. If next remains, report incomplete coverage and query with larger suitable pagination limits. SDK 4.46.0 can also clear next when pagination stops early: require completed=total and a document array covering that count before claiming complete results. Missing counters or fewer documents return exit 3, preserving the native response. A settled but partial snapshot is returned immediately instead of polling the same limited page repeatedly; resume with larger suitable pagination limits on the existing job.

## Response and recovery

Native envelope: `{"request_id":"...","data":...,"billing":{"status":"PENDING","provider_credits":null,"credits":null,"multiplier":1.5}}`. Sync scrape document is at data; batch/crawl documents are at data.data. Map links and Search source groups remain in their native SDK shape; no normalized results list is invented. start responses put the job ID at data.id. cancel data is boolean. Preserve provider error entries and partial results.

Billing states: STARTED/PENDING/READY/DEBITING/BILLED/REJECTED/REVIEW. Provider job states include completed/failed/cancelled. READY, DEBITING and REVIEW can return data=null. Background settlement runs separately; status queries do not themselves settle usage. REVIEW requires reconciliation; REJECTED means pre-send argument rejection. Polling and cancellation do not add a separate fee, but prior consumed usage remains payable.

Idempotency-Key is scoped by user and operation; 1..128 ASCII letters, digits, dots, underscores or hyphens. Changed arguments with the same key return 409. A sync-to-async route change is a different operation and can create another paid task. Submission uncertainty may also return 409; do not rotate keys. No automatic retries on timeout, 429 or 5xx. A successful start is submission only, not completed collection. These API notes do not verify the live deployment.

## Nested DTO fields

The helper checks required inputs, execution mode, async exclusions, job pagination and key search conflicts. Advanced options are forwarded without a local DTO schema; Server/SDK validation remains authoritative. Update these parameter notes when the Server API changes.

- **ViewportDto**: `width`, `height`
- **SelectorDto**: `selector`, `attribute`
- **FormatDto**: `type`, `prompt`, `schema`, `fullPage`, `quality`, `viewport`, `modes`, `tag`, `selectors`, `question`, `query`, `mode`
- **ActionDto**: `type`, `milliseconds`, `selector`, `target`, `text`, `key`, `direction`, `amount`, `script`, `fullPage`, `viewport`, `format`, `landscape`, `printBackground`, `scale`
- **ParserDto**: `type`, `mode`, `maxPages`, `pages`, `blocks`, `pageMarkers`
- **LocationDto**: `country`, `languages`
- **RedactPiiDto**: `mode`, `entities`, `replaceStyle`
- **ThreatProtectionDto**: `mode`, `riskScoreThreshold`, `blacklist`, `whitelist`, `blockedTlds`, `failurePolicy`
- **AuditMetadataDto**: `username`
- **PageScrapeOptionsDto**: `formats`, `headers`, `includeTags`, `excludeTags`, `onlyMainContent`, `timeout`, `waitFor`, `mobile`, `parsers`, `actions`, `location`, `skipTlsVerification`, `removeBase64Images`, `blockAds`, `proxy`, `maxAge`, `minAge`, `storeInCache`, `lockdown`, `checkPromptInjection`, `redactPII`, `threatProtection`, `auditMetadata`
- **WebhookDto**: `url`, `headers`, `metadata`, `events`
- **SearchSourceDto**: `type`
- **SearchCategoryDto**: `type`
