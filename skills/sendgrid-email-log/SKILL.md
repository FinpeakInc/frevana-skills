---
name: sendgrid-email-log
description: Use when the user wants to query Twilio SendGrid Email Logs or retrieve per-message activity for a specific sg_message_id, including whether an email was opened, clicked, delivered, bounced, deferred, dropped, spam-reported, or unsubscribed. Supports GET /v3/logs/{sg_message_id} by ID and POST /v3/logs search by recipient, optional subject, sent-at lower bound, status, raw query, and fuzzy message ID matching. Supports global or EU SendGrid API base URLs, optional on-behalf-of parent-account header for by-ID lookups, raw JSON output, event summary enrichment, dry-run URL or payload preview, and saved SendGrid API key reuse. Do not use for sending email or aggregate SendGrid statistics.
---

# SendGrid Email Log

Retrieve activity for a specific SendGrid message with the Email Logs API.

## Purpose

This skill is for **reading SendGrid Email Logs and per-message activity**.

It has two lookup paths:

- `scripts/get_email_log.sh` calls `GET /v3/logs/{sg_message_id}` for one specific message and computes an `event_summary`. If the full `sg_message_id` is not known, it can first call `POST /v3/logs` with recipient and sent time to resolve the full ID, then automatically call the detail endpoint.
- `scripts/query_email_logs.sh` calls `POST /v3/logs` to search Email Logs by recipient, status, time, optional subject, raw query, and fuzzy message ID matching.

Inputs:

- full `sg_message_id` from SendGrid Email Logs for the direct by-ID path, or any useful Email Logs search filters such as recipient, sender, sent time, subject, status, start/end time, raw query, and optional Mail Send `message_id` for the search-then-detail path
- SendGrid API key from `--api-key`, `SENDGRID_API_KEY`, or the locally saved SendGrid key

Output:

- raw SendGrid JSON by default
- optional `event_summary` added by the script, including booleans such as `opened`, `clicked`, `delivered`, `bounced`, `deferred`, `dropped`, `spam_reported`, and `unsubscribed`
- `log_resolution` when `get_email_log.sh` resolves the full `sg_message_id` before fetching details
- `matched_messages`, `matched_count`, and `_match_reason` when using `query_email_logs.sh` directly with `--message-id`
- optional saved JSON file when `--output` is provided
- dry-run request metadata when `--dry-run` is used

This is a read-only lookup. It does not send email and does not retrieve account-level aggregate stats.

## What This Skill Needs

- full `sg_message_id`, or recipient and sent-time search criteria for Email Logs
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
bash <skill-path>/scripts/get_email_log.sh --api-key "SG..." --save-api-key
```

or clear it with:

```bash
bash <skill-path>/scripts/get_email_log.sh --clear-api-key
```

## Execution Order

1. Extract full `sg_message_id` for direct by-ID lookups. If the user only has the Mail Send `x-message-id`, has an incomplete ID, or does not know the ID, collect as many search filters as available (`to`, `from`, `sent_at`, `subject`, `status`, `start_time`, `end_time`, or raw `query`) and let `get_email_log.sh` resolve the full `sg_message_id` first.
2. Prefer `scripts/get_email_log.sh` or `scripts/query_email_logs.sh` over ad hoc `curl`.
3. Use `--dry-run` when the user wants to inspect the URL before calling SendGrid.
4. Let the script use `--api-key`, `SENDGRID_API_KEY`, or the locally saved key.
5. In non-interactive agent runs, fail fast if the API key is missing from all supported sources.
6. Return raw JSON when requested; otherwise summarize the `event_summary`, matched messages, or recent activity events.

## Commands

### Check one message

```bash
bash <skill-path>/scripts/get_email_log.sh \
  --sg-message-id "abc123.recvd-xxxxxxxx"
```

### Check whether it opened or clicked

```bash
bash <skill-path>/scripts/get_email_log.sh \
  --sg-message-id "abc123.recvd-xxxxxxxx" \
  --summary-only
```

### Search Email Logs by recipient, sent time, and fuzzy message ID

Use this when the user has the `x-message-id` returned by Mail Send but needs to locate the Email Logs `sg_message_id` first. `get_email_log.sh` narrows Email Logs with `to_email` and `sg_message_id_created_at >= (--sent-at - 5 seconds)` by default, optionally adds an exact `subject` filter, fuzzy-matches returned `messages[].sg_message_id` against the Mail Send response `x-message-id`, then fetches the detail record with `GET /v3/logs/{sg_message_id}`.

If the user does not know any message ID, omit `--message-id`; the script uses the first returned Email Logs message after applying the provided filters, so pass more filters to avoid ambiguity.

For dynamic template sends, omit `--subject` because the template can define or override the final email subject.

```bash
bash <skill-path>/scripts/get_email_log.sh \
  --to "customer@example.com" \
  --sent-at "2026-06-15T10:37:21Z" \
  --message-id "abc123..." \
  --limit 100
```

### Search Email Logs without a message ID, then fetch details

```bash
bash <skill-path>/scripts/get_email_log.sh \
  --to "customer@example.com" \
  --from "sender@example.com" \
  --start-time "2026-06-15T10:00:00Z" \
  --end-time "2026-06-15T11:00:00Z" \
  --subject "Order update" \
  --status delivered \
  --limit 20
```

### Search Email Logs with a raw query

Use this lower-level script when the user only wants search results from `POST /v3/logs` and does not need the detail endpoint.

```bash
bash <skill-path>/scripts/query_email_logs.sh \
  --query "to_email = 'customer@example.com' AND status IN ('delivered', 'processed')" \
  --limit 10
