# Manage advertising resources

Resolve the intended account with `account`. Use `read list-campaigns`, `read list-ad-groups` or `read list-ads` and the resource's current settings to identify the target. If several names match, show the choices before planning a change.

For a named mutation, run `describe ACTION` to check its fields, then use `plan ACTION --state PATH` with the relevant input files. Show the current and proposed values and their impact. Apply and verify the approved change through the [shared confirmation and recovery flow](../SKILL.md#approval-and-recovery). Use the [operation guide](advertiser-operations.md) for bidding, bulk operations, creative updates, audience membership, feeds, Pixel configuration and Partner Data upload sessions.

## Account limits and Lead Sync

- Read current account-wide limits with `read get-ad-account-spend-limit-windows`. For a proposed edit show the exact amount, account currency, rule or window, dates and delivery impact. Follow the [limit revision and window rules](advertiser-operations.md#advertiser-accounts-and-administrator-access).
- To list subscriptions, pass the real target account ID in a query file, then run `read list-lead-sync-subscriptions --query ./account.json`. An empty successful list means there are no returned subscriptions. For a subscription change, follow the [webhook and private output instructions](advertiser-operations.md#lead-sync-and-partner-data).
- If either read returns 403, follow the [access checks](diagnose.md#account-access). Resolve access before proposing a change that depends on that read.

## Pause an existing resource

```bash
bash <skill-path>/scripts/chatgpt_ads.sh pause --resource campaign --id CAMPAIGN_ID --state ./pause.json
bash <skill-path>/scripts/chatgpt_ads.sh execute --state ./pause.json --confirm FINGERPRINT
```

`pause` prepares a read-only proposal. Show the account, exact resource name and ID, current state and effect before executing an approved pause. Resource choices are `campaign`, `ad_group`, and `ad`. Pausing a campaign stops delivery for its children. For an already paused target, execution verifies the state without another pause request.
