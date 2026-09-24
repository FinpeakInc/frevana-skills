# Douyin hot search API

The Frevana server controller and DTO define this contract.

- Create: `POST /service/douyin/hot-search/tasks` (HTTP 202)
- Status: `GET /service/douyin/tasks/{task_id}` (HTTP 200)
- Result: `GET /service/douyin/tasks/{task_id}/result` (HTTP 200, JSON array)
- Authentication: `Authorization: Bearer <FREVANA_TOKEN>`

Create accepts an optional `client_task_id` (nonempty, at most 128 characters), optional `boards` (1–5 entries from `hotspot`, `seeding`, `entertainment`, `social`, `challenge`), and optional integer `max_results_per_board` (1–60). Omitted `boards` defaults to `["hotspot"]`; omitted maximum defaults to 50. Unknown fields are rejected. The authenticated user's `client_task_id` is idempotent only when the complete normalized request matches.

The task response has `task_id`, `client_task_id`, `operation=HOT_SEARCH`, `status`, `media_archive_status`, `billing_status`, `is_reused`, `is_cached`, nullable `result_count`, nullable `billing_credits`, `created_at`, nullable `ready_at`, and optional `error_message`.

Statuses are `PENDING`, `RUNNING`, `READY`, `FAILED`, `TIMED_OUT`, `ABORTED`, `RESULT_EXPIRED`, and `TRIGGER_UNKNOWN`. Billing statuses are `PENDING`, `PROCESSING`, `RETRY`, `BILLED`, and `NOT_CHARGED`. Read the result only at `READY + BILLED`; otherwise the server returns HTTP 409. Terminal failure statuses must not be retriggered automatically.

The result endpoint streams a JSON array of vendor-native items from Frevana's persisted result. The server may reuse a fresh hot-search snapshot for the same parameters. Preserve all result bytes and item fields as returned.