```

### Parent account querying a subuser or customer account

```bash
bash <skill-path>/scripts/get_email_log.sh \
  --sg-message-id "abc123.recvd-xxxxxxxx" \
  --on-behalf-of "subuser-username"
```

For customer accounts, pass the full header value, such as:

```bash
--on-behalf-of "account-id 123456"
```

### Dry-run request metadata

```bash
bash <skill-path>/scripts/get_email_log.sh \
  --sg-message-id "abc123.recvd-xxxxxxxx" \
  --dry-run
```

## Fixed Request Shape

For by-ID activity lookup, the script sends a `GET` request to:

- global region: `https://api.sendgrid.com/v3/logs/{sg_message_id}`
- EU region: `https://api.eu.sendgrid.com/v3/logs/{sg_message_id}`

Supported headers:

- `Authorization: Bearer <SENDGRID_API_KEY>`
- optional `on-behalf-of: <subuser-username>` or `on-behalf-of: account-id <account-id>`

Do not invent query parameters. This endpoint reads one message by ID through the URL path.

For search lookup, the script sends a `POST` request to:

- global region: `https://api.sendgrid.com/v3/logs`
- EU region: `https://api.eu.sendgrid.com/v3/logs`

Supported body fields:

- `query`
- `limit`
- optional `subusers`

Do not use `custom_args.business_id` for Email Logs queries. Use recipient, optional subject, `--sent-at`, and message ID fuzzy matching, or pass a raw account-supported `--query`.

## Script Options

- `--sg-message-id ID`; full SendGrid Email Logs ID for direct activity retrieval
- `--to EMAIL`; recipient email used to resolve the full `sg_message_id`
- `--from EMAIL`; sender email used to resolve the full `sg_message_id`
- `--sent-at ISO_TIME`; sent/queued time used as the lower bound for resolving the full `sg_message_id`
- `--message-id ID`; optional Mail Send `x-message-id` used for fuzzy matching during resolution
- `--subject SUBJECT`; optional exact subject filter during resolution
- `--status STATUS`; optional status filter, repeatable or comma-separated
- `--start-time ISO_TIME`; optional lower bound for resolution search
- `--end-time ISO_TIME`; optional upper bound for resolution search
- `--query QUERY`; raw SendGrid Email Logs query string for resolution search, overriding generated filters
- `--sent-at-lookback-seconds N`; default `5`, allowed `0-300`
- `--limit N`; search-result limit during resolution, default `100`, allowed `1-1000`
- `--on-behalf-of VALUE`; optional SendGrid parent-account header value
- `--subuser ID`; optional numeric SendGrid subuser ID for `POST /v3/logs` search, repeatable or comma-separated
- `--region global|eu`; default `global`
- `--api-key KEY` for a one-time override
- `--save-api-key` to save the `--api-key` value for future runs
- `--configure-api-key` to prompt for and save the key
- `--clear-api-key` to remove the locally saved key
- `--output PATH` to save JSON
- `--summary-only` to print only the computed event summary
- `--dry-run` to print request metadata without calling SendGrid

`scripts/query_email_logs.sh` supports:

- `--query QUERY`; raw SendGrid Email Logs query string
- `--status STATUS`; repeatable or comma-separated
- `--to EMAIL`
- `--sent-at ISO_TIME`
- `--sent-at-lookback-seconds N`; default `5`, allowed `0-300`
- `--message-id ID`; fuzzy-matches returned `sg_message_id`
- `--subject SUBJECT`
- `--start-time ISO_TIME`
- `--end-time ISO_TIME`
- `--limit N`; default `10`, allowed `1-1000`
- `--subuser ID`
- shared `--region`, `--api-key`, `--save-api-key`, `--configure-api-key`, `--clear-api-key`, `--output`, and `--dry-run`

## Notes

- Never echo or store the API key in user-visible output.
- The script can save the API key locally at `~/.config/sendgrid-send-email/api_key` with file permission `600`; do not print the key value back to the user.
- Use `--api-key <key> --save-api-key` or `--configure-api-key` when the user wants to update the saved key. Use `--clear-api-key` when the user wants to remove it.
- If the user only has a Mail Send `x-message-id`, the send result may be incomplete for `GET /v3/logs/{sg_message_id}`. Prefer `scripts/get_email_log.sh --to ... --sent-at ... --message-id ...` so the script first resolves the full Email Logs `sg_message_id` with `POST /v3/logs`, then fetches details.
- If the user does not know any message ID, use `scripts/get_email_log.sh` with multiple filters such as `--to`, `--from`, `--start-time`, `--end-time`, `--subject`, and `--status`; the script picks the first matching Email Logs message, so use narrow filters.
- If `query_email_logs.sh` returns no data or no fuzzy `sg_message_id` match, direct the user to <https://app.sendgrid.com/email_logs> for manual review.
- If `--api-key`, `SENDGRID_API_KEY`, and the locally saved key are all missing, tell the user to read <https://frevana.gitbook.io/frevana-docs/email-integrations/sendgrid-integration> to get the required configuration.
- If a user shares an API key in chat, advise them to rotate it.

## Example Prompts

### Chinese

- "查一下这封 SendGrid 邮件有没有打开或点击，sg_message_id 是 ..."
- "获取这个 SendGrid message id 的事件 timeline"
- "看下这封邮件是否 delivered / opened / clicked"

### English

- "Check whether this SendGrid email was opened or clicked"
- "Retrieve SendGrid Email Logs activity for this sg_message_id"
- "Get the event timeline for this SendGrid message"
