# Frevana AgentWeb contract

Verified against the local Server controller, DTO, execution policy, billing service and `docs/api/agentweb.md` on 2026-11-03. This documents the implementation; deployment availability has not been verified. This skill wraps only discover, execute and request status.

Also checked the official [discover operation](https://www.agentweb.us/api-reference#tag/Runtime/operation/discoverDomain), [execute operation](https://www.agentweb.us/api-reference#tag/Runtime/operation/executeAction), [OpenAPI](https://www.agentweb.us/openapi.json) and [full agent reference](https://www.agentweb.us/llms-full.txt) on 2026-11-03.

Provider/Frevana differences: provider discovery accepts GET or POST and can include learned context plus `curated` executable actions. Its action-map schema permits `auth_model`; `requires_login`/`connect_providers` are explicit in site-directory/map-detail schemas, not guaranteed discover properties. Provider execute supports an `AUTH_REQUIRED` handoff in `error.auth`; its schema describes an object containing the connection provider and URL without declaring a concrete `connect_url` property. This helper recognizes that concrete field when returned, as in the user's example. Provider APIs require their own key; this skill continues to call Frevana using only `FREVANA_TOKEN`. Provider retries reuse a billing identity, while Frevana also reuses saved terminal results.

## Inputs

| Method and path | Body / path inputs |
| --- | --- |
| `POST /service/agentweb/discover` | Required `domain`: non-whitespace string, 1–2048 UTF-16 code units; may include a regional map path. |
| `POST /service/agentweb/execute` | Same `domain`; required `action`: non-whitespace string, 1–160 UTF-16 code units; optional `params`: flat object of string, finite number, boolean; optional `idempotency_key`. |
| `GET /service/agentweb/requests/:request_id` | Frevana request UUID belonging to the current user. Not a provider task ID. |

`Idempotency-Key` is 1–128 ASCII letters/digits/periods/underscores/hyphens. Header takes precedence over body `idempotency_key`. The helper always sends the resolved key as a header and omits the redundant body key. It rejects unknown fields instead of relying on Server DTO whitelisting. It does not normalize domain/action/parameter values or add defaults to `params`.

Discovery response is `{ "data": { "domain": "...", ...native mapping fields } }`. Mapping details remain dynamic; discover the site's actual actions/required parameters. New execution checks permissions against an exact anonymous public map before creating the paid call. Discovery alone does not guarantee an action is executable.

## Execute/status envelope

```json
{
  "request_id": "01234567-89ab-cdef-0123-456789abcdef",
  "status": "BILLED",
  "execution_http_status": 200,
  "data": {
    "domain": "asos.com",
    "action": "search_products",
    "data": {"kind": "json", "value": {}},
    "outcome": "partial",
    "map_version": "0.1.2"
  },
  "billing": {"status": "BILLED", "credits": 0.6}
}
```

The shape within `data` is native/dynamic; do not manufacture an `outcome` when absent. The server removes provider envelope bills/balance and masks raw header values without deleting business fields recursively. Errors may also contain `error`, `trace_id` and `support_id`. Failures before call creation may have no `request_id`. HTTP errors can contain an ID without a top-level status; retain it and query GET.

| State | Interpretation |
| --- | --- |
| STARTED | Original submission owns execution; still waiting for provider. |
| READY | Result/cost saved, awaiting settlement; business data withheld. |
| DEBITING | A worker owns debit; business data withheld. |
| BILLED | Cost settled (possibly zero); inspect execution status and error separately. |
| REJECTED | Action failed with verified zero usage; no charge. |
| REVIEW | Uncertain result/receipt/debit or interrupted settlement; stop automatic replay/debit. |

GET only reads the saved record, including errors with HTTP 200. It never reruns a website action, retries debit or looks up the provider. READY can settle later using the original price snapshot after sufficient balance is available. STARTED is not force-ended by a local timeout. No endpoint for cancellation, separate result fetch, task listing, provider usage or target-account authorization is included.

Execute price derives from verified `credits_charged` receipts, with Server-configured conversion to Frevana credits rounded upward to 0.1. Receipt errors enter REVIEW. Do not configure provider keys, prices or billing policy in the client. Successful execution and successful settlement are distinct; a failed action can be BILLED.

## User authorization handoff

Discovery may declare `requires_login` and `connect_providers`. These fields identify a login requirement; they do not provide a connection URL or prove the user is already connected. Prompt the user about required authorization instead of executing a known blocked action.

The provider-style handoff shown by the user is a 403 with `error.code="AUTH_REQUIRED"` and `error.auth.connect_url`. If Frevana returns this shape, or preserves `auth.connect_url` alongside `TARGET_AUTH_UNSUPPORTED`, display the exact HTTPS link and wait for the user's browser authorization and confirmation. Discovery's `data.auth.connect_url`, if explicitly returned, is also recognized; it is not guaranteed by OpenAPI. Never derive links from provider names, send Frevana Bearer credentials to them, or automatically retry POST.

The official full agent reference also describes a target-site flow using `agentweb_start_connection`, user-visible URL delivery, and connection-status polling. Those MCP tools are not exposed by the three Frevana routes and must not be invented as REST endpoints in this skill. A working connection and permission to perform a particular action remain separate.

This is conditional client handling, not a claim that current Server provides the handoff. Its public-action policy rejects login-required maps before a paid call is created; its response mapping replaces `AUTH_REQUIRED` and drops `auth`. Thus current responses normally have no connect URL. Tell the user that the backend must provide an authorization entry point; do not route users to connect accounts to the shared provider key. A working flow requires user-specific backend connection handling and an explicit retry/resume contract. Existing saved terminal failures remain terminal under their original idempotency key.

## Errors / recovery

| HTTP | Meaning / handling |
| --- | --- |
| 400 / 401 | Invalid body/key or failed Frevana authentication. Correct the cause deliberately. |
| 402 | Insufficient Frevana balance; if READY/ID exists, keep it and query the original after funding. |
| 403 | `AUTH_REQUIRED` / `TARGET_AUTH_UNSUPPORTED`: prompt for user authorization and show a returned `auth.connect_url` if available. `ACTION_NOT_PUBLIC` may also reject writes; do not assume authorization fixes every 403. |
| 404 | Missing map/action or missing/other user's request. Do not switch accounts/maps automatically. |
| 409 | Same key in progress or used for different arguments; preserve original body/key/ID. |
| 422 | Parameter resolution/business error; preserve candidates and billing, may cost credits. |
| 429 | Rate limit; no automatic resubmission. |
| 502 / 504 | Invalid/unavailable provider response or timeout; retain ID, query original. |
| 503 | Provider configuration/balance, public permissions, persistence or settlement unavailable. Retain ID if supplied. |

When no ID was received, explicit `recover` replays the exact persisted body/key against the same Frevana origin/account once. It relies on Frevana's local idempotency record, not on a stronger website exactly-once contract. Do not mutate parameters after a resolution error under the old key; a user-requested corrected operation needs a new state/key after the original cost/outcome is understood.
