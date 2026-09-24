# Douyin keyword search API

The Frevana server controller and DTO define this contract.

- Create: `POST /service/douyin/search/tasks` (HTTP 202)
- Status: `GET /service/douyin/tasks/{task_id}` (HTTP 200)
- Result: `GET /service/douyin/tasks/{task_id}/result` (HTTP 200, JSON array)
- Authentication: `Authorization: Bearer <FREVANA_TOKEN>`

Create requires `keywords`: 1–50 nonempty strings of at most 128 characters each. Other fields are optional:

| Field | Values | Default |
| --- | --- | --- |
| `client_task_id` | Nonempty string, at most 128 characters | Server-generated if absent |
| `max_results_per_query` | Integer 1–1999 | 10 in both the skill and server |
| `sort` | `general`, `most_liked`, `latest` | `general` |
| `publish_time` | `unlimited`, `one_day`, `one_week`, `half_year` | `unlimited` |
| `duration` | `unlimited`, `under_1m`, `one_to_five`, `over_5m` | `unlimited` |

The server trims and deduplicates keywords and requires `unique keywords × max_results_per_query <= 1999`. A value of 0 is rejected. Unknown fields are rejected. The authenticated user's `client_task_id` is idempotent only when the complete normalized request matches.

The task response has `task_id`, `client_task_id`, `operation=SEARCH`, `status`, `media_archive_status`, `billing_status`, `is_reused`, `is_cached`, nullable `result_count`, nullable `billing_credits`, `created_at`, nullable `ready_at`, and optional `error_message`.

Statuses are `PENDING`, `RUNNING`, `READY`, `FAILED`, `TIMED_OUT`, `ABORTED`, `RESULT_EXPIRED`, and `TRIGGER_UNKNOWN`. Billing statuses are `PENDING`, `PROCESSING`, `RETRY`, `BILLED`, and `NOT_CHARGED`. Read the result only at `READY + BILLED`; otherwise the server returns HTTP 409. Terminal failure statuses must not be retriggered automatically.

The result endpoint streams a JSON array from Frevana's persisted result. The server replaces recognized temporary media URLs with archived Frevana S3 URLs. Preserve all result bytes and item fields as returned.
