---
name: apple-app-store-reviews
description: Use when the user provides an Apple App Store product ID and wants app user reviews, paginated reviews, or reviews sorted by criteria (mostrecent, mosthelpful, mostfavorable, mostcritical).
---

# Apple App Store Reviews

Retrieve Apple App Store user reviews through Frevana.

## Purpose

This skill is for **fetching reviews for a specific Apple App Store product**.

Inputs:

- `product_id` (or `--id`)
- optional `country` (default: `us`)
- optional `page` (1-indexed, default: 1)
- optional `sort` (`mostrecent` | `mosthelpful` | `mostfavorable` | `mostcritical`, default: `mostrecent`)
- optional `output`; defaults to `./out/apple-reviews-<timestamp>-<pid>.json`
- optional SerpAPI flags: `serpapi_output` (`json` | `html`), `no_cache`, `async`, `zero_trace`

Output:

- validated response JSON with Apple App Store reviews
- the same validated JSON saved to a local file on every successful run

This skill validates that the response is JSON and returns it unchanged. Do **not** rewrite or reshape the returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- user-provided `product_id`
- optional `country`, `page`, `sort`
- `FREVANA_TOKEN` in the environment variables, or an explicit `--token` override for the current run
- `curl`
- `bash`
- `python3`

## Execution Order

Use this flow so the request stays simple and reliable:

1. Confirm the user has provided `product_id`.
2. Prefer the script over ad hoc `curl` commands.
3. Let the script read `FREVANA_TOKEN` first.
4. In interactive shell usage, if `FREVANA_TOKEN` is missing, the script may prompt for it.
5. In non-interactive or agent workflows, fail fast if the token is missing and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly.
6. Run the script once. It prints the validated JSON to stdout and saves the same JSON to a file.
7. Use the saved JSON file for any follow-up parsing or summarization instead of calling the API again.
8. Return the validated response JSON, or summarize the reviews if the user does not need the full payload.

## Commands

### Basic reviews lookup

```bash
bash <skill-path>/scripts/get_apple_reviews.sh \
  --product-id "6444058226"
```

`--id` is accepted as an alias for `--product-id`.

### Lookup with sort order and pagination

```bash
bash <skill-path>/scripts/get_apple_reviews.sh \
  --product-id "6444058226" \
  --country us \
  --page 2 \
  --sort mosthelpful
```

### Save response JSON to a specific file

```bash
bash <skill-path>/scripts/get_apple_reviews.sh \
  --product-id "6444058226" \
  --output ./out/my-apple-reviews.json
```

### Token override for the current run

```bash
bash <skill-path>/scripts/get_apple_reviews.sh \
  --product-id "6444058226" \
  --token "your bearer token"
```

## Fixed Request Shape

The script sends this payload shape, omitting optional fields that were not provided:

```json
{
  "product_id": "6444058226",
  "country": "us",
  "page": 1,
  "sort": "mostrecent"
}
```

Only `product_id` is required. Do not invent optional parameter values when the user did not provide them.

## Response Shape

The API returns JSON. Common sections include:

- `search_metadata`
- `search_parameters`
- `reviews`

## Output

- Success: the script validates that the response body is JSON, writes it to a file, prints the saved path to stderr, and prints the JSON to stdout
- Default file path: `./out/apple-reviews-<timestamp>-<pid>.json`
- With `--output`: the same JSON is written to the specified file path instead of the default path
- Failure: the script prints the response body or parsing error and exits non-zero

## Notes

- Require `--product-id` (or `--id`)
- `--page` is 1-indexed (minimum `1`)
- `--sort` must be `mostrecent`, `mosthelpful`, `mostfavorable`, or `mostcritical`
- If `curl` is missing, stop and tell the user to install `curl`
- If `python3` is missing, stop and tell the user to install `python3`
- Do not echo the Bearer token back to the user
- Summarize user reviews instead of dumping raw JSON unless the user asks for the full payload

## Example Prompts

### 中文

- "获取 App Store 应用 6444058226 的最新评价 (mostrecent)"
- "查一下 product_id=6444058226 的评价，按有用程度 (mosthelpful) 排序，第 2 页"
- "获取 Apple App Store 评价并保存原始 JSON"

### English

- "Get reviews for App Store app 6444058226 sorted by mostrecent"
- "Fetch page 2 of reviews for product_id 6444058226 sorted by mosthelpful"
- "Download Apple app reviews and save raw JSON to a file"
