---
name: google-immersive-product
description: Use when the user wants Google Immersive Product details through Frevana, including product detail popups, store offers, store pagination with stores_next_page_token, product ratings, top insights, reviews, thumbnails, or results from a Google Shopping immersive_product_page_token. Use this whenever the task mentions Google Immersive Product, immersive product page token, immersive_product_page_token, stores_next_page_token, or the Frevana endpoint.
---

# Google Immersive Product

Retrieve Google Immersive Product details through Frevana.

## Purpose

This skill is for **expanding a Google Shopping product result into the Google Immersive Product detail payload**.

Inputs:

- `page_token`
- optional `next_page_token`

Output:

- validated response JSON with Google Immersive Product details
- the same validated JSON saved to a local file on every successful run

The `page_token` must come from a Google Shopping result item's `immersive_product_page_token`. The optional `next_page_token` is used only for store-offer pagination and must come from a prior Google Immersive Product response's `product_results.stores_next_page_token`.

This skill validates that the response is JSON, saves it to disk, and returns it unchanged on stdout. Do **not** rewrite or reshape the returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- user-provided `page_token`
- optional user-provided `next_page_token`
- `FREVANA_TOKEN` in the environment, or an explicit `--token` override for the current run
- `curl`
- `bash`
- `python3`

## Execution Order

Use this flow so the request stays simple and reliable:

1. Confirm the user has provided `page_token` or an equivalent `immersive_product_page_token` from Google Shopping results.
2. If the user gives only a product name, shopping query, product URL, or generic keyword, do not guess a token. Tell them to run the Google Shopping search skill first and choose a result with `immersive_product_page_token`.
3. Use `next_page_token` only when the user is asking for the next page of stores from a prior Google Immersive Product result. It should come from `product_results.stores_next_page_token`.
4. Prefer the script over ad hoc `curl` commands.
5. Let the script read `FREVANA_TOKEN` first.
6. In interactive shell usage, if `FREVANA_TOKEN` is missing, the script may prompt for it.
7. In non-interactive or agent workflows, fail fast if the token is missing and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly.
8. Run the script once. It prints the validated JSON to stdout and saves the same JSON to a file.
9. Use the saved JSON file for any follow-up parsing or summarization instead of calling the API again.
10. Return the validated response JSON, or summarize the product, stores, ratings, insights, and follow-up store pagination token if the user does not need the full payload.

## Commands

### Basic immersive product lookup

```bash
bash <skill-path>/scripts/search_google_immersive_product.sh \
  --page-token "eyJlaSI6Im5ZVmxaOX..."
```

`--page_token` and `--immersive-product-page-token` are accepted as aliases for `--page-token`.

### Fetch next stores page

```bash
bash <skill-path>/scripts/search_google_immersive_product.sh \
  --page-token "eyJlaSI6Im5ZVmxaOX..." \
  --next-page-token "f69uOnica15aklmSk3pT0..."
```

`--next_page_token` is accepted as an alias for `--next-page-token`.

### Save response JSON to a specific file

```bash
bash <skill-path>/scripts/search_google_immersive_product.sh \
  --page-token "eyJlaSI6Im5ZVmxaOX..." \
  --output ./out/google-immersive-product-result.json
```

### Token override for the current run

```bash
bash <skill-path>/scripts/search_google_immersive_product.sh \
  --page-token "eyJlaSI6Im5ZVmxaOX..." \
  --token "your bearer token"
```

## Fixed Request Shape

The script sends this payload shape, omitting optional fields that were not provided:

```json
{
  "page_token": "eyJlaSI6Im5ZVmxaOX...",
  "next_page_token": "f69uOnica15aklmSk3pT0..."
}
```

Only `page_token` is required. Do not invent `page_token` or `next_page_token` values. Do not add unsupported passthrough fields such as `engine`, `api_key`, `output`, `no_cache`, `async`, or `zero_trace`.

## Response Shape

The API returns Frevana JSON. Common fields include:

- `search_metadata`
- `search_parameters`
- `product_results`

The `product_results` object can include fields such as `title`, `brand`, `rating`, `reviews`, `price_range`, `thumbnails`, `stores`, `stores_next_page_token`, `about_the_product`, `top_insights`, `ratings`, `reviews_images`, and `user_reviews`.

## Output

- Success: the script validates that the response body is JSON, writes it to a file, prints the saved path to stderr, and prints the JSON to stdout
- Default file path: `./out/google-immersive-product-<UTC timestamp>-<pid>.json`
- With `--output`: the same JSON is written to the specified file path instead of the default path
- Failure: the script prints the response body or parsing error and exits non-zero

## Notes

- Require `--page-token`, `--page_token`, or `--immersive-product-page-token`.
- If the user supplies only a product name or search query, recommend running the Google Shopping search skill first to get `immersive_product_page_token`, then continue with this skill.
- Use `--next-page-token` only for store pagination from a prior response's `product_results.stores_next_page_token`.
- The `page_token` is an input cursor for a specific immersive product, not a general search term.
- If `curl` is missing, stop and tell the user to install `curl`.
- If `python3` is missing, stop and tell the user to install `python3`.
- Do not echo the Bearer token back to the user.
- Summarize the product and store offers the user actually cares about instead of dumping raw JSON unless they ask for the full payload.

## Example Prompts

### 中文

- "用这个 immersive_product_page_token 查询 Google Immersive Product，并总结店铺报价"
- "查一下 Google Immersive Product，page_token 是 eyJlaSI6Im5ZVmxaOX..."
- "继续翻当前 Immersive Product 的 stores，next_page_token 是 f69uOnica15..."
- "我只有产品关键词，没有 page_token" -> 说明需要先用 Google Shopping search 获取 `immersive_product_page_token`

### English

- "Use this immersive_product_page_token to fetch Google Immersive Product details."
- "Get the next store page for this Google Immersive Product result."
- "Query the Frevana google-immersive-product endpoint with this page_token and save raw JSON."
- "Search Google Immersive Product for 'LG TV'." -> Explain that a `page_token` is required and suggest running Google Shopping search first to obtain `immersive_product_page_token`.
