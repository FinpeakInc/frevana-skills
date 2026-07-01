---
name: google-ads-keywords-search-volume
description: Use when the user wants to query keyword search volume, search-volume estimates, Google Ads keyword volume, batch keyword demand lookups, or keyword research for SEO, PPC, or ad planning.
---

# Google Ads Keywords Search Volume

Retrieve Google Ads keyword search volume through Frevana.

## Purpose

This skill is for **checking keyword search volume through Google Ads data**.

Inputs:

- `keywords`
- optional `search_partners`

Output:

- validated response JSON with Google Ads keyword search-volume data

This skill validates that the response is JSON and returns it unchanged. Do **not** rewrite or reshape the returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- user-provided `keywords`
- optional `search_partners` boolean, defaulting to `true`
- `FREVANA_TOKEN` in the environment variables, or an explicit `--token` override for the current run
- `curl`
- `bash`
- `python3`

## Execution Order

Use this flow so the request stays simple and reliable:

1. Confirm the user has provided one or more keywords.
2. If the user does not provide `search_partners`, default to `true`. In the user-facing response, explicitly say that this default was used when relevant.
3. Prefer the script over ad hoc `curl` commands.
4. Let the script read `FREVANA_TOKEN` first.
5. In interactive shell usage, if `FREVANA_TOKEN` is missing, the script may prompt for it.
6. In non-interactive or agent workflows, fail fast if the token is missing and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly.
7. Return the validated response JSON, or summarize the highest- and lowest-volume keywords if the user does not need the full payload.
8. The script saves the JSON response to `./out/` by default.

## Commands

### Default search partners

```bash
bash <skill-path>/scripts/search_google_ads_keywords_search_volume.sh \
  --keywords "wireless earbuds,gaming headset"
```

### Exclude search partners

```bash
bash <skill-path>/scripts/search_google_ads_keywords_search_volume.sh \
  --keywords "wireless earbuds,gaming headset" \
  --search-partners false
```

### Save response JSON to a specific file

```bash
bash <skill-path>/scripts/search_google_ads_keywords_search_volume.sh \
  --keywords "wireless earbuds,gaming headset" \
  --output ./out/google-ads-keywords-search-volume-result.json
```

### Token override for the current run

```bash
bash <skill-path>/scripts/search_google_ads_keywords_search_volume.sh \
  --keywords "wireless earbuds,gaming headset" \
  --token "your bearer token"
```

## Fixed Request Shape

The script sends this payload shape:

```json
{
  "keywords": [
    "wireless earbuds",
    "gaming headset"
  ],
  "search_partners": true
}
```

Default values when not provided:

- `search_partners`: `true`

Do not pass unsupported fields. Do not pass API keys, output paths, or request metadata in the payload; Frevana handles server-side details.

## Response Shape

The API returns JSON. This skill validates the response as JSON and returns it unchanged.

## Output

- Success: the script validates that the response body is JSON and prints it to stdout
- Default file path: `./out/google-ads-keywords-search-volume-<UTC timestamp>-<pid>.json`
- With `--output`: the same JSON is written to the specified file path instead
- Failure: the script prints the response body or parsing error and exits non-zero

## Notes

- Require `--keywords`
- `--keywords` must be a comma-separated list. Trim whitespace and preserve the user-supplied phrases
- `--search-partners` accepts `true`, `false`, `1`, `0`, `yes`, `no`, `on`, or `off`
- If the user does not specify `search_partners`, default to `true`
- If `curl` is missing, stop and tell the user to install `curl`
- If `python3` is missing, stop and tell the user to install `python3`
- Do not echo the Bearer token back to the user
- Summarize the highest- and lowest-volume keywords, and call out obvious gaps or opportunities when the user is doing keyword research

## Example Prompts

### 中文

- "查一下 wireless earbuds 和 gaming headset 的 Google Ads 搜索量"
- "调用 Google Ads keywords search volume API，并把原始 JSON 存到文件"
- "查 Google Ads 关键词搜索量，不包含 search partners"

### English

- "Check Google Ads search volume for wireless earbuds and gaming headset"
- "Get Google Ads keyword search volume and save the raw JSON to a file"
- "Check Google Ads keyword search volume without search partners"
