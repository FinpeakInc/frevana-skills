---
name: google-ads-ad-traffic-by-keywords
description: Use when the user wants Google Ads ad traffic forecasts, projected clicks, CPC, cost, impressions, bid-based keyword forecasting, or campaign planning metrics for keywords.
---

# Google Ads Ad Traffic By Keywords

Forecast Google Ads traffic for keywords through Frevana.

## Purpose

This skill is for **forecasting Google Ads traffic using keywords, a bid, and a match type**.

Inputs:

- `keywords`
- `bid`
- `match`
- optional location, language, date range, date interval, sorting, and tag fields

Output:

- validated response JSON with Google Ads ad traffic forecast data

This skill validates that the response is JSON and returns it unchanged. Do **not** rewrite or reshape the returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- user-provided `keywords`
- user-provided `bid`
- user-provided `match`
- optional location, language, date, sorting, and tag values
- `FREVANA_TOKEN` in the environment variables, or an explicit `--token` override for the current run
- `curl`
- `bash`
- `python3`

## Execution Order

Use this flow so the request stays simple and reliable:

1. Confirm the user has provided one or more keywords.
2. Confirm the user has provided `bid`.
3. Confirm the user has provided `match` as `exact`, `broad`, or `phrase`.
4. Prefer the script over ad hoc `curl` commands.
5. Let the script read `FREVANA_TOKEN` first.
6. In interactive shell usage, if `FREVANA_TOKEN` is missing, the script may prompt for it.
7. In non-interactive or agent workflows, fail fast if the token is missing and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly.
8. Return the validated response JSON, or summarize projected clicks, average CPC, and cost if the user does not need the full payload.
9. The script saves the JSON response to `./out/` by default.

## Commands

### Basic forecast

```bash
bash <skill-path>/scripts/search_google_ads_ad_traffic_by_keywords.sh \
  --keywords "seo marketing" \
  --bid 999 \
  --match exact
```

### With location and language

```bash
bash <skill-path>/scripts/search_google_ads_ad_traffic_by_keywords.sh \
  --keywords "wireless earbuds,gaming headset" \
  --bid 500 \
  --match phrase \
  --location-code 2840 \
  --language-code en
```

### With forecast interval

```bash
bash <skill-path>/scripts/search_google_ads_ad_traffic_by_keywords.sh \
  --keywords "seo marketing" \
  --bid 999 \
  --match exact \
  --date-interval next_month
```

### Save response JSON to a specific file

```bash
bash <skill-path>/scripts/search_google_ads_ad_traffic_by_keywords.sh \
  --keywords "seo marketing" \
  --bid 999 \
  --match exact \
  --output ./out/google-ads-ad-traffic-result.json
```

## Fixed Request Shape

The script sends this payload shape:

```json
{
  "keywords": [
    "seo marketing"
  ],
  "bid": 999,
  "match": "exact",
  "location_code": 2840,
  "language_code": "en",
  "date_interval": "next_month"
}
```

Default behavior when no dates are provided:

- DataForSEO applies `next_month`

Do not pass unsupported fields. Do not pass API keys, output paths, or request metadata in the payload; Frevana handles server-side details.

## Response Shape

The API returns JSON. This skill validates the response as JSON and returns it unchanged.

## Output

- Success: the script validates that the response body is JSON and prints it to stdout
- Default file path: `./out/google-ads-ad-traffic-by-keywords-<UTC timestamp>-<pid>.json`
- With `--output`: the same JSON is written to the specified file path instead
- Failure: the script prints the response body or parsing error and exits non-zero

## Notes

- Require `--keywords`
- Require `--bid`
- Require `--match`
- `--keywords` must be a comma-separated list. Trim whitespace and preserve the user-supplied phrases
- `--bid` must be a positive integer
- `--match` accepts `exact`, `broad`, or `phrase`
- `--date-interval` accepts `next_week`, `next_month`, or `next_quarter`
- `--sort-by` accepts `relevance`, `impressions`, `ctr`, `average_cpc`, `cost`, or `clicks`
- Use only one of `--location-name`, `--location-code`, or `--location-coordinate`
- Use only one of `--language-name` or `--language-code`
- `--date-interval` cannot be combined with `--date-from` or `--date-to`
- If either `--date-from` or `--date-to` is used, both must be provided
- If `curl` is missing, stop and tell the user to install `curl`
- If `python3` is missing, stop and tell the user to install `python3`
- Do not echo the Bearer token back to the user
- Summarize projected clicks, average CPC, cost, and any null or missing metrics when the user is doing ad planning

## Example Prompts

### 中文

- "预测 seo marketing 在 Google Ads 里的点击和 CPC，bid 999，exact match"
- "调用 Google Ads ad traffic by keywords API，并把原始 JSON 存到文件"
- "用 phrase match 预测 wireless earbuds 和 gaming headset 的广告流量"

### English

- "Forecast Google Ads clicks and CPC for seo marketing with bid 999 and exact match"
- "Get Google Ads ad traffic forecasts and save the raw JSON to a file"
- "Forecast ad traffic for wireless earbuds and gaming headset using phrase match"
