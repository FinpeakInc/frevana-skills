---
name: amazon-product-info
description: Use when the user wants Amazon product page details through Frevana using the Frevana Chrome Extension session and a full Amazon product URL.
---

# Amazon Product Info

Extract Amazon product details through the local Frevana daemon and Chrome Extension session.

## Purpose

This skill uses the Chrome Extension-backed Frevana MCP tool `frevana_ask` with fixed provider `amazon-product`.

Inputs:

- `url` (required) - full Amazon product page URL containing `/dp/<ASIN>` or `/gp/product/<ASIN>`
- `format` (optional) - `text` or `json`, defaults to `text`
- `timeout` (optional) - Frevana tool timeout in milliseconds, default `60000`

Return the product details directly unless the user asks for raw output or a saved file.

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
6. Amazon calls can be slow. If a call errors or times out, report the error and do not immediately retry in the same turn.
7. Return text output by default. If `format` is `json`, return structured JSON with `provider`, `prompt`, and `answer`.
8. Save output with `--output` when useful.

## Commands

```bash
bash <skill-path>/scripts/get_amazon_product_info.sh \
  --url "https://www.amazon.com/dp/B01NBKTPTS"
```

```bash
bash <skill-path>/scripts/get_amazon_product_info.sh \
  --url "https://www.amazon.com/dp/B01NBKTPTS" \
  --format json \
  --output ./out/amazon-product-info.json
```

## Fixed Tool Call Shape

The script calls:

```bash
frevana call frevana_ask '<json_args>'
```

The JSON arguments use this shape:

```json
{
  "provider": "amazon-product",
  "prompt": "https://www.amazon.com/dp/B01NBKTPTS",
  "timeout": 60000
}
```

Always send `provider: "amazon-product"`. Do not pass unsupported fields.

## Notes

- This is the Chrome-session Amazon product page extractor. For the existing Frevana HTTP API ASIN lookup, use `amazon-product`.
- Require a product URL containing `/dp/<ASIN>` or `/gp/product/<ASIN>`.
- `--format` must be `text` or `json`; default is `text`.
- `--timeout` must be a positive integer when provided.
- `scripts/setup.sh` downloads and executes the latest official setup script from `https://raw.githubusercontent.com/FinpeakInc/frevana-cli-releases/refs/heads/main/skills/frevana/scripts/setup.sh`.

