---
name: amazon-keyword-search-volume
description: Get Amazon keyword search volume through Frevana's `POST /dataforseo/amazon-keywords-search-volume` endpoint. Use whenever the user wants Amazon keyword demand, search-volume estimates, batch keyword lookups, or keyword research for Amazon SEO/PPC/listing decisions.
---

# Amazon Keyword Search Volume

Retrieve Amazon keyword search volume by calling Frevana's `POST https://ai-factory.frevana.com/dataforseo/amazon-keywords-search-volume`.

## Purpose

This skill is for **backend Amazon keyword demand retrieval**.

Inputs:

- `keywords`
- optional `location_code`
- optional `location_name`
- optional `language_code`
- optional `language_name`

Output:

- validated response JSON returned by the Amazon keyword search volume endpoint

This skill validates that the response is JSON and returns it unchanged. Do **not** rewrite or reshape the API payload unless the user explicitly asks for a transformation.

## What This Skill Needs

- user-provided `keywords`
- optional `location_code`, `location_name`, `language_code`, `language_name`
- `FREVANA_TOKEN` in the environment, or an explicit `--token` override for the current run
- `curl`
- `bash`
- `python3`

## Execution Order

Use this flow so the request stays simple and reliable:

1. Confirm the user has provided one or more keywords.
2. If the user does not provide location or language, default to `United States / English`. In the user-facing response, explicitly say that this default was used.
3. Prefer the script over ad hoc `curl` commands.
4. Let the script read `FREVANA_TOKEN` first.
5. In interactive shell usage, if `FREVANA_TOKEN` is missing, the script may prompt for it.
6. In non-interactive or agent workflows, fail fast if the token is missing and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly.
7. Return the validated response JSON, or summarize the highest- and lowest-volume keywords if the user does not need the full payload.
8. When useful, also save the JSON to a file.

## Commands

### Default marketplace

```bash
bash <skill-path>/scripts/get_search_volume.sh \
  --keywords "wireless earbuds,gaming headset"
```

### Explicit marketplace

```bash
bash <skill-path>/scripts/get_search_volume.sh \
  --keywords "wireless earbuds,gaming headset" \
  --location-name "United States"
```

### Save response JSON to a file

```bash
bash <skill-path>/scripts/get_search_volume.sh \
  --keywords "wireless earbuds,gaming headset" \
  --location-name "Germany" \
  --output ./out/amazon-keyword-search-volume-result.json
```

### Token override for the current run

```bash
bash <skill-path>/scripts/get_search_volume.sh \
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
  "location_code": 2840,
  "location_name": "United States",
  "language_code": "en",
  "language_name": "English"
}
```

Default values when not provided:

- `location_code`: `2840`
- `location_name`: `United States`
- `language_code`: `en`
- `language_name`: `English`

## Supported Marketplaces

Use only these location/language pairs for this skill:

| Marketplace | location_code | language_code |
|-------------|---------------|---------------|
| Australia | 2036 | en |
| Austria | 2040 | de |
| Canada | 2124 | en |
| Egypt | 2818 | ar |
| France | 2250 | fr |
| Germany | 2276 | de |
| India | 2356 | en |
| Italy | 2380 | it |
| Mexico | 2484 | es |
| Netherlands | 2528 | nl |
| Saudi Arabia | 2682 | ar |
| Singapore | 2702 | en |
| Spain | 2724 | es |
| United Arab Emirates | 2784 | ar |
| United Kingdom | 2826 | en |
| United States | 2840 | en |

If the user asks for a marketplace outside this list, stop and say that the skill currently supports only the listed marketplaces.

## Response Shape

The API returns JSON. This skill validates the response as JSON and returns it unchanged.

## Output

- Success: the script validates that the response body is JSON and prints it to stdout
- With `--output`: the same JSON is also written to the specified file path
- Failure: the script prints the response body or parsing error and exits non-zero

## Notes

- Require `--keywords`
- `--keywords` must be a comma-separated list. Trim whitespace and preserve the user-supplied phrases
- If the user does not specify marketplace/language, default to `United States / English`
- In the response, state the default explicitly when it was used
- If `curl` is missing, stop and tell the user to install `curl`
- If `python3` is missing, stop and tell the user to install `python3`
- Do not echo the Bearer token back to the user
- Summarize the highest- and lowest-volume keywords, and call out obvious gaps or opportunities when the user is doing keyword research

## Example Prompts

### 中文

- "查一下 wireless earbuds 和 gaming headset 的 Amazon 搜索量"
- "帮我查 Germany 的 Amazon 关键词搜索量"
- "调用 Amazon keyword search volume API，并把原始 JSON 存到文件"

### English

- "Check Amazon search volume for wireless earbuds and gaming headset"
- "Get Amazon keyword search volume in Germany"
- "Call the Amazon keyword search volume endpoint and save the raw JSON to a file"
