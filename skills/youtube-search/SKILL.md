---
name: youtube-search
description: Use when the user wants YouTube search results by keyword, localized YouTube video results, filtered YouTube results using an sp parameter, or paginated YouTube Search results through Frevana.
---

# YouTube Search

Search YouTube videos through Frevana.

## Purpose

This skill is for **finding YouTube search results**.

Inputs:

- `search_query`
- optional `sp`
- optional `hl`
- optional `gl`

Output:

- validated response JSON with YouTube Search results

This skill validates that the response is JSON and returns it unchanged. Do **not** rewrite or reshape the returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- user-provided `search_query`
- optional `sp`
- optional `hl`
- optional `gl`
- `FREVANA_TOKEN` in the environment variables, or an explicit `--token` override for the current run
- `curl`
- `bash`
- `python3`

## Execution Order

Use this flow so the request stays simple and reliable:

1. Confirm the user has provided `search_query` or an equivalent YouTube search keyword.
2. Prefer the script over ad hoc `curl` commands.
3. Let the script read `FREVANA_TOKEN` first.
4. In interactive shell usage, if `FREVANA_TOKEN` is missing, the script may prompt for it.
5. In non-interactive or agent workflows, fail fast if the token is missing and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly.
6. Return the validated response JSON, or summarize the most relevant videos if the user does not need the full payload.
7. When useful, also save the JSON to a file.

## Commands

### Basic YouTube search

```bash
bash <skill-path>/scripts/search_youtube.sh \
  --search-query "mrbeast"
```

`--query` is accepted as an alias for `--search-query`.

### Search with country and language

```bash
bash <skill-path>/scripts/search_youtube.sh \
  --search-query "mrbeast" \
  --gl us \
  --hl en
```

### Search with an `sp` filter or pagination token

```bash
bash <skill-path>/scripts/search_youtube.sh \
  --search-query "mrbeast" \
  --sp "EgIQAQ%253D%253D" \
  --hl en \
  --gl us
```

Use `--sp` when the user provides a YouTube filter token or wants to continue a paginated result using a follow-up token from the response.

### Save response JSON to a file

```bash
bash <skill-path>/scripts/search_youtube.sh \
  --search-query "mrbeast" \
  --gl us \
  --hl en \
  --output ./out/youtube-search-result.json
```

### Token override for the current run

```bash
bash <skill-path>/scripts/search_youtube.sh \
  --search-query "mrbeast" \
  --token "your bearer token"
```

## Fixed Request Shape

The script sends this payload shape, omitting optional fields that were not provided:

```json
{
  "search_query": "mrbeast",
  "sp": "EgIQAQ%253D%253D",
  "hl": "en",
  "gl": "us"
}
```

Only `search_query` is required. Do not invent `sp`, `hl`, or `gl` values when the user did not provide them.

The Frevana endpoint is already scoped to YouTube Search, so do not pass unsupported passthrough fields such as `engine`, `api_key`, `output`, `no_cache`, `async`, or `zero_trace`.

## Response Shape

The API returns JSON. This skill validates the response as JSON and returns it unchanged.

## Output

- Success: the script validates that the response body is JSON and prints it to stdout
- With `--output`: the same JSON is also written to the specified file path
- Failure: the script prints the response body or parsing error and exits non-zero

## Notes

- Require `--search-query` or `--query`
- Use `--gl` when the user requests a specific country or region
- Use `--hl` when the user requests a specific language
- Use `--sp` only when the user provides a filter or pagination token, or asks to continue a result using a token already present in a previous YouTube Search response
- If `curl` is missing, stop and tell the user to install `curl`
- If `python3` is missing, stop and tell the user to install `python3`
- Do not echo the Bearer token back to the user
- Summarize the videos the user actually cares about instead of dumping raw JSON unless they ask for the full payload

## Example Prompts

### 中文

- "搜索 YouTube 上的 mrbeast"
- "查一下 YouTube 里 search_query=mrbeast，gl=us，hl=en"
- "用这个 sp 参数继续查 YouTube Search，并保存原始 JSON"

### English

- "Search YouTube for mrbeast"
- "Look up YouTube results for mrbeast with gl=us and hl=en"
- "Search YouTube with this sp token and save the raw JSON to a file"
