---
name: apple-app-store-product
description: Use when the user provides an Apple App Store product ID and wants app product page details, attributes, or metadata.
---

# Apple App Store Product

Retrieve Apple App Store product page details through Frevana.

## Purpose

This skill is for **looking up details for a specific Apple App Store product**.

Inputs:

- `product_id` (or `--id`)
- optional `type` (default: `app`)
- optional `country` (default: `us`)
- optional `output`; defaults to `./out/apple-product-<timestamp>-<pid>.json`
- optional SerpAPI flags: `serpapi_output` (`json` | `html`), `no_cache`, `async`, `zero_trace`

Output:

- validated response JSON with Apple App Store product details
- the same validated JSON saved to a local file on every successful run

This skill validates that the response is JSON and returns it unchanged. Do **not** rewrite or reshape the returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- user-provided `product_id`
- optional `type`, `country`
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
8. Return the validated response JSON, or summarize the product details if the user does not need the full payload.

## Commands

### Basic product lookup

```bash
bash <skill-path>/scripts/get_apple_product.sh \
  --product-id "6444058226"
```

`--id` is accepted as an alias for `--product-id`.

### Lookup with region country

```bash
bash <skill-path>/scripts/get_apple_product.sh \
  --product-id "6444058226" \
  --country us
```

### Save response JSON to a specific file

```bash
bash <skill-path>/scripts/get_apple_product.sh \
  --product-id "6444058226" \
  --output ./out/my-apple-product.json
```

### Token override for the current run

```bash
bash <skill-path>/scripts/get_apple_product.sh \
  --product-id "6444058226" \
  --token "your bearer token"
```

## Fixed Request Shape

The script sends this payload shape, omitting optional fields that were not provided:

```json
{
  "product_id": "6444058226",
  "type": "app",
  "country": "us"
}
```

Only `product_id` is required. Do not invent optional parameter values when the user did not provide them.

## Response Shape

The API returns JSON. Common sections include:

- `search_metadata`
- `search_parameters`
- `product_results` / `product`

## Output

- Success: the script validates that the response body is JSON, writes it to a file, prints the saved path to stderr, and prints the JSON to stdout
- Default file path: `./out/apple-product-<timestamp>-<pid>.json`
- With `--output`: the same JSON is written to the specified file path instead of the default path
- Failure: the script prints the response body or parsing error and exits non-zero

## Notes

- Require `--product-id` (or `--id`)
- If the user provides an App Store URL (e.g., `https://apps.apple.com/us/app/id6444058226`), extract the numeric ID after `id` (`6444058226`)
- If `curl` is missing, stop and tell the user to install `curl`
- If `python3` is missing, stop and tell the user to install `python3`
- Do not echo the Bearer token back to the user
- Summarize the key fields the user actually cares about instead of dumping raw JSON unless they ask for the full payload

## Example Prompts

### 中文

- "获取 App Store 应用 ID 6444058226 的详情页面"
- "查一下 Apple App product_id=6444058226，country=us"
- "调用 Apple product API 并把原始 JSON 保存到文件"

### English

- "Fetch Apple App Store product details for product ID 6444058226"
- "Look up Apple product page for product_id 6444058226 in country=us"
- "Get Apple product details and save the raw JSON to a file"
