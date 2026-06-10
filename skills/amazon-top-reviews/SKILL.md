---
name: amazon-top-reviews
description: Use when the user wants top helpful Amazon product reviews through Frevana using the Frevana Chrome Extension session and a full Amazon product URL.
---

# Amazon Top Reviews

Fetch top helpful Amazon product reviews through the local Frevana daemon and Chrome Extension session.

## Purpose

This skill uses the Chrome Extension-backed Frevana MCP tool `frevana_ask` with fixed provider `amazon-product-reviews`.

Inputs:

- `url` (required) - full Amazon product page URL containing `/dp/<ASIN>` or `/gp/product/<ASIN>`
- `max_reviews` (optional) - review cap, default provider behavior is 100, max 500
- `sort_by` (optional) - Amazon reviews sort value, for example `helpful`
- `reviewer_type` (optional) - Amazon reviewer type, for example `all_reviews`
- `filter_by_star` (optional) - Amazon star filter, for example `five_star`
- `format` (optional) - `text` or `json`, defaults to `text`
- `timeout` (optional) - Frevana tool timeout in milliseconds, default `180000`

Return reviews directly unless the user asks for raw output or a saved file.

## What This Skill Needs

- Amazon product page URL
- bundled `scripts/setup.sh` wrapper, which downloads and runs the latest official Frevana setup script
- Frevana local daemon running after setup, default port `12306`
- Chrome connected through the Frevana Chrome Extension
- active Amazon login in Chrome
- `curl`
- `bash`
- `python3`

This is a Chrome Extension skill. It uses the local daemon and Chrome Extension session.

## Execution Order

1. Confirm the user provided a full Amazon product page URL.
2. Do not accept Amazon search pages, home pages, category pages, or bare product names.
3. Prefer the script over ad hoc `frevana call` commands.
4. Let the script run bundled `scripts/setup.sh` before every Frevana tool call.
5. If setup reports Chrome disconnected, stop and tell the user to open Chrome, connect the Frevana extension, and retry.
6. Amazon review calls are slow and paginated. If a call errors or times out, report the error and do not immediately retry in the same turn.
7. Return text output by default. If `format` is `json`, return structured JSON with `provider`, `prompt`, and `answer`.
8. Save output with `--output` when useful.

## Commands

```bash
bash <skill-path>/scripts/get_amazon_top_reviews.sh \
  --url "https://www.amazon.com/dp/B01NBKTPTS"
```

```bash
bash <skill-path>/scripts/get_amazon_top_reviews.sh \
  --url "https://www.amazon.com/dp/B01NBKTPTS" \
  --max-reviews 50 \
  --sort-by helpful \
  --reviewer-type all_reviews \
  --filter-by-star five_star \
  --format json \
  --output ./out/amazon-top-reviews.json
```

## Fixed Tool Call Shape

The script calls:

```bash
frevana call frevana_ask '<json_args>'
```

The JSON arguments use this shape:

```json
{
  "provider": "amazon-product-reviews",
  "prompt": "https://www.amazon.com/dp/B01NBKTPTS {\"maxReviews\":50,\"sortBy\":\"helpful\",\"reviewerType\":\"all_reviews\",\"filterByStar\":\"five_star\"}",
  "timeout": 180000
}
```

Always send `provider: "amazon-product-reviews"`. Do not pass unsupported fields.

## Notes

- Require a product URL containing `/dp/<ASIN>` or `/gp/product/<ASIN>`.
- Optional review settings are appended to the prompt as the JSON config expected by the original Frevana provider.
- `--max-reviews` must be an integer from 1 to 500.
- `--format` must be `text` or `json`; default is `text`.
- `--timeout` must be a positive integer when provided.
- `scripts/setup.sh` downloads and executes the latest official setup script from `https://raw.githubusercontent.com/FinpeakInc/frevana-cli-releases/refs/heads/main/skills/frevana/scripts/setup.sh`.

