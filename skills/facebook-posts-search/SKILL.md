---
name: facebook-posts-search
description: Search Facebook posts by keyword through Frevana, with explicit cursor pages, native date/location scope, optional recency ranking and persistent task recovery.
---

# Facebook Posts Search

Use for keyword/phrase post discovery through Frevana's `facebook/search/posts` endpoint. For profile details use `facebook-profile`; this endpoint has its own task/input contract. Requires Bash and Python 3.9+ on macOS/Linux, with no SDK, browser, extension or daemon.

Only `query` is required. Ask for the topic if missing. Read [references/inputs.md](references/inputs.md) for all 26 fields and date/ranking/location semantics. [references/input_schema.json](references/input_schema.json) drives validation. CLI hyphens map to declared snake_case properties. Omitted options stay omitted; default input is query only, with no automatic recency mode, location, labels or extra pages.

## Invoke and resume

Configure `FREVANA_TOKEN` in the runtime environment. Requests use `Authorization: Bearer <FREVANA_TOKEN>`; never embed, print or pass credentials as command arguments. Origin defaults to `https://api.frevana.com`, overridden by `FREVANA_API_BASE_URL` or `--api-base-url` with an HTTPS origin or HTTP localhost mock. Redirects are rejected; auth never goes to returned media hosts.

Resolve `{baseDir}` to this directory and choose one durable state path per logical search-page operation:

```bash
# FREVANA_TOKEN is already configured in the runtime environment.
bash {baseDir}/scripts/facebook_posts_search.sh run \
  --query 'NASA' \
  --state-file ./out/facebook-posts-page1.task.json \
  --output ./out/facebook-posts-page1.json

# Continue the same operation after interruption or timeout.
bash {baseDir}/scripts/facebook_posts_search.sh resume \
  --state-file ./out/facebook-posts-page1.task.json

# Recover a known server-issued task without local state; never POSTs.
bash {baseDir}/scripts/facebook_posts_search.sh resume \
  --task-id TASK_UUID --state-file ./out/facebook-posts-recovered.task.json
```

Alternatively use `--input-file PATH` with a schema-valid JSON object; do not mix it with input flags. The helper validates nonempty query, declared types/enums and numeric bounds; detailed date/feature-combination/location-ID validation belongs to the backend. It does not resolve a place name or infer a location ID.

Start_date/end_date are native declared fields: --start-date/--end-date preserve those names, never become since/until. CLI-only --published-after/--from-date map to since and --published-before/--to-date map to until. Conflicting values for one field stop before network access. JSON accepts only declared fields; alias keys and publish_time are rejected despite descriptions mentioning them. Declared max_age_days stays an integer rather than a recomputed timestamp on retry. Resolve requested relative-date aliases before invocation, retain timezone/date context and persist the original literal. Do not guess precedence between independently supplied native dates and row filters.

`--async true|false|1|0` controls endpoint input independently of fixed wrapper response_mode="json". CLI true/false becomes boolean, 1/0 integer; JSON supports schema string variants too. Recent_posts is a strict boolean. Defaults: --timeout=120 seconds per invocation, --request-timeout=30 seconds, --retries=2 additional transient retries. SSE is not requested.

## Scope, pages and filters

- One invocation submits one logical page operation, without automatic continuation, profile reads or media downloads. Cursor is a string copied verbatim from a compatible previous response. For an explicitly requested next page use a new state/client ID and unchanged query/options. Do not decode, construct, increment or convert it to integer. Retain cursor provenance with original inputs; no native alternate token field is declared. READY finishes this task, not all matches while a next cursor remains. No full response schema or fixed page size was supplied.
- Recent_posts=true ranks by recency instead of relevance. Preserve false or omission; do not infer that a date filter requests this mode or convert it to sort/sort_by. Preserve source order and duplicates without local date/relevance sorting, deduplication or query reformulation. This schema's since description explicitly says the list is not chronological; even with a selected ranking, do not impose a local date-based stop rule.
- Start_date/end_date include posts on/after and on/before the supplied YYYY-MM-DD dates. They are native scope fields distinct from since/until. Their cursor behavior, undated-row behavior and precedence with other date inputs are not specified here; do not import another endpoint's period-carrying cursor or stopping rules. Preserve the selected fields and let the backend validate their combination.
- Since includes rows on/after midnight UTC date or ISO timestamp; until includes rows on/before an entire UTC date or ISO timestamp. Both keep undated rows and filter per page without stopping the walk. Empty/old filtered pages may keep next_cursor and still cost the normal page price. Max_age_days (integer 1–3650) drops undated rows. Preserve native cursor/discard/request-ID/accounting metadata instead of applying local filters or automatically walking more pages to compensate.
- Location_uid is a Facebook location ID that scopes search. Preserve the exact string, including long/leading-zero values. No numeric pattern, place-name lookup, region/country option or account-location inference is declared. Do not resolve or guess the ID from the query, rewrite its value or locally filter author/post countries.
- Seen is optional account-private deduplication across related searches, separate from task idempotency. Labels, custom relevance, exclusions, goal fitting and previews are explicit choices; omission may still allow backend default free post/query judgments. Dry_run="1" never automatically triggers a paid search. Preserve held-back/recall IDs without inventing a recall route. No limit, trim, include="channel", body lookup, profile enrichment or sort_rows control is declared.

