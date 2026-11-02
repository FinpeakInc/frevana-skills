---
name: instagram-profile-details
description: Fetch Instagram profile data by username through Frevana, with persisted idempotency, inline results, and resumable background tasks.
---

# Instagram Profile Details

Use the bundled helper for Frevana's `instagram/profile` endpoint. The separate `instagram-profile` skill uses a different API and requires `profile_id` instead of `handle`.

Requires Bash and Python 3.9+ (macOS/Linux), and `FREVANA_TOKEN` supplied through the runtime environment. Requests use `Authorization: Bearer <FREVANA_TOKEN>`; do not embed credentials in files, command arguments, logs, or returned metadata. Only Frevana authentication is needed; no extension or daemon is required.

## Inputs

Ask for the required `handle` if missing. Input accepts **only** these schema properties, with unspecified options omitted:

| Input / CLI | Type and behavior |
| --- | --- |
| `handle` / `--handle` | Required string: Instagram username without `@`, e.g. `instagram`. |
| `trim` / `--trim true\|false` | Boolean. True skips recent posts; faster at the same price, with `author.last_post_at` and `computed.engagement_rate` null. |
| `async` / `--async true\|false\|1\|0` | Background job option. JSON input also accepts the exact schema values: booleans, integers 0/1, strings `"true"`, `"false"`, `"1"`, `"0"`. CLI values become booleans for true/false and integers for 1/0. |
| `contact_email` / `--contact-email 1` | Optional literal string `"1"`. Adds `author.ext.contact_email` when a personal contact can confidently be selected verbatim from multiple bio emails; otherwise null. `public_email` is unchanged; no extra credits. |

Alternatively pass an input object with `--input-file PATH`. It cannot be mixed with input flags. Unknown properties and wrong types are rejected before network access. Do not send `include`, `limit`, `cursor`, `since`, `until`, or aliases for undeclared fields. This schema offers no channel enrichment or pagination controls; requests for those need a separately verified endpoint/schema. Never enable enrichment or fetch extra pages automatically.

## Invoke and resume

Choose a durable `--state-file` path per logical operation and keep using it for every retry. The helper generates one `client_task_id` and atomically persists the complete original POST payload **before** sending it. Existing state is reused; changed input, client ID, or API origin is rejected. An existing file containing null, invalid JSON, an unsupported version or missing operation identity fields is rejected without overwriting it, generating an ID or submitting a task. Use a new state path only for an intentionally new operation. State includes profile data when complete; store it appropriately. Concurrent invocations using one state file are rejected with a nonblocking lock.

```bash
# FREVANA_TOKEN must already be configured in the runtime environment.
bash <skill-path>/scripts/instagram_profile.sh run \
  --handle instagram --trim true \
  --state-file ./out/instagram-operation.json

# Resume after interruption/timeout.
bash <skill-path>/scripts/instagram_profile.sh resume \
  --state-file ./out/instagram-operation.json

# Resume an already-known task even when no local state exists; never POSTs.
bash <skill-path>/scripts/instagram_profile.sh resume \
  --task-id TASK_ID --state-file ./out/recovered-operation.json
```

`run --task-id TASK_ID` also resumes instead of submitting. `resume` without a known task ID may replay the persisted original POST to recover an ambiguous submission; it never generates a replacement client ID. A state containing a completed result returns the cached result. FAILED and REVIEW_REQUIRED stop immediately; inspect their task metadata instead of automatically replacing the operation. A saved HTTP 409 stops automatic replays; resume with its known task ID to query status, or investigate a client-ID conflict if no task ID was returned.

Task IDs in arguments, state and responses must be UUID v4, matching the backend contract. Successful create, status and result responses must contain a valid task ID, including inline READY results. Invalid, missing or mismatched response IDs return a protocol error with the original operation identity; they never overwrite the original task ID or trigger a replacement task.

Successful create/status responses also require a matching client ID; result responses may omit it. A protocol error without a verified task ID blocks automatic POST replay until investigated. With a verified task ID, recovery uses GET only. Invalid persisted state returns state_error, requires_state_repair=true, the state-file path and any usable task identity/original payload without changing the file. Version-1 state files from the original helper remain supported, including those without a top-level endpoint_id.

The API base defaults to `https://api.frevana.com`. `FREVANA_API_BASE_URL` or `--api-base-url` can select an HTTP localhost mock or HTTPS origin. Redirects are rejected. Runtime options: `--timeout` (total budget, default 120 seconds), `--request-timeout` (per request, default 30 seconds), `--retries` (additional transient retries, default 2), and `--output` (also save stdout JSON). The fixed wrapper `response_mode` is `"json"`; this is a wire format, independent of input `async`. The helper does not consume SSE.

## Task behavior and output

- POST to Frevana's task-creation API with exactly `endpoint_id`, `client_task_id`, `input`, `response_mode`, using the fixed route in the bundled helper. HTTP 200 + READY + inline `data` completes immediately, including null or empty data, without a status/result request.
- HTTP 202 persists the task ID and polls status according to `next_poll_after_ms`. Status responses provide progress only, even when they contain data. READY triggers GET result; a 202 READY response also uses the result route. Only a READY result can complete the operation. Suggested poll timing survives restarts; zero/missing delay or unknown status returns control without a busy loop.
- Transient network failures and HTTP 429/500/502/503/504 have bounded retries using identical POST bytes and client ID. A request timeout returns control immediately because submission may still be in flight. A later invocation uses the persisted payload or known task ID.
- FAILED or REVIEW_REQUIRED, including HTTP 409 bodies, stop with task ID and `error_code`. Other HTTP 409 responses are parsed and returned without retries or replacement tasks. Server errors can use `error_code`, nested `error.code`, or the server's `message` string.
- Total/request timeouts return `outcome="timeout"` plus resumable metadata. Timeouts do not cancel backend work. Keep the state file; rerun `resume`.

Stdout is a JSON object with `outcome`, `endpoint_id`, unmodified structured `data`/`pagination` when available, `task_id`, `client_task_id`, `status`, `error_code`, `server_error_code`, `error_source`, `http_status`, `next_poll_after_ms`, `state_file`, `resumable`, `request_payload`, and the latest native `api_response`. error_source distinguishes server, client, protocol and state failures; server_error_code retains the latest server code when a local error is added. Tokens are excluded from state/output and redacted if echoed by a server. No output schema was supplied: preserve returned fields and do not promise profile field availability beyond the input descriptions above. Summarize data for a human by default and always include task metadata needed for continuation.

Local file errors are reported separately in `client_errors`: `OUTPUT_SAVE_FAILED` retains the task outcome, data and recovery metadata in stdout; it does not turn API success into a configuration error or replace a server error code. If the initial state save fails, no API request is sent. If a later checkpoint fails, stop further requests and return `STATE_SAVE_FAILED` with all known task metadata. The state file may then be stale: retain stdout and resume the returned task ID using a writable state file, or replay the saved original payload/client ID if no task ID is known.

Exit codes: 0 completed, 2 invalid input/runtime configuration, 3 timeout/pending, 4 task/HTTP/transport/protocol failure, 5 invalid state or local state/output persistence failure. Initial save failure sends no request; later file failures retain the task outcome and recovery metadata in stdout. The JSON outcome and error code distinguish these cases; a nonzero exit does not authorize a new task.

## Offline validation

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s skills/instagram-profile-details/tests -v
```

Tests mock transport and never access the network or contact a paid API. Wire-response details were checked against the local Frevana Server task controller, DTO, task service and result store on 2026-11-02; this does not verify deployment status.
