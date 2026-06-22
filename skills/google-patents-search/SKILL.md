---
name: google-patents-search
description: Use when the user wants Google Patents search results through Frevana, including patent/application searches by query, pagination, result-count, language, or patent status filters such as GRANT and APPLICATION.
---

# Google Patents Search

Search Google Patents results through Frevana.

## Purpose

This skill is for **finding Google Patents results** by patent query.

Inputs:

- `q`
- optional `page`
- optional `num`
- optional `language`
- optional `status`

Output:

- validated response JSON with Google Patents results
- the same validated JSON saved to a local file on every successful run

This skill validates that the response is JSON, saves it to disk, and returns it unchanged on stdout. Do **not** rewrite or reshape the returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- user-provided `q`
- optional `page`
- optional `num`
- optional `language`
- optional `status`
- `FREVANA_TOKEN` in the environment variables, or an explicit `--token` override for the current run
- `curl`
- `bash`
- `python3`

## Execution Order

Use this flow so the request stays simple and reliable:

1. Confirm the user has provided `q` or an equivalent patent search query.
2. Prefer the script over ad hoc `curl` commands.
3. Let the script read `FREVANA_TOKEN` first.
4. In interactive shell usage, if `FREVANA_TOKEN` is missing, the script may prompt for it.
5. In non-interactive or agent workflows, fail fast if the token is missing and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly.
6. Run the script once. It prints the validated JSON to stdout and saves the same JSON to a file.
7. Use the saved JSON file for any follow-up parsing or summarization instead of calling the search API again.
8. Return the validated response JSON, or summarize the most relevant patent results if the user does not need the full payload.

## Commands

### Basic patents search

```bash
bash <skill-path>/scripts/search_google_patents.sh \
  --q "(Coffee)"
```

`--query` is accepted as an alias for `--q`.

### Search with status, language, page, and result count

```bash
bash <skill-path>/scripts/search_google_patents.sh \
  --q "(Coffee)" \
  --status GRANT \
  --language en \
  --page 0 \
  --num 10
```

### Save response JSON to a specific file

```bash
bash <skill-path>/scripts/search_google_patents.sh \
  --q "(Coffee)" \
  --output ./out/google-patents-search-result.json
```

### Token override for the current run

```bash
bash <skill-path>/scripts/search_google_patents.sh \
  --q "(Coffee)" \
  --token "your bearer token"
```

## Fixed Request Shape

The script sends this payload shape, omitting optional fields that were not provided:

```json
{
  "q": "(Coffee)",
  "page": 0,
  "num": 10,
  "language": "en",
  "status": "GRANT"
}
```

Only `q` is required. Do not invent `page`, `num`, `language`, or `status` values when the user did not provide them.

The Frevana endpoint schema currently exposes only `q`, `page`, `num`, `language`, and `status`; do not pass unsupported passthrough fields such as `engine`, `api_key`, `output`, `no_cache`, `async`, or `zero_trace`, and do not pass other unsupported Google Patents fields unless the Frevana endpoint schema is expanded first.

## Response Shape

The API returns Frevana JSON. Common fields include:

- `search_metadata`
- `search_parameters`
- `search_information`
- `organic_results`
- `summary`
- `pagination`
- `pagination`

## Output

- Success: the script validates that the response body is JSON, writes it to a file, prints the saved path to stderr, and prints the JSON to stdout
- Default file path: `./out/google-patents-search-<UTC timestamp>-<pid>.json`
- With `--output`: the same JSON is written to the specified file path instead of the default path
- Failure: the script prints the response body or parsing error and exits non-zero

## Notes

- Require `--q` or `--query`
- Do not call the script twice just to save and summarize results. It always saves the same JSON that it prints.
- Use `--page` only for page numbers `0` or greater
- Use `--num` only for result counts from `10` through `100`
- Use `--language` when the user requests a patents language filter
- Use `--status` only for `GRANT` or `APPLICATION`
- If `curl` is missing, stop and tell the user to install `curl`
- If `python3` is missing, stop and tell the user to install `python3`
- Do not echo the Bearer token back to the user
- Summarize patent title, publication number, assignee, inventor, priority date, filing date, publication date, grant date, snippet, link, and follow-up pagination when available unless the user asks for the full payload

## Example Prompts

### 中文

- "搜索 Google Patents 里的 Coffee"
- "查 Google Patents，q=(Coffee)，status=GRANT，language=en"
- "Google Patents 搜索 AI coffee machine，第 0 页，每页 10 条，并保存原始 JSON"

### English

- "Search Google Patents for (Coffee)"
- "Look up Google Patents for (Coffee) with status=GRANT and language=en"
- "Search Google Patents for AI coffee machine page 0 with 10 results and save the raw JSON"
