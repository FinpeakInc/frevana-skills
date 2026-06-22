---
name: ebay-search
description: Use when the user wants eBay product listing search results through Frevana, including keyword search, category-specific search, eBay domain selection, pagination, or result-count control.
---

# eBay Search

Search eBay product listings through Frevana.

## Purpose

This skill is for **finding eBay product listing results**.

Inputs:

- `query`
- optional `category_id`
- optional `ebay_domain`
- optional `page`
- optional `results_per_page`

Output:

- validated response JSON with eBay listing results
- the same validated JSON saved to a local file on every successful run

This skill validates that the response is JSON, saves it to disk, and returns it unchanged on stdout. Do **not** rewrite or reshape the returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- user-provided `query` or `category_id`
- optional `ebay_domain`
- optional `page`
- optional `results_per_page`
- `FREVANA_TOKEN` in the environment variables, or an explicit `--token` override for the current run
- `curl`
- `bash`
- `python3`

## Execution Order

Use this flow so the request stays simple and reliable:

1. Confirm the user has provided `query` or `category_id`.
2. Prefer the script over ad hoc `curl` commands.
3. Let the script read `FREVANA_TOKEN` first.
4. In interactive shell usage, if `FREVANA_TOKEN` is missing, the script may prompt for it.
5. In non-interactive or agent workflows, fail fast if the token is missing and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly.
6. Run the script once. It prints the validated JSON to stdout and saves the same JSON to a file.
7. Use the saved JSON file for any follow-up parsing or summarization instead of calling the search API again.
8. Return the validated response JSON, or summarize the most relevant listings if the user does not need the full payload.

## Commands

### Basic eBay search

```bash
bash <skill-path>/scripts/search_ebay.sh \
  --query "vintage watch"
```

### Search a category

```bash
bash <skill-path>/scripts/search_ebay.sh \
  --category-id 31387
```

### Search with domain, page, and result count

```bash
bash <skill-path>/scripts/search_ebay.sh \
  --query "sony headphones" \
  --ebay-domain ebay.com \
  --page 2 \
  --results-per-page 100
```

### Save response JSON to a specific file

```bash
bash <skill-path>/scripts/search_ebay.sh \
  --query "vintage watch" \
  --output ./out/ebay-search-result.json
```

### Token override for the current run

```bash
bash <skill-path>/scripts/search_ebay.sh \
  --query "vintage watch" \
  --token "your bearer token"
```

## Fixed Request Shape

The script sends this payload shape, omitting optional fields that were not provided:

```json
{
  "query": "vintage watch",
  "category_id": "31387",
  "ebay_domain": "ebay.com",
  "page": 2,
  "results_per_page": 100
}
```

At least one of `query` or `category_id` is required. Do not invent `category_id`, `ebay_domain`, `page`, or `results_per_page` values when the user did not provide them.

The Frevana endpoint is already scoped to eBay Search, so do not pass unsupported passthrough fields such as `engine`, `api_key`, `output`, `no_cache`, `async`, or `zero_trace`.

## Response Shape

The API returns Frevana JSON. Common result fields include `organic_results`, `related_searches`, `categories`, and `pagination`, depending on the eBay response.

## Output

- Success: the script validates that the response body is JSON, writes it to a file, prints the saved path to stderr, and prints the JSON to stdout
- Default file path: `./out/ebay-search-<UTC timestamp>-<pid>.json`
- With `--output`: the same JSON is written to the specified file path instead of the default path
- Failure: the script prints the response body or parsing error and exits non-zero

## Notes

- Require `--query` or `--category-id`
- Do not call the script twice just to save and summarize results. It always saves the same JSON that it prints.
- Use `--ebay-domain` only when the user specifies an eBay domain such as `ebay.com`
- Use `--page` when the user requests pagination; the value must be an integer >= 1
- Use `--results-per-page` when the user requests a result count; the value must be an integer from 1 to 240
- If `curl` is missing, stop and tell the user to install `curl`
- If `python3` is missing, stop and tell the user to install `python3`
- Do not echo the Bearer token back to the user
- Summarize listing title, product ID, price, condition, shipping, seller, and link when available unless the user asks for raw JSON

## Example Prompts

### 中文

- "搜索 eBay 上的 vintage watch"
- "查一下 eBay 里 query=sony headphones，page=2，results_per_page=100"
- "用 category_id=31387 搜索 eBay，并保存原始 JSON"

### English

- "Search eBay for vintage watch"
- "Look up eBay results for sony headphones on page 2 with 100 results per page"
- "Search eBay category_id 31387 and save the raw JSON"
