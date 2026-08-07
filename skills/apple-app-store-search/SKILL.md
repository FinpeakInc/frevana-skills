---
name: apple-app-store-search
description: Use when the user wants Apple App Store search results through Frevana, including searching apps by query term, developer, category, country, language, device type, or pagination.
---

# Apple App Store Search

Search app listings from the Apple App Store through Frevana.

## Purpose

This skill is for **searching Apple App Store app listings**.

Inputs:

- `term` (or `--q` / `--query`)
- optional `country` (default: `us`)
- optional `lang` (default: `en-us`)
- optional `num` (1 to 200, default: 10)
- optional `page` (0-indexed, default: 0)
- optional `disallow_explicit` (boolean)
- optional `property` (e.g. `developer`)
- optional `category_id` (numeric genre ID, e.g. 6014 for Games)
- optional `device` (`desktop` | `tablet` | `mobile`, default: `desktop`)
- optional `output`; defaults to `./out/apple-app-store-search-<timestamp>-<pid>.json`
- optional SerpAPI flags: `serpapi_output` (`json` | `html`), `no_cache`, `async`, `zero_trace`

Output:

- validated response JSON with Apple App Store search results
- the same validated JSON saved to a local file on every successful run

This skill validates that the response is JSON, saves it to disk, and returns it unchanged on stdout. Do **not** rewrite or reshape the returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- user-provided `term`
- optional `country`, `lang`, `num`, `page`, `disallow_explicit`, `property`, `category_id`, `device`
- `FREVANA_TOKEN` in the environment variables, or an explicit `--token` override for the current run
- `curl`
- `bash`
- `python3`

## Execution Order

Use this flow so the request stays simple and reliable:

1. Confirm the user has provided `term`.
2. Prefer the script over ad hoc `curl` commands.
3. Let the script read `FREVANA_TOKEN` first.
4. In interactive shell usage, if `FREVANA_TOKEN` is missing, the script may prompt for it.
5. In non-interactive or agent workflows, fail fast if the token is missing and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly.
6. Run the script once. It prints the validated JSON to stdout and saves the same JSON to a file.
7. Use the saved JSON file for any follow-up parsing or summarization instead of calling the search API again.
8. Return the validated response JSON, or summarize the search results if the user does not need the full payload.

## Commands

### Basic search

```bash
bash <skill-path>/scripts/search_apple_app_store.sh \
  --term "instagram"
```

Aliases `--query` and `--q` are accepted for `--term`.

### Search with region, language, category, and device

```bash
bash <skill-path>/scripts/search_apple_app_store.sh \
  --term "games" \
  --country us \
  --lang en-us \
  --category-id 6014 \
  --num 20 \
  --page 0 \
  --device mobile
```

### Search by developer name

```bash
bash <skill-path>/scripts/search_apple_app_store.sh \
  --term "Apple" \
  --property developer
```

### Save response JSON to a specific file

```bash
bash <skill-path>/scripts/search_apple_app_store.sh \
  --term "instagram" \
  --output ./out/my-apple-search.json
```

### Token override for the current run

```bash
bash <skill-path>/scripts/search_apple_app_store.sh \
  --term "instagram" \
  --token "your bearer token"
```

## Fixed Request Shape

The script sends this payload shape, omitting optional fields that were not provided:

```json
{
  "term": "instagram",
  "country": "us",
  "lang": "en-us",
  "num": 10,
  "page": 0,
  "disallow_explicit": false,
  "property": "developer",
  "category_id": 6014,
  "device": "desktop"
}
```

Only `term` is required. Do not invent optional parameter values when the user did not provide them.

## Response Shape

The API returns JSON. Common sections include:

- `search_metadata`
- `search_parameters`
- `organic_results`

## Output

- Success: the script validates that the response body is JSON, writes it to a file, prints the saved path to stderr, and prints the JSON to stdout
- Default file path: `./out/apple-app-store-search-<timestamp>-<pid>.json`
- With `--output`: the same JSON is written to the specified file path instead of the default path
- Failure: the script prints the response body or parsing error and exits non-zero

## Notes

- Require `--term` (or `--q`/`--query`)
- `--num` must be an integer from 1 to 200
- `--page` is 0-indexed (`>= 0`)
- `--device` must be `desktop`, `tablet`, or `mobile`
- If `curl` is missing, stop and tell the user to install `curl`
- If `python3` is missing, stop and tell the user to install `python3`
- Do not echo the Bearer token back to the user
- Summarize search results instead of dumping raw JSON unless the user asks for the full payload

## Example Prompts

### 中文

- "搜索 Apple App Store 上的 instagram"
- "查一下 App Store 开发者 Apple 的应用， country=us，lang=en-us"
- "搜索 App Store 中的游戏应用，category_id=6014，移动端结果"

### English

- "Search Apple App Store for instagram"
- "Look up App Store apps by developer Apple in country=us, lang=en-us"
- "Search App Store games category 6014 on mobile device"
