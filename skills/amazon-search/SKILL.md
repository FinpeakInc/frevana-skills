---
name: amazon-search
description: Use when the user wants Amazon search results by keyword, product discovery, later result pages, or delivery-aware search results.
---

# Amazon Search

Search Amazon product listings through Frevana.

## Purpose

This skill is for **finding Amazon search results**.

Inputs:

- `query`
- optional `delivery_zip`
- optional `page`

Output:

- validated response JSON with Amazon search results

This skill validates that the response is JSON and returns it unchanged. Do **not** rewrite or reshape the returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- user-provided `query`
- optional `delivery_zip`
- optional `page`
- `FREVANA_TOKEN` in the environment, or an explicit `--token` override for the current run
- `curl`
- `bash`
- `python3`

## Execution Order

Use this flow so the request stays simple and reliable:

1. Confirm the user has provided `query`.
2. Prefer the script over ad hoc `curl` commands.
3. Let the script read `FREVANA_TOKEN` first.
4. In interactive shell usage, if `FREVANA_TOKEN` is missing, the script may prompt for it.
5. In non-interactive or agent workflows, fail fast if the token is missing and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly.
6. Return the validated response JSON, or summarize the most relevant listings if the user does not need the full payload.
7. When useful, also save the JSON to a file.

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

## Fixed Request Shape

The script sends this payload shape:

```json
{
  "query": "wireless mouse",
  "delivery_zip": "10001",
  "page": 1
}
```

`page` defaults to `1` when not provided.

## Response Shape

The API returns JSON. This skill validates the response as JSON and returns it unchanged.

## Output

- Success: the script validates that the response body is JSON and prints it to stdout
- With `--output`: the same JSON is also written to the specified file path
- Failure: the script prints the response body or parsing error and exits non-zero

## Notes

- Require `--query`
- Use `--page` when the user asks for later results or more options beyond the first page
- Use `--delivery-zip` when localized offer availability or delivery messaging matters
- If `curl` is missing, stop and tell the user to install `curl`
- If `python3` is missing, stop and tell the user to install `python3`
- Do not echo the Bearer token back to the user
- Summarize the listings the user actually cares about instead of dumping raw JSON unless they ask for the full payload

## Example Prompts

### 中文

- "搜索 Amazon 上的 wireless mouse"
- "帮我查一下 wireless mouse，第 2 页，ZIP 是 10001"
- "查 Amazon 搜索结果并把原始 JSON 保存到文件里"

### English

- "Search Amazon for wireless mouse"
- "Show me page 2 of Amazon search results for wireless mouse with ZIP 10001"
- "Search Amazon for this keyword and save the raw JSON to a file"
