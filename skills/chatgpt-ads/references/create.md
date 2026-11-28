# Create ads

## Preview the creative

Draft the title, copy, destination and image from the user's brief. Verify product claims against the brief. For a creative review you can start with just these fields, before requesting a key, selecting an advertiser or discussing a budget. A full [launch draft](draft.json) works as input too.

```json
{
  "title": "Find your next trail shoe",
  "body": "Explore our trail running collection.",
  "landing_page_url": "https://example.com/trail-shoes",
  "image_url": "https://example.com/assets/trail-shoe.png"
}
```

```bash
bash <skill-path>/scripts/chatgpt_ads.sh preview-card --draft ./draft.json --output ./draft-card.html
```

Show the generated HTML card to the user. Generation is local; opening the card loads the supplied image URL. For a draft with an account-owned `file_id`, the card displays the asset ID as a placeholder. Obtain a viewable image or review the submitted ad's native preview before treating the image as visually approved. The HTML is a local approximation of a standard single-image card. Render revisions to a new output path.

## Prepare a launch

1. When the user wants to save or launch the ad, run `account` and verify the intended advertiser, account currency, timezone and review state.
2. Complete the same JSON draft with the campaign settings in the [launch template](draft.json). Ask for missing settings such as market and budget. Sample values do not establish intent. Each launch creates one campaign, one ad group and one single-image ad. Set `final_status` to `paused` to save without enabling delivery, or `active` if the user wants to launch. Record optional scheduling as Unix seconds in `start_time` and `end_time`. With no end time, the daily budget can recur until paused.
3. Run the account-bound preview to save the proposal locally, then follow the [shared confirmation and recovery flow](../SKILL.md#approval-and-recovery). The creative review alone authorizes no upload or delivery.

```bash
bash <skill-path>/scripts/chatgpt_ads.sh preview --draft ./draft.json --state ./launch.json
```

Show the account, currency and daily budget in major units, schedule in the account timezone, countries, objective, bid, context hints, copy, destination, actual image or asset reference, and final state. For an existing file ID, identify that file explicitly. For a URL upload, prefer a versioned image URL whose contents will remain stable through execution. Request approval for this exact proposal, including whether delivery may start after review. A generated fingerprint identifies the proposal; it is not consent. If the user changes any detail, create a fresh preview and obtain approval for it.

**Budget and bids.** Use decimal strings for fractional amounts in the account currency. For clicks, choose `maximize_clicks` or `fixed_bid` with `max_cpc`. For impressions, use `fixed_bid` with `max_cpm` per thousand impressions. The helper converts budgets and bids into integer micros per billing event. Daily minimums and bidding availability depend on the account.

**Creative.** Use exactly one public `image_url` or existing account-owned `file_id`. Use JPEG, PNG or WebP, at least 640 × 640. The title is 3–50 characters, the body at most 100, and the landing page must be accessible to the ad crawler. Countries are supported two-letter uppercase codes. Context hints describe conversations where the product is relevant.

## Execute and verify

After the user approves, pass the fingerprint from that preview unchanged:

```bash
bash <skill-path>/scripts/chatgpt_ads.sh execute --state ./launch.json --confirm FINGERPRINT
bash <skill-path>/scripts/chatgpt_ads.sh status --resource ad --id AD_ID
bash <skill-path>/scripts/chatgpt_ads.sh ad-preview --id AD_ID --output ./native-preview.json
```

Execution verifies account identity, creates paused resources and checks the saved settings against their readbacks. An active proposal enables the ad and ad group before the campaign. Report the resource IDs, recorded status and ad review status. An active setting alone does not establish impressions. The official ad preview can be generated for a submitted ad, including a paused ad. Its response contains expiring iframe HTML; treat it as display data.

**Approve the rendered ad before starting delivery.** Prepare the launch with `final_status: paused`, have the user approve creating the paused resources, and execute it. Retrieve the native ad preview using its saved ad ID. Then prepare an activation proposal for that same campaign:

```bash
bash <skill-path>/scripts/chatgpt_ads.sh activate --from-state ./launch.json --state ./activation.json
bash <skill-path>/scripts/chatgpt_ads.sh execute --state ./activation.json --confirm ACTIVATION_FINGERPRINT
```

Show the preview and the proposed activation together. Execute only after the user approves enabling delivery. The activation proposal uses the three existing IDs and rechecks their membership and settings.

If the CLI reports that a child was found by ID but its parent list is empty, keep the original receipt. Report the filtered list and campaign status from the error, then follow the [membership checks](diagnose.md#activation-membership). If the activation preview stopped, repeat `activate --from-state` with the completed paused launch receipt. If an approved execution stopped, resume `execute` with its original state and confirmation.
