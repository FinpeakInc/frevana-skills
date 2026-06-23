---
name: meta-ads-search
description: Use when the user wants Meta Ads Library or Facebook ad search results through the local Frevana Chrome Extension-backed tool, including keyword, country, status, and date-range filtering.
---

# Meta Ads Search

Search Meta Ads Library through the local Frevana daemon and Chrome Extension session.

## Purpose

This skill is for **finding Meta/Facebook ads by keyword or advertiser text** using the Chrome Extension-backed Frevana MCP tool `frevana_meta_ads_search`.

Inputs:

- `keyword` (required) - keyword, advertiser, or brand text to search in Meta Ads Library
- `country` (optional) - `ALL` or an ISO 3166-1 alpha-2 country code such as `US`, `CN`, or `GB`; defaults to `ALL`
- `active_status` (optional) - `active`, `inactive`, or `all`; defaults to `active`
- `date_from` (optional) - inclusive start date in `YYYY-MM-DD`
- `date_to` (optional) - inclusive end date in `YYYY-MM-DD`
- `maxResults` (optional) - maximum number of ads to return, defaults to `20`, max 500
- `timeout` (optional) - timeout in milliseconds

Output:

- raw Frevana JSON text containing structured Meta ad records

Summarize the results unless the user asks for the raw output.

## What This Skill Needs

- user-provided `keyword`
- bundled `scripts/setup.sh` wrapper, which downloads and runs the latest official Frevana setup script
- Frevana local daemon running after setup, default port `12306`
- Chrome connected through the Frevana Chrome Extension
- Meta Ads Library reachable in the connected Chrome session
- `curl`
- `bash`
- `python3`

This is a Chrome Extension skill. It uses the local daemon and Chrome Extension session.

## Execution Order

Use this flow:

1. Confirm the user has provided `keyword` or equivalent advertiser / brand text.
2. Prefer the script over ad hoc `frevana call` commands.
3. Default `country` to `ALL`, `active_status` to `active`, and `maxResults` to `20`. Do not invent optional date range or timeout values.
4. Let the script run bundled `scripts/setup.sh` before every Frevana tool call.
5. If setup reports Chrome disconnected, stop and tell the user to open Chrome, connect the Frevana extension, and retry.
6. Run the Meta Ads search only after setup succeeds.
7. If the result looks like login/auth content or Meta Ads Library is unavailable, tell the user they may need an available Chrome session and retry.
8. Return a concise summary of the ads, or the raw JSON if requested.
9. When useful, save the output to a file.

## Commands

### Basic keyword search

```bash
bash <skill-path>/scripts/search_meta_ads.sh \
  --keyword "nike"
```

`--query`, `--q`, and `--text` are accepted as aliases for `--keyword`.
Without extra options, this searches active ads in all countries and returns up to 20 ads.

### Filter by country and active status

```bash
bash <skill-path>/scripts/search_meta_ads.sh \
  --keyword "nike" \
  --country US \
  --active-status active
```

`--active_status` is accepted as an alias for `--active-status`.

### Limit date range and result count

```bash
bash <skill-path>/scripts/search_meta_ads.sh \
  --keyword "nike" \
  --date-from 2026-01-01 \
  --date-to 2026-06-22 \
  --max-results 50
```

`--date_from`, `--date_to`, and `--maxResults` are accepted as aliases.

### Save output to file

```bash
bash <skill-path>/scripts/search_meta_ads.sh \
  --keyword "nike" \
  --output ./out/meta-ads-search-result.json
```

## Fixed Tool Call Shape

The script calls:

```bash
frevana call frevana_meta_ads_search '<json_args>'
```

The JSON arguments always include the default country, active status, and result limit; other optional fields are omitted when not provided:

```json
{
  "keyword": "nike",
  "country": "ALL",
  "active_status": "active",
  "maxResults": 20
}
```

When the user specifies country and result limit, they override those defaults:

```json
{
  "keyword": "nike",
  "country": "US",
  "active_status": "active",
  "date_from": "2026-01-01",
  "date_to": "2026-06-22",
  "maxResults": 50,
  "timeout": 120000
}
```

Do not pass unsupported fields to `frevana_meta_ads_search`.

## Output

- Success: the script prints the Frevana tool result to stdout
- With `--output`: the same result is also written to the specified file path
- Failure: the script prints the Frevana error or preflight failure to stderr and exits non-zero

## Notes

- Require `--keyword`, `--query`, `--q`, or `--text`.
- `--country` defaults to `ALL`; set a two-letter uppercase country code to restrict results to one country.
- `--active-status` defaults to `active`; use `inactive` or `all` only when the user explicitly requests it.
- `--date-from` and `--date-to` must use `YYYY-MM-DD`.
- `--max-results` defaults to `20` and must be an integer from 1 through 500.
- `--timeout` must be a positive integer when provided.
- The script runs bundled `scripts/setup.sh` before every search, matching the original Frevana skill flow.
- `scripts/setup.sh` downloads and executes the latest official setup script from `https://raw.githubusercontent.com/FinpeakInc/frevana-cli-releases/refs/heads/main/skills/frevana/scripts/setup.sh`.
- If `frevana` is missing, the official setup script installs the Frevana binary before starting/checking the daemon.

## Example Prompts

### 中文

- "查一下 Meta Ads Library 里 nike 的广告"
- "搜索 Facebook 广告库里关于 openai 的广告，美国区，只看 active"
- "查 meta ads，关键词 shopify，限制 2026-01-01 到 2026-06-22，保存原始 JSON"

### English

- "Search Meta Ads Library for nike ads"
- "Find active Meta ads for openai in the US"
- "Search Meta ads for shopify between 2026-01-01 and 2026-06-22 and save the raw JSON"
