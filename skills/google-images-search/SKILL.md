---
name: google-images-search
description: Use when the user wants Google Images results through Frevana, including image filters, localization, safe search, pagination, time periods, colors, size, type, or license filters.
---

# Google Images Search

Search Google Images through Frevana.

## Purpose

This skill calls Frevana's `/service/google-images` endpoint and returns the SerpAPI response unchanged.

Required input: `q`.

Supported request fields:

- `q` (required)
- `location`
- `uule`
- `google_domain`
- `gl`
- `hl`
- `cr`
- `device`
- `start`
- `ijn`
- `tbs`
- `chips`
- `imgar`
- `imgsz`
- `safe`
- `nfpr`
- `filter`
- `image_size`
- `image_type`
- `image_color`
- `licenses`
- `period_unit`
- `period_value`
- `start_date`
- `end_date`
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

### Search images

```bash
bash <skill-path>/scripts/search_google_images.sh \
  --q "coffee shop interior" \
  --gl "us" \
  --hl "en"
```

### Filter images

```bash
bash <skill-path>/scripts/search_google_images.sh \
  --q "coffee shop interior" \
  --image-color "blue" \
  --safe "active"
```

### Save JSON to a file

```bash
bash <skill-path>/scripts/search_google_images.sh \
  --q "Q" \
  --output "./out/google-images-search.json"
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
  "cr": "CR",
  "device": "DEVICE"
}
```

Do not pass unsupported fields. Do not pass SerpAPI `engine` or `api_key`; Frevana sets those server-side. Use `--output` for local file saving.

## Output

- Success: validated JSON on stdout
- With `--output`: the same JSON is also written to the requested file
- Failure: response body or parsing error on stderr, with a non-zero exit code

## Example Prompts

- "Search Google Images for query."
- "Run Google Images Search and save the raw JSON."
