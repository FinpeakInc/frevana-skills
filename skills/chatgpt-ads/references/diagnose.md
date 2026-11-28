# Diagnose delivery, measurement and access

Use read-only evidence to find the first constraint that explains the symptom. Record the account, resource, time window and observed state. If an upstream resource is paused, a child can still show its own status as active.

1. Run `account` to verify account identity, status, review and timezone. For delivery questions, read the relevant account-local [performance report](analyze.md).
2. Trace the selected campaign, ad group and ad with `status --resource campaign|ad_group|ad --id ID`, using each resource's own ID. Inspect the parent status, schedule, budget, targeting and ad review. For serving issues, run `read get-ad --param ad_id=ID --query ./include.json` with `{"include":["serving_issues"]}`. If relevant, check ad-group low-bid diagnostics or landing-page crawler evidence in the [operation guide](advertiser-operations.md#pixel-events-attribution-and-diagnosis).
3. For missing conversions, read `list-conversion-sources` and `list-conversion-event-settings` through the CLI's `read` command. Check the reporting window, attribution settings and the intended Pixel before interpreting an empty report.
4. Report the observed constraint, what remains unknown and how to verify recovery. If the user requests a fix, switch to [Manage](manage.md) and prepare a new proposal for the specific change.

## Activation membership

Use the receipt IDs to distinguish the detail lookup from the parent-filtered list. For example, if `status --resource ad --id AD_ID` succeeds and `list-ads` with `ad_group_id=GROUP_ID` returns an empty page, report “Ad AD_ID was found by ID. The list for group GROUP_ID is empty, so its membership is still unconfirmed.” Include the observed campaign status. An empty list alone cannot establish a broken link or its cause. When the original calls are unavailable, identify which checks you ran now.

For a child created within the last minute, the CLI retries a complete, empty list after 1, 2 and 4 seconds. It rechecks both lists and the approved settings before continuing. If the list stays empty, recheck the existing IDs with the same receipt. If a list returns an unexpected ID, a conflicting parent or incomplete pagination, stop activation and report the list filter and observed evidence. Resolve the scope before enabling delivery.

## Account access

| 403 on | What to check |
| --- | --- |
| Account spending limits | Even reading limits requires permission to manage billing on the selected ad account. Ask its admin to check **Billing → Account limits** and eligibility for postpaid invoice billing. After a billing change, existing daily limits can still be viewed and removed. A generic account-access error does not identify which condition failed. [Official limit requirements](https://developers.openai.com/ads/api-reference/ad-account#account-spending-limits) |
| Lead Sync subscriptions | If the API says Lead Sync is disabled, contact the OpenAI Ads representative or `ads-support@openai.com` with the ad account ID and exact error to request enablement. For a generic 403, verify the credential's access to that account first. With OAuth, reads require `ads.admin.all.read`; creating or deleting also requires `ads.admin.all.write`. After access is confirmed, verify with the subscription list GET. [Official API contract](https://developers.openai.com/ads/openapi.json) |
