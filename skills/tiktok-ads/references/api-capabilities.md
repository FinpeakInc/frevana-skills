# TikTok Business API v1.3 capabilities

Use the official API reference as the runtime source of truth:

- API v1.3 reference: <https://business-api.tiktok.com/portal/docs/api-reference/v1.3>
- Authorization concepts and workflow: <https://business-api.tiktok.com/portal/docs>
- API host: `https://business-api.tiktok.com`
- Version prefix: `/open_api/v1.3/`

The bundled client calls the REST API directly and does not install or import TikTok's SDK.

## Endpoint families

- Authentication: authorization-code token exchange, advertiser grants, token lifecycle
- Ad Accounts: account details and configuration
- Campaign: create, retrieve, update, copy, status, budget, and quota operations
- Ad Groups: create, retrieve, update, status, budget, quota, targeting, bidding, and review
- Ads: create, retrieve, update, status, review, appeals, Smart Creative, and Spark Ads
- Creatives and Files: image, video, music, playable, portfolio, creative tools, and multipart uploads
- Reporting: synchronous and asynchronous reports, creative reports, GMV Max, Business Center, and attribution data
- Audience: customer files, rule-based, lookalike, saved, shared, applied, and insight audiences
- Measurement: pixels, events, offline events, CRM events, apps, and custom conversions
- Business Center: centers, assets, groups, members, partners, billing, balances, transactions, and payments
- Catalog and Commerce: catalogs, feeds, products, product sets, diagnostics, insights, videos, stores, and GMV Max
- Automated Rules: create, inspect, update, bind, status, and results
- Comments and Blocked Words: list, reply, delete, status, export, and moderation
- Tools: locations, languages, targeting, keywords, devices, bids, URLs, time zones, and diagnostics
- Webhooks and Subscriptions: app subscriptions and account/business messaging events

## Generic request routing

Use a built-in action when one matches. For another documented endpoint, supply the method and full versioned path:

```bash
bash <skill-path>/scripts/tiktok_ads.sh call \
  --method GET \
  --path /open_api/v1.3/<documented-path>/ \
  --params-file /secure/path/params.json
```

The client rejects:

- absolute URLs or alternate hosts
- paths outside `/open_api/v1.3/`
- embedded queries or fragments
- `..` path traversal
- methods outside GET, POST, PUT, PATCH, and DELETE

For GET, nested dictionaries and lists are compact JSON inside query parameters. For non-GET requests, parameters are sent as JSON unless `--file FIELD=PATH` is present, in which case the request uses streaming multipart form data.

## OAuth flow

The authorization URL uses:

```text
https://ads.tiktok.com/marketing_api/auth
  ?app_id=<APP_ID>
  &state=<RANDOM_STATE>
  &redirect_uri=<REGISTERED_CALLBACK>
  [&scope=<SCOPES>]
```

After a successful callback, exchange `auth_code` at:

```text
POST /open_api/v1.3/oauth2/access_token/
```

with `app_id`, `secret`, and `auth_code`. TikTok documents `auth_code` as one-time and valid for one hour. Always validate `state` before exchange.

The long-term Marketing API flow does not use a Refresh Token; TikTok deprecated `/oauth2/refresh_token/` after introducing long-term tokens. If credentials originate from the short-term TikTok account flow and include a Refresh Token, retain it and renew through:

```text
POST /open_api/v1.3/tt_user/oauth2/refresh_token/
```

Send `client_id`, `client_secret`, `grant_type=refresh_token`, and `refresh_token`. Save the complete returned token set because TikTok may rotate the Refresh Token.
