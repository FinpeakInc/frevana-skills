# Sensor Tower API reference

The bundled CLI uses the following endpoints from the source repository:

| Action | Endpoint |
|---|---|
| `search` | `/v1/{os}/search_entities` |
| `sales` | `/v1/{os}/sales_report_estimates` |
| `top-charts` | `/v1/{os}/top_charts`; iOS uses `itunes` |
| `active-users` | `/v1/{os}/active_users`; iOS uses `itunes` |
| `publisher-apps` | `/v1/{os}/publisher_apps`; iOS uses `itunes` |
| `ad-intelligence` | `/v1/unified/ad_intel/{action}` |

The default origin is `https://api.sensortower.com`. For a controlled test environment only, set `SENSORTOWER_API_BASE_URL` to another HTTPS origin.

Authentication uses the provider's `auth_token` query parameter. The CLI never includes the prepared URL or raw exception in diagnostics because those values may contain the credential.

Use `python3 <skill-path>/scripts/sensortower.py <action> --help` for the authoritative parameter list.

The CLI returns provider JSON without normalizing money or response objects. Do not silently treat missing or malformed values as zero. When summarizing revenue, confirm the endpoint's unit for the account/API version in use.

