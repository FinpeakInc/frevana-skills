---
name: klaviyo-send-email
description: Use when the user wants to manage Klaviyo campaigns through the Klaviyo Campaign API: list, get, create, update, delete, clone, or send campaigns; assign email templates to campaign messages; list, get, or update campaign messages; refresh or get recipient estimations; or create, get, or update campaign audiences. Uses campaign.sh and audience.sh scripts. Uses Klaviyo-API-Key authorization.
---

# Klaviyo Send Email

Manage Klaviyo campaigns and campaign audiences through the Klaviyo REST API.

## Core Model

Klaviyo exposes a JSON:API for campaign management. This skill covers five resource types:

- **Campaigns** (`campaign.sh`): list, get, create, update, delete, clone, send, send-status, cancel, assign-template, list-messages, get-message, update-message, refresh-estimation, get-estimation, get-estimation-job
- **Campaign Audiences** (`audience.sh`): get, create, update
- **Lists** (`lists.sh`): list, get, create, update, delete, get-profiles, get-profile-ids, add-profiles, remove-profiles
- **Profiles** (`profiles.sh`): search, list, get, create, update, upsert, get-lists, get-segments
- **Segments** (read via `segments` endpoints): segments have their own API, but the scripts above can reference segment IDs in audiences

Audience endpoints are currently in **beta** and require the `2026-04-15.pre` revision header. All campaign endpoints use the stable `2026-04-15` revision.

Never use a SendGrid API key, Instantly API key, or `FREVANA_TOKEN` with these scripts.

## Scripts

Use exactly these bundled scripts:

- `scripts/campaign.sh`: `list`, `get`, `create`, `update`, `delete`, `clone`, `send`, `send-status`, `cancel`, `assign-template`, `list-messages`, `get-message`, `update-message`, `refresh-estimation`, `get-estimation`, `get-estimation-job`
- `scripts/audience.sh`: `get`, `create`, `update`
- `scripts/lists.sh`: `list`, `get`, `create`, `update`, `delete`, `get-profiles`, `get-profile-ids`, `add-profiles`, `remove-profiles`
- `scripts/profiles.sh`: `search`, `list`, `get`, `create`, `update`, `upsert`, `get-lists`, `get-segments`

Read actions call the API immediately. Write actions dry-run by default and require `--send`.

API key resolution order for all scripts:

1. `--api-key`
2. `KLAVIVO_API_KEY`
3. locally saved key at `~/.config/klaviyo-send-email/api_key`

Use `--api-key <key> --save-api-key`, `--configure-api-key`, or `--clear-api-key` with any script to manage the saved key.

If no API key is available, point the user to this guide to create one: <https://frevana.gitbook.io/frevana-docs/email-integrations/klaviyo-integration>.

## Workflow A: List and Inspect Campaigns

1. List campaigns by channel:

```bash
bash <skill-path>/scripts/campaign.sh list \
  --filter 'equals(messages.channel,"email")'
```

This calls `GET /api/campaigns?filter=equals(messages.channel,"email")`. Present campaign name, ID, status, created_at, and scheduled_at.

2. Get a specific campaign by ID:

```bash
bash <skill-path>/scripts/campaign.sh get \
  --campaign-id "campaign_id_here"
```

This calls `GET /api/campaigns/{id}`. Present the campaign attributes, status, and related messages.

## Workflow B: Create a Campaign

1. Collect required fields: campaign name, audience groups (included/excluded segment IDs), and message content (subject, from_email, from_label).

2. Dry-run the campaign create:

```bash
bash <skill-path>/scripts/campaign.sh create \
  --name "Spring Sale 2026" \
  --audience-json '{"included":["Y6nRLr"],"excluded":[]}' \
  --message-json '{"subject":"Spring Sale is here!","from_email":"store@my-company.com","from_label":"My Company","preview_text":"Check out our spring deals"}'
```

3. Send only after explicit approval:

```bash
bash <skill-path>/scripts/campaign.sh create \
  --name "Spring Sale 2026" \
  --audience-json '{"included":["Y6nRLr"],"excluded":[]}' \
  --message-json '{"subject":"Spring Sale is here!","from_email":"store@my-company.com","from_label":"My Company","preview_text":"Check out our spring deals"}' \
  --send
```

This calls `POST /api/campaigns`. The response includes the created campaign with its ID.

## Workflow C: Update a Campaign

Update campaign name and/or audience:

```bash
bash <skill-path>/scripts/campaign.sh update \
  --campaign-id "campaign_id" \
  --name "Updated Campaign Name" \
  --audience-json '{"included":["Y6nRLr"],"excluded":["UTd5ui"]}'
```

