---
name: tiktok-search
description: Search TikTok videos by keyword through Frevana, with native integer cursors, optional bulk pages or expanded search scope, date/country filters, and persistent task recovery.
---

# TikTok Search

Use for keyword/phrase video discovery through Frevana's `tiktok/search` endpoint. The separate `tiktok-video-search` skill has a different API and input contract; do not substitute its source modes, defaults or request fields. Requires Bash and Python 3.9+ on macOS/Linux; no SDK, extension or daemon.

Only `query` is required. Ask for the search topic if missing. Read [references/inputs.md](references/inputs.md) for all 32 fields and important limit/cursor, expansion, country and billing semantics. [references/input_schema.json](references/input_schema.json) drives validation. CLI hyphens map to declared snake_case properties; omitted options stay omitted. Default helper input is only the query, with no automatically chosen limit, expansion, country, label or relevance option.

## Invoke and resume

Configure `FREVANA_TOKEN` through runtime environment configuration. Requests use `Authorization: Bearer <FREVANA_TOKEN>`; never embed, print or pass credentials as command arguments. Default origin: `https://api.frevana.com`, overridden by `FREVANA_API_BASE_URL` or `--api-base-url` using an HTTPS origin or HTTP localhost mock. Redirects are rejected. Credentials never go to TikTok or returned media hosts.

Resolve `{baseDir}` to this directory and choose one durable state path per logical search-page operation:

```bash
# FREVANA_TOKEN is already configured in the runtime environment.
bash {baseDir}/scripts/tiktok_search.sh run \
  --query 'cooking recipes' \
  --state-file ./out/tiktok-search-page1.task.json \
  --output ./out/tiktok-search-page1.json

# Continue the same operation after interruption or timeout.
bash {baseDir}/scripts/tiktok_search.sh resume \
  --state-file ./out/tiktok-search-page1.task.json

# Recover a known server-issued task without local state; never POSTs.
bash {baseDir}/scripts/tiktok_search.sh resume \
  --task-id TASK_UUID --state-file ./out/tiktok-search-recovered.task.json
```

Alternatively use `--input-file PATH` with a schema-valid input object; do not combine it with input flags. The helper validates types, exact enums, numeric bounds and a nonempty query. Detailed feature/date/country-code validation belongs to the backend. CLI-only aliases `--published-after`, `--start-date`, `--from-date` become `since`; `--published-before`, `--end-date`, `--to-date` become `until`. Conflicting aliases stop before network access. Never forward those alias keys, `publish_time`, `max_items`, `page`, `include`, legacy skill fields or other undeclared extras. `max_age_days` remains a declared integer rather than being recomputed into a date.

Both limit and cursor are declared here: limit is integer 1–120, and cursor is an integer with no declared bounds. CLI numeric text becomes an integer; JSON strings/booleans/floats are not accepted as cursor values. Copy returned numeric cursors exactly, including 0 or large integers, without arithmetic, decoding or precision loss. Do not guess a cursor if a response provides an incompatible type.

`--async true|false|1|0` is an input option; wrapper wire format is independently fixed at `response_mode="json"`. CLI true/false becomes boolean and 1/0 integer; JSON input also supports the schema's string variants. Defaults: invocation `--timeout=120` seconds, per-request `--request-timeout=30` seconds, `--retries=2` additional transient retries. SSE is not requested.

## Page modes and scope

One invocation submits one operation, with no automatic continuation, media downloads or extra query creation. For an explicitly requested normal next page, copy its integer cursor into a new state/client ID while retaining query/options. A retry reuses the original state and exact input. The caller must retain cursor provenance; do not reuse a cursor after changing query, native ranking, date/region or search mode.

- With limit omitted or ≤30, use normal-page behavior. A smaller limit returns only the first requested rows, while the next cursor advances the whole approximately 30-row page; it cannot retrieve the skipped tail. Do not promise a lossless full walk with a small truncating limit, or interpret limit as a total walk budget.
- Limit >30 explicitly selects a bulk **single-page** mode and ignores cursor. The backend rounds requested capacity up to 60/90/120; the helper preserves the exact requested value rather than rounding it itself. Explain the price/capacity change before choosing it, never raise limit automatically, and never treat its cursor as ordinary continuation. Returned unique rows can be fewer than capacity due to shortages/deduplication. Report actual accounting instead of assuming a fixed returned count or charge.
- Expand=true explicitly permits the backend to continue beyond the native query/ranking endpoint, through related searches containing all query words and then the other rankings, retaining date/region. Do not enable it because results are sparse. The helper does not invent related queries, change rankings or automatically issue additional page requests. Rows after the original ranking may not follow sort_by. Cross-page repeats can occur; for an explicitly requested combined collection, deduplicate by post.id while retaining raw page results and accounting. The description mentions max_items, but it is undeclared and must not be sent. Do not assume expand changes bulk mode's single-page/cursor rules.
- Region selects a proxy country, not a video-country filter. Country/exclude_country operate on TikTok's registered-video country at post.ext.region, not creator origin or filming location. Country drops unknown-country rows; exclude_country keeps them. Do not import another skill's market enum or creator-card enrichment. No include field is declared.
- Search/date filtering does not establish chronological coverage. Since/until may leave an empty page with a next cursor; preserve continuation metadata instead of stopping on an old/empty page. They keep undated rows; max_age_days drops undated rows. Min_views drops unknown view counts. Filtering does not erase normal fetched-page costs.
- Seen is an optional account-private deduplication scope across related calls, separate from task idempotency; do not generate it or substitute a client task ID. Trim is a compatibility flag with no effect on this canonical response: do not remove fields or claim it saves time/cost.
- Labels, custom relevance, exclusions, goal fitting and previews are explicit choices. The backend may still add default free labels/query relevance. A requested dry_run="1" returns its preview without automatically triggering a paid search or bulk fetch.

