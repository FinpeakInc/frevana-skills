---
name: instantly-send-email
description: Use when the user wants to send email through Instantly API V2 using the normal Instantly workflow: check/create leads, choose or create a campaign, move/enroll leads into campaigns, inspect campaign sending status, list a lead's emails, and reply to an existing selected email. Uses separate lead.sh, campaign.sh, and email.sh scripts. Do not use the Instantly test-email endpoint, SendGrid, SMTP, or a nonexistent direct send API.
---

# Instantly Send Email

Send email through Instantly's real workflow paths.

## Core Model

Instantly API V2 does not expose a generic direct `POST /send` endpoint for new outbound email.

Use these workflows:

- **Cold/outbound first touch:** find or create a Lead, let the user choose or create a Campaign, then place the Lead into that Campaign. Instantly sends according to the campaign's configured sequence, sender accounts, schedule, limits, and health.
- **Reply to an existing conversation:** list emails for the lead email address, let the user choose the specific email, then call `POST /api/v2/emails/reply` with that selected email's `id` as `reply_to_uuid`.

Never use `POST /api/v2/emails/test` for user-requested sending. It is only a preview/test endpoint.

## Scripts

Use exactly these bundled scripts:

- `scripts/lead.sh`: `list`, `create`, `move`
- `scripts/campaign.sh`: `list`, `create`, `sending-status`
- `scripts/email.sh`: `list`, `reply`

Read actions call the API immediately. Write actions dry-run by default and require `--send`.

API key resolution order for all scripts:

1. `--api-key`
2. `INSTANTLY_API_KEY`
3. locally saved key at `~/.config/instantly-send-email/api_key`

Use `--api-key <key> --save-api-key`, `--configure-api-key`, or `--clear-api-key` with any script to manage the saved key.

If no API key is available, point the user to this article to create one: <https://developer.instantly.ai/getting-started/getting-started>.

## Workflow A: Cold / First Email

1. Check whether the lead already exists:

```bash
bash <skill-path>/scripts/lead.sh list --email "prospect@example.com"
```

This calls `POST /api/v2/leads/list` with `contacts: ["prospect@example.com"]`.

2. If the lead does not exist, collect any available lead fields. Do not create yet if the target campaign is not known.

3. List campaigns for the user to choose:

```bash
bash <skill-path>/scripts/campaign.sh list
```

This calls `GET /api/v2/campaigns`. Show the user campaign names, IDs, status, schedule summary, and sequence summary when available.

4. If the user wants a new campaign, collect all required campaign fields together before calling the script. Instantly requires both `name` and `campaign_schedule`; use `--campaign-json` when the user provides full campaign settings, otherwise use `--name` plus `--schedule-json`. Run dry-run first.

```bash
bash <skill-path>/scripts/campaign.sh create \
  --name "AI 自动触达" \
  --schedule-json '{"schedules":[{"name":"Weekdays","timing":{"from":"09:00","to":"17:00"},"days":{"0":true,"1":true,"2":true,"3":true,"4":true,"5":false,"6":false},"timezone":"America/New_York"}]}'
```

Then run with `--send` only after approval.

5. Put the lead into the selected campaign:

- If the lead does not exist, create it with the selected campaign:

```bash
bash <skill-path>/scripts/lead.sh create \
  --email "prospect@example.com" \
  --campaign-id "campaign_uuid" \
  --first-name "Jane"
```

- If the lead already exists, move/enroll by email into the selected campaign:

```bash
bash <skill-path>/scripts/lead.sh move \
  --email "prospect@example.com" \
  --to-campaign-id "campaign_uuid"
```

For removing a lead from a campaign, Instantly's documented move endpoint requires a destination. Use `lead.sh move` with a destination `--to-list-id` or `--to-campaign-id`, and provide `--from-campaign-id` when narrowing the source campaign matters.

6. After successful create/move, inspect when sending can happen:

