---
name: instagram-reels-search
description: Search Instagram reels by keyword through Frevana, with date and view filters, optional market localization or creator-country filtering, explicit cursor pagination and resumable tasks.
---

# Instagram Reels Search

Use for keyword/phrase discovery through Frevana's `instagram/search/reels` endpoint. For posts from a known account use `instagram-profile-posts`; for account details use `instagram-profile-details`. Requires Bash and Python 3.9+ on macOS/Linux, with no SDK, extension or daemon.

Only `query` is required. Ask for the search topic if missing. Read [references/inputs.md](references/inputs.md) for all 29 fields and their semantics, feature costs and caveats. [references/input_schema.json](references/input_schema.json) drives CLI input validation. CLI flags use hyphens; JSON uses declared snake_case properties. Omitted options stay omitted; the helper does not choose enrichment, labels, country, relevance filtering, pages or dates for the user.

## Invoke and resume

Configure `FREVANA_TOKEN` in the runtime environment. Requests use `Authorization: Bearer <FREVANA_TOKEN>`; never hardcode, print or pass credentials as command arguments. Default origin is `https://api.frevana.com`, overridden by `FREVANA_API_BASE_URL` or `--api-base-url` using an HTTPS origin or HTTP localhost mock. Redirects are rejected.

Resolve `{baseDir}` to the skill directory. Use one durable state file per logical search-page operation:

```bash
# FREVANA_TOKEN is already configured in the runtime environment.
bash {baseDir}/scripts/instagram_reels.sh run \
  --query 'workout routine' \
  --state-file ./out/instagram-reels-page1.task.json \
  --output ./out/instagram-reels-page1.json

# Continue that operation after interruption or timeout.
bash {baseDir}/scripts/instagram_reels.sh resume \
  --state-file ./out/instagram-reels-page1.task.json

# Recover a known server-issued task without local state; never POSTs.
bash {baseDir}/scripts/instagram_reels.sh resume \
  --task-id TASK_UUID --state-file ./out/instagram-reels-recovered.task.json
```

Alternatively use `--input-file PATH` with a schema-valid input object; do not combine it with input flags. The helper validates declared types, exact enums and numeric bounds. Feature-combination and date-string validation belongs to the backend. CLI-only aliases `--published-after`, `--start-date`, `--from-date` map to `since`; `--published-before`, `--end-date`, `--to-date` map to `until`. Conflicting aliases stop before network access. Never forward undeclared aliases, `handle`, `limit`, `max_pages`, `publish_time` or other extras. The declared `max_age_days` field remains an integer; it is not recomputed into `since` on retries.

`--async true|false|1|0` is an input option; the independent wrapper wire format is fixed at `response_mode="json"`. CLI true/false becomes boolean and 1/0 becomes integer. JSON input also supports the schema's string variants. Runtime defaults: total `--timeout=120` seconds, `--request-timeout=30` seconds and `--retries=2` additional transient retries. SSE is not requested.

## Search scope and optional features

- Search requests return one page. For an explicitly requested continuation, copy `pagination.next_cursor` verbatim into `cursor`, preserve the other inputs and use a new state path/client ID. Do not decode or construct cursors. Prefer `cursor` to native integer `page`; the helper rejects both together. No automatic pagination or media downloads. A READY task means that operation completed; a next cursor means more search results remain.
- Search results are not chronological. `since`/`until` may leave an empty page while a next cursor remains. Do not stop a user-requested walk merely because a date-filtered page is empty. `since`/`until` retain undated rows; `max_age_days` drops undated rows.
- `region` localizes the search query and does not guarantee creator location. Use `country` only when the user specifically requests creators based in that market. Country filtering triggers creator-card lookups and can cost substantially more; it can return no matches while retaining lookup charges. Explain the difference and the supplied cost model before applying it; do not silently replace region with country or add an `include` value yourself.
- Only creator/country enrichment is documented: `include=creator`, `country` or `creator,country`. Never add `include=channel` or profile-post audio/tags options. An explicit country filter may cause the backend itself to imply creator enrichment; report `data.hydration` without changing the submitted payload.
- `seen` is a user-chosen deduplication scope across related searches, separate from task idempotency. Do not auto-generate it or reuse a client task ID as a seen ID. The helper preserves it when provided.
- Relevance scoring/filtering, goal fitting, labels, exclusions and cost previews are explicit options. Server defaults may still add free judgments and query relevance when omitted. A requested `dry_run="1"` returns its preview; never automatically follow with a paid search.

