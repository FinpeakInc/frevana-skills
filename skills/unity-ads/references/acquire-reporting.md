# Advertising Statistics API v2

Use this module for advertiser acquisition and SKAdNetwork performance reports.

## Endpoints

```text
GET https://services.api.unity.com/advertise/stats/v2/organizations/{organizationId}/reports/acquisitions
GET https://services.api.unity.com/advertise/stats/v2/organizations/{organizationId}/reports/skan
```

Use a Unity service account with the organization-level `Advertise Stats API Viewer` role. Use the `Advertise Stats API MMP Viewer` role only for an MMP integration.

## Query behavior

- Require timezone-aware ISO 8601 `start` and `end` values. The end is exclusive.
- Require `scale`: `summary`, `hour`, `day`, `week`, or `month`.
- Require comma-separated `metrics`.
- Optionally provide comma-separated `breakdowns` and documented filters.
- Use `format=json` for JSON; CSV is the default.
- Use `eofMarker=true` for large CSV downloads and verify the final marker row.
- Stream report bodies to an owner-only temporary file and atomically move the file into place only after validation succeeds.

Metrics and filters change over time, so consult the official v2 schema rather than freezing a complete list in SKILL.md. Common metrics include `starts`, `views`, `clicks`, `installs`, `spend`, `cpi`, `ctr`, `cvr`, and post-install `d0` through `d28` metrics.

Unity limits this API to one request per second and 30 requests per 30 minutes for each organization and IP address. High-cardinality queries should be requested one day at a time. A `204` response means the request succeeded but no data exists.

Official documentation: https://services.docs.unity.com/statistics/