Send with `--send` to execute `PATCH /api/campaigns/{id}`.

## Workflow D: Manage Lists

### List all lists

```bash
bash <skill-path>/scripts/lists.sh list
```

Calls `GET /api/lists`. Optional `--filter`, `--sort`.

### Create a list

```bash
bash <skill-path>/scripts/lists.sh create \
  --name "My New List"
```

Send with `--send` to execute `POST /api/lists`.

### Get a list

```bash
bash <skill-path>/scripts/lists.sh get \
  --list-id "list_id"
```

Calls `GET /api/lists/{id}`.

### Update a list name

```bash
bash <skill-path>/scripts/lists.sh update \
  --list-id "list_id" \
  --name "Updated Name"
```

Send with `--send` to execute `PATCH /api/lists/{id}`.

### Delete a list

```bash
bash <skill-path>/scripts/lists.sh delete \
  --list-id "list_id"
```

Send with `--send` to execute `DELETE /api/lists/{id}`.

### Get profiles for a list

```bash
bash <skill-path>/scripts/lists.sh get-profiles \
  --list-id "list_id"
```

Calls `GET /api/lists/{id}/profiles`. Optional `--limit`.

### Get profile IDs for a list

```bash
bash <skill-path>/scripts/lists.sh get-profile-ids \
  --list-id "list_id"
```

Calls `GET /api/lists/{id}/relationships/profiles`.

### Add profiles to a list

```bash
bash <skill-path>/scripts/lists.sh add-profiles \
  --list-id "list_id" \
  --profile-ids '["profile_id_1","profile_id_2"]'
```

Send with `--send` to execute `POST /api/lists/{id}/relationships/profiles`.

### Remove profiles from a list

```bash
bash <skill-path>/scripts/lists.sh remove-profiles \
  --list-id "list_id" \
  --profile-ids '["profile_id_1"]'
```

Send with `--send` to execute `DELETE /api/lists/{id}/relationships/profiles`.

## Workflow E: Manage Profiles

### Search for a profile by email

```bash
bash <skill-path>/scripts/profiles.sh search \
  --email "user@example.com"
```

Calls `GET /api/profiles?filter=equals(email,"...")`. Returns the profile if found.

### List all profiles

```bash
bash <skill-path>/scripts/profiles.sh list
```

Calls `GET /api/profiles`. Optional `--filter`, `--sort`, `--limit`.

### Get a profile by ID

```bash
bash <skill-path>/scripts/profiles.sh get \
  --profile-id "profile_id"
```

Calls `GET /api/profiles/{id}`.

### Create a profile

```bash
bash <skill-path>/scripts/profiles.sh create \
  --profile-json '{"data":{"type":"profile","attributes":{"email":"user@example.com","first_name":"John"}}}'
```

Send with `--send` to execute `POST /api/profiles`.

### Update a profile

```bash
bash <skill-path>/scripts/profiles.sh update \
  --profile-id "profile_id" \
  --profile-json '{"data":{"type":"profile","id":"profile_id","attributes":{"first_name":"Jane"}}}'
```

Send with `--send` to execute `PATCH /api/profiles/{id}`.

### Upsert (create or update) a profile

Uses the idempotent profile-import endpoint. If a profile with the given email exists, it is updated; otherwise a new profile is created.

```bash
bash <skill-path>/scripts/profiles.sh upsert \
  --profile-json '{"data":{"type":"profile","attributes":{"email":"user@example.com","first_name":"John"}}}'
```

Send with `--send` to execute `POST /api/profile-import`.

### Get lists for a profile

```bash
bash <skill-path>/scripts/profiles.sh get-lists \
  --profile-id "profile_id"
```

Calls `GET /api/profiles/{id}/lists`.

### Get segments for a profile

```bash
bash <skill-path>/scripts/profiles.sh get-segments \
  --profile-id "profile_id"
```

Calls `GET /api/profiles/{id}/segments`.

## Workflow G: Manage Campaign Audiences

### Get an audience

```bash
bash <skill-path>/scripts/audience.sh get \
  --audience-id "audience_id"
```

Calls `GET /api/campaign-audiences/{id}`.

### Create an audience

```bash
bash <skill-path>/scripts/audience.sh create \
  --campaign-id "campaign_id" \
  --definition-json '{"name":"My Audience","included":["abc123"],"excluded":[],"priority":1}'
```

Send with `--send` to execute `POST /api/campaign-audiences`.

### Update an audience

