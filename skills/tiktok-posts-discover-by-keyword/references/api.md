# TikTok Posts Discover by Keyword API contract

This reference mirrors the current `frevana-server` controller and request DTO.

## Endpoints

- Create: `POST /service/tiktok/posts/discover-by-keyword`
- Status: `GET /service/tiktok/tasks/{task_id}`
- Result: `GET /service/tiktok/tasks/{task_id}/result`
- Authentication: `Authorization: Bearer <FREVANA_TOKEN>`

Creation returns HTTP 202. Status and result return HTTP 200.

## Create request

```json
{
  "client_task_id": "caller-stable-id",
  "limit_per_input": 100,
  "input": [
    {"search_keyword":"#artist","num_of_posts":100,"country":"US"}
  ]
}
```

Envelope fields:

- `client_task_id`: optional non-empty string, maximum 128 characters. It is idempotent per authenticated user only when the complete request is unchanged.
- `limit_per_input`: optional integer from 1 through 2147483647, or null.
- `input`: required array containing 1 through 20 objects.
- Complete request size: maximum 1 MB.

Input fields:

- `search_keyword`: required non-whitespace string, maximum 256 characters.\n- `num_of_posts`: optional integer greater than or equal to zero.\n- `country`: optional ISO 3166-1 alpha-2 code or empty string.

Unknown fields are rejected.

## Task response and lifecycle

```json
{
  "task_id": "7af283fe-13aa-431d-a7cf-b58675701884",
  "client_task_id": "caller-stable-id",
  "operation": "posts.discover_by_keyword",
  "snapshot_id": "s_xxx",
  "status": "RUNNING",
  "billing_status": "PENDING",
  "record_count": null,
  "credits_charged": null,
  "billing_error": null,
  "billed_at": null,
  "input_count": 1,
  "created_at": "2026-09-11T12:00:00.000Z",
  "ready_at": null,
  "error_message": null,
  "is_reused": false
}
```

Task statuses are `PENDING_TRIGGER`, `TRIGGERED`, `RUNNING`, `READY`, `FAILED`, `EXPIRED`, and `TRIGGER_UNKNOWN`. The last three are terminal without a result. Never automatically resubmit after `TRIGGER_UNKNOWN`.

Billing statuses are `PENDING`, `PROCESSING`, `RETRY`, `BILLED`, and `NOT_CHARGED`. Fetch the result only after `READY + BILLED`.

The bundled `run` and `wait` actions call the Frevana status endpoint every ten seconds. They never call Bright Data directly; Frevana refreshes upstream progress when the task is due, and its background scheduler may refresh the same persisted task independently.

Before readiness, the result endpoint returns the task object. Once ready and billed, it streams the native Bright Data JSON array. One input may produce zero, one, or many records; never map results by array position, requested count, or input count.
