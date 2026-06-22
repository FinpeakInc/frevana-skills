---
name: home-depot-search
description: Use when the user wants Home Depot product search results through Frevana, including product titles, brands, prices, ratings, reviews, delivery or pickup availability, country-specific US/Canada searches, Home Depot store-specific searches, delivery ZIP filtering, pagination, page size control, or Frevana API calls.
---

# Home Depot Search

Search Home Depot product listings through Frevana.

## Purpose

This skill is for **finding Home Depot product search results**.

Inputs:

- `q`
- optional `country`
- optional `store`
- optional `delivery_zip`
- optional `page`
- optional `page_size`

Output:

- validated response JSON with Home Depot product results
- the same validated JSON saved to a local file on every successful run

This skill validates that the response is JSON, saves it to disk, and returns it unchanged on stdout. Do **not** rewrite or reshape the returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- user-provided `q`
- optional `country`
- optional `store`
- optional `delivery_zip`
- optional `page`
- optional `page_size`
- `FREVANA_TOKEN` in the environment variables, or an explicit `--token` override for the current run
- `curl`
- `bash`
- `python3`

## Execution Order

Use this flow so the request stays simple and reliable:

1. Confirm the user has provided `q` or an equivalent Home Depot product search query.
2. Prefer the script over ad hoc `curl` commands.
3. Let the script read `FREVANA_TOKEN` first.
4. In interactive shell usage, if `FREVANA_TOKEN` is missing, the script may prompt for it.
5. In non-interactive or agent workflows, fail fast if the token is missing and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly.
6. Run the script once. It prints the validated JSON to stdout and saves the same JSON to a file.
7. Use the saved JSON file for any follow-up parsing or summarization instead of calling the search API again.
8. Return the validated response JSON, or summarize the most relevant products if the user does not need the full payload.

## Commands

### Basic Home Depot search

```bash
bash <skill-path>/scripts/search_home_depot.sh \
  --q "patio chairs"
```

`--query` is accepted as an alias for `--q`.

### Search with country, store, and delivery ZIP

```bash
bash <skill-path>/scripts/search_home_depot.sh \
  --q "cordless drill" \
  --country us \
  --store 121 \
  --delivery-zip 10001
```

### Search with pagination and page size

```bash
bash <skill-path>/scripts/search_home_depot.sh \
  --q "paint roller" \
  --page 2 \
  --page-size 40
```

### Save response JSON to a specific file

```bash
bash <skill-path>/scripts/search_home_depot.sh \
  --q "workbench" \
  --output ./out/home-depot-search-result.json
```

### Token override for the current run

```bash
bash <skill-path>/scripts/search_home_depot.sh \
  --q "workbench" \
  --token "your bearer token"
```

## Fixed Request Shape

The script sends this payload shape, omitting optional fields that were not provided:

```json
{
  "q": "cordless drill",
  "country": "us",
  "store": "121",
  "delivery_zip": "10001",
  "page": 2,
  "page_size": 40
}
```

Only `q` is required. Do not invent `country`, `store`, `delivery_zip`, `page`, or `page_size` values when the user did not provide them.

The Frevana endpoint schema currently exposes only `q`, `country`, `store`, `delivery_zip`, `page`, and `page_size`; do not pass unsupported passthrough fields such as `engine`, `api_key`, `output`, `no_cache`, `async`, `zero_trace`, `hd_sort`, `hd_filter_tokens`, `store_id`, `nao`, `ps`, `sort`, `filter`, `lowerbound`, `upperbound`, `minmax`, or `pagesize`.

## Response Shape

The API returns Frevana JSON. Common result fields include `products`, `filters`, `taxonomy`, `search_information`, and `pagination`, depending on the Home Depot response.

## Output

- Success: the script validates that the response body is JSON, writes it to a file, prints the saved path to stderr, and prints the JSON to stdout
- Default file path: `./out/home-depot-search-<UTC timestamp>-<pid>.json`
- With `--output`: the same JSON is written to the specified file path instead of the default path
- Failure: the script prints the response body or parsing error and exits non-zero

## Notes

- Require `--q` or `--query`
- Do not call the script twice just to save and summarize results. It always saves the same JSON that it prints.
- Use `--country` only when the user specifies a country; accepted values are `us` and `ca`
- Use `--store` only when the user specifies a Home Depot store ID
- Use `--delivery-zip` only when the user specifies a delivery ZIP or postal code
- Use `--page` when the user requests pagination; the value must be an integer >= 1
- Use `--page-size` when the user requests a result count; the value must be an integer from 1 to 40
- Home Depot may return a different number of products than the requested page size
- If `curl` is missing, stop and tell the user to install `curl`
- If `python3` is missing, stop and tell the user to install `python3`
- Do not echo the Bearer token back to the user
- Summarize product title, product ID, brand, price, rating, reviews, delivery, pickup, link, and follow-up pagination when available unless the user asks for the full payload

## Example Prompts

### 中文

- "搜索 Home Depot 上的 patio chairs"
- "查一下 Home Depot 里 q=cordless drill，country=us，delivery_zip=10001"
- "Home Depot 搜索 paint roller，第 2 页，每页 40 条，并保存原始 JSON"

### English

- "Search Home Depot for patio chairs"
- "Look up Home Depot results for cordless drill with country=us and delivery_zip=10001"
- "Search Home Depot for paint roller on page 2 with page_size=40 and save raw JSON"
