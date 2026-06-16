---
name: sendgrid-send-email
description: Use when the user wants to send transactional email through the Twilio SendGrid v3 Mail Send API using a SendGrid API key, or query SendGrid Email Logs for send status by recipient, optional subject, sent-at lower bound, and message ID. Supports single sends, multiple recipients, cc/bcc, reply-to, plain text or HTML content, dynamic templates, attachments, categories, custom args, sandbox validation, scheduled send fields, global or EU SendGrid API base URLs, dry-run payload preview, and POST /v3/logs status lookup. Do not use for the separate Twilio Email API.
---

# SendGrid Send Email

Send email through SendGrid's v3 Mail Send API.

## Purpose

This skill is for **sending transactional email with SendGrid** by calling `POST /v3/mail/send` directly, and for querying send status with `POST /v3/logs`.

Inputs:

- `from` verified sender email. This address should be a verified sender in your Twilio SendGrid account.
- one or more `to` recipients
- `subject`, unless the subject is defined by a dynamic template
- `text`, `html`, or `template_id`
- SendGrid API key from `--api-key`, `SENDGRID_API_KEY`, or the locally saved key
- automatic `custom_args.business_id` for application-side correlation, or user-provided `--business-id`

Output:

- dry-run JSON payload by default
- SendGrid HTTP status, message metadata, and one status-query prompt example when `--send` is explicitly provided
- Email Logs JSON when querying by recipient, optional subject, sent-at lower bound, and message ID

Sending email is irreversible once queued. Always confirm recipients, subject, and content with the user before running with `--send`.

## What This Skill Needs

- user-provided sender. This address should be a verified sender in the user's Twilio SendGrid account.
- user-provided recipients and message content
- a SendGrid API key, usually `SENDGRID_API_KEY`
- `curl`
- `bash`
- `python3`

SendGrid API keys are separate from Twilio Account SID/Auth Token credentials. Do not use this skill for the separate Twilio Email API at `comms.twilio.com`.

API key resolution order:

1. `--api-key` for the current run
2. `SENDGRID_API_KEY`
3. locally saved key at `~/.config/sendgrid-send-email/api_key`

If no API key is available and the script is running interactively, prompt once and save it locally for future runs. If no API key is available in a non-interactive run, guide the user to read the SendGrid integration guide: <https://wenjun.gitbook.io/wenjun-docs/sendgrid-integration>.

Users can update the saved API key with:

```bash
bash <skill-path>/scripts/send_email.sh --api-key "SG..." --save-api-key
```

or clear it with:

```bash
bash <skill-path>/scripts/send_email.sh --clear-api-key
```

## Status Query

Use `scripts/query_email_logs.sh` to query SendGrid Email Logs with `POST /v3/logs`.

### Add status or time filters

```bash
bash <skill-path>/scripts/query_email_logs.sh \
  --to "customer@example.com" \
  --status delivered \
  --start-time "2026-06-15T00:00:00Z" \
  --end-time "2026-06-16T00:00:00Z"
```

### Query by recipient, optional subject, sent time, and fuzzy message ID

Use this as the default status lookup path. The script first narrows Email Logs with `to_email` and `sg_message_id_created_at >= (--sent-at - 5 seconds)` by default, optionally adds an exact `subject` filter when provided, then fuzzy-matches returned `messages[].sg_message_id` against the Mail Send response `x-message-id`. The 5-second lookback absorbs small timing differences where the SendGrid `202` response timestamp is slightly later than the Email Logs creation time. SendGrid Email Logs may append suffixes such as `.recvd-...` to `sg_message_id`; the script treats a user-provided message ID as matching when it is the prefix or normalized substring of the returned `sg_message_id`.

For dynamic template sends, omit `--subject` when querying status. The template can define or override the final email subject, so filtering Email Logs by the request subject may hide the matching message.

```bash
bash <skill-path>/scripts/query_email_logs.sh \
  --to "customer@example.com" \
  --subject "Order update" \
  --sent-at "2026-06-15T10:37:21Z" \
  --message-id "abc123..." \
  --limit 100
```