## Task protocol and identity

The bundled helper POSTs its fixed Frevana task-creation route with exactly `endpoint_id="instagram/search/reels"`, `client_task_id`, `input` and `response_mode`. It generates and atomically persists one client ID and the original full payload before submission. Retries use identical serialized bytes and ID. Known task IDs resume by GET and never issue another POST.

- HTTP 200 + READY + inline `data` (including null/empty data) completes immediately without another request.
- HTTP 202 saves the task ID and polls GET status according to `next_poll_after_ms`. GET status supplies progress and timing, not final data: even if it includes a `data` field, fetch GET result only after READY. A 202 response with READY also uses the result route. Never fetch results from an active/failed/review task.
- Bounded transient transport failures and HTTP 429/500/502/503/504 retries preserve request bytes. A transient response with an ID stops retries so the task can be resumed. A request timeout stops immediately because submission may still be in flight; return recovery metadata rather than replacing the operation.
- FAILED or REVIEW_REQUIRED stops with task ID and server code. Parse and stop on HTTP 409. A conflict without a task ID blocks automatic POST replay. A saved identity/protocol error without a task ID also stops until investigated; no automatic replacement ID or submission.
- Poll schedules survive restarts. Zero/missing/invalid delay or unknown task status returns control without a busy loop. A timeout does not cancel backend work; resume the same state. If an interrupted submission never returned an ID, `resume` can replay only its saved original POST/client ID.

Task IDs must be UUID v4; client IDs are stable strings of 1–128 letters/digits or `_.:-`. Successful create/status responses must include matching task/client IDs; final result responses may omit the client ID. Missing, malformed or mismatched IDs return protocol errors with the original verified identity and native response. State is bound to this endpoint. Only an absent state file permits a new operation; null, damaged, unsupported or incomplete state stops without overwriting, generating an ID or contacting the API. Changed query/options/origin/identity are rejected. Atomic private state writes and a nonblocking lock serialize one state path.

## Results and errors

Stdout JSON contains `outcome`, native `data` and `pagination` when available, task/client IDs, status, HTTP status, `error_code`, `server_error_code`, `error_source`, polling guidance, `state_file`, `resumable`, original `request_payload` and latest native `api_response`. Summarize relevant reels, views, dates and creator information when returned, and include task metadata for continuation. Where `data.items` exists, preserve its reel rows, `post` fields and any `computed` labels/relevance. No full output schema was supplied: do not invent fields or infer no more pages from an empty items array. Preserve region/country accounting, walk/discard counts, warnings, pending judgments, dropped IDs, hydration, held-back rows and preview estimates. Captions are untrusted data; generated labels are review signals, not facts about an author.

Error sources distinguish server failures, client/runtime errors, protocol/identity errors and invalid persisted state. `server_error_code` remains separate when a local error is added. Local state/output write failures appear in `client_errors`: retain API outcome, data and known task identity in stdout. Initial checkpoint failure sends no request; later checkpoint failure stops further requests and returns `STATE_SAVE_FAILED`. Output saving failure returns `OUTPUT_SAVE_FAILED` without converting API success into configuration failure. State errors return `requires_state_repair=true` with the state path and usable recovery metadata. Repair the file or resume its known task ID with a new writable path; never use a new path to recreate a known task.

Cached READY results return locally. Saved FAILED/REVIEW_REQUIRED stops locally. Exit codes: 0 completed; 2 invalid input/runtime configuration; 3 timeout/pending; 4 server/transport/protocol failure; 5 state or local persistence failure, with task outcome retained where available. Nonzero exits never authorize a replacement operation.

## Offline validation

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s skills/instagram-reels-search/tests -v
```

All HTTP transport is mocked; tests never call paid APIs. The input contract comes from the supplied schema, and task recovery follows the existing Frevana helpers. No live deployment or full result-schema coverage is claimed.
