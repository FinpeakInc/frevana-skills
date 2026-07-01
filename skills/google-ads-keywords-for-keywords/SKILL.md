---
name: google-ads-keywords-for-keywords
description: Use when the user wants to find keywords related to a keyword, query related keywords, expand keywords, get Google Ads keyword suggestions, seed keyword research, or Google Ads keyword ideas with search volume and CPC metrics.
---

# Google Ads Keywords For Keywords

Retrieve Google Ads keyword suggestions from seed keywords through Frevana.

## Purpose

This skill is for **expanding seed keywords into related Google Ads keyword ideas**.

Inputs:

- `keywords`
- optional location, language, search partners, historical date range, sorting, adult-keyword inclusion, and tag fields

Output:

- validated response JSON with Google Ads keyword suggestion data

This skill validates that the response is JSON and returns it unchanged. Do **not** rewrite or reshape the returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- user-provided seed `keywords`
- optional location, language, date, sorting, search partners, adult-keyword, and tag values
- `FREVANA_TOKEN` in the environment variables, or an explicit `--token` override for the current run
- `curl`
- `bash`
- `python3`

## Execution Order

Use this flow so the request stays simple and reliable:

1. Confirm the user has provided one or more seed keywords.
2. If the user does not provide `search_partners`, default to `false`. In the user-facing response, explicitly say that this default was used when relevant.
3. If the user does not provide `include_adult_keywords`, default to `false`.
4. Prefer the script over ad hoc `curl` commands.
5. Let the script read `FREVANA_TOKEN` first.
6. In interactive shell usage, if `FREVANA_TOKEN` is missing, the script may prompt for it.
7. In non-interactive or agent workflows, fail fast if the token is missing and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly.
8. Return the validated response JSON, or summarize the strongest keyword ideas if the user does not need the full payload.
9. The script saves the JSON response to `./out/` by default.

## Commands

### Basic keyword suggestions

```bash
bash <skill-path>/scripts/search_google_ads_keywords_for_keywords.sh \
  --keywords "phone,cellphone"
```

### With location and language

```bash
bash <skill-path>/scripts/search_google_ads_keywords_for_keywords.sh \
  --keywords "wireless earbuds,gaming headset" \
  --location-code 2840 \
  --language-code en
```

### Include search partners

```bash
bash <skill-path>/scripts/search_google_ads_keywords_for_keywords.sh \
  --keywords "phone,cellphone" \
  --search-partners true
```

### Save response JSON to a specific file

```bash
bash <skill-path>/scripts/search_google_ads_keywords_for_keywords.sh \
  --keywords "phone,cellphone" \
  --output ./out/google-ads-keywords-for-keywords-result.json
```

## Fixed Request Shape

The script sends this payload shape:

```json
{
  "keywords": [
    "phone",
    "cellphone"
  ],
  "location_code": 2840,
  "language_code": "en",
  "search_partners": false,
  "include_adult_keywords": false
}
```

Default values when not provided:

- `search_partners`: `false`
- `include_adult_keywords`: `false`

Do not pass unsupported fields. Do not pass API keys, output paths, or request metadata in the payload; Frevana handles server-side details.

## Response Shape

The API returns JSON. This skill validates the response as JSON and returns it unchanged.

## Output

- Success: the script validates that the response body is JSON and prints it to stdout
- Default file path: `./out/google-ads-keywords-for-keywords-<UTC timestamp>-<pid>.json`
- With `--output`: the same JSON is written to the specified file path instead
- Failure: the script prints the response body or parsing error and exits non-zero

## Notes

- Require `--keywords`
- `--keywords` must be a comma-separated list. Trim whitespace and preserve the user-supplied phrases
- `--keywords` accepts up to 20 seed keywords
- `--search-partners` accepts `true`, `false`, `1`, `0`, `yes`, `no`, `on`, or `off`
- `--include-adult-keywords` accepts `true`, `false`, `1`, `0`, `yes`, `no`, `on`, or `off`
- If the user does not specify `search_partners`, default to `false`
- If the user does not specify `include_adult_keywords`, default to `false`
- `--sort-by` accepts `relevance`, `search_volume`, `competition_index`, `low_top_of_page_bid`, or `high_top_of_page_bid`
- Use only one of `--location-name`, `--location-code`, or `--location-coordinate`
- Use only one of `--language-name` or `--language-code`
- If `curl` is missing, stop and tell the user to install `curl`
- If `python3` is missing, stop and tell the user to install `python3`
- Do not echo the Bearer token back to the user
- Summarize the highest-volume keyword ideas and notable CPC or competition gaps when the user is doing keyword research

## Example Prompts

### 中文

- "用 phone 和 cellphone 查 Google Ads 关键词建议"
- "查询 phone 相关的关键词"
- "帮我查 wireless earbuds 这个关键词相关的关键词"
- "调用 Google Ads keywords for keywords API，并把原始 JSON 存到文件"
- "帮我扩展 wireless earbuds 的 Google Ads 关键词，地区美国，语言英文"

### English

- "Get Google Ads keyword ideas for phone and cellphone"
- "Call the Google Ads keywords for keywords API and save the raw JSON"
- "Expand wireless earbuds into Google Ads keyword suggestions for the US in English"
