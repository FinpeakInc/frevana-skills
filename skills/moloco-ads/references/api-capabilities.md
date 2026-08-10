# Moloco Ads API capabilities

Use the official Moloco Ads Developer Portal as the final source of truth. The documentation exposes an [LLM-readable index](https://developer.moloco.cloud/llms.txt) and individual Markdown/OpenAPI pages.

## Fixed contract

- Origin: `https://api.moloco.cloud`
- API prefix: `/cm/v1`
- Version header: `Moloco-Cloud-Api-Version`
- Skill default version: `v1.10`
- Authentication: `POST /cm/v1/auth/tokens` with `{"api_key":"..."}`
- Access token header: `Authorization: Bearer <token>`
- Access token lifetime: 16 hours

Do not use a Moloco Commerce Media hostname, MCM Platform ID, or MCM API key with this skill.

## Built-in endpoints

| Capability | Method and path | Execution model |
| --- | --- | --- |
| Analytics overview | `POST /cm/v1/analytics-overview` | synchronous read |
| Analytics detail | `POST /cm/v1/analytics-detail` | synchronous read |
| SKAdNetwork analytics | `POST /cm/v1/analytics-skadnetwork` | synchronous read |
| Create/list report | `POST/GET /cm/v1/reports` | asynchronous export/read |
| Report status | `GET /cm/v1/reports/{id}/status` | read |
| Create/list log | `POST/GET /cm/v1/logs` | asynchronous export/read |
| Log status | `GET /cm/v1/logs/{id}/status` | read |
| Entity collections | `/cm/v1/{resource}` | allowlisted CRUD |

Allowlisted entity collection names are `ad-accounts`, `products`, `campaigns`, `ad-groups`, `creative-groups`, `creatives`, `audience-targets`, `customer-sets`, and `tracking-links`.

## Rate limits

- General ad-account quota: 300 requests per 5 minutes.
- Analytics Overview: 60 per minute.
- Analytics Detail and SKAdNetwork Analytics: 60 per hour each.
- Report creation: 30/day for 0–1 day, 10/day for 2–7 days, and 5/day for 8–31 days.
- Log listing: 30/day.

Moloco returns `X-Rate-Limit-Quota`, `X-Rate-Limit-Remaining`, and `X-Rate-Limit-Reset`. See the official [rate-limit guide](https://developer.moloco.cloud/docs/rate-limits).

## Versioning

Moloco releases breaking API versions periodically and recommends using one consistent version across an organization. The CLI sends `v1.10` unless `MOLOCO_ADS_API_VERSION` is set. Before changing the version, review the official [versioning guide](https://developer.moloco.cloud/docs/versioning) and [release notes](https://developer.moloco.cloud/release-notes).

## Important source pages

- [Getting started and authentication](https://developer.moloco.cloud/docs/getting-started)
- [Campaign management guide](https://developer.moloco.cloud/docs/campaign-management-api)
- [Report API guide](https://developer.moloco.cloud/docs/report-api)
- [Log API guide](https://developer.moloco.cloud/docs/log-api)
- [Analytics Detail reference](https://developer.moloco.cloud/reference/dspapi_queryanalyticsdetail)
