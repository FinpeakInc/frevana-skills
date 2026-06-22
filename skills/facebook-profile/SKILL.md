---
name: facebook-profile
description: Use when the user wants a Facebook profile lookup from a Facebook profile ID or username through Frevana.
---

# Facebook Profile

Retrieve a Facebook profile through Frevana.

## Purpose

This skill retrieves a Facebook profile by its numeric profile ID or username.

Required input:

- `profile_id`

Output:

- validated response JSON with Facebook profile data

The script returns the API response unchanged. Do not rewrite or reshape it unless the user explicitly asks for a transformation.

## Commands

```bash
bash <skill-path>/scripts/get_facebook_profile.sh \
  --profile-id "zuck"
```

Save JSON to a file:

```bash
bash <skill-path>/scripts/get_facebook_profile.sh \
  --profile-id "zuck" \
  --output ./out/facebook-profile.json
```

Use another API host:

```bash
FREVANA_API_BASE_URL="https://api-dev.frevana.com" \
  bash <skill-path>/scripts/get_facebook_profile.sh --profile-id "zuck"
```

## What This Skill Needs

- `--profile-id` (or `--profile_id`), a Facebook profile ID or username
- `FREVANA_TOKEN` in the environment, or `--token` for the current run
- `curl`, `bash`, and `python3`

The API base URL defaults to `https://ai-factory.frevana.com`. Set `FREVANA_API_BASE_URL` to point at another host.

## Output

- Success: validated JSON on stdout
- With `--output`: the same JSON is also written to the requested file
- Failure: response body or parsing error on stderr, with a non-zero exit code

## Example Prompts

- “Get the Facebook profile for username `zuck`.”
- “Look up this Facebook profile ID and save the raw JSON.”
