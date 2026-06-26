---
name: google-maps-reviews
description: Use when the user wants Google Maps reviews through Frevana from a Google Maps data ID or place ID, including sort order, topics, review search, result counts, and pagination.
---

# Google Maps Reviews

Retrieve Google Maps reviews through Frevana.

## Purpose

This skill calls Frevana's `/service/google-maps-reviews` endpoint and returns the SerpAPI response unchanged.

Required input: one of `data_id`, `place_id`.

Supported request fields:

- `data_id` (one of required group)
- `place_id` (one of required group)
- `hl`
- `sort_by`
- `topic_id`
- `query`
- `num`
- `next_page_token`
- `no_cache`
- `async`
- `zero_trace`

The script validates that the response is JSON and prints it to stdout. Do not rewrite or reshape returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- data ID or place ID
- `FREVANA_TOKEN` in the environment variables, or `--token` for the current run
- `curl`, `bash`, and `python3`

The API base URL defaults to `https://ai-factory.frevana.com`. Set `FREVANA_API_BASE_URL` to point at another host.

## Commands

### Get reviews

```bash
bash <skill-path>/scripts/get_google_maps_reviews.sh \
  --place-id "ChIJIQBpAG2ahYAR_6128GcTUEo"
```

### Search reviews

```bash
bash <skill-path>/scripts/get_google_maps_reviews.sh \
  --data-id "0x123" \
  --query "service" \
  --num "20"
```

### Save JSON to a file

```bash
bash <skill-path>/scripts/get_google_maps_reviews.sh \
  --data-id "DATA_ID" \
  --output "./out/google-maps-reviews.json"
```

## Fixed Request Shape

The script sends this payload shape, omitting optional fields that were not provided. For this skill, provide either `data_id` or `place_id`:

```json
{
  "data_id": "DATA_ID",
  "place_id": "PLACE_ID",
  "hl": "HL",
  "sort_by": "SORT_BY",
  "topic_id": "TOPIC_ID",
  "query": "QUERY",
  "num": 1,
  "next_page_token": "NEXT_PAGE_TOKEN"
}
```

Do not pass unsupported fields. Do not pass SerpAPI `engine` or `api_key`; Frevana sets those server-side. Use `--output` for local file saving.

## Output

- Success: validated JSON on stdout
- With `--output`: the same JSON is also written to the requested file
- Failure: response body or parsing error on stderr, with a non-zero exit code

## Example Prompts

- "Get Google Maps reviews for data ID or place ID."
- "Run Google Maps Reviews and save the raw JSON."