```bash
bash <skill-path>/scripts/campaign.sh sending-status --campaign-id "campaign_uuid"
```

Report `summary.status`, `summary.status_message`, `summary.ai_summary`, schedule state, daily limits, account availability, `last_healthy_send_at`, and lead readiness. Do not promise an exact send time unless the API response provides one. If the move response returns a background job, explain that enrollment is still processing.

## Workflow B: Reply To Existing Email

1. List emails for the lead email address:

```bash
bash <skill-path>/scripts/email.sh list \
  --lead "customer@example.com" \
  --limit 20
```

This calls `GET /api/v2/emails?lead=<email>&sort_order=desc`. Present a concise selection list with email `id`, `thread_id`, subject, timestamp, from/to, and preview.

2. Ask the user to choose the exact email to reply to.

3. Draft the reply body if requested. Confirm `eaccount`, selected email `id`, subject, and body.

4. Dry-run the reply:

```bash
bash <skill-path>/scripts/email.sh reply \
  --eaccount "sender@example.com" \
  --reply-to-uuid "selected_email_id" \
  --subject "Re: Your inquiry" \
  --text "Thanks for the context."
```

5. Send only after explicit approval:

```bash
bash <skill-path>/scripts/email.sh reply \
  --eaccount "sender@example.com" \
  --reply-to-uuid "selected_email_id" \
  --subject "Re: Your inquiry" \
  --text "Thanks for the context." \
  --send
```

## Script Capabilities

### `lead.sh`

- `list --email EMAIL [--limit N]`
- `create --email EMAIL [--campaign-id UUID] [lead fields] [--send]`
- `move --email EMAIL (--to-campaign-id UUID | --to-list-id UUID) [--from-campaign-id UUID | --from-list-id UUID] [--send]`

Supported lead fields include first name, last name, company name, job title, website, phone, personalization, custom variables, duplicate skip flags, blocklist ID, and verification flags.

For the send-email workflow, collect these lead fields together before creating the lead:

- Required: `email`, selected `campaign_id`
- Recommended for template personalization: `first_name`, `last_name`, `company_name`, `job_title`, `website`
- Optional: `phone`, `personalization`, `custom_variables`, duplicate skip flags, blocklist ID, verification flags

### `campaign.sh`

- `list [--limit N]`
- `create --name NAME --schedule-json JSON [--send]`
- `create --campaign-json JSON [--send]`
- `sending-status --campaign-id UUID`

Creating a campaign does not guarantee it is ready to send. Campaigns still need sequences/templates, sender accounts, schedule, activation state, and limits configured.

For campaign creation, collect these fields together before calling the script:

- Required by API: `name`, `campaign_schedule`
- Strongly recommended before using it for sending: at least one sequence/template, sender `email_list`, daily limits, tracking/stop behavior, and activation plan

### `email.sh`

- `list --lead EMAIL [--limit N] [--latest-of-thread]`
- `reply --eaccount EMAIL --reply-to-uuid EMAIL_ID --subject SUBJECT (--html HTML | --text TEXT) [--send]`

`reply_to_uuid` is the selected email `id`, not the `thread_id`.

## Notes

- Never invent campaign IDs, list IDs, email IDs, sending accounts, or API keys.
- Never print API keys. If the user shares a key in chat, advise rotation.
- For user choice steps, show a compact numbered list and wait for the user's selection before write actions.
- Treat lead creation or movement as campaign enrollment, not delivery confirmation.
- For missing API key in non-interactive runs, tell the user to create an Instantly API V2 key by following <https://developer.instantly.ai/getting-started/getting-started>.

## Example Prompts

- "用 Instantly 给这个邮箱发冷邮件"
- "把这个 lead 加到 AI 自动触达 campaign"
- "查一下这个邮箱有没有 lead，没有就创建，然后让我选 campaign"
- "用 Instantly 回复 customer@example.com 最近的一封邮件"
- "把这个 email 从当前 campaign 移到另一个 campaign"
