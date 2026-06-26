---
name: google-ai-overview
description: Use when the user wants a Google AI Overview through Frevana from a page token returned by Google Search SerpAPI results.
---

# Google AI Overview

Retrieve a Google AI Overview through Frevana.

## Purpose

This skill calls Frevana's `/service/google-ai-overview` endpoint and returns the SerpAPI response unchanged.

Required input: `page_token`.

Supported request fields:

- `page_token` (required)
- `no_cache`
- `async`
- `zero_trace`

The script validates that the response is JSON and prints it to stdout. Do not rewrite or reshape returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- page token
- `FREVANA_TOKEN` in the environment variables, or `--token` for the current run
- `curl`, `bash`, and `python3`

The API base URL defaults to `https://ai-factory.frevana.com`. Set `FREVANA_API_BASE_URL` to point at another host.

## Commands

### Get AI Overview

```bash
bash <skill-path>/scripts/get_google_ai_overview.sh \
  --page-token "PAGE_TOKEN"
```

### Save JSON to a file

```bash
bash <skill-path>/scripts/get_google_ai_overview.sh \
  --page-token "PAGE_TOKEN" \
  --output "./out/google-ai-overview.json"
```

## Fixed Request Shape

The script sends this payload shape, omitting optional fields that were not provided:

```json
{
  "page_token": "PAGE_TOKEN",
  "no_cache": true,
  "async": true,
  "zero_trace": true
}
```

Do not pass unsupported fields. Do not pass SerpAPI `engine` or `api_key`; Frevana sets those server-side. Use `--output` for local file saving.

## Output

- Success: validated JSON on stdout
- With `--output`: the same JSON is also written to the requested file
- Failure: response body or parsing error on stderr, with a non-zero exit code

## Example Prompts

- "Get Google AI Overview for page token."
- "Run Google AI Overview and save the raw JSON."
