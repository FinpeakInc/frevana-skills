# Mintegral AppGrowth Open API Reference

Use this reference for action selection and safety semantics. Check the linked official documentation before sending fields not represented here.

## Authentication

Send these headers on every request:

```text
access-key: MINTEGRAL_ACCESS_KEY
timestamp: current Unix time in seconds
token: md5(MINTEGRAL_API_KEY + md5(timestamp))
```

Official documentation:

- [API overview](https://helpcenter.mintegral.com/en/docs/quick-start-api)
- [Token generation](https://helpcenter.mintegral.com/en/docs/token-api/retargeting-mmp-key-events-postback-overview)
- [Enumeration values](https://helpcenter.mintegral.com/en/docs/enumeration/retargeting-mmp-key-events-postback-overview)

## Fixed Actions

| Action | Method | Path | Required payload fields |
| --- | --- | --- | --- |
| `balance` | GET | `/api/open/v1/account/balance` | none |
| `campaigns` | GET | `/api/open/v1/campaign` | none |
| `offers` | GET | `/api/open/v1/offers` | none |
| `creative-sets` | GET | `/api/open/v1/creative_sets` | none; filter by offer or creative-set ID/name |
| `report` | GET | `/api/v1/reports/data` | none; dates default to yesterday |
| `campaign-create` | POST | `/api/open/v1/campaign` | `campaign_name`, `promotion_type`, `preview_url` |
| `campaign-update` | PUT | `/api/open/v1/campaign` | `campaign_id` |
| `offer-create` | POST | `/api/open/v1/offer` | `campaign_id`, `offer_name` |
| `offer-update` | PUT | `/api/open/v1/offer` | `offer_id` |
| `offer-bid` | PUT | `/api/open/v1/offer/bid_rate` | `offer_id`; bid fields per offer model |
| `offer-budget` | PUT | `/api/open/v1/offer/budget` | `offer_id`, `budget` |
| `offer-status` | PUT | `/api/open/v1/offer/status` | `offer_id`, `status` |
| `publisher-target` | PUT | `/api/open/v1/offer/target` | `offer_id`, `option` |
| `tracking-update` | PUT | `/api/open/v1/tracking` | `offer_id`, `tracking_method` |
| `audience-target` | PUT | `/api/open/v1/offer/target-audience` | `offer_id`, `include_ta_id`, `exclude_ta_id` |
| `target-goal` | PUT | `/api/open/v3/offer/target_goal` | `offer_id` plus goal fields |
| `creative-set-create` | POST | `/api/open/v1/creative_set` | `creative_set_name`, `ad_outputs`, `creatives` |
| `creative-set-update` | PUT | `/api/open/v1/creative_set` | `offer_id`, `creative_set_name` |
| `creative-set-delete` | DELETE | `/api/open/v1/creative_set` | `offer_id`, `creative_set_name` |
| `creative-upload` | POST multipart | `/api/open/v1/creatives/upload` | local `--file` |
| `playable-upload` | POST multipart | `/api/open/v1/playable/upload` | local `--file` |

## Full-Replacement Hazards

Treat these actions as complete replacements and include every setting that must remain:

- `offer-bid`: missing geo or publisher overrides may revert to the default bid. Empty arrays remove overrides.
- `offer-budget`: when maintaining budgets by area, cover all targeted areas without overlapping a country in multiple entries.
- `publisher-target`: Mintegral documents this as a full update. `ALLOW_ALL` can clear existing restrictions.

Previewing these actions performs a safe live read and returns:

- `before`: the exact current object;
- `replacement_diff`: fields changed, omitted, or not returned by Mintegral;
- `replacement_plan_hash`: SHA-256 over the action, current object, and exact payload.

Execution requires both `--acknowledge-full-replacement` and `--replacement-plan-hash`. The CLI re-reads the object and recomputes the hash before sending the mutation. A changed object or payload invalidates the plan and forces a new preview.

## Important Enums

- Offer mutable delivery status: `RUNNING`, `STOPPED`.
- Publisher target option: `ENABLE`, `DISABLE`, `ALLOW_ALL`.
- Pricing models include `CPI`, `CPC`, `CPM`, and account-enabled goal models.
- Tracking methods include `ADJUST`, `APPSFLYER`, `KOCHAVA`, `SINGULAR`, `TENJIN`, `S2S`, `BRANCH`, and other documented values.
- Creative-set update option: `ENABLE`, `DISABLE`.

Do not submit non-mutable status values such as `OVER_CAP` or `INSUFFICIENT_ACCOUNT_BALANCE` as desired delivery states.

## Reporting Limits

The performance report endpoint:

- can retrieve data from at most 30 days ago;
- only exposes yesterday or earlier;
- accepts at most eight days per request;
- accepts `per_page` up to 5000;
- returns `code=207` when the date range violates its constraints.

The CLI exposes one report request at a time. Split longer ranges into safe windows before calling it and merge only raw rows with compatible dimensions.

## Official Endpoint Documentation

- [Campaign list/create/update](https://adv-new.mintegral.com/doc/en/guide/campaign/getCampaign.html)
- [Offer list](https://adv-new.mintegral.com/doc/en/guide/offer/getOffer.html)
- [Offer creation](https://adv-new.mintegral.com/doc/en/guide/offer/createOffer.html)
- [Offer bid update](https://adv-new.mintegral.com/doc/en/guide/offer/updateBidrate.html)
- [Offer budget update](https://adv-new.mintegral.com/doc/en/guide/offer/updateBudget.html)
- [Offer status update](https://adv-new.mintegral.com/doc/en/guide/offer/updateStatus.html)
- [Tracking URL update](https://adv-new.mintegral.com/doc/en/guide/offer/updateTracking.html)
- [Target goal update](https://adv-new.mintegral.com/doc/en/guide/offer/updateTargetGoal.html)
- [Creative-set creation](https://adv-new.mintegral.com/doc/en/guide/creative_set/createCreativeSet.html)
- [Creative-set querying](https://adv-new.mintegral.com/doc/en/guide/creative_set/getCreativeSet.html)
- [Creative upload](https://adv-new.mintegral.com/doc/en/guide/creative/uploadCreative.html)
- [Performance report](https://adv-new.mintegral.com/doc/en/guide/report/performanceReport)
