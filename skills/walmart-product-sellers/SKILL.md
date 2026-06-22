---
name: walmart-product-sellers
description: Use when the user wants Walmart seller offers through Frevana, including sellers for a known Walmart product_id or us_item_id, store-specific seller availability, offer prices, delivery dates, return policies, or Frevana API calls.
---

# Walmart Product Sellers

Fetch Walmart product seller offers through Frevana.

## Purpose

This skill is for **retrieving seller offers for one known Walmart product**.

Inputs:

- `product_id`
- optional `store_id`

Output:

- validated response JSON with Walmart product seller results
- the same validated JSON saved to a local file on every successful run

The required `product_id` is the Walmart `us_item_id` from Walmart Search results or Walmart Product results. This skill validates that the response is JSON, saves it to disk, and returns it unchanged on stdout. Do **not** rewrite or reshape the returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- user-provided `product_id` / Walmart `us_item_id`
- optional Walmart `store_id`
- `FREVANA_TOKEN` in the environment variables, or an explicit `--token` override for the current run
- `curl`
- `bash`
- `python3`

## Execution Order

Use this flow so the request stays simple and reliable:

1. Confirm the user has provided `product_id` or an equivalent Walmart `us_item_id`.
2. If the user gives only a product name, search query, or generic Walmart URL without a clear item id, do not guess. Suggest running `walmart-search` first to obtain an `organic_results[].us_item_id`.
3. Use `store_id` only when the user explicitly provides a Walmart store ID.
4. Prefer the script over ad hoc `curl` commands.
5. Let the script read `FREVANA_TOKEN` first.
6. In interactive shell usage, if `FREVANA_TOKEN` is missing, the script may prompt for it.
7. In non-interactive or agent workflows, fail fast if the token is missing and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly.
8. Run the script once. It prints the validated JSON to stdout and saves the same JSON to a file.
9. Use the saved JSON file for any follow-up parsing or summarization instead of calling the sellers API again.
10. Return the validated response JSON, or summarize the product, shipping destination, sellers, prices, delivery, return policy, availability, seller type, and store-front links when available.

## Commands

### Basic seller lookup

```bash
bash <skill-path>/scripts/search_walmart_product_sellers.sh \
  --product-id 10543894
```

`--product_id`, `--us-item-id`, and `--us_item_id` are accepted as aliases for `--product-id`.

### Store-specific seller lookup

```bash
bash <skill-path>/scripts/search_walmart_product_sellers.sh \
  --product-id 10543894 \
  --store-id 5888
```

`--store_id` is accepted as an alias for `--store-id`.

### Save response JSON to a specific file

```bash
bash <skill-path>/scripts/search_walmart_product_sellers.sh \
  --product-id 10543894 \
  --output ./out/walmart-product-sellers-result.json
```

### Token override for the current run

```bash
bash <skill-path>/scripts/search_walmart_product_sellers.sh \
  --product-id 10543894 \
  --token "your bearer token"
```

## Fixed Request Shape

The script sends this payload shape, omitting optional fields that were not provided:

```json
{
  "product_id": "10543894",
  "store_id": "5888"
}
```

Only `product_id` is required. Do not invent `product_id` or `store_id` values when the user did not provide them.

The Frevana endpoint schema currently exposes only `product_id` and `store_id`; do not pass unsupported passthrough fields such as `engine`, `api_key`, `output`, `no_cache`, `async`, or `zero_trace`..

## Response Shape

The API returns Frevana JSON. Common fields include:

- `search_metadata`
- `search_parameters`
- `sellers_results`

The `sellers_results` object commonly includes `product`, `shipping_destination`, and `sellers`. Seller entries commonly include `position`, `us_item_id`, `offer_id`, `offer_type`, `availability_status`, `seller_id`, `seller_name`, `seller_display_name`, `seller_type`, `seller_store_front_url`, `price`, `extracted_price`, `return_policy_text`, `delivery_date`, `delivery_price`, and `extracted_delivery_price`.

## Output

- Success: the script validates that the response body is JSON, writes it to a file, prints the saved path to stderr, and prints the JSON to stdout
- Default file path: `./out/walmart-product-sellers-<UTC timestamp>-<pid>.json`
- With `--output`: the same JSON is written to the specified file path instead of the default path
- Failure: the script prints the response body or parsing error and exits non-zero

## Notes

- Require `--product-id`, `--product_id`, `--us-item-id`, or `--us_item_id`.
- Use `--store-id` only when the user provides a Walmart store ID.
- If the user only has a product search query, run `walmart-search` first and use the chosen result's `us_item_id` as `product_id`.
- If `curl` is missing, stop and tell the user to install `curl`.
- If `python3` is missing, stop and tell the user to install `python3`.
- Do not echo the Bearer token back to the user.
- Summarize product name, shipping destination, seller name, seller type, availability, offer type, price, delivery date, delivery price, return policy, and seller store-front URL unless the user asks for the full payload.

## Example Prompts

### 中文

- "查 Walmart product_id=10543894 的 sellers"
- "获取 Walmart us_item_id 10543894 在 store_id=5888 的卖家报价"
- "查这个 Walmart 商品有哪些第三方卖家"
- "我只有 coffee maker 关键词" -> 先用 `walmart-search` 获取 `us_item_id`

### English

- "Get Walmart product sellers for product_id 10543894."
- "Fetch Walmart seller offers for this us_item_id and store_id 5888."
- "Call the Frevana walmart-product-sellers endpoint and save the raw JSON."
- "Find sellers for 'coffee maker'." -> Explain that a Walmart `product_id` / `us_item_id` is required, and suggest running Walmart search first.
