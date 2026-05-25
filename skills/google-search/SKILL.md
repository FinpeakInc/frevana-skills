---
name: google-search
description: Use when the user wants Google Search results through Frevana/SerpAPI, including organic results, related searches, related questions, knowledge graph, answer boxes, localized country/language results, pagination offsets, safe search, result count, or device-specific Google results.
---

# Google Search

Search Google results through Frevana.

## Purpose

This skill is for **finding regular Google Search results**.

Inputs:

- `q`
- optional `location`
- optional `gl`
- optional `hl`
- optional `num`
- optional `start`
- optional `safe`
- optional `device`

Output:

- validated response JSON with Google Search results
- the same validated JSON saved to a local file on every successful run

This skill validates that the response is JSON, saves it to disk, and returns it unchanged on stdout. Do **not** rewrite or reshape the returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- user-provided `q`
- optional `location`
- optional `gl`
- optional `hl`
- optional `num`
- optional `start`
- optional `safe`
- optional `device`
- `FREVANA_TOKEN` in the environment, or an explicit `--token` override for the current run
- `curl`
- `bash`
- `python3`

## Execution Order

Use this flow so the request stays simple and reliable:

1. Confirm the user has provided `q` or an equivalent Google search query.
2. Prefer the script over ad hoc `curl` commands.
3. Let the script read `FREVANA_TOKEN` first.
4. In interactive shell usage, if `FREVANA_TOKEN` is missing, the script may prompt for it.
5. In non-interactive or agent workflows, fail fast if the token is missing and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly.
6. Run the script once. It prints the validated JSON to stdout and saves the same JSON to a file.
7. Use the saved JSON file for any follow-up parsing or summarization instead of calling the search API again.
8. Return the validated response JSON, or summarize the most relevant search results if the user does not need the full payload.

## Commands

### Basic Google search

```bash
bash <skill-path>/scripts/search_google.sh \
  --q "coffee"
```

`--query` is accepted as an alias for `--q`.

### Search with country, language, and location

```bash
bash <skill-path>/scripts/search_google.sh \
  --q "coffee" \
  --location "Austin, Texas, United States" \
  --gl us \
  --hl en
```

### Search with pagination, result count, safe search, and device

```bash
bash <skill-path>/scripts/search_google.sh \
  --q "coffee" \
  --num 20 \
  --start 20 \
  --safe off \
  --device mobile
```

### Save response JSON to a specific file

```bash
bash <skill-path>/scripts/search_google.sh \
  --q "coffee" \
  --gl us \
  --hl en \
  --output ./out/google-search-result.json
```

### Token override for the current run

```bash
bash <skill-path>/scripts/search_google.sh \
  --q "coffee" \
  --token "your bearer token"
```

## Fixed Request Shape

The script sends this payload shape, omitting optional fields that were not provided:

```json
{
  "q": "coffee",
  "location": "Austin, Texas, United States",
  "gl": "us",
  "hl": "en",
  "num": 20,
  "start": 20,
  "safe": "off",
  "device": "mobile"
}
```

Only `q` is required. Do not invent `location`, `gl`, `hl`, `num`, `start`, `safe`, or `device` values when the user did not provide them.

The Frevana endpoint schema currently exposes only `q`, `location`, `gl`, `hl`, `num`, `start`, `safe`, and `device`; do not pass upstream SerpAPI-only fields such as `engine`, `api_key`, `output`, `no_cache`, `async`, or `zero_trace`, and do not pass other upstream Google Search fields unless the Frevana endpoint schema is expanded first.

## Response Shape

The API returns SerpAPI-origin JSON. Common fields include:

- `search_metadata`
- `search_parameters`
- `search_information`
- `organic_results`
- `related_questions`
- `related_searches`
- `knowledge_graph`
- `answer_box`
- `pagination`

## Output

- Success: the script validates that the response body is JSON, writes it to a file, prints the saved path to stderr, and prints the JSON to stdout
- Default file path: `./out/google-search-<UTC timestamp>-<pid>.json`
- With `--output`: the same JSON is written to the specified file path instead of the default path
- Failure: the script prints the response body or parsing error and exits non-zero

## Notes

- Require `--q` or `--query`
- Do not call the script twice just to save and summarize results. It always saves the same JSON that it prints.
- Use `--location` when the user requests a city, state, or country search origin
- Use `--gl` when the user requests a country or region code
- Use `--hl` when the user requests a language code
- Use `--num` only for result counts from `1` to `100`
- Use `--start` when the user requests pagination by result offset
- Use `--safe` only for `active` or `off`
- Use `--device` only for `desktop`, `mobile`, or `tablet`
- If `curl` is missing, stop and tell the user to install `curl`
- If `python3` is missing, stop and tell the user to install `python3`
- Do not echo the Bearer token back to the user
- Summarize the search results the user actually cares about instead of dumping raw JSON unless they ask for the full payload

## Example Prompts

### 中文

- "搜索 Google 上的 coffee"
- "查一下 Google 搜索 q=coffee，location=Austin, Texas, United States，gl=us，hl=en"
- "Google 搜索 coffee，第 3 页，移动端结果，并保存原始 JSON"

### English

- "Search Google for coffee"
- "Look up Google results for coffee with location=Austin, Texas, United States, gl=us, hl=en"
- "Search Google for coffee on mobile with start=20 and save the raw JSON"
