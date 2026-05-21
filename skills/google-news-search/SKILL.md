---
name: google-news-search
description: Use when the user wants Google News search results, current news articles by keyword, or scoped Google News results by topic, publication, section, or story token through Frevana.
---

# Google News Search

Search Google News through Frevana.

## Purpose

This skill is for **finding Google News results**.

Inputs:

- `q`
- optional `gl`
- optional `hl`
- optional `topic_token`
- optional `publication_token`
- optional `section_token`
- optional `story_token`

Output:

- validated response JSON with Google News search results

This skill validates that the response is JSON and returns it unchanged. Do **not** rewrite or reshape the returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- user-provided `q`
- optional `gl`
- optional `hl`
- optional `topic_token`
- optional `publication_token`
- optional `section_token`
- optional `story_token`
- `FREVANA_TOKEN` in the environment, or an explicit `--token` override for the current run
- `curl`
- `bash`
- `python3`

## Execution Order

Use this flow so the request stays simple and reliable:

1. Confirm the user has provided `q` or an equivalent search query.
2. Prefer the script over ad hoc `curl` commands.
3. Let the script read `FREVANA_TOKEN` first.
4. In interactive shell usage, if `FREVANA_TOKEN` is missing, the script may prompt for it.
5. In non-interactive or agent workflows, fail fast if the token is missing and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly.
6. Return the validated response JSON, or summarize the most relevant news items if the user does not need the full payload.
7. When useful, also save the JSON to a file.

## Commands

### Basic news search

```bash
bash <skill-path>/scripts/search_google_news.sh \
  --q "artificial intelligence"
```

`--query` is accepted as an alias for `--q`.

### Search with country and language

```bash
bash <skill-path>/scripts/search_google_news.sh \
  --q "artificial intelligence" \
  --gl US \
  --hl en
```

### Search with a Google News token

```bash
bash <skill-path>/scripts/search_google_news.sh \
  --q "economy" \
  --topic-token "CAAqJggKIiBDQkFTRWdvSUwyMHZNRGcxY1Y4U0FIVnVHZ0pWVXlnQVAB"
```

### Save response JSON to a file

```bash
bash <skill-path>/scripts/search_google_news.sh \
  --q "artificial intelligence" \
  --gl US \
  --hl en \
  --output ./out/google-news-search-result.json
```

### Token override for the current run

```bash
bash <skill-path>/scripts/search_google_news.sh \
  --q "artificial intelligence" \
  --token "your bearer token"
```

## Fixed Request Shape

The script sends this payload shape, omitting optional fields that were not provided:

```json
{
  "q": "artificial intelligence",
  "gl": "US",
  "hl": "en",
  "topic_token": "CAAq..."
}
```

Only `q` is required. Do not invent `gl`, `hl`, or token values when the user did not provide them.

## Response Shape

The API returns JSON. This skill validates the response as JSON and returns it unchanged.

## Output

- Success: the script validates that the response body is JSON and prints it to stdout
- With `--output`: the same JSON is also written to the specified file path
- Failure: the script prints the response body or parsing error and exits non-zero

## Notes

- Require `--q` or `--query`
- Use `--gl` when the user requests a specific country or region
- Use `--hl` when the user requests a specific language
- Use token fields only when the user provides the corresponding Google News token
- If `curl` is missing, stop and tell the user to install `curl`
- If `python3` is missing, stop and tell the user to install `python3`
- Do not echo the Bearer token back to the user
- Summarize the news results the user actually cares about instead of dumping raw JSON unless they ask for the full payload

## Example Prompts

### 中文

- "搜索 Google News 上的 AI 新闻"
- "查一下 Google News 里 q=tesla，gl=US，hl=en"
- "用这个 topic_token 搜 Google News，并保存原始 JSON"

### English

- "Search Google News for artificial intelligence"
- "Look up Google News results for Tesla with gl=US and hl=en"
- "Search Google News with this topic token and save the raw JSON to a file"
