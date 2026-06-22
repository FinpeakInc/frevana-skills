---
name: google-ads-transparency-center
description: Use when the user wants Google Ads Transparency Center ad creative search results through Frevana, including advertiser ad lookup by advertiser_id, domain or text ad searches, platform filters for Google Search/Shopping/YouTube/Maps/Play, region-specific ad transparency searches, pagination with next_page_token, or Frevana API calls.
---

# Google Ads Transparency Center

Search Google Ads Transparency Center ad creative listings through Frevana.

## Purpose

This skill is for **finding Google Ads Transparency Center ad creative results**.

Inputs:

- `advertiser_id` or `text`
- optional `platform`
- optional `region`
- optional `next_page_token`

Output:

- validated response JSON with Google Ads Transparency Center results
- the same validated JSON saved to a local file on every successful run

This skill validates that the response is JSON, saves it to disk, and returns it unchanged on stdout. Do **not** rewrite or reshape the returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- user-provided `advertiser_id`, `text`, or `next_page_token`
- optional filters listed above
- `FREVANA_TOKEN` in the environment variables, or an explicit `--token` override for the current run
- `curl`
- `bash`
- `python3`

## Execution Order

Use this flow so the request stays simple and reliable:

1. Confirm the user has provided an `advertiser_id`, `text`, or `next_page_token`.
2. Prefer the script over ad hoc `curl` commands.
3. Let the script read `FREVANA_TOKEN` first.
4. In interactive shell usage, if `FREVANA_TOKEN` is missing, the script may prompt for it.
5. In non-interactive or agent workflows, fail fast if the token is missing and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly.
6. Run the script once. It prints the validated JSON to stdout and saves the same JSON to a file.
7. Use the saved JSON file for any follow-up parsing or summarization instead of calling the search API again.
8. Return the validated response JSON, or summarize the relevant ad creatives if the user does not need the full payload.

## Commands

### Search by domain or text

```bash
bash <skill-path>/scripts/search_google_ads_transparency_center.sh \
  --text "apple.com"
```

`--q` and `--query` are accepted as aliases for `--text`.

### Search by advertiser ID

```bash
bash <skill-path>/scripts/search_google_ads_transparency_center.sh \
  --advertiser-id "AR17828074650563772417"
```

`--advertiser_id` is accepted as an alias for `--advertiser-id`.

### Search with filters

```bash
bash <skill-path>/scripts/search_google_ads_transparency_center.sh \
  --text "apple.com" \
  --platform YOUTUBE \
  --region 2840
```

### Fetch the next page

```bash
bash <skill-path>/scripts/search_google_ads_transparency_center.sh \
  --text "apple.com" \
  --region 2840 \
  --next-page-token "CgoAP7zn5TAzVgIz..."
```

`--next_page_token` is accepted as an alias for `--next-page-token`.

### Save response JSON to a specific file

```bash
bash <skill-path>/scripts/search_google_ads_transparency_center.sh \
  --text "apple.com" \
  --region 2840 \
  --output ./out/google-ads-transparency-center-result.json
```

### Token override for the current run

```bash
bash <skill-path>/scripts/search_google_ads_transparency_center.sh \
  --text "apple.com" \
  --token "your bearer token"
```

## Fixed Request Shape

The script sends this payload shape, omitting optional fields that were not provided:

```json
{
  "advertiser_id": "AR17828074650563772417",
  "text": "apple.com",
  "platform": "YOUTUBE",
  "region": "2840",
  "next_page_token": "CgoAP7zn5TAzVgIz..."
}
```

Provide at least one of `advertiser_id`, `text`, or `next_page_token`. Do not invent advertiser IDs, region codes, platforms, or pagination tokens when the user did not provide them.

## Response Shape

The API returns Frevana JSON. Common fields include:

- `search_metadata`
- `search_parameters`
- `search_information.total_results`
- `ad_creatives`
- `pagination.next_page_token`

Each `ad_creatives[]` item may include `advertiser_id`, `advertiser`, `ad_creative_id`, `format`, `target_domain`, `image`, `link`, `width`, `height`, `first_shown`, `last_shown`, `details_link`.

## Output

- Success: the script validates that the response body is JSON, writes it to a file, prints the saved path to stderr, and prints the JSON to stdout
- Default file path: `./out/google-ads-transparency-center-<UTC timestamp>-<pid>.json`
- With `--output`: the same JSON is written to the specified file path instead of the default path
- Failure: the script prints the response body or parsing error and exits non-zero

## Notes

- Require at least one of `--advertiser-id`, `--text`, or `--next-page-token`.
- Use `--text` for domains or free-text Google Ads Transparency Center searches.
- Use `--advertiser-id` only when the user provides a Google advertiser ID such as `AR17828074650563772417`; do not guess it from a brand name.
- Use `--next-page-token` only for pagination from a prior response's `pagination.next_page_token`.
- Valid `--platform` values are `PLAY`, `MAPS`, `SEARCH`, `SHOPPING`, and `YOUTUBE`.
- The Frevana endpoint schema currently exposes `advertiser_id`, `text`, `platform`, `region`, and `next_page_token`. Do not pass unsupported passthrough fields such as `engine`, `api_key`, `output`, `no_cache`, `async`, `zero_trace`, `political_ads`, `start_date`, `end_date`, `creative_format`, or `num`.
- If `curl` is missing, stop and tell the user to install `curl`.
- If `python3` is missing, stop and tell the user to install `python3`.
- Do not echo the Bearer token back to the user.
- Summarize ad creatives by advertiser, advertiser ID, creative ID, format, target domain, first/last shown, and links when available unless the user asks for raw JSON.

## Example Prompts

### 中文

- "查 Google Ads Transparency Center 里 apple.com 的广告"
- "用 advertiser_id AR17828074650563772417 查询广告素材，region 2840"
- "继续翻上一页 Google Ads Transparency Center 结果，next_page_token 是 CgoAP7..."
- "查 YouTube 平台上 apple.com 的广告，保存原始 JSON"

### English

- "Search Google Ads Transparency Center for ads from apple.com."
- "Look up ad creatives for advertiser_id AR17828074650563772417 in region 2840."
- "Fetch the next page of Google Ads Transparency Center results with this next_page_token."
- "Find ads for apple.com on YouTube and save the raw JSON."
