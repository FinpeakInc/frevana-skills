---
name: mintegral-ads
description: Query and safely manage Mintegral AppGrowth advertising through the official Open API. Use when the user wants Mintegral account balance, performance reports, campaigns, offers, creatives, or creative sets, or wants to create or update campaigns and offers, start or stop delivery, change bids, budgets, publisher targeting, tracking URLs, audience targeting, optimization goals, or creative sets.
---

# Mintegral Ads

Use the bundled CLI to call the official Mintegral AppGrowth Open API. Do not construct ad hoc HTTP requests.

## Requirements

- Require Python 3.10 or newer.
- Run commands through `scripts/mintegral_ads.sh`.
- Read `MINTEGRAL_ACCESS_KEY` and `MINTEGRAL_API_KEY` from the environment.
- Keep API hosts fixed to `ss-api.mintegral.com` and, for uploads only, `ss-storage-api.mintegral.com`.
- Never print, save, or pass either credential on the command line.
- Read [references/api.md](references/api.md) before using an unfamiliar action or payload.

Acquire both credentials from Mintegral AppGrowth under **Account > Basic Information**. The script derives the short-lived request token in memory for every request.

## Safety Rules

- Execute GET actions directly when the user requests the data.
- Preview every mutation by default. Require the user's explicit authorization, then rerun with `--execute`.
- Identify the exact campaign, offer, creative set, audience, or publisher ID before mutation.
- On execution, automatically retrieve the affected campaign or offer and require `maintain_by=ADV` when Mintegral returns that field.
- Require `--acknowledge-full-replacement` for bid, budget, and publisher-target actions. These APIs can replace complete regional or publisher settings.
- Preview full-replacement actions against the live current object. Copy the returned `replacement_plan_hash` only after reviewing `before` and `replacement_diff`; require that hash during execution. Never reuse it with a changed payload.
- Require `--confirm-delete` in addition to `--execute` for deletion.
- Use an owner-only JSON payload file for tracking URLs, audience identifiers, or large payloads.
- Do not automatically retry mutations. Retry only safe reads after rate-limit or transient server errors.
- Treat HTTP 2xx as insufficient: require response `code=200`.
- Re-read the affected object after a successful campaign or offer mutation and compare the requested fields. Treat `verified=false` as incomplete verification even when the mutation response returned `code=200`.
- Treat reports, tracking links, audience files, advertiser identifiers, and campaign configuration as sensitive.

## Workflow

1. Check configuration without exposing credentials:

   ```bash
   bash <skill-path>/scripts/mintegral_ads.sh check
   ```

2. Inspect the available fixed actions:

   ```bash
   bash <skill-path>/scripts/mintegral_ads.sh list-actions
   bash <skill-path>/scripts/mintegral_ads.sh describe --action offer-budget
   ```

3. Read the current object before proposing a mutation:

   ```bash
   bash <skill-path>/scripts/mintegral_ads.sh call \
     --action offers \
     --params-json '{"offer_id":123,"limit":10}'
   ```

4. Store the final payload in a JSON file, preview it, explain the impact, and ask for explicit execution approval:

   ```bash
   bash <skill-path>/scripts/mintegral_ads.sh call \
     --action offer-status \
     --params-file /secure/path/offer-status.json
   ```

5. After approval, execute the identical payload:

   ```bash
   bash <skill-path>/scripts/mintegral_ads.sh call \
     --action offer-status \
     --params-file /secure/path/offer-status.json \
     --execute
   ```

6. Summarize changed IDs, previous state, returned state, and verification result. Save raw JSON with `--output` when useful.

## Common Actions

| Action | Behavior |
| --- | --- |
| `balance` | Read account balance |
| `campaigns` / `offers` / `creative-sets` | Read campaigns, offers, or creative sets |
| `report` | Read performance data |
| `campaign-create` / `campaign-update` | Create or update a campaign |
| `offer-create` / `offer-update` | Create or update an offer |
| `offer-status` | Start or stop an offer |
| `offer-bid` | Replace default, geo, or publisher bids; require replacement acknowledgement |
| `offer-budget` | Replace offer budget configuration; require replacement acknowledgement |
| `publisher-target` | Replace publisher allow/block settings; require replacement acknowledgement |
| `tracking-update` | Update click and impression tracking URLs |
| `audience-target` | Update included and excluded target-audience IDs |
| `target-goal` | Update Target-ROAS or Target-CPE goals through the v3 endpoint |
| `creative-set-create` / `creative-set-update` | Create or update a creative set |
| `creative-set-delete` | Delete a creative set; require delete confirmation |
| `creative-upload` / `playable-upload` | Upload a creative file and return its Mintegral MD5 |

## Payload Examples

Pause an offer:

```json
{"offer_id": 123, "status": "STOPPED"}
```

Replace regional bids:

```json
{
  "offer_id": 123,
  "bid_rate": 3.2,
  "bid_rate_by_location": [
    {"country_code": "US", "bid_rate": 4.1},
    {"country_code": "JP", "bid_rate": 4.5}
  ]
}
```

Preview that payload with configured credentials. Review `before`, `replacement_diff`, and the returned `replacement_plan_hash`. Execute the exact same payload only after checking that it contains every regional override that must remain:

```bash
bash <skill-path>/scripts/mintegral_ads.sh call \
  --action offer-bid \
  --params-file /secure/path/bids.json \
  --acknowledge-full-replacement \
  --replacement-plan-hash '<hash from the immediately preceding preview>' \
  --execute
```

If the payload or live Offer changes after preview, discard the hash, preview again, and review the new diff.

Upload a creative after previewing the local file path:

```bash
bash <skill-path>/scripts/mintegral_ads.sh call \
  --action creative-upload \
  --file /absolute/path/video.mp4

bash <skill-path>/scripts/mintegral_ads.sh call \
  --action creative-upload \
  --file /absolute/path/video.mp4 \
  --execute
```

## Failure Handling

- On missing credentials, explain where to obtain them and ask the user to export the two environment variables. Never ask them to paste secrets into a command argument.
- On `maintain_by=AM`, stop: the account manager owns the object and the API caller cannot safely update it.
- On permission denied for publisher-level bidding or targeting, tell the user to request the advanced feature from their Mintegral account manager.
- On a stale timestamp or authentication error, verify local clock accuracy and credential pairing without printing either value.
- On `code=207` for reports, reduce the date window to at most eight days and exclude today/future dates.
- On replacement plan hash mismatch, stop and preview again. Do not bypass the mismatch or reuse an older hash.
- On `verified=false`, show the mismatched fields and do not claim the requested state is active.
- On uncertain fields or enum values, consult the current official documentation and update this skill before execution; do not guess.
