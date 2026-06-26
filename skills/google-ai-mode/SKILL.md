---
name: google-ai-mode
description: Use when the user wants Google AI Mode answers through Frevana, including localized AI Mode searches, subsequent request tokens, continuation, image URL input, or device-specific results.
---

# Google AI Mode

Search Google AI Mode through Frevana.

## Purpose

This skill calls Frevana's `/service/google-ai-mode` endpoint and returns the SerpAPI response unchanged.

Required input: `q`.

Supported request fields:

- `q` (required)
- `location`
- `uule`
- `gl`
- `hl`
- `next_page_token`
- `continuable`
- `subsequent_request_token`
- `image_url`
- `device`
- `no_cache`
- `async`
- `zero_trace`

The script validates that the response is JSON and prints it to stdout. Do not rewrite or reshape returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- query
- `FREVANA_TOKEN` in the environment variables, or `--token` for the current run
- `curl`, `bash`, and `python3`

The API base URL defaults to `https://ai-factory.frevana.com`. Set `FREVANA_API_BASE_URL` to point at another host.

## Commands

### Ask AI Mode

```bash
bash <skill-path>/scripts/search_google_ai_mode.sh \
  --q "best tools for competitor research"
```

### Continue a request

```bash
bash <skill-path>/scripts/search_google_ai_mode.sh \
  --q "best tools for competitor research" \
  --subsequent-request-token "TOKEN"
```

### Save JSON to a file

```bash
bash <skill-path>/scripts/search_google_ai_mode.sh \
  --q "Q" \
  --output "./out/google-ai-mode.json"
```

## Fixed Request Shape

The script sends this payload shape, omitting optional fields that were not provided:

```json
{
  "q": "Q",
  "location": "LOCATION",
  "uule": "UULE",
  "gl": "GL",
  "hl": "HL",
  "next_page_token": "NEXT_PAGE_TOKEN",
  "continuable": true,
  "subsequent_request_token": "SUBSEQUENT_REQUEST_TOKEN"
}
```

Do not pass unsupported fields. Do not pass SerpAPI `engine` or `api_key`; Frevana sets those server-side. Use `--output` for local file saving.

## Output

- Success: validated JSON on stdout
- With `--output`: the same JSON is also written to the requested file
- Failure: response body or parsing error on stderr, with a non-zero exit code

## Example Prompts

- "Search Google AI Mode for query."
- "Run Google AI Mode and save the raw JSON."