```bash
bash <skill-path>/scripts/audience.sh update \
  --audience-id "audience_id" \
  --definition-json '{"name":"Updated Audience","included":["abc123","def456"],"excluded":[],"priority":2}'
```

Send with `--send` to execute `PATCH /api/campaign-audiences/{id}`.

## Workflow H: Delete a Campaign

```bash
bash <skill-path>/scripts/campaign.sh delete \
  --campaign-id "campaign_id"
```

Send with `--send` to execute `DELETE /api/campaigns/{id}`. Returns 204 on success.

## Workflow I: Clone a Campaign

Clone an existing campaign (sets status to draft, keeps original name):

```bash
bash <skill-path>/scripts/campaign.sh clone \
  --campaign-id "campaign_id"
```

Send with `--send` to execute `POST /api/campaign-clone`.

## Workflow J: Send / Schedule a Campaign

Important: Before sending, the campaign message must have a template assigned (see Workflow K).

### 0. Let user choose an existing campaign

First list all email campaigns and ask the user which one to send:

```bash
bash <skill-path>/scripts/campaign.sh list \
  --filter 'equals(messages.channel,"email")'
```

Present as a table: name, ID, status, created_at. Ask the user to pick one or create new.
- If user picks a **Sent/Cancelled** campaign → clone it first to get a draft, then use the clone.
- If user picks a **Draft** campaign → use directly.

### 0b. Show current content & ask if modify

After user picks a campaign, list its messages to show the current content (subject, from_email, from_label, preview_text, template_id). Present as a table and ask:

> "This is the current content. Do you want to modify it?"

If yes → let user provide new content and call `update-message --send`.
If no → keep as-is.
If no template assigned yet → proceed to Workflow K to assign one.

### 1. Send the campaign

```bash
bash <skill-path>/scripts/campaign.sh send \
  --campaign-id "campaign_id"
```

Send with `--send` to execute `POST /api/campaign-send-jobs`. Returns a campaign send job ID.

### Check send status

```bash
bash <skill-path>/scripts/campaign.sh send-status \
  --send-job-id "send_job_id"
```

Calls `GET /api/campaign-send-jobs/{id}`. Job statuses: `queued`, `processing`, `cancelled`, `complete`.

### Cancel a scheduled send

```bash
bash <skill-path>/scripts/campaign.sh cancel \
  --send-job-id "send_job_id"
```

Send with `--send` to execute `PATCH /api/campaign-send-jobs/{id}` with status `cancelled`.

## Workflow K: Assign Template to Campaign Message

After creating a campaign, you must assign a template to its message before sending:

1. Create a template via the Klaviyo Templates API.
2. Get the campaign message ID from `list-messages`.
3. Assign the template:

```bash
bash <skill-path>/scripts/campaign.sh assign-template \
  --message-id "message_id" \
  --template-id "template_id"
```

Send with `--send` to execute `POST /api/campaign-message-assign-template`. This clones the reusable template and assigns the non-reusable clone to the message.

## Workflow L: Manage Campaign Messages

### List messages for a campaign

```bash
bash <skill-path>/scripts/campaign.sh list-messages \
  --campaign-id "campaign_id"
```

Calls `GET /api/campaigns/{id}/campaign-messages`.

### Get a single message

```bash
bash <skill-path>/scripts/campaign.sh get-message \
  --message-id "message_id"
```

Calls `GET /api/campaign-messages/{id}`.

### Update a message

```bash
bash <skill-path>/scripts/campaign.sh update-message \
  --message-id "message_id" \
  --message-json '{"definition":{"label":"Updated","content":{"subject":"New Subject","from_email":"new@example.com","from_label":"Sender"}}}'
```

Send with `--send` to execute `PATCH /api/campaign-messages/{id}`.

## Workflow M: Estimate Campaign Recipients

### Refresh estimation

```bash
bash <skill-path>/scripts/campaign.sh refresh-estimation \
  --campaign-id "campaign_id"
```

Send with `--send` to execute `POST /api/campaign-recipient-estimation-jobs`. Triggers an async job.

### Check estimation job status

```bash
bash <skill-path>/scripts/campaign.sh get-estimation-job \
  --estimation-job-id "estimation_job_id"
```

Calls `GET /api/campaign-recipient-estimation-jobs/{id}`. Statuses: `queued`, `processing`, `cancelled`, `complete`.

### Get estimated recipient count

```bash
bash <skill-path>/scripts/campaign.sh get-estimation \
  --campaign-id "campaign_id"
```

Calls `GET /api/campaign-recipient-estimations/{campaign_id}`.

## Script Capabilities

### `campaign.sh`

