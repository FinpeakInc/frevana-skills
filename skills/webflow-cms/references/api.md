# Webflow API and App contract

Reviewed the local `frevana-electron-app` implementation on 2026-11-04:

- `src/main/services/report-publishing/providers/webflow/provider.ts`: Bearer-authenticated `https://api.webflow.com/v2`, site collections, Collection details/fields, POST/PATCH live item writes, dynamic field mapping, and candidate URL construction.
- `providers/webflow/types.ts` and `config.ts`: site URL/ID, Collection ID, token, and name/slug/content/summary field mappings.
- `src/renderer/components/publishing/ConfigDialog.tsx`: the App recommends a RichText field after connecting. This skill requires the destination mapping to be resolved explicitly when ambiguous.
- `providers/webflow/hooks.ts` and `providers/shared/html.utils.ts`: the App scopes CSS and creates/truncates report summaries. The skill accepts final content unchanged and sends a summary only when supplied.

The skill uses independent local JSON configuration, not App IPC or protected desktop storage. Schema discovery precedes a mutation instead of running alongside it; a discovery failure therefore cannot mask a completed creation. Native write receipts survive readback failure. The helper reports publication more conservatively than the App, which also treats `isDraft: false` alone as published.

## Frevana setup guide

Use the user-facing [Webflow Integration guide](https://frevana.gitbook.io/frevana-docs/cms-integrations/webflow-integration) for first-time setup or missing credentials. It explains generating a token in Site Settings → Apps & Integrations with CMS read/write access, collecting Site ID and Site URL, and preparing a CMS Collection.

Its starter workflow uses the Blog Post Collection Template with default fields, adds a Rich Text element to the Collection Page, binds it to Post Body, then publishes the site layout. This is a recommended setup path, not a requirement to replace a compatible existing Collection or impose its example layout. The helper only publishes items; it does not perform Designer or whole-site publishing operations.

Configure `WEBFLOW_API_TOKEN`, `WEBFLOW_SITE_ID`, and `WEBFLOW_SITE_URL`. All three are required by the helper, including for existing saved configurations. Site URL is the public HTTPS website origin used to construct frontend candidate links; this requirement ensures that publication cannot proceed with an unconfigured frontend domain. The API request itself still targets `api.webflow.com`. Use `collections`/`fields` to obtain the actual Collection ID and body field slug, then configure `WEBFLOW_COLLECTION_ID` and `WEBFLOW_CONTENT_FIELD_SLUG`. Never infer a field slug solely from the label “Post Body”.

## API calls

| Operation | v2 path |
| --- | --- |
| Site collections | `GET /sites/{site_id}/collections` |
| Schema and fields | `GET /collections/{collection_id}` |
| Staged list/get | `GET /collections/{collection_id}/items[/{item_id}]` |
| Live list/get | `GET /collections/{collection_id}/items/live` or `/items/{item_id}/live` |
| Create and publish | `POST /collections/{collection_id}/items/live` |
| Update and publish | `PATCH /collections/{collection_id}/items/{item_id}/live` |

Headers: `Authorization: Bearer API_TOKEN`, `Accept: application/json`, `Content-Type: application/json`. Requires `cms:read` for discovery/verification and `cms:write` for writes. Requests have a 30-second timeout, refuse redirects and do not automatically retry.

Write body contains `fieldData` at the top level, plus `isArchived: false` and `isDraft: false`. This is one item per operation, without the bulk `items` shape or locale selectors. RichText fields receive HTML strings, Reference fields receive existing item IDs, and other field values must match the actual Collection schema. Do not guess field IDs or coerce arbitrary values to text.

Tokens with read permission alone can pass connection tests but still fail publishing. Site/Collection existence also does not prove that its Collection page is deployed, its domain matches `site_url`, or an inferred public URL resolves.

Official documentation:

- [Site token setup](https://developers.webflow.com/data/reference/authentication/site-token)
- [List Collections](https://developers.webflow.com/data/reference/cms/collections/list)
- [Get Collection Details](https://developers.webflow.com/data/reference/cms/collections/get)
- [Create Live Items](https://developers.webflow.com/data/reference/cms/collection-items/live-items/create-item-live)
- [Update Single Live Item](https://developers.webflow.com/data/reference/cms/collection-items/live-items/update-item-live)
- [Get Live Item](https://developers.webflow.com/data/reference/cms/collection-items/live-items/get-item-live)
- [CMS API overview](https://developers.webflow.com/data/reference/cms)
