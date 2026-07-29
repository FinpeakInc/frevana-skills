---
name: wordpress-content
description: Create, inspect, update, schedule, publish, trash, and bulk-manage WordPress posts, pages, custom post types, media, categories, tags, post meta, classic menus, and block-theme navigation through the WordPress REST API, preserving user-supplied body content verbatim by default and resolving credentials from explicit input, environment variables, or a protected local config file. Use when the user wants to manage WordPress editorial content, publish content without rewriting or format conversion, upload or attach media, set featured images, organize taxonomies, update navigation, preserve or edit Gutenberg blocks, or perform scoped content operations without WP-CLI or local PHP.
---

# WordPress Content

Manage WordPress content exclusively through the built-in REST API. Do not install or invoke WP-CLI. Require `bash`, `curl`, and Python 3; do not require local PHP.

## Required Inputs

Ensure these values are available through explicit input, environment variables, or local configuration:

- HTTPS WordPress site URL
- WordPress username
- WordPress Application Password
- requested operation and content type
- exact object ID when changing existing content
- final title, content, status, date, taxonomy, media, or navigation details required by the operation

Do not guess an object ID from a title alone. Search and resolve ambiguity before writing.

## Verbatim Publishing Default

Treat user-supplied body content as authoritative. Before creating or updating any body content, read [references/verbatim-publishing.md](references/verbatim-publishing.md) completely and follow its comparison workflow.

- Do not rewrite, summarize, translate, reformat, normalize, or repair supplied content.
- Do not convert between plain text, Markdown, HTML, Classic content, and Gutenberg blocks unless explicitly requested.
- Keep title, excerpt, taxonomy, dates, and media assignments separate from the body; do not duplicate them inside `content`.
- Use `verbatim-create` or `verbatim-update` for every body write; the generic `request` action refuses executable JSON writes containing `content`.
- Submit the user's payload without changing its requested status. If WordPress changes or sanitizes the body, report the mismatch as a warning; do not stop, unpublish, return to draft, or roll back solely because of that difference.

Verbatim source preservation does not copy the originating application's CSS or override the WordPress theme. Treat visual fidelity as a separate, explicit styling task.

## Credential Resolution

Prefer the bundled wrapper for configuration and authenticated requests:

```bash
bash <skill-path>/scripts/wordpress_rest.sh status
```

