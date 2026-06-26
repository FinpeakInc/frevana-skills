---
name: google-autocomplete
description: Use when the user wants Google Autocomplete suggestions through Frevana, including localized suggestions, cursor position, or client-specific autocomplete results.
---

# Google Autocomplete

Search Google Autocomplete suggestions through Frevana.

## Purpose

This skill calls Frevana's `/service/google-autocomplete` endpoint and returns the SerpAPI response unchanged.

Required input: `q`.

Supported request fields:

- `q` (required)
- `gl`
- `hl`
- `cp`
- `client`
- `no_cache`
- `async`
- `zero_trace`

The script validates that the response is JSON and prints it to stdout. Do not rewrite or reshape returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- query prefix
- `FREVANA_TOKEN` in the environment variables, or `--token` for the current run
- `curl`, `bash`, and `python3`

The API base URL defaults to `https://ai-factory.frevana.com`. Set `FREVANA_API_BASE_URL` to point at another host.

## Commands

### Get suggestions

```bash
bash <skill-path>/scripts/search_google_autocomplete.sh \
  --q "coffee" \
  --gl "us" \
  --hl "en"
```

### Save JSON to a file

```bash
bash <skill-path>/scripts/search_google_autocomplete.sh \
  --q "Q" \
  --output "./out/google-autocomplete.json"
```

## Fixed Request Shape

The script sends this payload shape, omitting optional fields that were not provided:

```json
{
  "q": "Q",
  "gl": "GL",
  "hl": "HL",
  "cp": 1,
  "client": "CLIENT",
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

- "Search Google Autocomplete for query prefix."
- "Run Google Autocomplete and save the raw JSON."
