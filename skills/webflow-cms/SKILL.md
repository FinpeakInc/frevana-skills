---
name: webflow-cms
description: Publish or update Webflow CMS collection items through Data API v2 live endpoints, discover collections and fields, and inspect staged or live items. Use for Webflow CMS editorial publishing, not Designer layouts or whole-site deployment.
---

# Webflow CMS

Publish final HTML to a Webflow CMS Collection or update an exact item ID. Follows the Frevana App's v2 live-item publishing contract. Requires Python 3 and Bash; no Frevana token, daemon, or browser extension.

## Configure and discover

Credentials/settings resolve per field: command-line option, environment, then local JSON config. Keep API tokens in environment variables or the hidden interactive prompt, outside chat, content payloads, and repository files.

| Environment variable | Purpose |
| --- | --- |
| `WEBFLOW_API_TOKEN` | Webflow token with `cms:read` and `cms:write` access to the site |
| `WEBFLOW_SITE_ID` | Destination Site ID |
| `WEBFLOW_SITE_URL` | Required HTTPS website origin for frontend candidate URLs, e.g. `https://example.webflow.io` or the site's custom domain |
| `WEBFLOW_COLLECTION_ID` | Exact destination Collection ID |
| `WEBFLOW_CONTENT_FIELD_SLUG` | Selected RichText body field slug |
| `WEBFLOW_NAME_FIELD_SLUG` | Name field; defaults to `name` |
| `WEBFLOW_SLUG_FIELD_SLUG` | URL slug field; defaults to `slug` |
| `WEBFLOW_SUMMARY_FIELD_SLUG` | Optional PlainText summary field |

```bash
bash <skill-path>/scripts/webflow_cms.sh status
bash <skill-path>/scripts/webflow_cms.sh configure
bash <skill-path>/scripts/webflow_cms.sh collections
bash <skill-path>/scripts/webflow_cms.sh fields --collection-id COLLECTION_ID
```

`configure` requires Site ID, Site URL, and API Token, prompting for missing values when interactive. It saves resolved values with mode `0600` to `${WEBFLOW_CONFIG_FILE:-${XDG_CONFIG_HOME:-$HOME/.config}/webflow-content/config.json}`. Use `--config FILE` to override. New directories use `0700`; existing parent permissions are preserved. JSON keys are lowercase names without `WEBFLOW_`, such as `site_id`, `site_url`, `api_token`, `collection_id`, `content_field_slug`. Re-run `configure` with the selected `--collection-id`, `--content-field-slug`, and optional summary mapping to save them.

`status` verifies site access by listing collections; with a selected collection it also reads its schema. If credentials/settings are missing or the user asks how to obtain them, show the [Frevana Webflow Integration guide](https://frevana.gitbook.io/frevana-docs/cms-integrations/webflow-integration) and identify the missing fields. The wrapper returns this link as `setupGuide` on missing configuration. The guide covers obtaining the token and site details, preparing a Collection, binding its body to a Collection Page, and publishing that page. Do not ask the user to paste tokens into chat or invent missing values.

Site URL is required for configuration, connection checks, discovery/reads, and create/update previews or execution. Use the actual public website origin, not a Webflow Designer/admin URL, and do not invent a domain from Site ID. Existing saved configurations without Site URL must be completed before proceeding; do not publish first and defer the frontend link because the domain is missing. For example:

```bash
bash <skill-path>/scripts/webflow_cms.sh configure --site-url https://example.webflow.io
```

Discover Collection IDs and field slugs through the helper after connection. A CMS item API success does not prove that a Collection Page exists or displays its body; when content is absent on the public page, check the guide's Post Body binding and page publication steps. The App UI's “Connected” state does not supply credentials to this independent skill. Do not read encrypted desktop storage. See [API and App behavior](references/api.md) for setup details and endpoint links.

Resolve the destination from actual collections and read its fields before preparing the payload. Use exact field **slugs**, not labels or field IDs. When several RichText fields could hold the body, resolve the intended field with the user/context. Do not create a field, change the Collection schema, or choose the first RichText field silently.

The local credential file path retains `webflow-content` for compatibility with configurations saved before the skill was renamed.

## Prepare final content

Example JSON payload:

```json
{
  "title": "Summer guide",
  "slug": "summer-guide",
  "bodyHtml": "<p>Final article HTML.</p>",
  "summary": "Optional summary",
  "fieldData": {"author": "EXISTING_AUTHOR_ITEM_ID"}
}
```

`title`, `slug`, and `bodyHtml` are required strings. `slug` must be a single URL segment; do not regenerate it during an update without user intent. Optional `summary` requires a summary field mapping. Optional `fieldData` supplies additional fields required by this Collection, using native Webflow value types. Resolve reference/option IDs from authoritative site data or the user; do not invent them. Extra fields cannot override mapped title, slug, body, or summary.

The helper verifies site/Collection membership and reads schema before any write. It checks known/editable fields, mapping types, and required values; the API remains authoritative for detailed field validations. Updates fetch the current staged item, check required values across existing and submitted fields, then send only supplied fields. Unrelated fields remain untouched.

Preserve HTML exactly. Do not rewrite, translate, normalize, truncate, auto-summarize, extract bodies, inject CSS wrappers, or convert Markdown without a request. Platform sanitization can change stored HTML; a readback mismatch produces a warning without rollback. Website layout/CSS fidelity is not guaranteed.

## Publish or update

```bash
# Offline preview. API token is not needed; schema checks occur on execution.
bash <skill-path>/scripts/webflow_cms.sh create \
  --data-file /absolute/path/item.json

bash <skill-path>/scripts/webflow_cms.sh create \
  --data-file /absolute/path/item.json --execute

bash <skill-path>/scripts/webflow_cms.sh get --id ITEM_ID
bash <skill-path>/scripts/webflow_cms.sh update \
  --id ITEM_ID --data-file /absolute/path/item.json --execute
```

Writes dry-run by default. A request to publish final content authorizes `--execute`; no additional confirmation is needed just because preview is the default. Draft-writing requests authorize preparing content/preview only.

Creation uses `POST /collections/{id}/items/live`; updates use `PATCH /collections/{id}/items/{item_id}/live`. Both send `isArchived: false`, `isDraft: false` and publish immediately. Do not use staged creation, then publish the entire site. This skill does not implement draft writes, scheduling, schema mutation, deletion, whole-site publishing, asset uploads, or localized/bulk writes; it uses the default CMS locale as the App does.

## Verify and recover

After a write the helper fetches the live item. Return `remoteObjectId`, status, material warnings, and candidate URL. Native mutation data is retained under `response` and readback under `verified`, including if verification fails. `published` requires `lastPublished` and no draft/archive flag; otherwise `unverified` exits nonzero and preserves the receipt. The candidate URL assumes `SITE_URL/collection-slug/item-slug`; verify actual site routing before calling it a working public link.

Reads default to staged items. Use `--live` explicitly for published content:

```bash
bash <skill-path>/scripts/webflow_cms.sh get --id ITEM_ID --live
bash <skill-path>/scripts/webflow_cms.sh items --live --limit 50 --offset 0
```

Each `items` invocation returns one page with pagination metadata; request further offsets only as needed/authorized. No automatic pagination, mutation retries, or replacement creation. On timeout, connection failure, 429, 5xx, or missing/mismatched IDs, reconcile using `get`/`items` before another write. A schema/discovery failure occurs before creation. A failed verification must not prompt another create. HTTP errors preserve native JSON, HTTP status, and `Retry-After` when supplied, with credentials redacted.

Offline validation (all HTTP mocked):

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s <skill-path>/tests -v
```