When `--message-id` is provided, the response includes `matched_messages`, `matched_count`, and `_match_reason` for each matched message. If no matching messages are returned, ask the user to review SendGrid Email Logs manually at <https://app.sendgrid.com/email_logs>.

### Raw SendGrid query

```bash
bash <skill-path>/scripts/query_email_logs.sh \
  --query "to_email = 'customer@example.com' AND status IN ('delivered', 'processed')" \
  --limit 10
```

Use `--dry-run` to inspect the `/v3/logs` request payload without calling SendGrid.

Note: Do not use `custom_args.business_id` for Email Logs queries. Use recipient, optional subject, `--sent-at`, and message ID fuzzy matching, or pass a raw account-supported `--query`.

## Execution Order

1. Confirm the user explicitly wants to send email and has provided the final recipients, subject, and content.
2. Prefer the bundled script over ad hoc `curl` commands.
3. Run a dry run first unless the user already asked for an immediate send and the final email details are unambiguous.
4. Review the dry-run payload for recipient visibility, content, attachments, sandbox mode, and scheduled-send fields.
5. Run again with `--send` only after explicit user approval.
6. Treat HTTP `202` as queued, not delivered. Delivery confirmation is asynchronous through SendGrid events or webhooks.
7. Report the recipients, subject, business ID, sandbox/send mode, HTTP status, SendGrid `x-message-id` header, and a concise prompt example for querying status when available.

## Commands

### Dry-run a simple email

```bash
bash <skill-path>/scripts/send_email.sh \
  --from "verified@example.com" \
  --to "recipient@example.com" \
  --subject "Hello" \
  --text "Hello from SendGrid."
```

### Actually send

```bash
bash <skill-path>/scripts/send_email.sh \
  --from "verified@example.com" \
  --to "recipient@example.com" \
  --subject "Hello" \
  --html "<p>Hello from SendGrid.</p>" \
  --send
```

### Multiple recipients with private personalizations

```bash
bash <skill-path>/scripts/send_email.sh \
  --from "verified@example.com" \
  --to "alice@example.com" \
  --to "bob@example.com" \
  --subject "Private update" \
  --text "Each recipient is in a separate personalization." \
  --private-recipients \
  --send
```

Without `--private-recipients`, recipients in the same `to` array can see each other.

### Dynamic template send

```bash
bash <skill-path>/scripts/send_email.sh \
  --from "verified@example.com" \
  --to "alice@example.com" \
  --template-id "d-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
  --dynamic-template-data-json '{"name":"Alice","order_id":"123"}' \
  --send
```

When using `--template-id`, omit `--text` and `--html` unless the user specifically wants both. Template content normally comes from SendGrid.

### Sandbox validation

```bash
bash <skill-path>/scripts/send_email.sh \
  --from "verified@example.com" \
  --to "recipient@example.com" \
  --subject "Validate only" \
  --text "This request is validated but not delivered." \
  --sandbox \
  --send
```

Sandbox mode validates the request without delivery and usually returns HTTP `200`.

### Attach a file

```bash
bash <skill-path>/scripts/send_email.sh \
  --from "verified@example.com" \
  --to "customer@example.com" \
  --subject "Invoice" \
  --html-file ./email.html \
  --attachment ./invoice.pdf \
  --send
```

Attachments are base64-encoded into the `attachments` array. Keep total request size under SendGrid's documented limit.

### Add a business correlation ID

Every request automatically includes `custom_args.business_id`. To control the value, pass:

```bash
bash <skill-path>/scripts/send_email.sh \
  --from "verified@example.com" \
  --to "customer@example.com" \
  --subject "Order update" \
  --text "Your order shipped." \
  --business-id "order_12345"
```

Use this ID later when correlating SendGrid Event Webhook events or application logs. Do not use it as the default Email Logs query path.

## Fixed Request Shape

The script sends to:

- global region: `https://api.sendgrid.com/v3/mail/send`
- EU region: `https://api.eu.sendgrid.com/v3/mail/send`

It sends JSON shaped like:

