---
name: walmart-product-reviews
description: Use when the user wants Walmart product review data through Frevana, including reviews for a known Walmart product_id or us_item_id, review pagination, review sorting, rating filters, top positive or negative reviews, or Frevana API calls.
---

# Walmart Product Reviews

Fetch Walmart product reviews through Frevana.

## Purpose

This skill is for **retrieving reviews for one known Walmart product**.

Inputs:

- `product_id`
- optional `page`
- optional `sort`
- optional `rating`

Output:

- validated response JSON with Walmart product review results
- the same validated JSON saved to a local file on every successful run

The required `product_id` is the Walmart `us_item_id` from Walmart Search results or Walmart Product results. This skill validates that the response is JSON, saves it to disk, and returns it unchanged on stdout. Do **not** rewrite or reshape the returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- user-provided `product_id` / Walmart `us_item_id`
- optional page number
- optional sort value
- optional rating filter
- `FREVANA_TOKEN` in the environment variables, or an explicit `--token` override for the current run
- `curl`
- `bash`
- `python3`

## Execution Order

Use this flow so the request stays simple and reliable:

1. Confirm the user has provided `product_id` or an equivalent Walmart `us_item_id`.
2. If the user gives only a product name, search query, or generic Walmart URL without a clear item id, do not guess. Suggest running `walmart-search` first to obtain an `organic_results[].us_item_id`.
3. Prefer the script over ad hoc `curl` commands.
4. Let the script read `FREVANA_TOKEN` first.
5. In interactive shell usage, if `FREVANA_TOKEN` is missing, the script may prompt for it.
6. In non-interactive or agent workflows, fail fast if the token is missing and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly.
7. Run the script once. It prints the validated JSON to stdout and saves the same JSON to a file.
8. Use the saved JSON file for any follow-up parsing or summarization instead of calling the reviews API again.
9. Return the validated response JSON, or summarize the product, overall rating, rating counts, top positive/negative review, individual reviews, and follow-up pagination when available.

## Commands

### Basic review lookup

```bash
bash <skill-path>/scripts/search_walmart_product_reviews.sh \
  --product-id 5689919121
```

`--product_id`, `--us-item-id`, and `--us_item_id` are accepted as aliases for `--product-id`.

### Review lookup with filters

```bash
bash <skill-path>/scripts/search_walmart_product_reviews.sh \
  --product-id 5689919121 \
  --rating 5 \
  --sort submission-desc \
  --page 2
```

### Save response JSON to a specific file

```bash
bash <skill-path>/scripts/search_walmart_product_reviews.sh \
  --product-id 5689919121 \
  --output ./out/walmart-product-reviews-result.json
```

### Token override for the current run

```bash
bash <skill-path>/scripts/search_walmart_product_reviews.sh \
  --product-id 5689919121 \
  --token "your bearer token"
```

## Fixed Request Shape

The script sends this payload shape, omitting optional fields that were not provided:

```json
{
  "product_id": "5689919121",
  "page": 2,
  "sort": "submission-desc",
  "rating": 5
}
```

Only `product_id` is required. Do not invent `product_id`, `page`, `sort`, or `rating` values when the user did not provide them.

The Frevana endpoint schema currently exposes only `product_id`, `page`, `sort`, and `rating`; do not pass unsupported passthrough fields such as `engine`, `api_key`, `output`, `no_cache`, `async`, or `zero_trace`..

## Response Shape

The API returns Frevana JSON. Common fields include:

- `search_metadata`
- `search_parameters`
- `product`
- `overall_rating`
- `total_count`
- `ratings`
- `top_positive`
- `top_negative`
- `reviews`
- `pagination`

Review entries commonly include `position`, `title`, `text`, `rating`, `positive_feedback`, `negative_feedback`, `review_submission_time`, `user_nickname`, and `customer_type`.

## Output

- Success: the script validates that the response body is JSON, writes it to a file, prints the saved path to stderr, and prints the JSON to stdout
- Default file path: `./out/walmart-product-reviews-<UTC timestamp>-<pid>.json`
- With `--output`: the same JSON is written to the specified file path instead of the default path
- Failure: the script prints the response body or parsing error and exits non-zero

## Notes

- Require `--product-id`, `--product_id`, `--us-item-id`, or `--us_item_id`.
- Use `--page` only when the user requests a review page; it must be an integer >= 1.
- Use `--sort` only when the user specifies review sorting. Accepted values are `relevancy`, `helpful`, `submission-desc`, `submission-asc`, `rating-desc`, and `rating-asc`.
- Use `--rating` only when the user requests a star filter. Accepted values are integers from 1 to 5.
- If the user only has a product search query, run `walmart-search` first and use the chosen result's `us_item_id` as `product_id`.
- If `curl` is missing, stop and tell the user to install `curl`.
- If `python3` is missing, stop and tell the user to install `python3`.
- Do not echo the Bearer token back to the user.
- Summarize review title, text, rating, date, user nickname, customer type, positive/negative feedback, and pagination when available unless the user asks for the full payload.

## Example Prompts

### 中文

- "查 Walmart product_id=5689919121 的评论"
- "获取 Walmart us_item_id 5689919121 的 1 星评论"
- "查这个 Walmart 商品评论，sort=submission-desc，page=2"
- "我只有 coffee maker 关键词" -> 先用 `walmart-search` 获取 `us_item_id`

### English

- "Get Walmart product reviews for product_id 5689919121."
- "Fetch 5-star Walmart reviews sorted by submission-desc for this us_item_id."
- "Call the Frevana walmart-product-reviews endpoint and save the raw JSON."
- "Find reviews for 'coffee maker'." -> Explain that a Walmart `product_id` / `us_item_id` is required, and suggest running Walmart search first.
