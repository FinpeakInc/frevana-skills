---
name: instagram-profile
description: Use when the user wants Instagram profile details through Frevana from an Instagram profile ID, including paginated profile data from SerpAPI.
---

# Instagram Profile

Retrieve an Instagram profile through Frevana.

## Purpose

This skill calls Frevana's `/service/instagram-profile` endpoint and returns the SerpAPI response unchanged.

Required input: `profile_id`.

Supported request fields:

- `profile_id` (required)
- `next_page_token`
- `no_cache`
- `async`
- `zero_trace`

The script validates that the response is JSON and prints it to stdout. Do not rewrite or reshape returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- profile ID
- `FREVANA_TOKEN` in the environment variables, or `--token` for the current run
- `curl`, `bash`, and `python3`

The API base URL defaults to `https://ai-factory.frevana.com`. Set `FREVANA_API_BASE_URL` to point at another host.

## Commands

### Get a profile

```bash
bash <skill-path>/scripts/get_instagram_profile.sh \
  --profile-id "serpapicom"
```

### Save JSON to a file

```bash
bash <skill-path>/scripts/get_instagram_profile.sh \
  --profile-id "PROFILE_ID" \
  --output "./out/instagram-profile.json"
```

## Fixed Request Shape

The script sends this payload shape, omitting optional fields that were not provided:

```json
{
  "profile_id": "PROFILE_ID",
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

- "Get Instagram profile for profile ID."
- "Run Instagram Profile and save the raw JSON."
