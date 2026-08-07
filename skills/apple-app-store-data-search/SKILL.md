---
name: apple-app-store-data-search
description: Use when the user wants Apple App Store data through Frevana, including searching apps by term/developer/category, fetching app product page details by product ID, or getting app reviews sorted by criteria.
---

# Apple App Store Search

Search apps, retrieve product page details, and fetch app reviews from the Apple App Store through Frevana.

## Purpose

This skill provides access to Apple App Store data via three endpoints:

- `scripts/search_apple_app_store.sh`: calls `POST /service/apple-app-store-search` to search apps by term, developer, category, country, language, device, and pagination.
- `scripts/get_apple_product.sh`: calls `POST /service/apple-product` to retrieve product page details for a specific app by `product_id`.
- `scripts/get_apple_reviews.sh`: calls `POST /service/apple-reviews` to fetch user reviews for a specific app by `product_id`, page, and sort order.

Inputs:

### App Store Search (`search_apple_app_store.sh`)
- `term` (or `--q` / `--query`)
- optional `country` (default: `us`)
- optional `lang` (default: `en-us`)
- optional `num` (1 to 200, default: 10)
- optional `page` (0-indexed, default: 0)
- optional `disallow_explicit` (boolean)
- optional `property` (e.g. `developer`)
- optional `category_id` (numeric genre ID, e.g. 6014 for Games)
- optional `device` (`desktop` | `tablet` | `mobile`, default: `desktop`)
- optional SerpAPI flags: `serpapi_output` (`json` | `html`), `no_cache`, `async`, `zero_trace`

### Product Page (`get_apple_product.sh`)
- `product_id` (or `--id`)
- optional `type` (default: `app`)
- optional `country` (default: `us`)
- optional SerpAPI flags: `serpapi_output` (`json` | `html`), `no_cache`, `async`, `zero_trace`

### App Reviews (`get_apple_reviews.sh`)
- `product_id` (or `--id`)
- optional `country` (default: `us`)
- optional `page` (1-indexed, default: 1)
- optional `sort` (`mostrecent` | `mosthelpful` | `mostfavorable` | `mostcritical`, default: `mostrecent`)
- optional SerpAPI flags: `serpapi_output` (`json` | `html`), `no_cache`, `async`, `zero_trace`

Output:

- validated response JSON from the requested Apple App Store API
- the same validated JSON saved to a local file on every successful run

This skill validates that the response is JSON, saves it to disk, and returns it unchanged on stdout. Do **not** rewrite or reshape the returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- user-provided `term` (for search) or `product_id` (for product page / reviews)
- `FREVANA_TOKEN` in the environment variables, or an explicit `--token` override for the current run
- `curl`
- `bash`
- `python3`

## Execution Order

Use this flow so the request stays simple and reliable:

1. Determine which operation the user wants: App Search, Product Page lookup, or App Reviews.
2. Confirm required inputs are provided (`term` for search; `product_id` for product/reviews).
3. Prefer the repository scripts over ad hoc `curl` commands.
4. Let the script read `FREVANA_TOKEN` first.
5. In interactive shell usage, if `FREVANA_TOKEN` is missing, the script may prompt for it.
6. In non-interactive or agent workflows, fail fast if the token is missing and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly.
7. Run the appropriate script once. It prints the validated JSON to stdout and saves the same JSON to a file.
8. Use the saved JSON file for any follow-up parsing or summarization instead of calling the API again.
9. Return the validated response JSON, or summarize the most relevant results if the user does not need the full payload.

## Commands

### Search Apple App Store

```bash
bash <skill-path>/scripts/search_apple_app_store.sh \
  --term "instagram"
```

Aliases `--query` and `--q` are also accepted for `--term`.

### Search with region, language, category, and device

```bash
bash <skill-path>/scripts/search_apple_app_store.sh \
  --term "games" \
  --country us \
  --lang en-us \
  --category-id 6014 \
  --num 20 \
  --page 0 \
  --device mobile
```

### Search by developer name

```bash
bash <skill-path>/scripts/search_apple_app_store.sh \
  --term "Apple" \
  --property developer
```

### Get Apple App product page details

```bash
bash <skill-path>/scripts/get_apple_product.sh \
  --product-id "6444058226" \
  --country us
```

### Get Apple App Store reviews

```bash
bash <skill-path>/scripts/get_apple_reviews.sh \
  --product-id "6444058226" \
  --country us \
  --page 1 \
  --sort mostrecent
```

### Save response JSON to a specific file

```bash
bash <skill-path>/scripts/search_apple_app_store.sh \
  --term "instagram" \
  --output ./out/my-apple-search.json
```

### Token override for current run

```bash
bash <skill-path>/scripts/search_apple_app_store.sh \
  --term "instagram" \
  --token "your bearer token"
```

## Fixed Request Shapes

### 1. Apple App Store Search (`POST /service/apple-app-store-search`)

```json
{
  "term": "instagram",
  "country": "us",
  "lang": "en-us",
  "num": 10,
  "page": 0,
  "disallow_explicit": false,
  "property": "developer",
  "category_id": 6014,
  "device": "desktop"
}
```

### 2. Apple Product Details (`POST /service/apple-product`)

```json
{
  "product_id": "6444058226",
  "type": "app",
  "country": "us"
}
```

### 3. Apple App Reviews (`POST /service/apple-reviews`)

```json
{
  "product_id": "6444058226",
  "country": "us",
  "page": 1,
  "sort": "mostrecent"
}
```

Only include optional fields when provided by the user. Do not invent optional parameter values.

## Response Shape

The APIs return SerpAPI JSON responses wrapped by Frevana. Common response sections include:

- `search_metadata`
- `search_parameters`
- `organic_results` (for search)
- `product_results` / `product` (for product details)
- `reviews` (for reviews)

## Output

- Success: the script validates that the response body is JSON, writes it to a file, prints the saved path to stderr, and prints the JSON to stdout
- Default output paths:
  - Search: `./out/apple-app-store-search-<timestamp>-<pid>.json`
  - Product Page: `./out/apple-product-<timestamp>-<pid>.json`
  - Reviews: `./out/apple-reviews-<timestamp>-<pid>.json`
- With `--output`: the same JSON is written to the specified file path instead
- Failure: the script prints the response body or error message and exits non-zero

## Notes

- Require `--term` (or `--q`/`--query`) for `search_apple_app_store.sh`.
- Require `--product-id` (or `--id`) for `get_apple_product.sh` and `get_apple_reviews.sh`.
- `--num` must be an integer from 1 to 200.
- `--page` is 0-indexed for search (`>= 0`), and 1-indexed for reviews (`>= 1`).
- `--device` must be `desktop`, `tablet`, or `mobile`.
- `--sort` must be `mostrecent`, `mosthelpful`, `mostfavorable`, or `mostcritical`.
- Do not echo the Bearer token in terminal output.
- Summarize relevant app results/details/reviews instead of dumping full JSON unless the user asks for the raw payload.

## Example Prompts

### 中文

- "搜索 Apple App Store 上的 instagram"
- "查一下 App Store 开发者 Apple 的应用， country=us，lang=en-us"
- "获取 App Store 应用 ID 6444058226 的详情页面"
- "获取 App Store 应用 6444058226 的最新评价 (mostrecent)"

### English

- "Search Apple App Store for instagram"
- "Look up App Store apps by developer Apple in country=us, lang=en-us"
- "Fetch Apple App Store product details for product ID 6444058226"
- "Get reviews for App Store app 6444058226 sorted by mostrecent"
