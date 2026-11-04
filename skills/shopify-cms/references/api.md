# Shopify API and App contract

Reviewed against the local `frevana-electron-app` report-publishing service on 2026-11-04:

- `src/main/services/report-publishing/providers/shopify/provider.ts`: client-secret token exchange, `shop`, `blogs(first: 250)`, Blog node lookup, `articleCreate`, `articleUpdate`, numeric-to-GID conversion, and immediate publication.
- `providers/shopify/config.ts`: persisted App configuration defaults to `2026-01`; the provider fallback is `2026-04`. This helper explicitly defaults to `2026-04` and allows a stable version override.
- `providers/shopify/hooks.ts` and `providers/shared/html.utils.ts`: the App normalizes report HTML, scopes CSS, removes a matching leading title, generates a summary, and collapses/truncates it. This standalone helper accepts final HTML and optional summary unchanged; it does not reproduce those automatic transformations.

The skill does not call Electron IPC or read the App's protected credentials. Its local JSON configuration is independent. Source paths above document implementation provenance, not runtime dependencies.

## Frevana setup guide

Use the user-facing [Shopify CMS Integration guide](https://frevana.gitbook.io/frevana-docs/cms-integrations/shopify-cms-integration) for first-time setup or missing credentials. It describes creating an app in Shopify Dev Dashboard, releasing a version with scopes, retrieving Client ID/Secret from Settings, installing the app on the target store, and obtaining its `myshopify.com` domain.

The guide's scope list is `read_files,write_files,read_online_store_pages,write_online_store_pages,read_content,write_content`. These are the guide's App setup instructions, not six scopes independently enforced by this helper. This helper publishes articles without uploading files; its content access requirements are described below. Do not automatically alter an app's permissions.

Map the collected values to `SHOPIFY_STORE_DOMAIN`, `SHOPIFY_CLIENT_ID`, and `SHOPIFY_CLIENT_SECRET` in local configuration. Then run `blogs`, select a returned Blog ID, and set `SHOPIFY_BLOG_ID`. The guide's credential setup alone does not select a publication destination or guarantee write access.

## Authentication

`POST https://STORE.myshopify.com/admin/oauth/access_token`

Form fields: `client_id`, `client_secret`, `grant_type=client_credentials`. The token is sent as `X-Shopify-Access-Token` to `POST /admin/api/VERSION/graphql.json`. No `scope` parameter, Storefront token, or Frevana Bearer token is used.

Install the app on the store and grant the required content scopes. Shopify's client-secret credentials grant applies to an app and store in the same organization; other merchant integrations require another supported authorization flow, outside this helper. Never repeatedly exchange secrets after `shop_not_permitted`.

Authoritative setup: [Client credentials grant](https://shopify.dev/docs/apps/build/authentication-authorization/client-credentials-grant), [access tokens](https://shopify.dev/docs/apps/build/authentication-authorization/access-tokens).

## GraphQL

Read blog/article access requires `read_content` or the applicable `read_online_store_pages` scope. Article mutation access requires `write_content` or `write_online_store_pages` as documented by Shopify. A successful `shop` query alone does not prove content-write permission.

Create: `articleCreate(article: ArticleCreateInput!)`. Update: `articleUpdate(id: ID!, article: ArticleUpdateInput!)`.

Inputs map `blogId`, `title`, `body`, optional `summary`, `author: {name}`, optional `tags`, and `isPublished: true`. Never send the skill's local `bodyHtml` key directly to GraphQL. Update uses an exact Article GID and sends only the supported payload fields; it does not copy unrelated current metadata.

The helper requests IDs, handles, content, blog identity, and publication flags so it can preserve receipts and check results. It checks both top-level GraphQL errors and `userErrors`. It never retries a mutation or claims idempotency for `articleCreate`.

Authoritative contracts: [articleCreate](https://shopify.dev/docs/api/admin-graphql/latest/mutations/articleCreate), [articleUpdate](https://shopify.dev/docs/api/admin-graphql/latest/mutations/articleUpdate), [Article](https://shopify.dev/docs/api/admin-graphql/latest/objects/Article). These links track current documentation; the runtime API version remains explicit.
