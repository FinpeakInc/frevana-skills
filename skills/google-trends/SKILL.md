---
name: google-trends
description: Use when the user wants Google Trends trend data through Frevana, including keyword interest over time, regional trend data, related queries, category-specific trends, country-specific trends, Google property filtering, language selection, date ranges, or timezone-aware trend results. Use this whenever the user asks to query Google Trends, compare trend interest, check search trend demand, or requests the Frevana endpoint.
---

# Google Trends

Query Google Trends through Frevana.

## Purpose

This skill is for **retrieving Google Trends results**.

Inputs:

- `q`
- optional `geo`
- optional `cat`
- optional `date`
- optional `gprop`
- optional `hl`
- optional `tz`

Output:

- validated response JSON with Google Trends results
- the same validated JSON saved to a local file on every successful run

This skill validates that the response is JSON, saves it to disk, and returns it unchanged on stdout. Do **not** rewrite or reshape the returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- user-provided `q`
- optional `geo`
- optional `cat`
- optional `date`
- optional `gprop`
- optional `hl`
- optional `tz`
- `FREVANA_TOKEN` in the environment variables, or an explicit `--token` override for the current run
- `curl`
- `bash`
- `python3`

## Execution Order

Use this flow so the request stays simple and reliable:

1. Confirm the user has provided `q` or an equivalent trend search query.
2. Prefer the script over ad hoc `curl` commands.
3. Let the script read `FREVANA_TOKEN` first.
4. In interactive shell usage, if `FREVANA_TOKEN` is missing, the script may prompt for it.
5. In non-interactive or agent workflows, fail fast if the token is missing and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly.
6. Run the script once. It prints the validated JSON to stdout and saves the same JSON to a file.
7. Use the saved JSON file for any follow-up parsing or summarization instead of calling the trends API again.
8. Return the validated response JSON, or summarize the trend data if the user does not need the full payload.

## Commands

### Basic trends query

```bash
bash <skill-path>/scripts/search_google_trends.sh \
  --q "home treadmill"
```

`--query` is accepted as an alias for `--q`.

### Query with region, date range, language, and timezone

```bash
bash <skill-path>/scripts/search_google_trends.sh \
  --q "home treadmill" \
  --geo US \
  --date "today 12-m" \
  --hl en \
  --tz 420
```

### Query with category and Google property

```bash
bash <skill-path>/scripts/search_google_trends.sh \
  --q "running shoes" \
  --cat 18 \
  --gprop images
```

### Save response JSON to a specific file

```bash
bash <skill-path>/scripts/search_google_trends.sh \
  --q "home treadmill" \
  --geo US \
  --output ./out/google-trends-result.json
```

### Token override for the current run

```bash
bash <skill-path>/scripts/search_google_trends.sh \
  --q "home treadmill" \
  --token "your bearer token"
```

## Fixed Request Shape

The script sends this payload shape, omitting optional fields that were not provided:

```json
{
  "q": "home treadmill",
  "geo": "US",
  "cat": "18",
  "date": "today 12-m",
  "gprop": "images",
  "hl": "en",
  "tz": "420"
}
```

Only `q` is required. Do not invent `geo`, `cat`, `date`, `gprop`, `hl`, or `tz` values when the user did not provide them.

## Response Shape

The API returns Frevana JSON. This skill validates the response as JSON and returns it unchanged.

## Output

- Success: the script validates that the response body is JSON, writes it to a file, prints the saved path to stderr, and prints the JSON to stdout
- Default file path: `./out/google-trends-<UTC timestamp>-<pid>.json`
- With `--output`: the same JSON is written to the specified file path instead of the default path
- Failure: the script prints the response body or parsing error and exits non-zero

## Notes

- Require `--q` or `--query`
- Use `--geo` only when the user requests a country/region code for Trends
- Use `--cat` only when the user provides a category id
- Use `--date` only when the user provides a date range
- Use `--gprop` only when the user requests a Google property such as images, news, youtube, or froogle
- Use `--hl` only when the user requests a language code
- Use `--tz` only when the user provides a timezone offset in minutes
- If `curl` is missing, stop and tell the user to install `curl`
- If `python3` is missing, stop and tell the user to install `python3`
- Do not echo the Bearer token back to the user
- Summarize the trend results the user actually cares about instead of dumping raw JSON unless they ask for the full payload

## Example Prompts

### 中文

- "查询 Google Trends 上 home treadmill 的趋势"
- "查一下 Google Trends 里 q=家庭跑步机，geo=US，date=today 12-m，hl=en"
- "用 Google Trends 看 running shoes 在美国过去 12 个月的趋势，并保存原始 JSON"

### English

- "Search Google Trends for home treadmill"
- "Look up Google Trends for running shoes with geo=US and date=today 12-m"
- "Query Google Trends for coffee maker in the shopping property and save the raw JSON"
