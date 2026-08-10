# Monetization Stats API

Use this module only for publisher monetization reporting.

## Endpoint and authentication

```text
GET https://monetization.api.unity.com/stats/v1/operate/organizations/{organizationId}
Authorization: Token {apiKey}
```

Obtain the API key from the Unity Monetization dashboard under Setup > API Access. Treat it as a secret. Organization transfer changes the Organization ID.

Unity redirects authenticated report requests to the data response. Follow HTTPS redirects, preserve authentication only for the same origin, and strip authentication before every cross-origin request.

## Parameters

- Require `fields`: `adrequest_count`, `start_count`, `view_count`, `available_sum`, `revenue_sum`.
- Require `scale`: `hour`, `day`, `week`, `month`, `year`, or `all`.
- Require timezone-aware ISO 8601 `start` and `end` values.
- Optionally split with `groupBy`: `placement`, `country`, `platform`, or `game`.
- Optionally filter with comma-separated `gameIds`.
- Select CSV with `Accept: text/csv` or JSON with `Accept: application/json`.

Requests that split large ranges across several dimensions can exceed Unity's 60-second processing timeout. Reduce the range or dimensions rather than repeatedly retrying the same large request.

Official documentation: https://docs.unity.com/en-us/grow/ads/optimization/monetization-stats-api
