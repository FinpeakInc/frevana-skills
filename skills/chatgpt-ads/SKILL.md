---
name: chatgpt-ads
description: Preview draft ad cards before choosing an account, create and manage ChatGPT ads, analyze performance and diagnose delivery. Use the official Ads API for accounts, targeting, bulk jobs, product or Hotel feeds, Pixel, conversions, Lead Sync subscriptions and Partner Data upload sessions. Preview and confirm changes before execution.
---

# ChatGPT Ads

Use `bash <skill-path>/scripts/chatgpt_ads.sh` for every command in these workflows. Requires Python 3.8+ on macOS or Linux. For live advertiser calls, read the account-scoped Advertiser API key from `OPENAI_ADS_API_KEY` in the execution environment. The advertiser can issue it in [Ads Manager settings](https://ads.openai.com/settings). Keep credentials out of chat, drafts and receipts.

## Choose a workflow

| User goal | Workflow |
| --- | --- |
| Draft an ad card before selecting an account, then prepare and launch a campaign | [Create](references/create.md) |
| Change existing resources, pause or activate delivery, manage limits, bulk jobs, audiences, feeds or webhook subscriptions | [Manage](references/manage.md) |
| Compare performance and report spend, clicks or attributed conversions | [Analyze](references/analyze.md) |
| Explain missing delivery, missing measurements or access errors | [Diagnose](references/diagnose.md) |

## Approval and recovery

`preview-card` renders local HTML for creative review. For an advertising change, use `preview`, `plan`, `pause` or `activate` to freeze the account, target, values and effects in a receipt. Show that proposal and request explicit approval. If any detail changes, prepare a fresh proposal for approval. Pass the saved fingerprint to `execute --state PATH --confirm FINGERPRINT` only after approval.

Keep the original receipt at its original path. Inspect progress with `show --state ./launch.json`. Resume an approved operation with the same state and fingerprint. Known creates are skipped; uncertain campaign, group and ad creation reuses the original idempotency key and request body. A completed receipt returns its saved result, including after a later pause. For an uncertain upload or status transition, inspect Ads Manager. If the desired transition already happened, ordinary resume verifies it. Only use `--retry-uncertain` after the user authorizes retrying the unresolved step; a repeated upload can create another asset. On an unexpected change, stop and show the recorded IDs. Keep one authoritative copy of each receipt. Do not regenerate an operation to recover a timeout.

Use `operations` and `describe ACTION` offline to discover commands and parameters. Consult the [advertiser operation guide](references/advertiser-operations.md) for native payloads and the [coverage audit](references/coverage.md) for official routes and account-gated features.
