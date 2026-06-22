---
name: google-forums-search
description: Use when the user wants Google Forums search results through Frevana, including forum-style discussions from Google's Forums tab, Reddit/Quora/community results, localized country/language results, device-specific forum results, pagination offsets, or date-bounded forum searches.
---

# Google Forums Search

Search Google Forums results through Frevana.

## Purpose

This skill is for **finding forum-style Google results** from Google's Forums tab.

Inputs:

- `q`
- optional `device`
- optional `hl`
- optional `gl`
- optional `start`
- optional `start_date`
- optional `end_date`

Output:

- validated response JSON with Google Forums results
- the same validated JSON saved to a local file on every successful run

This skill validates that the response is JSON, saves it to disk, and returns it unchanged on stdout. Do **not** rewrite or reshape the returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- user-provided `q`
- optional `device`
- optional `hl`
- optional `gl`
- optional `start`
- optional `start_date`
- optional `end_date`
- `FREVANA_TOKEN` in the environment variables, or an explicit `--token` override for the current run
- `curl`
- `bash`
- `python3`

## Execution Order

Use this flow so the request stays simple and reliable:

1. Confirm the user has provided `q` or an equivalent forum search query.
2. Prefer the script over ad hoc `curl` commands.
3. Let the script read `FREVANA_TOKEN` first.
4. In interactive shell usage, if `FREVANA_TOKEN` is missing, the script may prompt for it.
5. In non-interactive or agent workflows, fail fast if the token is missing and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly.
6. Run the script once. It prints the validated JSON to stdout and saves the same JSON to a file.
7. Use the saved JSON file for any follow-up parsing or summarization instead of calling the search API again.
8. Return the validated response JSON, or summarize the most relevant forum results if the user does not need the full payload.

## Commands

### Basic forum search

```bash
bash <skill-path>/scripts/search_google_forums.sh \
  --q "best programming language"
```

`--query` is accepted as an alias for `--q`.

### Search with country, language, and device

```bash
bash <skill-path>/scripts/search_google_forums.sh \
  --q "vibe coding" \
  --gl us \
  --hl en \
  --device mobile
```

### Search with pagination and date bounds

```bash
bash <skill-path>/scripts/search_google_forums.sh \
  --q "vibe coding" \
  --start 10 \
  --start-date 20260101 \
  --end-date 20260525
```

### Save response JSON to a specific file

```bash
bash <skill-path>/scripts/search_google_forums.sh \
  --q "vibe coding" \
  --output ./out/google-forums-search-result.json
```

### Token override for the current run

```bash
bash <skill-path>/scripts/search_google_forums.sh \
  --q "vibe coding" \
  --token "your bearer token"
```

## Fixed Request Shape

The script sends this payload shape, omitting optional fields that were not provided:

```json
{
  "q": "vibe coding",
  "device": "mobile",
  "hl": "en",
  "gl": "us",
  "start": 10,
  "start_date": "20260101",
  "end_date": "20260525"
}
```

Only `q` is required. Do not invent `device`, `hl`, `gl`, `start`, `start_date`, or `end_date` values when the user did not provide them.

The Frevana endpoint schema currently exposes only `q`, `device`, `hl`, `gl`, `start`, `start_date`, and `end_date`; do not pass unsupported passthrough fields such as `engine`, `api_key`, `output`, `no_cache`, `async`, or `zero_trace`, and do not pass other unsupported Google Forums fields such as `location`, `uule`, `period_unit`, `period_value`, `nfpr`, `filter`, or `tbs` unless the Frevana endpoint schema is expanded first.

## Response Shape

The API returns Frevana JSON. Common fields include:

- `search_metadata`
- `search_parameters`
- `search_information`
- `organic_results`
- `related_searches`
- `pagination`
- `pagination`

## Output

- Success: the script validates that the response body is JSON, writes it to a file, prints the saved path to stderr, and prints the JSON to stdout
- Default file path: `./out/google-forums-search-<UTC timestamp>-<pid>.json`
- With `--output`: the same JSON is written to the specified file path instead of the default path
- Failure: the script prints the response body or parsing error and exits non-zero

## Notes

- Require `--q` or `--query`
- Do not call the script twice just to save and summarize results. It always saves the same JSON that it prints.
- Use `--device` only for `desktop`, `mobile`, or `tablet`
- Use `--hl` when the user requests a language code
- Use `--gl` when the user requests a country code
- Use `--start` when the user requests pagination by result offset
- Use `--start-date` and `--end-date` only when the user asks for a specific date-bounded search; Frevana expects `YYYYMMDD` date strings
- If `curl` is missing, stop and tell the user to install `curl`
- If `python3` is missing, stop and tell the user to install `python3`
- Do not echo the Bearer token back to the user
- Summarize forum title, source/community, link, snippet, comment/answer count, date, sitelinks, and follow-up pagination when available unless the user asks for the full payload

## Example Prompts

### 中文

- "搜索 Google Forums 上的 vibe coding"
- "查 Google Forums 里 q=vibe coding，gl=us，hl=en，移动端"
- "Google Forums 搜索 AI coding，从 20260101 到 20260525，并保存原始 JSON"

### English

- "Search Google Forums for vibe coding"
- "Look up Google Forums results for vibe coding with gl=us, hl=en, and device=mobile"
- "Search Google Forums for AI coding from 20260101 to 20260525 and save the raw JSON"
