---
name: youtube-video
description: Use when the user wants YouTube video details through Frevana from a video ID, including localized video data and next-page-token pagination for related videos, comments, or replies.
---

# YouTube Video

Retrieve YouTube video details through Frevana.

## Purpose

This skill calls Frevana's `/service/youtube-video` endpoint and returns the SerpAPI response unchanged.

Required input: `v`.

Supported request fields:

- `v` (required)
- `gl`
- `hl`
- `next_page_token`
- `no_cache`
- `async`
- `zero_trace`

The script validates that the response is JSON and prints it to stdout. Do not rewrite or reshape returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- YouTube video ID
- `FREVANA_TOKEN` in the environment variables, or `--token` for the current run
- `curl`, `bash`, and `python3`

The API base URL defaults to `https://ai-factory.frevana.com`. Set `FREVANA_API_BASE_URL` to point at another host.

## Commands

### Get video details

```bash
bash <skill-path>/scripts/get_youtube_video.sh \
  --v "Gk8gB5VACZw"
```

### Save JSON to a file

```bash
bash <skill-path>/scripts/get_youtube_video.sh \
  --v "V" \
  --output "./out/youtube-video.json"
```

## Fixed Request Shape

The script sends this payload shape, omitting optional fields that were not provided:

```json
{
  "v": "V",
  "gl": "GL",
  "hl": "HL",
  "next_page_token": "NEXT_PAGE_TOKEN",
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

- "Get YouTube video details for YouTube video ID."
- "Run YouTube Video and save the raw JSON."
