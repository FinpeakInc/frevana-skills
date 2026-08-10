# Campaign management

## Entity relationships

A typical campaign depends on an ad account, product, tracking link, creatives, creative groups, campaign, and one or more ad groups. Reuse existing entities when appropriate and create prerequisites before creating a campaign.

Supported CLI resources:

| Resource | Collection path | Common create query fields |
| --- | --- | --- |
| Ad account | `/cm/v1/ad-accounts` | none |
| Product | `/cm/v1/products` | `ad_account_id` |
| Campaign | `/cm/v1/campaigns` | `ad_account_id`, `product_id` |
| Ad group | `/cm/v1/ad-groups` | `ad_account_id`, `product_id`, `campaign_id` |
| Creative group | `/cm/v1/creative-groups` | `ad_account_id`, `product_id` |
| Creative | `/cm/v1/creatives` | `ad_account_id`, `product_id` |
| Audience target | `/cm/v1/audience-targets` | `ad_account_id` |
| Customer set | `/cm/v1/customer-sets` | `ad_account_id` |
| Tracking link | `/cm/v1/tracking-links` | `ad_account_id`, `product_id` |

Use `--params-file` for additional documented query parameters. Payloads must use the exact current OpenAPI schema; the CLI deliberately does not guess or rewrite entity fields.

## Mutation workflow

1. Resolve exact resource IDs and list existing prerequisites.
2. For update or delete, retrieve the current entity.
3. Prepare the complete documented payload in a local JSON file.
4. Run without `--execute` and inspect the preview.
5. Confirm the exact target, delivery impact, budget, bid, schedule, targeting, and state changes.
6. Rerun with `--execute`.
7. For updates, compare the CLI's `before`, mutation `response`, and `after` objects.

Moloco entity update endpoints use PUT and can expect a complete resource representation. Do not assume PATCH semantics. Preserve unknown enum values and server-returned fields when the current API version requires them to be echoed back.

## Campaign-specific cautions

- Campaigns require valid prerequisite objects and mapped app events for some CPA/ROAS goals.
- Campaigns become eligible for delivery only after Moloco's preparation and review states complete.
- `enabling_state=ENABLED` can activate spending when the campaign is eligible and on schedule.
- A campaign that has ever been activated might not be deletable; pausing with `enabling_state=DISABLED` may be the appropriate operation.
- Starting with API v1.10, enabling a campaign can require acknowledgement of returned launch notices. Retrieve the current campaign and preserve required confirmation fields.
- Creative asset upload uses a separate upload-session flow and pre-signed storage URL. The generic entity commands do not upload asset bytes.

Consult the official [campaign management guide](https://developer.moloco.cloud/docs/campaign-management-api) and the relevant endpoint's OpenAPI page immediately before a write.