```json
{
  "personalizations": [
    {
      "to": [{ "email": "recipient@example.com" }],
      "dynamic_template_data": { "name": "Alice" }
    }
  ],
  "from": { "email": "verified@example.com" },
  "subject": "Hello",
  "content": [{ "type": "text/plain", "value": "Hello from SendGrid." }],
  "custom_args": {
    "business_id": "sendgrid_email_20260615T120000Z_0123456789abcdef0123456789abcdef"
  }
}
```

Optional fields are omitted when the user does not provide them. Require `--from` from the user. Do not invent sender identities, recipients, template IDs, categories, custom args, batch IDs, or scheduled-send timestamps.

## Script Options

- `--from EMAIL` or `--from "Name <email@example.com>"`; required sender address. This address should be a verified sender in the user's Twilio SendGrid account.
- `--to`, `--cc`, `--bcc`; repeat flags or comma-separate values
- `--subject`
- `--text`, `--text-file`
- `--html`, `--html-file`
- `--template-id`
- `--dynamic-template-data-json`
- `--reply-to`
- `--attachment PATH`; repeatable
- `--business-id VALUE`; optional business correlation ID. Auto-generated when omitted and written to `custom_args.business_id`
- `--category NAME`; repeatable, up to SendGrid's limit
- `--custom-arg KEY=VALUE`; repeatable
- `--batch-id`
- `--send-at UNIX_SECONDS`
- `--sandbox`
- `--private-recipients`
- `--region global|eu`
- `--api-key KEY` for a one-time override
- `--save-api-key` to save the `--api-key` value for future runs
- `--configure-api-key` to prompt for and save the key
- `--clear-api-key` to remove the locally saved key
- `--output PATH` to save dry-run JSON or send metadata
- `--send` to perform the API call
- `query_email_logs.sh --sent-at-lookback-seconds N`; optional Email Logs query lookback before `--sent-at`, default `5`

## Notes

- `--send` is required for side effects; without it, the script only prints the payload.
- Never echo or store the API key in user-visible output.
- The scripts can save the API key locally at `~/.config/sendgrid-send-email/api_key` with file permission `600`; do not print the key value back to the user.
- Use `--api-key <key> --save-api-key` or `--configure-api-key` when the user wants to update the saved key. Use `--clear-api-key` when the user wants to remove it.
- The `from` address should be a verified sender in the user's Twilio SendGrid account.
- Every request includes `custom_args.business_id`. Use `--business-id` to set a business-specific correlation ID; otherwise the script generates one.
- Do not pass `--custom-arg business_id=...`; use `--business-id` for that reserved key.
- Use `query_email_logs.sh --to <email> --sent-at <iso-time> --message-id <x-message-id> [--subject <subject>]` to query send status through SendGrid Email Logs by recipient, optional subject, buffered sent-at lower bound, and fuzzy-match returned `sg_message_id`, including `sg_message_id` values with `.recvd-...` suffixes. The script subtracts 5 seconds from `--sent-at` by default; override with `--sent-at-lookback-seconds`. If the email was sent with `--template-id`, omit subject in status lookups because the template may override it.
- After a successful send, the script returns `status_query.prompt_example` and `status_query.query_params` so the user can ask the agent to query status later without displaying shell scripts.
- If Email Logs returns no data or no fuzzy `sg_message_id` match, direct the user to <https://app.sendgrid.com/email_logs> for manual review.
- If `--api-key`, `SENDGRID_API_KEY`, and the locally saved key are all missing, tell the user to read <https://wenjun.gitbook.io/wenjun-docs/sendgrid-integration> to get the required configuration.
- SendGrid returns `202 Accepted` for queued mail. That does not mean delivered.
- Sandbox mode returns validation status and does not deliver.
- For scheduled sends, `--send-at` must be Unix seconds, not JavaScript milliseconds.
- For private bulk sends, use `--private-recipients` or separate API calls.
- If a user shares an API key in chat, advise them to rotate it.

## Example Prompts

### 中文

- "用 SendGrid 给 alice@example.com 发一封测试邮件"
- "用这个 verified sender 发送 HTML 邮件，先 dry run"
- "用 SendGrid template d-... 给这几个收件人分别发邮件"

### English

- "Send a SendGrid email to this customer"
- "Dry-run this SendGrid Mail Send payload before sending"
- "Send a SendGrid dynamic template email with these variables"
