---
name: google-ads-search
description: Use when the user wants Google Ads sponsored search results through Frevana, including localized ad searches, safe search, no-auto-correct, and device-specific results.
---

# Google Ads Search

Search Google Ads through Frevana.

## Purpose

This skill calls Frevana's `/service/google-ads` endpoint and returns the SerpAPI response unchanged.

Required input: `q`, `location`.

Supported request fields:

- `q` (required)
- `location` (required)
- `hl`
- `safe`
- `nfpr`
- `device`
- `no_cache`
- `async`
- `zero_trace`

The script validates that the response is JSON and prints it to stdout. Do not rewrite or reshape returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- query and location
- `FREVANA_TOKEN` in the environment variables, or `--token` for the current run
- `curl`, `bash`, and `python3`

The API base URL defaults to `https://ai-factory.frevana.com`. Set `FREVANA_API_BASE_URL` to point at another host.

## Commands

### Search ads

```bash
bash <skill-path>/scripts/search_google_ads.sh \
  --q "project management software" \
  --location "Austin, Texas, United States"
```

### Save JSON to a file

```bash
bash <skill-path>/scripts/search_google_ads.sh \
  --q "Q" \
  --location "LOCATION" \
  --output "./out/google-ads-search.json"
```

## Fixed Request Shape

The script sends this payload shape, omitting optional fields that were not provided:

```json
{
  "q": "Q",
  "location": "LOCATION",
  "hl": "HL",
  "safe": "SAFE",
  "nfpr": 1,
  "device": "DEVICE",
  "no_cache": true,
  "async": true
}
```

Do not pass unsupported fields. Do not pass SerpAPI `engine` or `api_key`; Frevana sets those server-side. Use `--output` for local file saving.

## Output

- Success: validated JSON on stdout
- With `--output`: the same JSON is also written to the requested file
- Failure: response body or parsing error on stderr, with a non-zero exit code

## Example Prompts

- "Search Google Ads for query and location."
- "Run Google Ads Search and save the raw JSON."