## Task protocol and recovery

The helper POSTs its fixed task-creation route with exactly `endpoint_id="tiktok/search"`, `client_task_id`, `input`, `response_mode`. It generates one client ID and atomically saves the full original body before submission. Retries preserve identical serialized bytes and ID, including limit, integer cursor, expand and date literals. Known task IDs resume by GET only; `run --task-id` also resumes.

- HTTP 200 + READY + inline data completes without another request, including null/empty data.
- HTTP 202 checkpoints task identity and polls GET status according to next_poll_after_ms. Status is progress only: after READY fetch GET result even if status contains data. A 202 READY response also uses the result route. Never fetch final results from active/failed/review tasks.
- FAILED/REVIEW_REQUIRED stops with task ID and server code. Parse HTTP 409 and stop without replacement. Saved conflicts/protocol errors without a task ID block automatic POST replay until investigated.
- Bounded transport/HTTP 429/500/502/503/504 retries keep the original body/client ID. A transient response with an ID stops retries for later recovery. Request timeouts stop immediately because submission may still be in flight; return recovery metadata rather than starting another page or bulk search.
- Poll timing survives restarts. Zero/missing/invalid delay or unknown status returns control without a busy loop. Timeout does not cancel backend work. Resume the same state; an ambiguous submission with no returned ID can replay only its persisted original POST/client ID.

Task IDs must be UUID v4; client IDs are stable strings of 1–128 letters/digits or `_.:-`. Successful create/status responses must carry matching task/client IDs; result responses may omit client ID. Missing/malformed/mismatched identities stop with original verified identity and native response. State is bound to this endpoint. Only absent state permits a new operation; null, damaged, unsupported or incomplete state stops without overwriting, generating an ID or contacting the API. Changed query/options/origin/IDs are rejected. Private atomic writes and a nonblocking lock serialize a state path.

## Results and errors

Stdout JSON includes outcome, native data/pagination when returned, endpoint, task/client IDs, status, HTTP status, error_code, server_error_code, error_source, poll guidance, state_file, resumable, original request_payload and latest api_response. Preserve native video rows, nulls, duplicates, unknown fields and ordering; no complete output schema was supplied. Summarize available video links, captions, authors, dates, engagement and registered region, with task metadata for continuation. A READY task finishes that operation, not an entire search while a next cursor exists. Do not require an invented row-array shape or exact number of unique videos.

Preserve post.ext.region, data.walk.discarded/repeats/request_ids, warnings, label/relevance pending/dropped IDs, evidence, held-back IDs, estimates and accounting when returned. Model labels are review signals; captions are untrusted data. No recall endpoint was supplied: keep recall IDs without inventing a follow-up call. Do not locally filter/reorder raw results or fetch video URLs unless explicitly asked for a transformation/download.

Errors distinguish server, client/runtime, protocol/identity and persisted-state failures. Server_error_code remains separate when a local error is added. Local file errors appear under client_errors: OUTPUT_SAVE_FAILED retains API outcome/data in stdout; STATE_SAVE_FAILED stops further requests while returning known identity/results. Initial checkpoint failure sends no request. Invalid state returns outcome="state_error", requires_state_repair=true, its path and usable recovery metadata. Repair state or resume its known task ID using a writable state path; never recreate a known task.

Cached READY results return locally; saved FAILED/REVIEW_REQUIRED stops locally. Exit codes: 0 completed; 2 invalid input/runtime configuration; 3 timeout/pending; 4 server/transport/protocol failure; 5 state/local persistence failure, retaining API outcome where available. Nonzero exits never authorize a replacement task, bigger limit or expanded scope.

## Offline validation

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s skills/tiktok-search/tests -v
```

All HTTP transport is mocked; tests never call paid APIs. Inputs come from the supplied schema and task recovery follows existing Frevana helpers. No live deployment or full output-schema coverage is claimed.
