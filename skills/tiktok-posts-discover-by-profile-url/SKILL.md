---
name: tiktok-posts-discover-by-profile-url
description: Discover public TikTok posts or videos published by one or more creator, account, homepage, or profile URLs through Frevana, and continue status or result retrieval for tasks created by this operation. Use for profile-based post discovery; do not use for keyword discovery, exact post collection, profile-detail collection, or TikTok Ads management.
---

# TikTok Posts Discover by Profile URL

Use this skill to discover public posts from one or more TikTok profile URLs. The bundled script owns the complete create, poll, and raw-result flow.

## Required input

Every input object requires TikTok profile `url`. Supply one to twenty objects through repeatable `--input-json` or one `--input-file` containing a JSON array.

Read [references/api.md](references/api.md) for all accepted fields and task states.

## Workflow

1. Confirm the exact user input; do not guess keywords or TikTok URLs.
2. Prefer `run` for creation through final raw result. Use `create`, `status`, `wait`, or `result` only when the caller needs separate phases.
3. Treat creation as billable. The script generates and reports a `client_task_id` when omitted. After a creation timeout or transport failure, retry only with that same ID; never submit a new task automatically.
4. Poll at the fixed ten-second interval. Stop without resubmitting on `FAILED`, `EXPIRED`, or `TRIGGER_UNKNOWN`.
5. Return result bytes unchanged. Do not wrap, reshape, merge, deduplicate, or associate records with inputs by result order or count.

## Commands

Resolve `{baseDir}` to the directory containing this `SKILL.md`.

```bash
# Complete flow
bash {baseDir}/scripts/tiktok_task.sh run \
  --input-json '{"url":"https://www.tiktok.com/@babyariel","num_of_posts":100,"post_type":"Video Posts","country":"US"}'

# Complete flow with a JSON array file and chosen output
bash {baseDir}/scripts/tiktok_task.sh run \
  --input-file ./inputs.json \
  --output ./out/tiktok-result.json

# Separate phases
bash {baseDir}/scripts/tiktok_task.sh create \
  --client-task-id caller-stable-id \
  --input-json '{"url":"https://www.tiktok.com/@babyariel","num_of_posts":100,"post_type":"Video Posts","country":"US"}'
bash {baseDir}/scripts/tiktok_task.sh status --task-id TASK_UUID
bash {baseDir}/scripts/tiktok_task.sh wait --task-id TASK_UUID
bash {baseDir}/scripts/tiktok_task.sh result --task-id TASK_UUID
```

`create --wait` is equivalent to `run`. Run the script with `--help` for all flags.

## Authentication and output

Use `FREVANA_TOKEN` or a one-time `--token` override. Never print the token. The default base URL is `https://ai-factory.frevana.com`; `FREVANA_API_BASE_URL` and `--api-base-url` support another Frevana deployment or local tests.

`create`, `status`, and `result` print the unchanged API JSON. `run`, `create --wait`, and `wait` save the raw final array under `./out/` by default and print the same bytes to stdout. Use `--output` to choose the file.

## Guardrails

- This skill fixes creation to `POST /service/tiktok/posts/discover-by-profile-url`; do not route another TikTok operation through it.
- Do not combine `--input-file` with `--input-json`.
- `limit_per_input` is an optional request-level integer from 1 through 2147483647.
- The complete request must stay within 1 MB.
- The result is available only when `status=READY` and `billing_status=BILLED`; before that the result endpoint returns a task object.
