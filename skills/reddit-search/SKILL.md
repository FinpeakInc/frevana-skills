---
name: reddit-search
description: Use when the user wants Reddit search results by query, recent or top Reddit link posts, or paginated Reddit search through the Chrome Extension-backed Frevana scrape tool.
---

# Reddit Search

Search Reddit link posts through Reddit's public `search.json` endpoint using the local Frevana Chrome Extension session.

## Purpose

This skill is for **finding Reddit link posts by search query**.

Inputs:

- `q` (required) - search query
- `sort` (optional) - `new` or `top`, defaults to `new`
- `limit` (optional) - result count, defaults to `25`, max `100`
- `after` (optional) - pagination token from the previous response

Output:

- validated response JSON from Reddit Search

This skill validates that the response is JSON and returns it unchanged. Do **not** rewrite or reshape the returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- user-provided `q` or equivalent Reddit search query
- optional `sort`
- optional `limit`
- optional `after`
- bundled `scripts/setup.sh` wrapper, which downloads and runs the latest official Frevana setup script
- Frevana local daemon running after setup, default port `12306`
- Chrome connected through the Frevana Chrome Extension
- `curl`
- `bash`
- `python3`

This is a Chrome Extension skill. It uses the local daemon and Chrome Extension session, which lets Reddit set and reuse browser cookies without asking the user to pass cookies manually.

## Execution Order

Use this flow so the request stays simple and reliable:

1. Confirm the user has provided `q` or an equivalent Reddit search query.
2. Default `sort` to `new` when the user does not provide it.
3. Default `limit` to `25` when the user does not provide it.
4. Validate `sort` is either `new` or `top`.
5. Validate `limit` is an integer from `1` to `100`.
6. Prefer the script over ad hoc `curl` or raw HTTP requests.
7. Let the script run bundled `scripts/setup.sh` before every Frevana tool call.
8. If setup reports Chrome disconnected, stop and tell the user to open Chrome, connect the Frevana extension, and retry.
9. The script first calls `frevana_scrape` on `https://www.reddit.com/` to warm up the browser/extension session, then calls `frevana_scrape` on the `search.json` URL.
10. The script extracts and validates JSON from the scrape result.
11. Return the validated response JSON, or summarize the most relevant posts if the user does not need the full payload.
12. When useful, also save the JSON to a file.

## Commands

### Basic Reddit search

```bash
bash <skill-path>/scripts/search_reddit.sh \
  --q "openai"
```

`--query` is accepted as an alias for `--q`.

### Sort by top posts

```bash
bash <skill-path>/scripts/search_reddit.sh \
  --q "openai" \
  --sort top
```

### Change result count

```bash
bash <skill-path>/scripts/search_reddit.sh \
  --q "openai" \
  --limit 100
```

### Continue with an `after` pagination token

```bash
bash <skill-path>/scripts/search_reddit.sh \
  --q "openai" \
  --sort new \
  --limit 25 \
  --after "t3_example"
```

Use `--after` with the `data.after` value from the previous Reddit Search response.

### Save response JSON to a file

```bash
bash <skill-path>/scripts/search_reddit.sh \
  --q "openai" \
  --sort new \
  --output ./out/reddit-search-result.json
```

## Fixed Scrape Shape

The script first warms the browser session with:

```json
{
  "url": "https://www.reddit.com/",
  "provider": "url"
}
```

Then it scrapes the Reddit Search JSON URL:

```text
https://www.reddit.com/search.json?q=openai&type=link&sort=new&limit=25
```

using:

```json
{
  "url": "https://www.reddit.com/search.json?q=openai&type=link&sort=new&limit=25",
  "provider": "url"
}
```

The `type` parameter is always fixed to `link`. The script omits `after` unless the user provides it.

Do not invent unsupported Reddit Search fields. This skill supports only `q`, fixed `type=link`, `sort`, `limit`, and `after`.

## Response Shape

The API returns JSON. Pagination uses the top-level `data.after` field:

```json
{
  "kind": "Listing",
  "data": {
    "after": "t3_example",
    "children": [
      {
        "kind": "t3",
        "data": {
          "title": "Example post",
          "permalink": "/r/example/comments/...",
          "url": "https://example.com"
        }
      }
    ]
  }
}
```

This skill validates the response as JSON and returns it unchanged.

## Output

- Success: the script validates that the response body is JSON and prints it to stdout
- With `--output`: the same JSON is also written to the specified file path
- Failure: the script prints the response body or parsing error and exits non-zero

## Notes

- Require `--q` or `--query`
- `type` is fixed to `link`
- `sort` supports only `new` and `top`; default is `new`
- `limit` defaults to `25` and must be between `1` and `100`
- Use `--after` only when continuing from a previous response's `data.after`
- The script runs bundled `scripts/setup.sh` before every search, matching the original Frevana skill flow.
- The script uses `frevana_scrape` rather than direct `curl` to Reddit.
- The user must have Chrome open and the Frevana Chrome Extension connected.
- If the scrape returns a Reddit block page or empty content, open `https://www.reddit.com/` in Chrome through the connected profile and retry.
- If `curl` is missing, stop and tell the user to install `curl`
- If `python3` is missing, stop and tell the user to install `python3`
- Summarize the posts the user actually cares about instead of dumping raw JSON unless they ask for the full payload

## Example Prompts

### 中文

- "搜索 Reddit 上 openai 的最新 link 帖子"
- "查 Reddit q=openai，sort=top，limit=100"
- "用上一次返回的 after 继续翻页查 Reddit"

### English

- "Search Reddit link posts for openai"
- "Get top Reddit results for openai with limit 100"
- "Continue the Reddit search with this after token"