- `list --filter FILTER [--limit N] [--sort SORT]` — List campaigns by channel filter. Requires `--filter` (e.g., `equals(messages.channel,'email')`). Optional `--sort` (e.g., `-created_at`).
- `get --campaign-id UUID` — Get a single campaign with full attributes.
- `create --name NAME --audience-json JSON --message-json JSON [--send]` — Create a campaign. Requires name, audience groups, and email message definition.
- `update --campaign-id UUID --name NAME [--audience-json JSON] [--send]` — Update campaign name and optionally audience.
- `delete --campaign-id UUID [--send]` — Delete a campaign. Dry-run by default.
- `clone --campaign-id UUID [--send]` — Clone an existing campaign in draft status (keeps original name).
- `send --campaign-id UUID [--send]` — Trigger async campaign send via `POST /api/campaign-send-jobs`.
- `send-status --send-job-id UUID` — Check campaign send job status (queued/processing/cancelled/complete).
- `cancel --send-job-id UUID [--send]` — Cancel a campaign send job. Sets status to cancelled.
- `assign-template --message-id UUID --template-id UUID [--send]` — Clone a reusable template and assign it to a campaign message (`POST /api/campaign-message-assign-template`).
- `list-messages --campaign-id UUID` — List all messages for a campaign.
- `get-message --message-id UUID` — Get a single campaign message.
- `update-message --message-id UUID --message-json JSON [--send]` — Update a campaign message definition.
- `refresh-estimation --campaign-id UUID [--send]` — Trigger async recipient estimation job.
- `get-estimation --campaign-id UUID` — Get estimated recipient count for a campaign.
- `get-estimation-job --estimation-job-id UUID` — Check recipient estimation job status.

Message JSON fields for create:
- Required: `subject`, `from_email`, `from_label`
- Optional: `preview_text`, `reply_to_email`, `cc_email`, `bcc_email`, `label`, `send_options`, `tracking_options`, `send_strategy`

### `audience.sh`

- `get --audience-id UUID` — Get audience details (beta).
- `create --campaign-id UUID --definition-json JSON [--send]` — Create an audience for a campaign (beta).
- `update --audience-id UUID --definition-json JSON [--send]` — Update an audience definition (beta).

Definition JSON fields:
- `name` (string, nullable) — audience name
- `included` (array of strings, nullable) — list of included group/segment IDs
- `excluded` (array of strings, nullable) — list of excluded group/segment IDs
- `priority` (integer, nullable) — audience priority

### `lists.sh`

- `list [--filter FILTER] [--limit N] [--sort SORT]` — List all lists. Optional filter by name, sort by created/updated/name.
- `get --list-id UUID` — Get a single list with full attributes.
- `create --name NAME [--send]` — Create a new list. Dry-run by default.
- `update --list-id UUID --name NAME [--send]` — Update a list name.
- `delete --list-id UUID [--send]` — Delete a list. Returns 204 on success.
- `get-profiles --list-id UUID [--limit N]` — Get all profiles on a list.
- `get-profile-ids --list-id UUID` — Get profile relationship IDs for a list.
- `add-profiles --list-id UUID --profile-ids JSON [--send]` — Add profiles to a list. `--profile-ids` is a JSON array of profile ID strings.
- `remove-profiles --list-id UUID --profile-ids JSON [--send]` — Remove profiles from a list.

### `profiles.sh`

- `search --email EMAIL` — Search for a profile by email address (shorthand for `list --filter`).
- `list [--filter FILTER] [--limit N] [--sort SORT]` — List all profiles. Optional filter by email/name/etc.
- `get --profile-id UUID` — Get a single profile with full attributes.
- `create --profile-json JSON [--send]` — Create a new profile. JSON must include `data.type` and `data.attributes.email`.
- `update --profile-id UUID --profile-json JSON [--send]` — Update existing profile attributes.
- `upsert --profile-json JSON [--send]` — Create or update a profile idempotently via `POST /api/profile-import` (matches on email).
- `get-lists --profile-id UUID` — Get lists that a profile belongs to.
- `get-segments --profile-id UUID` — Get segments that a profile belongs to.

## Notes

