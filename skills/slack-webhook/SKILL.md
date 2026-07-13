---
name: slack-webhook
description: Use when the user wants to post a Slack message or Slack notification through an incoming webhook URL. Supports plain text, Slack mrkdwn, links, Block Kit payload JSON, thread replies, unfurl controls, dry-run payload preview, and saved webhook URL reuse. Do not use for reading Slack, deleting messages, managing channels, or Slack Bot Token Web API workflows.
---

# Slack Webhook

Post messages to Slack through an incoming webhook URL.

## Purpose

This skill is for **sending Slack notifications with Slack Incoming Webhooks** by calling the webhook URL directly.

Inputs:

- message text, or a complete Slack webhook JSON payload
- Slack incoming webhook URL from `SLACK_WEBHOOK_URL`, `--webhook-url-stdin`, or the locally saved URL
- optional Block Kit `blocks`
- optional `thread_ts`, `unfurl_links`, and `unfurl_media`

Output:

- dry-run JSON payload by default
- Slack HTTP status and response body when `--send` is explicitly provided

Sending Slack messages is externally visible and cannot be undone by this webhook. Always confirm the channel/workspace implied by the webhook URL and the final message content before running with `--send`.

## What This Skill Needs

- user-provided message text or payload JSON
- a Slack incoming webhook URL, usually `SLACK_WEBHOOK_URL`
- `curl`
- `bash`
- `python3`

Webhook URL resolution order:

1. `SLACK_WEBHOOK_URL`
2. `--webhook-url-stdin` for the current run
3. locally saved URL at `~/.config/slack-webhook/webhook_url`

If no webhook URL is available, dry-run payload preview still works. Sending requires a webhook URL. When the user has not configured one yet, direct them to https://frevana.gitbook.io/frevana-docs/connect-chat-apps/slack-webhook-integration for setup instructions.

Users can save a webhook URL with:

```bash
SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..." \
  bash <skill-path>/scripts/send_slack_webhook.sh \
  --save-webhook-url
```

For a one-time non-interactive send without exporting an environment variable first:

```bash
printf '%s\n' 'https://hooks.slack.com/services/...' | \
  bash <skill-path>/scripts/send_slack_webhook.sh \
  --webhook-url-stdin \
  --text "Deploy completed." \
  --send
```

or clear it with:

```bash
bash <skill-path>/scripts/send_slack_webhook.sh --clear-webhook-url
```

Never print the webhook URL back to the user. Treat it as a secret.

## Execution Order

1. Extract the final Slack message text or payload JSON.
2. Prefer `scripts/send_slack_webhook.sh` over ad hoc `curl`.
3. Run a dry run first unless the user already asked for an immediate Slack post and the final message is unambiguous.
4. Review the dry-run payload for channel intent, text fallback, Block Kit structure, thread target, and unfurl behavior.
5. If `--send` is used in an interactive terminal and no webhook is configured yet, the script prompts for one-time secure input and can save it for future runs.
6. Run again with `--send` only after explicit user approval.
7. Treat Slack response body `ok` with HTTP `200` as posted. Report non-`ok` Slack error strings such as `invalid_payload`, `no_text`, `no_service`, `channel_not_found`, `channel_is_archived`, or `action_prohibited`.

## Commands

### Dry-run a simple message

```bash
bash <skill-path>/scripts/send_slack_webhook.sh \
  --text "Deploy completed."
```

### Actually post a message

```bash
bash <skill-path>/scripts/send_slack_webhook.sh \
  --text "Deploy completed. :rocket:" \
  --send
```

### Use Slack mrkdwn

```bash
bash <skill-path>/scripts/send_slack_webhook.sh \
  --text "*Production deploy* finished successfully."
```

Slack mrkdwn examples:

| Syntax | Result |
| --- | --- |
| `*bold*` | bold text |
| `_italic_` | italic text |
| `~strike~` | strikethrough text |
| `` `code` `` | inline code |
| `<https://example.com|label>` | hyperlink |
| `:white_check_mark:` | emoji |

### Send a Block Kit payload

```bash
bash <skill-path>/scripts/send_slack_webhook.sh \
  --text "Deployment status" \
  --blocks-json '[{"type":"section","text":{"type":"mrkdwn","text":"*Production deploy* succeeded."}}]'
```

`text` is still recommended as a fallback for notifications and clients that do not render blocks.

### Send a complete payload file

```bash
bash <skill-path>/scripts/send_slack_webhook.sh \
  --payload-file ./slack_payload.json \
  --send
```

### Reply in a thread

```bash
bash <skill-path>/scripts/send_slack_webhook.sh \
  --text "Follow-up status update" \
  --thread-ts "1712345678.123456" \
  --send
```

### Save the dry-run payload

```bash
bash <skill-path>/scripts/send_slack_webhook.sh \
  --text "Queued notification" \
  --output ./out/slack-payload.json
```

## Fixed Request Shape

The script sends a `POST` request to the configured incoming webhook URL with:

- `Content-Type: application/json`
- JSON payload containing either a user-provided complete payload, or a constructed payload from the supported options

Constructed payload fields:

- `text`; required unless `--payload-json` or `--payload-file` is used
- `blocks`; optional JSON array from `--blocks-json`
- `attachments`; optional JSON array from `--attachments-json`
- `thread_ts`; optional Slack message timestamp
- `unfurl_links`; optional boolean
- `unfurl_media`; optional boolean

Do not invent unsupported Slack fields. Use `--payload-json` or `--payload-file` when the user needs a full custom Incoming Webhook payload.

## Script Options

- `--text TEXT`; message text and fallback
- `--text-file PATH`; read message text from a UTF-8 file
- `--payload-json JSON`; complete Slack webhook payload object
- `--payload-file PATH`; complete Slack webhook payload file
- `--blocks-json JSON`; Block Kit blocks array
- `--attachments-json JSON`; Slack attachments array
- `--thread-ts TS`; post as a thread reply
- `--unfurl-links true|false`; control link unfurling
- `--unfurl-media true|false`; control media unfurling
- `--webhook-url-stdin`; read a one-time webhook URL from stdin
- `--save-webhook-url`; save the resolved webhook URL for future runs
- `--configure-webhook-url`; prompt for and save a webhook URL
- `--clear-webhook-url`; remove the locally saved webhook URL
- `--output PATH`; save dry-run payload or send metadata JSON; save failures do not change the send result
- `--send`; actually call the Slack webhook

## Notes

- Incoming webhooks are bound to one configured Slack destination. The script cannot choose arbitrary channels unless the webhook app configuration supports it.
- Incoming webhooks are send-only. They cannot read messages, delete messages, list channels, or manage users.
- Webhook URLs are secrets. Never echo a webhook URL, save it in logs, or include it in user-facing output.
- Messages containing `!` can break ad hoc interactive shell commands because of history expansion. Prefer the bundled script with quoted arguments or `--text-file`.
- Slack commonly rate-limits incoming webhooks around one message per second. Avoid bulk posting unless the user explicitly asks for it.
- If a user shares a webhook URL in chat, advise them to rotate it if it may have been exposed.

## Example Prompts

### Chinese

- "发一条 Slack 通知说部署完成"
- "用 Slack webhook 发这个 Block Kit payload"
- "把这段内容 dry-run 成 Slack webhook JSON"
- "保存一下 Slack webhook URL，以后发通知用"

### English

- "Post this to Slack via webhook"
- "Send a Slack notification that the deploy completed"
- "Dry-run the Slack webhook payload"
- "Reply in this Slack thread using thread_ts"
