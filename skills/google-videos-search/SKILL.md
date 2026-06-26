---
name: google-videos-search
description: Use when the user wants Google Videos results through Frevana, including localization, language restriction, safe search, advanced filters, pagination, or device-specific results.
---

# Google Videos Search

Search Google Videos through Frevana.

## Purpose

This skill calls Frevana's `/service/google-videos` endpoint and returns the SerpAPI response unchanged.

Required input: `q`.

Supported request fields:

- `q` (required)
- `location`
- `uule`
- `google_domain`
- `gl`
- `hl`
- `lr`
- `device`
- `start`
- `tbs`
- `safe`
- `nfpr`
- `filter`
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

### Search videos

```bash
bash <skill-path>/scripts/search_google_videos.sh \
  --q "coffee recipes" \
  --gl "us" \
  --hl "en"
```

### Save JSON to a file

```bash
bash <skill-path>/scripts/search_google_videos.sh \
  --q "Q" \
  --output "./out/google-videos-search.json"
```

## Fixed Request Shape

The script sends this payload shape, omitting optional fields that were not provided:

```json
{
  "q": "Q",
  "location": "LOCATION",
  "uule": "UULE",
  "google_domain": "GOOGLE_DOMAIN",
  "gl": "GL",
  "hl": "HL",
  "lr": "LR",
  "device": "DEVICE"
}
```

Do not pass unsupported fields. Do not pass SerpAPI `engine` or `api_key`; Frevana sets those server-side. Use `--output` for local file saving.

## Output

- Success: validated JSON on stdout
- With `--output`: the same JSON is also written to the requested file
- Failure: response body or parsing error on stderr, with a non-zero exit code

## Example Prompts

- "Search Google Videos for query."
- "Run Google Videos Search and save the raw JSON."
