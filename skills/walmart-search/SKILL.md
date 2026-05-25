---
name: walmart-search
description: Use when the user wants Walmart product search results through Frevana/SerpAPI, including product titles, prices, ratings, sellers, thumbnails, Walmart category filtering, device-specific results, pagination, sorting, facets, price bounds, or calls to /service/serpapi/walmart-search.
---

# Walmart Search

Search Walmart product listings through Frevana.

## Purpose

This skill is for **finding Walmart product search results**.

Inputs:

- `query`
- optional `device`
- optional `cat_id`
- optional `page`
- optional `sort`
- optional `facet`
- optional `min_price`
- optional `max_price`

Output:

- validated response JSON with Walmart product results
- the same validated JSON saved to a local file on every successful run

This skill validates that the response is JSON, saves it to disk, and returns it unchanged on stdout. Do **not** rewrite or reshape the returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- user-provided `query`
- optional `device`
- optional `cat_id`
- optional `page`
- optional `sort`
- optional `facet`
- optional `min_price`
- optional `max_price`
- `FREVANA_TOKEN` in the environment, or an explicit `--token` override for the current run
- `curl`
- `bash`
- `python3`

## Execution Order

Use this flow so the request stays simple and reliable:

1. Confirm the user has provided `query` or an equivalent Walmart product search query.
2. Prefer the script over ad hoc `curl` commands.
3. Let the script read `FREVANA_TOKEN` first.
4. In interactive shell usage, if `FREVANA_TOKEN` is missing, the script may prompt for it.
5. In non-interactive or agent workflows, fail fast if the token is missing and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly.
6. Run the script once. It prints the validated JSON to stdout and saves the same JSON to a file.
7. Use the saved JSON file for any follow-up parsing or summarization instead of calling the search API again.
8. Return the validated response JSON, or summarize the most relevant products if the user does not need the full payload.

## Commands

### Basic Walmart search

```bash
bash <skill-path>/scripts/search_walmart.sh \
  --query "coffee maker"
```

`--q` is accepted as an alias for `--query`.

### Search with filters, sorting, and pagination

```bash
bash <skill-path>/scripts/search_walmart.sh \
  --query "wireless earbuds" \
  --device mobile \
  --sort price_low \
  --min-price 25 \
  --max-price 100 \
  --page 2
```

### Search within a Walmart category

```bash
bash <skill-path>/scripts/search_walmart.sh \
  --query "coffee maker" \
  --cat-id 4044
```

### Save response JSON to a specific file

```bash
bash <skill-path>/scripts/search_walmart.sh \
  --query "coffee maker" \
  --output ./out/walmart-search-result.json
```

### Token override for the current run

```bash
bash <skill-path>/scripts/search_walmart.sh \
  --query "coffee maker" \
  --token "your bearer token"
```

## Fixed Request Shape

The script sends this payload shape, omitting optional fields that were not provided:

```json
{
  "query": "wireless earbuds",
  "device": "mobile",
  "cat_id": "4044",
  "page": 2,
  "sort": "price_low",
  "facet": "brand:Sony",
  "min_price": 25,
  "max_price": 100
}
```

Only `query` is required. Do not invent `device`, `cat_id`, `page`, `sort`, `facet`, `min_price`, or `max_price` values when the user did not provide them.

The Frevana endpoint schema currently exposes only `query`, `device`, `cat_id`, `page`, `sort`, `facet`, `min_price`, and `max_price`; do not pass upstream SerpAPI-only fields such as `engine`, `api_key`, `output`, `no_cache`, `async`, `zero_trace`, `walmart_domain`, `soft_sort`, `store_id`, `spelling`, `nd_en`, or `include_filters`.

## Response Shape

The API returns SerpAPI-origin JSON. Common result fields include `organic_results`, `filters`, `related_queries`, `spell_check`, `search_information`, and `pagination`, depending on the Walmart response.

## Output

- Success: the script validates that the response body is JSON, writes it to a file, prints the saved path to stderr, and prints the JSON to stdout
- Default file path: `./out/walmart-search-<UTC timestamp>-<pid>.json`
- With `--output`: the same JSON is written to the specified file path instead of the default path
- Failure: the script prints the response body or parsing error and exits non-zero

## Notes

- Require `--query` or `--q`
- Do not call the script twice just to save and summarize results. It always saves the same JSON that it prints.
- Use `--device` only when the user specifies a device; accepted values are `desktop`, `mobile`, and `tablet`.
- Use `--cat-id` only when the user specifies a Walmart category ID.
- Use `--page` when the user requests pagination; the value must be an integer from 1 to 100.
- Use `--sort` only when the user specifies sorting; accepted values are `price_low`, `price_high`, `best_seller`, `best_match`, `rating_high`, and `new`.
- Use `--facet` only when the user provides a Walmart facet filter string.
- Use `--min-price` and `--max-price` only when the user specifies price bounds.
- If `curl` is missing, stop and tell the user to install `curl`.
- If `python3` is missing, stop and tell the user to install `python3`.
- Do not echo the Bearer token back to the user.
- Summarize product title, item ID, product ID, price, currency, rating, reviews, seller, shipping signals, link, and follow-up pagination when available unless the user asks for the full payload.

## Example Prompts

### 中文

- "搜索 Walmart 上的 coffee maker"
- "查一下 Walmart 里 query=wireless earbuds，sort=price_low，page=2"
- "Walmart 搜索 laptop，价格 300 到 800，并保存原始 JSON"

### English

- "Search Walmart for coffee maker"
- "Look up Walmart results for wireless earbuds sorted by price low"
- "Search Walmart for laptop with min_price 300 and max_price 800 and save raw JSON"