On first use, run `status`. It checks local configuration and authenticates against `/wp-json/wp/v2/users/me`. If any credential is missing, direct the user to the [Frevana WordPress Integration guide](https://frevana.gitbook.io/frevana-docs/cms-integrations/wordpress-integration) to obtain the site URL, username, and Application Password. The wrapper prints this guide automatically for incomplete configuration. Do not invent these values.

Resolve each value independently in this order:

1. explicit options: `--url`, `--username`, `--app-password`
2. environment: `WORDPRESS_URL`, `WORDPRESS_USERNAME`, `WORDPRESS_APP_PASSWORD`
3. local config file
4. interactive prompt when the process has a terminal

This allows, for example, the URL to come from the config file while the Application Password is temporarily overridden through the environment.

The default config path is:

```text
${WORDPRESS_CONFIG_FILE:-${XDG_CONFIG_HOME:-$HOME/.config}/wordpress-content/config}
```

Override it with `--config FILE` or `WORDPRESS_CONFIG_FILE`. The file format is:

```dotenv
WORDPRESS_URL=https://example.com
WORDPRESS_USERNAME=editor
WORDPRESS_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
```

Matching single or double quotes around a complete value are accepted when reading the file.

Configure interactively; the Application Password prompt is hidden:

```bash
bash <skill-path>/scripts/wordpress_rest.sh configure
```

Or save explicit values:

```bash
bash <skill-path>/scripts/wordpress_rest.sh configure \
  --url "https://example.com" \
  --username "editor" \
  --app-password "xxxx xxxx xxxx xxxx xxxx xxxx"
```

The wrapper creates the config directory with mode `0700` and the config file with mode `0600`. Prefer the interactive prompt or environment variables over `--app-password` when command-line arguments may be visible to other local processes.

Clear the selected config only when requested:

```bash
bash <skill-path>/scripts/wordpress_rest.sh clear-config
```

Treat the Application Password as a secret. Never print it, persist it in repository files, include it in URLs, or expose a generated Authorization header.

Requests ignore the user's default `.curlrc` and use connection and total timeouts. Override the defaults only when needed with `WORDPRESS_CONNECT_TIMEOUT` and `WORDPRESS_MAX_TIME`.

## Request Wrapper

Use the wrapper for real requests so configuration, environment variables, and interactive input all work consistently:

```bash
bash <skill-path>/scripts/wordpress_rest.sh request \
  --endpoint "/wp-json/wp/v2/users/me?context=edit"
```

GET, HEAD, and OPTIONS execute immediately. POST, PUT, PATCH, and DELETE dry-run by default:

```bash
bash <skill-path>/scripts/wordpress_rest.sh request \
  --method POST \
  --endpoint "/wp-json/wp/v2/posts" \
  --data-file /absolute/path/post.json
```

After reviewing the redacted plan, add `--execute` to perform the write. Use `--binary-file`, `--content-type`, and `--filename` for media uploads. Use `--headers` and `--output` for pagination or saved responses.

For body content, use `verbatim-create` or `verbatim-update` instead. These actions dry-run by default, submit the supplied JSON unchanged, and perform an advisory `content.raw` comparison through the bundled Python helper.

The read-only direct `curl` examples below show the underlying REST request shape and assume the three environment variables are already populated. Use the wrapper for every write.

## Connect and Discover

Normalize the URL and inspect the REST index:

```bash
WORDPRESS_URL="${WORDPRESS_URL%/}"

curl --fail-with-body --silent --show-error \
  "$WORDPRESS_URL/wp-json/"
```

Verify authenticated access:

```bash
curl --fail-with-body --silent --show-error \
  --user "$WORDPRESS_USERNAME:$WORDPRESS_APP_PASSWORD" \
  "$WORDPRESS_URL/wp-json/wp/v2/users/me?context=edit"
```

Use only HTTPS for Application Password authentication. If `/wp-json/` is unavailable, inspect the site's API discovery link before assuming the REST root. Do not fall back to WP-CLI.

Discover routes and accepted methods before using a site-specific or unfamiliar endpoint:

```bash
curl --fail-with-body --silent --show-error \
  --request OPTIONS \
  --user "$WORDPRESS_USERNAME:$WORDPRESS_APP_PASSWORD" \
  "$WORDPRESS_URL/wp-json/wp/v2/posts"
```

WordPress plugins, themes, versions, permissions, and custom post-type registration can change which routes and fields are available. Treat the REST index and `OPTIONS` response as the source of truth for the target site.

## Safety Contract

Before modifying or deleting an existing object:

1. Fetch the current object with `context=edit`.
2. Record its ID, type, slug, status, modified time, and fields being changed.
3. Send only fields that must change.
4. Preserve the current editor format and unrelated plugin-managed fields.
5. Preserve the status in the approved payload; do not force a draft or add a second publication step.
6. Preview exact targets for publishing, scheduling, navigation changes, taxonomy renames, deletes, and bulk updates.
7. Trash posts and pages by default. Use `force=true` only when permanent deletion was explicitly requested.
8. Verify the response and fetch the object again after each write.

For resources such as taxonomy terms that do not support Trash and require permanent deletion, explain that behavior and obtain explicit approval first.

## Core Endpoints

| Resource | Base endpoint |
| --- | --- |
| Posts | `/wp-json/wp/v2/posts` |
| Pages | `/wp-json/wp/v2/pages` |
| Media | `/wp-json/wp/v2/media` |
| Categories | `/wp-json/wp/v2/categories` |
| Tags | `/wp-json/wp/v2/tags` |
| Post types | `/wp-json/wp/v2/types` |
| Taxonomies | `/wp-json/wp/v2/taxonomies` |
| Classic menus | `/wp-json/wp/v2/menus` |
| Classic menu items | `/wp-json/wp/v2/menu-items` |
| Menu locations | `/wp-json/wp/v2/menu-locations` |
| Block navigation | `/wp-json/wp/v2/navigation` |

Do not assume every endpoint is enabled. Confirm it through `/wp-json/` or `OPTIONS`.

## Read and Search

Fetch editable source, not only rendered public HTML:

```bash
curl --fail-with-body --silent --show-error \
  --user "$WORDPRESS_USERNAME:$WORDPRESS_APP_PASSWORD" \
  "$WORDPRESS_URL/wp-json/wp/v2/posts/123?context=edit&_fields=id,type,slug,status,date,date_gmt,modified,link,title,content,excerpt,featured_media,categories,tags,meta"
```

Search before resolving an ID:

```bash
curl --fail-with-body --silent --show-error \
  --user "$WORDPRESS_USERNAME:$WORDPRESS_APP_PASSWORD" \
  "$WORDPRESS_URL/wp-json/wp/v2/posts?context=edit&search=phrase&per_page=20&_fields=id,type,slug,status,modified,title"
```

Use URL encoding for user-supplied query values. Do not interpolate raw search text, slugs, or filters into a URL without encoding.

## Create Posts and Pages

Write JSON payloads to a temporary or workspace file using the host's file-editing tools. Avoid complex inline shell quoting.

Example post payload:

```json
{
  "title": "Post title",
  "slug": "post-slug",
  "content": "<!-- wp:paragraph --><p>Post content.</p><!-- /wp:paragraph -->",
  "excerpt": "Short summary",
  "status": "draft",
  "categories": [3, 5],
  "tags": [10, 12]
}
```

Create the post:

```bash
bash <skill-path>/scripts/wordpress_rest.sh verbatim-create \
  --endpoint "/wp-json/wp/v2/posts" \
  --data-file /absolute/path/post.json
```

Review the dry-run, then add `--execute`. The action sends the payload file directly, including its original `content` and requested `status`. A `content.raw` mismatch is only a warning and never triggers an automatic status change or rollback. A requested publication status that was not applied is a real failure.

Create a page by sending the appropriate payload to `/wp-json/wp/v2/pages`. Page-specific fields can include `parent`, `menu_order`, and `template` when supported by the endpoint schema.

## Update Existing Content

Fetch and save the current editable response first:

```bash
curl --fail-with-body --silent --show-error \
  --user "$WORDPRESS_USERNAME:$WORDPRESS_APP_PASSWORD" \
  "$WORDPRESS_URL/wp-json/wp/v2/posts/123?context=edit" \
  --output /absolute/path/post-123-before.json
```

Prepare a minimal update payload, for example:

```json
{
  "title": "Updated title",
  "excerpt": "Updated summary"
}
```

Update:

```bash
bash <skill-path>/scripts/wordpress_rest.sh request \
  --method POST \
  --endpoint "/wp-json/wp/v2/posts/123" \
  --data-file /absolute/path/post-update.json
```

Review the dry-run, then add `--execute`. Do not resend `content` unless content is intended to change. When the update includes `content`, use `verbatim-update` with `--backup /absolute/path/post-123-before.json` instead.

## Gutenberg Blocks

Treat `content.raw` from `context=edit` as structured block source:

```html
<!-- wp:heading {"level":2} -->
<h2 class="wp-block-heading">Section title</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>Paragraph text.</p>
<!-- /wp:paragraph -->
```

When editing:

- retain matching block comments
- preserve block JSON attributes unless the requested change requires them
- preserve plugin blocks and shortcodes outside the requested scope
- avoid wrapping existing blocks in extra HTML
- verify the returned `content.raw`

Do not convert Gutenberg content to Classic HTML or Classic content to blocks unless requested.

## Schedule and Publish

WordPress accepts `date` in the site's timezone and `date_gmt` in UTC. Inspect `/wp-json/wp/v2/settings` when the authenticated user has permission:

```bash
curl --fail-with-body --silent --show-error \
  --user "$WORDPRESS_USERNAME:$WORDPRESS_APP_PASSWORD" \
  "$WORDPRESS_URL/wp-json/wp/v2/settings?_fields=timezone"
```

If the timezone cannot be read, ask for the intended timezone instead of guessing.

Schedule with an explicit local date and `future` status:

```json
{
  "status": "future",
  "date": "2030-12-01T09:00:00"
}
```

Publish an approved draft with:

```json
{
  "status": "publish"
}
```

POST the payload to the exact post or page endpoint, then verify `status`, `date`, `date_gmt`, and `link`.

## Media and Featured Images

Upload binary media:

```bash
bash <skill-path>/scripts/wordpress_rest.sh request \
  --method POST \
  --endpoint "/wp-json/wp/v2/media" \
  --binary-file /absolute/path/hero.jpg \
  --content-type "image/jpeg" \
  --filename "hero.jpg"
```

Review the dry-run, then add `--execute`.

Capture the returned media `id`. Then update its metadata:

```json
{
  "title": "Hero image",
  "alt_text": "Descriptive alternative text",
  "caption": "Optional caption",
  "post": 123
}
```

POST that payload to `/wp-json/wp/v2/media/<id>`. Set it as the featured image by updating the post with:

```json
{
  "featured_media": 456
}
```

Use meaningful alt text that describes the image's purpose. Use an empty value for purely decorative images. Do not invent image details that were not inspected.

## Categories, Tags, and Custom Taxonomies

Search existing terms before creating new ones:

```bash
curl --fail-with-body --silent --show-error \
  --user "$WORDPRESS_USERNAME:$WORDPRESS_APP_PASSWORD" \
  "$WORDPRESS_URL/wp-json/wp/v2/categories?search=News&hide_empty=false&context=edit"
```

Create a category:

```json
{
  "name": "News",
  "slug": "news",
  "description": "Company news and updates",
  "parent": 0
}
```

POST to `/wp-json/wp/v2/categories`. Create tags through `/wp-json/wp/v2/tags`. Assign terms by sending numeric category or tag IDs in the post payload.

Discover custom taxonomy routes through `/wp-json/wp/v2/taxonomies` and the REST index. Do not derive a route from the taxonomy name without checking its registered REST base.

## Custom Post Types and Meta

Discover post types:

```bash
curl --fail-with-body --silent --show-error \
  --user "$WORDPRESS_USERNAME:$WORDPRESS_APP_PASSWORD" \
  "$WORDPRESS_URL/wp-json/wp/v2/types?context=edit"
```

Use each type's returned `rest_namespace` and `rest_base`. A custom post type must be registered for REST access.

Only registered REST-visible meta fields can be read or written through `meta`. Inspect `OPTIONS` for the target endpoint before sending custom fields. Preserve Advanced Custom Fields and SEO-plugin data unless the site exposes a documented REST field and the user requested that change.

## Navigation

Discover available navigation routes first.

For classic menus:

- list or create menus through `/wp-json/wp/v2/menus`
- list or create items through `/wp-json/wp/v2/menu-items`
- filter items by their `menus` term ID
- inspect assignments through `/wp-json/wp/v2/menu-locations`

For block themes, manage `wp_navigation` content through `/wp-json/wp/v2/navigation` while preserving its block markup.

Read the current menu and all affected items before reordering or deleting. Send numeric IDs and explicit positions; never infer the target menu from its display name alone.

## Delete and Restore

Trash a post or page:

```bash
bash <skill-path>/scripts/wordpress_rest.sh request \
  --method DELETE \
  --endpoint "/wp-json/wp/v2/posts/123"
```

Bypass Trash only after explicit approval:

```bash
bash <skill-path>/scripts/wordpress_rest.sh request \
  --method DELETE \
  --endpoint "/wp-json/wp/v2/posts/123?force=true"
```

Restore trashed editorial content by POSTing `{"status":"draft"}` when the endpoint and permissions support it.

Term deletion requires `force=true` because terms do not support Trash. Treat it as permanent.

## Pagination and Bulk Operations

WordPress caps `per_page` at 100. Capture response headers:

```bash
curl --fail-with-body --silent --show-error \
  --dump-header /absolute/path/headers.txt \
  --output /absolute/path/posts-page-1.json \
  --user "$WORDPRESS_USERNAME:$WORDPRESS_APP_PASSWORD" \
  "$WORDPRESS_URL/wp-json/wp/v2/posts?context=edit&per_page=100&page=1"
```

Read `X-WP-Total` and `X-WP-TotalPages`, then fetch remaining pages.

For bulk writes:

1. Build and display an explicit list of target endpoint paths and IDs.
2. Save the intended payload for each target.
3. Obtain approval for the exact set when the request did not already make it unambiguous.
4. Send requests sequentially or in small bounded groups.
5. Stop on the first unexpected error.
6. Record successes and failures to avoid duplicate retries.
7. Fetch every changed object again.

Use the batch endpoint only if it appears in the target site's REST index and its limits are understood. Do not assume batch support.

## Response Handling

Treat HTTP status and JSON body together:

- `200`: successful read or update
- `201`: successful creation
- `400`: invalid field, payload, or unsupported parameter
- `401`: missing or invalid authentication
- `403`: authenticated user lacks the required capability, or a security layer blocked the request
- `404`: wrong REST root, disabled route, wrong endpoint, or missing object
- `409`: conflicting state or duplicate resource
- `429`: rate limited; honor `Retry-After` when present
- `5xx`: server or plugin failure; do not blindly retry writes

Use `--fail-with-body --silent --show-error` so errors retain the WordPress JSON response. Never treat a successful HTTP response alone as proof that the rendered page is correct.

## Verification and Handoff

After a write, report:

- site URL
- endpoint and HTTP method
- object type and ID
- title, slug, status, and modified or scheduled date
- admin edit URL when derivable
- public or preview link returned by WordPress
- taxonomy and featured-media IDs changed
- any skipped or partially failed targets

Fetch the object with `context=edit` and compare every written field. If browser access is available and presentation matters, open the preview or live link and visually verify the rendered page.

Use the official references when exact behavior is uncertain:

- <https://developer.wordpress.org/rest-api/>
- <https://developer.wordpress.org/rest-api/using-the-rest-api/authentication/>
- <https://developer.wordpress.org/rest-api/reference/>
