---
name: amazon-search
description: Use when the user wants Amazon search results by keyword, product discovery, later result pages, or delivery-aware search results.
---

# Amazon Search

Search Amazon product listings through Frevana.

## Purpose

This skill is for **finding Amazon search results**.

Inputs:

- one of `query` or `node`
- optional `amazon_domain`
- optional `language`
- optional `delivery_zip`
- optional `shipping_location`
- optional `sort_by`
- optional `rh`
- optional `device`
- optional `no_cache`
- optional `async`
- optional `zero_trace`
- optional `page`
- optional `output`; defaults to `./out/amazon-search-<timestamp>-<pid>.json`

Output:

- validated response JSON with Amazon search results

This skill validates that the response is JSON and returns it unchanged. Do **not** rewrite or reshape the returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- one of `query` or `node`
- optional `amazon_domain`
- optional `language`
- optional `delivery_zip`
- optional `shipping_location`
- optional `sort_by`
- optional `rh`
- optional `device`
- optional `no_cache`
- optional `async`
- optional `zero_trace`
- optional `page`
- `FREVANA_TOKEN` in the environment variables, or an explicit `--token` override for the current run
- `curl`
- `bash`
- `python3`

## Execution Order

Use this flow so the request stays simple and reliable:

1. Confirm the user has provided exactly one of `query` or `node`.
2. Prefer the script over ad hoc `curl` commands.
3. Let the script read `FREVANA_TOKEN` first.
4. In interactive shell usage, if `FREVANA_TOKEN` is missing, the script may prompt for it.
5. In non-interactive or agent workflows, fail fast if the token is missing and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly.
6. Save the validated response JSON to `./out/amazon-search-<timestamp>-<pid>.json` by default, or to the user-provided `--output` path.
7. Return the validated response JSON, or summarize the most relevant listings if the user does not need the full payload.

## Commands

### Basic search

```bash
bash <skill-path>/scripts/search_amazon.sh \
  --query "wireless mouse"
```

### Search with page and delivery ZIP

```bash
bash <skill-path>/scripts/search_amazon.sh \
  --query "wireless mouse" \
  --delivery-zip 10001 \
  --page 2
```

### Search by category node

```bash
bash <skill-path>/scripts/search_amazon.sh \
  --node 283155 \
  --amazon-domain amazon.com \
  --language en_US
```

### Search with sorting, device, and shipping location

```bash
bash <skill-path>/scripts/search_amazon.sh \
  --query "wireless mouse" \
  --shipping-location "Seattle,Washington,United States" \
  --sort-by price-asc-rank \
  --device mobile
```

### Save response JSON to a file

```bash
bash <skill-path>/scripts/search_amazon.sh \
  --query "wireless mouse" \
  --delivery-zip 10001 \
  --page 1 \
  --output ./out/amazon-search-result.json
```

### Token override for the current run

```bash
bash <skill-path>/scripts/search_amazon.sh \
  --query "wireless mouse" \
  --token "your bearer token"
```

## Request Mapping

The script maps CLI options to the request body like this:

```json
{
  "query": "wireless mouse",
  "amazon_domain": "amazon.com",
  "language": "en_US",
  "delivery_zip": "10001",
  "shipping_location": "Seattle,Washington,United States",
  "sort_by": "price-asc-rank",
  "rh": "n:283155,p_76:1249146011",
  "device": "mobile",
  "no_cache": true,
  "async": false,
  "zero_trace": false,
  "page": 1
}
```

Rules:

- Provide exactly one of `query` or `node`
- `page` defaults to `1` when not provided
- `delivery_zip` can be used together with `shipping_location`; the endpoint prioritizes `delivery_zip`
- The script keeps local `--output` only as the save path and does not send request field `output`

## Response Shape

The API returns JSON. This skill validates the response as JSON and returns it unchanged.

## Output

- Success: the script validates that the response body is JSON and prints it to stdout
- By default, the same JSON is saved to `./out/amazon-search-<timestamp>-<pid>.json`
- With `--output`: the same JSON is written to the specified file path instead
- Failure: the script prints the response body or parsing error and exits non-zero

## Notes

- Require exactly one of `--query` or `--node`
- Do not pass `--query` and `--node` together
- Use `--amazon-domain` when the user needs a marketplace-specific Amazon domain
- Use `--language` when the endpoint needs an Amazon language override
- See `references/enums.md` for the current `amazon_domain` and `language` enum snapshot
- Use `--page` when the user asks for later results or more options beyond the first page
- Use `--delivery-zip` when localized offer availability or delivery messaging matters
- Use `--shipping-location` as the city/state/country alternative to `--delivery-zip`
- Use `--sort-by` only with supported values: `review-rank`, `price-asc-rank`, `price-desc-rank`, `date-desc-rank`, `relevanceblender`
- Use `--device` only with supported values: `desktop`, `mobile`
- Use `--no-cache`, `--async`, and `--zero-trace` only with boolean values `true` or `false`
- If `curl` is missing, stop and tell the user to install `curl`
- If `python3` is missing, stop and tell the user to install `python3`
- Do not echo the Bearer token back to the user
- Summarize the listings the user actually cares about instead of dumping raw JSON unless they ask for the full payload

## Example Prompts

### 中文

- "搜索 Amazon 上的 wireless mouse"
- "帮我查一下 wireless mouse，第 2 页，ZIP 是 10001"
- "按类目节点 283155 查 Amazon 搜索结果"
- "查 wireless mouse，按价格从低到高，移动端结果"
- "查 Amazon 搜索结果并把原始 JSON 保存到文件里"

### English

- "Search Amazon for wireless mouse"
- "Show me page 2 of Amazon search results for wireless mouse with ZIP 10001"
- "Search Amazon category node 283155"
- "Search Amazon for wireless mouse on mobile sorted by price low to high"
- "Search Amazon for this keyword and save the raw JSON to a file"
