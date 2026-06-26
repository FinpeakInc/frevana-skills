---
name: youtube-video-transcript
description: Use when the user wants a YouTube video transcript through Frevana, including transcript language, title, or transcript type selection from SerpAPI.
---

# YouTube Video Transcript

Retrieve a YouTube video transcript through Frevana.

## Purpose

This skill calls Frevana's `/service/youtube-video-transcript` endpoint and returns the SerpAPI response unchanged.

Required input: `v`.

Supported request fields:

- `v` (required)
- `language_code`
- `title`
- `type`
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

### Get a transcript

```bash
bash <skill-path>/scripts/get_youtube_video_transcript.sh \
  --v "Gk8gB5VACZw" \
  --language-code "en"
```

### Save JSON to a file

```bash
bash <skill-path>/scripts/get_youtube_video_transcript.sh \
  --v "V" \
  --output "./out/youtube-video-transcript.json"
```

## Fixed Request Shape

The script sends this payload shape, omitting optional fields that were not provided:

```json
{
  "v": "V",
  "language_code": "LANGUAGE_CODE",
  "title": "TITLE",
  "type": "TYPE",
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

- "Get YouTube video transcript for YouTube video ID."
- "Run YouTube Video Transcript and save the raw JSON."
