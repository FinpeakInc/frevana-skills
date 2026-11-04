---
name: shopify-cms
description: Publish or update Shopify CMS blog articles through the Admin GraphQL API, discover blogs, and inspect existing articles. Use for Shopify editorial content publishing, not products, themes, or storefront pages.
---

# Shopify CMS

Publish a final HTML article to a selected Shopify blog, or update an exact article ID. Uses the same client-credentials exchange and article mutations as the Frevana desktop App. Requires Python 3 and Bash; no Frevana token, daemon, or browser extension.

## Connect and select a blog

Resolve credentials per field: command-line option, environment, then local JSON configuration. Prefer environment variables or the hidden interactive secret prompt over command-line secrets. Never include secrets in content files, chat output, or repository files.

| Environment variable | Purpose |
| --- | --- |
| `SHOPIFY_STORE_DOMAIN` | Canonical `store.myshopify.com` domain; optional `https://` |
| `SHOPIFY_CLIENT_ID` | Installed app's Client ID |
| `SHOPIFY_CLIENT_SECRET` | Installed app's Client Secret |
| `SHOPIFY_BLOG_ID` | Selected numeric Blog ID or `gid://shopify/Blog/ID` |
| `SHOPIFY_API_VERSION` | Stable Admin API version; default `2026-04` |
| `SHOPIFY_DEFAULT_AUTHOR` | Optional author; new articles otherwise use `Frevana` |

First run:

```bash
bash <skill-path>/scripts/shopify_cms.sh status
bash <skill-path>/scripts/shopify_cms.sh configure
bash <skill-path>/scripts/shopify_cms.sh blogs
```

`configure` saves supplied/resolved values to `${SHOPIFY_CONFIG_FILE:-${XDG_CONFIG_HOME:-$HOME/.config}/shopify-content/config.json}` with mode `0600`. Override with `--config FILE`. New directories use `0700`; existing parent permissions are preserved. Config keys are the lowercase names without `SHOPIFY_`, such as `store_domain`, `client_secret`, and `blog_id`. Add `--blog-id ID` when configuring after choosing a destination. `status` authenticates and verifies the selected blog when configured. Token exchanges occur once per invocation and tokens remain in memory.

If credentials are missing or the user asks how to obtain them, show the [Frevana Shopify CMS Integration guide](https://frevana.gitbook.io/frevana-docs/cms-integrations/shopify-cms-integration) and identify the missing store domain, Client ID, or Client Secret. The wrapper returns this link as `setupGuide` on missing configuration. Guide the user through local environment/configuration rather than asking them to paste secrets into chat; do not invent credentials. After connecting, discover and select the destination blog separately.

If the app and store are in different Shopify organizations, this client-secret grant may be unavailable; do not promise that arbitrary merchant stores support it. Consult [API and App behavior](references/api.md) for scopes, setup steps, and differences. An App UI “Connected” indicator does not populate this standalone skill's config; do not scrape encrypted desktop storage.

Blog discovery returns GIDs, titles, handles, and `pageInfo`. Resolve the destination from these results; do not invent IDs or choose arbitrarily between blogs. `--after CURSOR` requests one additional page explicitly.

The local credential file path retains `shopify-content` for compatibility with configurations saved before the skill was renamed.

## Publish and update

Prepare a UTF-8 JSON file:

```json
{
  "title": "Summer guide",
  "bodyHtml": "<p>Final article HTML.</p>",
  "summary": "Optional summary",
  "author": "Editorial team",
  "tags": ["Guides"]
}
```

`title` and `bodyHtml` are required strings. Optional `summary` and `author` are strings; `tags` is an array of strings. Unknown keys and wrong types fail locally. Omitted summary/tags are not sent; omitted author on updates is preserved unless a configured default author applies. Empty summary or `tags: []` explicitly clears those values.

```bash
# Offline preview; requires domain and destination blog, no credentials or network.
bash <skill-path>/scripts/shopify_cms.sh create \
  --blog-id 123 --data-file /absolute/path/article.json

# Execute after reviewing the target and final content.
bash <skill-path>/scripts/shopify_cms.sh create \
  --blog-id 123 --data-file /absolute/path/article.json --execute

# Read before changing an existing article; use its exact returned ID.
bash <skill-path>/scripts/shopify_cms.sh get --id 456
bash <skill-path>/scripts/shopify_cms.sh update \
  --blog-id 123 --id 456 --data-file /absolute/path/article.json --execute
```

Creation and updates publish immediately with `isPublished: true`. A user request to publish the final content authorizes execution; do not ask again solely because preview is the script default. Draft-writing requests authorize preparing the content and preview only. This helper does not support scheduling, draft writes, deletion, article moves, or product operations. Updates check the existing article's blog before writing and refuse to move it.

Preserve `bodyHtml` exactly, including whitespace and Unicode. Do not rewrite, translate, truncate, remove duplicate headings, extract HTML bodies, or convert Markdown unless requested. Ask for/prepare an explicit conversion when needed. The API/theme may sanitize or render HTML differently; a stored-body mismatch is advisory and causes no rollback. Full website layout or CSS fidelity is not guaranteed.

## Results and recovery

Return the remote article ID, publication status, candidate URL, and material warnings. Native provider data remains under `response`; successful readback is under `verified`. `remoteUrlCandidate` uses the store/blog/article handles and is not a verified public page.

HTTP success alone is insufficient: GraphQL `errors`, mutation `userErrors`, and missing/mismatched IDs are failures. Publication is reported only when the response/readback declares `isPublished: true`; `unverified` exits nonzero and retains the receipt. A failed readback preserves the successful mutation's ID and response.

No requests are automatically retried. On timeout, connection failure, 429, 5xx, or malformed/missing mutation results, stop and reconcile by reading/listing articles; do not create a replacement or assume nothing was published. Preserve IDs returned in errors. Use exact IDs for follow-up updates.

```bash
bash <skill-path>/scripts/shopify_cms.sh articles --blog-id 123 --limit 50
bash <skill-path>/scripts/shopify_cms.sh articles --blog-id 123 --after 'EXACT_CURSOR'
```

Each list call returns one page. Do not infer complete coverage while `hasNextPage` is true. Local configuration errors, provider errors, and uncertain publication results must be distinguished in the user summary.

Offline validation (all HTTP mocked):

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s <skill-path>/tests -v
```
