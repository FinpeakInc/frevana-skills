---
name: google-events-search
description: Use when the user wants Google Events results through Frevana, including localized event searches, event pagination, date or event-type filters, and raw SerpAPI event result JSON.
---

# Google Events Search

Search Google Events through Frevana.

## Purpose

This skill calls Frevana's `/service/google-events` endpoint and returns the SerpAPI response unchanged.

Required input: `q`.

Supported request fields:

- `q` (required)
- `location`
- `uule`
- `gl`
- `hl`
- `start`
- `htichips`
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

### Search events

```bash
bash <skill-path>/scripts/search_google_events.sh \
  --q "Events in Austin, TX"
```

### Search with event filters

```bash
bash <skill-path>/scripts/search_google_events.sh \
  --q "Events in Chicago" \
  --htichips "event_type:Virtual-Event,date:today"
```

### Save JSON to a file

```bash
bash <skill-path>/scripts/search_google_events.sh \
  --q "Q" \
  --output "./out/google-events-search.json"
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
  "start": 1,
  "htichips": "HTICHIPS",
  "no_cache": true
}
```

Do not pass unsupported fields. Do not pass SerpAPI `engine` or `api_key`; Frevana sets those server-side. Use `--output` for local file saving.

## Output

- Success: validated JSON on stdout
- With `--output`: the same JSON is also written to the requested file
- Failure: response body or parsing error on stderr, with a non-zero exit code

## Example Prompts

- "Search Google Events for query."
- "Run Google Events Search and save the raw JSON."