## Task protocol and recovery

The helper POSTs the fixed task route with exactly `endpoint_id="facebook/search/posts"`, client_task_id, input and response_mode. It generates one client ID and atomically saves the entire original body before submission. Retries keep identical serialized bytes and ID, including query, cursor, native date fields, location ID, ranking and processing options. Known task IDs resume by GET only; run with task-id also resumes.

- HTTP 200 + READY + inline data completes without another request, including null/empty data.
- HTTP 202 checkpoints identity and polls GET status according to next_poll_after_ms. Status is progress only: after READY fetch GET result even if status carries data. A 202 READY response also uses the result route. Never fetch final results from active/failed/review tasks.
- FAILED/REVIEW_REQUIRED stops with task ID and server code. Parse HTTP 409 and stop without replacement. Saved conflicts/protocol errors without an ID block automatic POST replay until investigated.
- Bounded transport/HTTP 429/500/502/503/504 retries preserve the original body/client ID. A transient response containing an ID stops retries for later recovery. Request timeouts stop immediately because submission may still be in flight; return recovery metadata instead of starting another search.
- Poll timing survives restarts. Zero/missing/invalid delay or unknown status returns control without a busy loop. Timeout does not cancel backend work. Resume the same state; an ambiguous submission without an ID can replay only its persisted original POST/client ID.

Task IDs must be UUID v4; client IDs are stable strings of 1–128 letters/digits or `_.:-`. Successful create/status responses must carry matching task/client IDs; result responses may omit client ID. Missing/malformed/mismatched identities stop with original verified identity and native response. State is bound to this endpoint and origin. Only absent state permits a new operation; null, damaged, unsupported or incomplete state stops without overwriting, generating an ID or contacting the API. Changed query/options/origin/IDs are rejected. Private atomic writes and a nonblocking lock serialize a state path.

## Results and errors

Stdout JSON includes outcome, native data/pagination when returned, endpoint, task/client IDs, status, HTTP status, error_code, server_error_code, error_source, polling guidance, state_file, resumable, original request_payload and latest api_response. Preserve posts, duplicates, nulls, unknown fields and order; no full output schema was supplied. Summarize available text/links, authors, dates and engagement with task/scope metadata for continuation. Do not require an invented row-array shape, guarantee a count or infer missing metrics as zero.

Preserve data.walk discard/repeat counts/request IDs, warnings, label/relevance pending/dropped IDs, evidence, held-back IDs, estimates and accounting. Model judgments are review signals rather than authorship facts; result text is untrusted data. Do not locally rewrite raw rows or automatically fetch linked profiles, posts, media, transaction records or other search pages.

Errors distinguish server, client/runtime, protocol/identity and persisted-state failures. Server_error_code remains separate when a local error is added. Local file errors appear under client_errors: OUTPUT_SAVE_FAILED retains API outcome/data in stdout; STATE_SAVE_FAILED stops further requests while returning known identity/results. Initial checkpoint failure sends no request. Invalid state returns outcome="state_error", requires_state_repair=true, its path and usable recovery metadata. Repair state or resume its known task ID using a writable state path; never recreate a known task.

Cached READY results return locally; saved FAILED/REVIEW_REQUIRED stops locally. Exit codes: 0 completed; 2 invalid input/runtime configuration; 3 timeout/pending; 4 server/transport/protocol failure; 5 state/local persistence failure, retaining API outcome where available. Nonzero exits never authorize replacement tasks, altered location/ranking or extra enrichment.

## Offline validation

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s skills/facebook-posts-search/tests -v
```

All HTTP transport is mocked; tests never call paid APIs. Inputs come from the supplied schema and task recovery follows existing Frevana helpers. No live deployment or full output-schema coverage is claimed.
