---
name: tiktok-ads
description: Manage TikTok advertising by calling the official TikTok Business API v1.3 directly. Use when the user wants to authorize a TikTok developer app through a local OAuth callback, obtain, inspect, or refresh an Access-Token, retain and rotate a Refresh Token, inspect authorized advertisers or ad accounts, list/create/update campaigns, ad groups, ads, and creatives, change delivery status, upload assets, query reports, manage audiences, pixels, catalogs, Business Center resources, automated rules, comments, or call another documented v1.3 endpoint. Provides fixed-host HTTP requests, local credential reuse, multipart uploads, secret redaction, read execution, mutation previews, and explicit execution gates without an SDK dependency.
---

# TikTok Ads

Operate TikTok advertising by calling the official Business API v1.3 directly. Use the bundled wrapper instead of an SDK or handwritten HTTP request.

## Requirements

- Require Python 3 only; do not install the TikTok SDK.
- Run commands through `scripts/tiktok_ads.sh`.
- Keep the API host fixed to `https://business-api.tiktok.com` and paths under `/open_api/v1.3/`.
- Use the official [API v1.3 reference](https://business-api.tiktok.com/portal/docs/api-reference/v1.3) as the source of truth for parameters and endpoint availability.

## Authorization

`TIKTOK_ADS_APP_ID` and `TIKTOK_ADS_APP_SECRET` are read from environment variables or user input. If either is missing, in the same response show the setup guide and ask the user to provide the missing value(s), then **end the turn immediately** — do not block or loop waiting for a reply. Resume only when the user responds with the values:

> **https://frevana.gitbook.io/frevana-docs/integrations/tiktok-ads-integration**


Run the local OAuth flow when no Access-Token is available:

```bash
bash <skill-path>/scripts/tiktok_ads.sh authorize
```

**Run this command as a background task** (do not wait for it to complete synchronously). The command will block internally while waiting for the user to complete authorization in the browser — the agent must not block alongside it. Instead:

1. Launch the command as a background task.
2. In the same response, output the authorization URL printed by the command and tell the user: the browser has been opened automatically; if it did not open, they can copy the URL and open it manually; **after completing authorization in the browser, please reply "授权完成" to continue**.
3. When the user replies that authorization is complete, verify the background task has finished successfully, then **immediately proceed to the next step without asking for any further reply**.

The command:

1. Binds an HTTP callback server only to `localhost` (also accepts `127.0.0.1`).
2. Generates a cryptographically random `state`, prints the TikTok authorization URL as plain text, and automatically opens it in the default browser simultaneously.
3. Waits for the user to complete authorization in the browser at `http://localhost:51021/callback` by default. Once the user finishes, the callback is received automatically and the flow continues without any further user input.
4. Validates the callback path and `state`.
5. Exchanges the one-time `auth_code` through `POST /open_api/v1.3/oauth2/access_token/`.
6. Saves the Access-Token and any returned Refresh Token in `${XDG_CONFIG_HOME:-~/.config}/tiktok-ads/credentials.json` with mode `0600`.
7. Prints "Authorization complete" — at this point the agent resumes and continues.


Configure the exact redirect URI in the TikTok developer app before starting. TikTok requires the authorization URL redirect URI to match the registered callback. A loopback URI works only if TikTok accepts and the app registers that exact URI; otherwise use an approved public HTTPS callback or tunnel rather than binding the local server publicly.

Use overrides only when needed:

```bash
bash <skill-path>/scripts/tiktok_ads.sh authorize \
  --app-id '<app id>' \
  --app-secret-file /secure/path/app-secret \
  --redirect-uri http://localhost:9876/tiktok/callback \
  --scope 'scope1,scope2' \
  --timeout 600
```

The authorization URL is automatically opened in the default browser. If the browser does not open, copy and paste `authorization_url` manually. Never print or save the App Secret. Treat `auth_code`, Access-Token, and refresh token as secrets.

Inspect saved authorization without exposing tokens:

```bash
bash <skill-path>/scripts/tiktok_ads.sh auth-status
```

Preserve and use the Refresh Token flow when TikTok returns one for a short-term TikTok account authorization:

```bash
export TIKTOK_ADS_APP_SECRET='<app secret>'
bash <skill-path>/scripts/tiktok_ads.sh refresh-token
unset TIKTOK_ADS_APP_SECRET
```

The refresh command calls `POST /open_api/v1.3/tt_user/oauth2/refresh_token/`, saves both the new Access-Token and a rotated Refresh Token, and records calculated expiry timestamps when TikTok returns `expires_in` values. It preserves the prior Refresh Token if the response omits an unchanged value. Never discard a newly returned Refresh Token.

This refresh endpoint applies only to short-term TikTok account tokens. The advertising authorization flow above obtains a long-term Marketing API token through `/oauth2/access_token/`; TikTok deprecated `/oauth2/refresh_token/` for those long-term tokens. If saved credentials have no Refresh Token, do not manufacture one or call the short-term endpoint—reauthorize only after the long-term token becomes invalid.

Credential resolution order for API calls:

1. `--access-token-file`, accepting a raw token or owner-only credentials JSON
2. `TIKTOK_ADS_ACCESS_TOKEN`
3. the saved credentials file

Resolve App ID from `--app-id`, `TIKTOK_ADS_APP_ID`, or saved credentials. Resolve App Secret only from `--app-secret-file` or `TIKTOK_ADS_APP_SECRET`.

## Safety Rules

- Never allow an alternate API host, absolute request URL, path outside `/open_api/v1.3/`, path traversal, or URL query embedded in `--path`.
- Require secret files to be regular, non-symlink, current-user-owned files with mode `0400` or `0600`.
- Send the Access-Token only in the official `Access-Token` header. Redact token and secret fields from terminal output.
- Treat every non-GET operation as a mutation. Preview it by default and require `--execute` after explicit user confirmation.
- Identify exact advertiser, campaign, ad group, ad, audience, pixel, catalog, Business Center, and creative IDs before mutation.
- Before changing budgets, bids, schedules, targeting, billing, or delivery status, retrieve and compare the current object.
- Before deletes, transfers, audience sharing, Business Center membership/asset changes, or bulk operations, verify every target and explain impact.
- After mutation, retrieve the affected object or status. Treat a nonzero TikTok response `code` as failure even when HTTP status is 2xx.
- Do not automatically retry mutations. Report rate limits and wait for user direction.
- Treat customer lists, audience files, reports, comments, and identifiers as sensitive.

## Workflow

1. Check the runtime and fixed target:

   ```bash
   bash <skill-path>/scripts/tiktok_ads.sh check
   ```

2. List or describe common actions:

   ```bash
   bash <skill-path>/scripts/tiktok_ads.sh list-actions
   bash <skill-path>/scripts/tiktok_ads.sh describe --action campaigns
   ```

3. Read the exact endpoint in the official reference. Put large or sensitive parameters in an owner-only JSON file.

4. Execute GET reads directly. Preview writes, confirm the final payload and target IDs, then rerun with `--execute`.

5. Summarize useful IDs, status, pagination, spend, and TikTok error details. Use `--output` for raw JSON; output files are mode `0600` and token fields remain redacted on screen.

## Common Actions

| Action | Official endpoint | Behavior |
| --- | --- | --- |
| `advertisers` | `GET /oauth2/advertiser/get/` | Read; needs App ID and Secret, not Access-Token |
| `account-get` | `GET /advertiser/info/` | Read |
| `campaigns` | `GET /campaign/get/` | Read |
| `campaign-create` | `POST /campaign/create/` | Preview/write |
| `campaign-update` | `POST /campaign/update/` | Preview/write |
| `campaign-status` | `POST /campaign/status/update/` | Preview/write |
| `adgroups` | `GET /adgroup/get/` | Read |
| `adgroup-create` | `POST /adgroup/create/` | Preview/write |
| `adgroup-update` | `POST /adgroup/update/` | Preview/write |
| `adgroup-status` | `POST /adgroup/status/update/` | Preview/write |
| `ads` | `GET /ad/get/` | Read |
| `ad-create` | `POST /ad/create/` | Preview/write |
| `ad-update` | `POST /ad/update/` | Preview/write |
| `ad-status` | `POST /ad/status/update/` | Preview/write |
| `report` | `GET /report/integrated/get/` | Read |

All paths are automatically prefixed with `/open_api/v1.3`. Read [references/api-capabilities.md](references/api-capabilities.md) to select other endpoint families.

## Examples

List campaigns using saved authorization:

```bash
bash <skill-path>/scripts/tiktok_ads.sh call \
  --action campaigns \
  --params-json '{"advertiser_id":"123456789","page":1,"page_size":20}'
```

Preview and then create a campaign:

```bash
bash <skill-path>/scripts/tiktok_ads.sh call \
  --action campaign-create \
  --params-file /secure/path/campaign-create.json

bash <skill-path>/scripts/tiktok_ads.sh call \
  --action campaign-create \
  --params-file /secure/path/campaign-create.json \
  --execute
```

Call another documented v1.3 endpoint:

```bash
bash <skill-path>/scripts/tiktok_ads.sh call \
  --method GET \
  --path /open_api/v1.3/dmp/custom_audience/list/ \
  --params-json '{"advertiser_id":"123456789","page":1,"page_size":20}'
```

Upload a local file with streaming multipart encoding:

```bash
bash <skill-path>/scripts/tiktok_ads.sh call \
  --method POST \
  --path /open_api/v1.3/file/video/ad/upload/ \
  --params-json '{"advertiser_id":"123456789","upload_type":"UPLOAD_BY_FILE"}' \
  --file video_file=/absolute/path/video.mp4
```

Preview the upload first, then add `--execute` after confirmation.

## Failure Handling

- If the callback is rejected, verify the exact registered redirect URI, App ID, requested scope, and TikTok support for the loopback address.
- If the callback times out, rerun authorization; do not reuse an old `state` or `auth_code`.
- If the OAuth callback was received successfully but the `auth_code → access_token` exchange fails (network reset, timeout, or HTTP error), this is a transient network problem. Tell the user to rerun the full `authorize` command and try again. Do NOT ask the user to manually provide an Access Token as a workaround — the Access Token is obtained exclusively through the automated OAuth exchange and must never be entered by hand.
- If TikTok returns an authorization error, verify app approval, permissions, advertiser grant, and token validity without exposing credentials.
- If an endpoint rejects parameters, compare the payload directly with the official v1.3 reference; do not infer SDK model names.
- If TikTok returns a rate-limit response, report it and do not retry a mutation automatically.
- If a newer endpoint uses a different version prefix, update and review the skill before calling it; do not bypass the fixed v1.3 restriction ad hoc.
