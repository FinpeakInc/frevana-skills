---
name: sendgrid-global-email-stats
description: Use when the user wants to retrieve Twilio SendGrid global email statistics with GET /v3/stats. Supports start/end date ranges, day/week/month aggregation, limit/offset pagination, parent-account on-behalf-of lookups for subusers or customer accounts, global or EU SendGrid API base URLs, dry-run URL preview, and saved SendGrid API key reuse. Do not use for sending email or Email Logs status lookup.
---

# SendGrid Global Email Stats

Retrieve global email statistics from SendGrid's Stats API.

## Purpose

This skill is for **reading aggregate SendGrid email activity metrics** by calling `GET /v3/stats`.

Inputs:

- `start_date` in `YYYY-MM-DD` format
- optional `end_date` in `YYYY-MM-DD` format
- optional aggregation level: `day`, `week`, or `month`
- optional `limit` and `offset`
- SendGrid API key from `--api-key`, `SENDGRID_API_KEY`, or the locally saved SendGrid key

Output:

- raw SendGrid JSON statistics by default
- optional saved JSON file when `--output` is provided
- dry-run request metadata when `--dry-run` is used

This is a read-only statistics lookup. It does not send email and does not query per-message Email Logs.

## What This Skill Needs

- `start_date`
- a SendGrid API key, usually `SENDGRID_API_KEY`
- `curl`
- `bash`
- `python3`

API key resolution order:

1. `--api-key` for the current run
2. `SENDGRID_API_KEY`
3. locally saved key at `~/.config/sendgrid-send-email/api_key`

The saved key path intentionally matches `sendgrid-send-email` so users who configured the SendGrid send skill can reuse the same key. If no API key is available and the script is running interactively, prompt once and save it locally for future runs. If no API key is available in a non-interactive run, guide the user to read the SendGrid integration guide: <https://frevana.gitbook.io/frevana-docs/email-integrations/sendgrid-integration>.

Users can update the saved API key with:

```bash
bash <skill-path>/scripts/retrieve_global_email_stats.sh --api-key "SG..." --save-api-key
```

or clear it with:

```bash
bash <skill-path>/scripts/retrieve_global_email_stats.sh --clear-api-key
```

## Execution Order

1. Extract `start_date`, optional `end_date`, optional `aggregated_by`, optional pagination, optional `on_behalf_of`, and optional region.
2. Prefer `scripts/retrieve_global_email_stats.sh` over ad hoc `curl`.
3. Use `--dry-run` when the user wants to inspect the URL before calling SendGrid.
4. Let the script use `--api-key`, `SENDGRID_API_KEY`, or the locally saved key.
5. In non-interactive agent runs, fail fast if the API key is missing from all supported sources.
6. Return either the raw JSON payload or summarize metrics such as `requests`, `processed`, `delivered`, `bounces`, `opens`, `unique_opens`, `clicks`, `unique_clicks`, `spam_reports`, and `unsubscribes`, depending on what the user asked for.

## Commands

### Retrieve daily stats

```bash
bash <skill-path>/scripts/retrieve_global_email_stats.sh \
  --start-date "2026-06-01" \
  --end-date "2026-06-30" \
  --aggregated-by day
```

### Retrieve monthly stats

```bash
bash <skill-path>/scripts/retrieve_global_email_stats.sh \
  --start-date "2026-01-01" \
  --end-date "2026-06-30" \
  --aggregated-by month
```

### Parent account querying a subuser

```bash
bash <skill-path>/scripts/retrieve_global_email_stats.sh \
  --start-date "2026-06-01" \
  --end-date "2026-06-30" \
  --on-behalf-of "subuser-username"
```

For customer accounts, pass the full header value, such as:

```bash
--on-behalf-of "account-id 123456"
```

### Dry-run request metadata

```bash
bash <skill-path>/scripts/retrieve_global_email_stats.sh \
  --start-date "2026-06-01" \
  --aggregated-by week \
  --dry-run
```

## Fixed Request Shape

The script sends a `GET` request to:

- global region: `https://api.sendgrid.com/v3/stats`
- EU region: `https://api.eu.sendgrid.com/v3/stats`

Supported query parameters:

- `start_date`; required, `YYYY-MM-DD`
- `end_date`; optional, `YYYY-MM-DD`, defaults to today in SendGrid when omitted
- `aggregated_by`; optional, one of `day`, `week`, `month`
- `limit`; optional integer
- `offset`; optional integer

Supported headers:

- `Authorization: Bearer <SENDGRID_API_KEY>`
- optional `on-behalf-of: <subuser-username>` or `on-behalf-of: account-id <account-id>`

Do not invent or pass unsupported query parameters.

## Script Options

- `--start-date YYYY-MM-DD`; required for stats retrieval
- `--end-date YYYY-MM-DD`; optional
- `--aggregated-by day|week|month`; optional
- `--limit N`; optional positive integer
- `--offset N`; optional non-negative integer
- `--on-behalf-of VALUE`; optional SendGrid parent-account header value
- `--region global|eu`; default `global`
- `--api-key KEY` for a one-time override
- `--save-api-key` to save the `--api-key` value for future runs
- `--configure-api-key` to prompt for and save the key
- `--clear-api-key` to remove the locally saved key
- `--output PATH` to save JSON
- `--dry-run` to print request metadata without calling SendGrid

## Notes

- Never echo or store the API key in user-visible output.
- The script can save the API key locally at `~/.config/sendgrid-send-email/api_key` with file permission `600`; do not print the key value back to the user.
- Use `--api-key <key> --save-api-key` or `--configure-api-key` when the user wants to update the saved key. Use `--clear-api-key` when the user wants to remove it.
- `start_date` and `end_date` must use `YYYY-MM-DD`.
- `aggregated_by` must be `day`, `week`, or `month`.
- Category statistics have a documented thirteen-month availability window, but this global stats endpoint is for account-level global statistics, not category stats.
- Parent accounts can use `--on-behalf-of` to query a subuser or customer account with the parent account API key.
- If `--api-key`, `SENDGRID_API_KEY`, and the locally saved key are all missing, tell the user to read <https://frevana.gitbook.io/frevana-docs/email-integrations/sendgrid-integration> to get the required configuration.
- If a user shares an API key in chat, advise them to rotate it.

## Example Prompts

### Chinese

- "查一下 SendGrid 这个月每天的全局邮件统计"
- "用 SendGrid Stats API 查询 2026-06 的 delivered 和 bounces"
- "帮我 dry-run 一下 GET /v3/stats 的请求"

### English

- "Retrieve SendGrid global email stats for June 2026"
- "Get daily SendGrid stats from 2026-06-01 to 2026-06-30"
- "Check monthly SendGrid global email statistics for this year"