- Never invent campaign IDs, audience IDs, segment IDs, API keys, template IDs, or message IDs.
- Never print API keys. If the user shares a key in chat, advise rotation.
- Audience endpoints are in beta. Use `2026-04-15.pre` revision header. GA expected in `2026-07-15`.
- All campaign endpoints (including send, clone, delete, template assignment, messages, estimation) use the stable `2026-04-15` revision.
- The Klaviyo API uses `Klaviyo-API-Key` in the `Authorization` header (not Bearer token).
- Required API key scopes per script: `campaign.sh` and `audience.sh` need `campaigns:read`, `campaigns:write`; `lists.sh` needs `lists:read`, `lists:write`; `profiles.sh` needs `profiles:read`, `profiles:write`.
- Campaign creation through the API does not immediately send. You must: create campaign → assign template → create campaign send job.
- If you cancel a campaign and want to resend it, clone the campaign first (creates a draft), then send again.
- To send an email campaign: (0) list campaigns and let user pick one, (1) if needed create campaign with message, (2) `list-messages` to get message ID, (3) `assign-template` to add email template, (4) `send` to schedule.
- **Always** list existing campaigns first when the user asks to send an email — ask them to pick an existing campaign or create a new one. Never skip this step.
- For missing API key in non-interactive runs, tell the user to create a Klaviyo API key by following <https://frevana.gitbook.io/frevana-docs/email-integrations/klaviyo-integration>.

## Complete Send Flow

### Step 0: List existing campaigns and let user choose

Before creating a new campaign, always list existing campaigns and ask the user if they want to reuse one:

```bash
bash <skill-path>/scripts/campaign.sh list \
  --filter 'equals(messages.channel,"email")'
```

Present the results as a numbered list with: name, ID, status, created_at. Ask:

> "Here are the existing campaigns. Which one would you like to use, or create a new one?"

- If user wants a new one → proceed to Step 1.
- If user picks an existing campaign:
  - If **Sent/Cancelled** → clone it first to get a draft, then use the cloned campaign's ID.
  - If **Draft** → use directly.

### Step 1 (existing campaign): Show current content & ask if modify

After the user picks a campaign (or clone), list its messages to show current content:

```bash
bash <skill-path>/scripts/campaign.sh list-messages \
  --campaign-id "campaign_id"
```

Present the current message content in a clear table:

| Field | Value |
|-------|-------|
| Subject | `subject` |
| From Email | `from_email` |
| From Name | `from_label` |
| Preview | `preview_text` |
| Template ID | `template.id` |

Then ask the user:

> "This is the current campaign content. Do you want to modify it?"

- If **yes** → let the user provide new subject/from_email/from_label/preview_text, then update with:
  ```bash
  bash <skill-path>/scripts/campaign.sh update-message \
    --message-id "message_id" \
    --message-json '{"definition":{"label":"...","content":{"subject":"...","from_email":"...","from_label":"...","preview_text":"..."}}}' \
    --send
  ```
- If **no** → keep the existing content as-is.

If the message already has a template assigned (`template.id` is present), skip template assignment. If no template, proceed to Step 3 (assign-template).

### Step 1 (new): Create the campaign (only if user chooses to create new)

```bash
bash <skill-path>/scripts/campaign.sh create \
  --name "Campaign Name" \
  --audience-json '{"included":["segment_id"],"excluded":[]}' \
  --message-json '{"subject":"Subject","from_email":"from@example.com","from_label":"Sender"}' \
  --send
```

### Step 2: Get the campaign message ID (if creating new)

```bash
bash <skill-path>/scripts/campaign.sh list-messages \
  --campaign-id "campaign_id"
```

### Step 3: Assign a template to the message (if needed)

```bash
bash <skill-path>/scripts/campaign.sh assign-template \
  --message-id "message_id" \
  --template-id "template_id" \
  --send
```

### Step 4: (Optional) Estimate recipients

```bash
bash <skill-path>/scripts/campaign.sh refresh-estimation \
  --campaign-id "campaign_id" --send
```

### Step 5: Send the campaign

```bash
bash <skill-path>/scripts/campaign.sh send \
  --campaign-id "campaign_id" --send
```

### Step 6: Check send status

```bash
bash <skill-path>/scripts/campaign.sh send-status \
  --send-job-id "send_job_id"
```

## Example Prompts

- "Create an email campaign in Klaviyo"
- "List all my Klaviyo email campaigns"
- "Show me details for a campaign"
- "Update campaign audience settings"
- "Create a new audience for a campaign"
- "View campaign audience"
- "Delete a Klaviyo campaign"
- "Clone a Klaviyo campaign"
- "Send a campaign email" (first list existing campaigns and let user choose)
- "Use an existing campaign to send"
- "Assign an email template to a campaign"
- "Check campaign send status"
- "View estimated recipients for a campaign"
- "List all Klaviyo lists"
- "Create a new Klaviyo list"
- "Add profiles to a list"
- "Search for a Klaviyo profile"
- "Create or update a Klaviyo profile"
- "Upsert a Klaviyo profile"
