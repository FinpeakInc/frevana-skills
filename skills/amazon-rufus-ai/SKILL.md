---
name: amazon-rufus-ai
description: Use when the user wants to ask Amazon Rufus AI a question about a specific Amazon product through Frevana using the Frevana Chrome Extension session.
---

# Amazon Rufus AI

Ask Amazon Rufus AI about a specific product through the local Frevana daemon and Chrome Extension session.

## Purpose

This skill uses the Chrome Extension-backed Frevana MCP tool `frevana_ask` with fixed provider `amazon-rufus`.

Inputs:

- `url` (required) - full Amazon product page URL containing `/dp/<ASIN>` or `/gp/product/<ASIN>`
- `question` (required) - question to ask Rufus about that product
- `format` (optional) - `text` or `json`, defaults to `text`
- `timeout` (optional) - Frevana tool timeout in milliseconds, default `120000`

Return the Rufus answer directly unless the user asks for raw output or a saved file.

## What This Skill Needs

- Amazon product page URL
- user-provided question
- bundled `scripts/setup.sh` wrapper, which downloads and runs the latest official Frevana setup script
- Frevana local daemon running after setup, default port `12306`
- Chrome connected through the Frevana Chrome Extension
- active Amazon login in Chrome
- `curl`
- `bash`
- `python3`

This is a Chrome Extension skill. It uses the local daemon and Chrome Extension session.

## Execution Order

1. Confirm the user provided a full Amazon product page URL and a question.
2. Do not accept Amazon search pages, home pages, category pages, or bare product names.
3. Prefer the script over ad hoc `frevana call` commands.
4. Let the script run bundled `scripts/setup.sh` before every Frevana tool call.
5. If setup reports Chrome disconnected, stop and tell the user to open Chrome, connect the Frevana extension, and retry.
6. Run Rufus only after setup succeeds.
7. Amazon calls can be slow. If a call errors or times out, report the error and do not immediately retry in the same turn.
8. Return text output by default. If `format` is `json`, return structured JSON with `provider`, `prompt`, and `answer`.
9. Save output with `--output` when useful.

## Commands

```bash
bash <skill-path>/scripts/ask_amazon_rufus.sh \
  --url "https://www.amazon.com/dp/B01NBKTPTS" \
  --question "Does this work with M1 Mac?"
```

```bash
bash <skill-path>/scripts/ask_amazon_rufus.sh \
  --url "https://www.amazon.com/dp/B01NBKTPTS" \
  --question "Is this a good travel adapter?" \
  --format json \
  --timeout 120000 \
  --output ./out/amazon-rufus-answer.json
```

## Fixed Tool Call Shape

The script calls:

```bash
frevana call frevana_ask '<json_args>'
```

The JSON arguments use this shape:

```json
{
  "provider": "amazon-rufus",
  "prompt": "https://www.amazon.com/dp/B01NBKTPTS Does this work with M1 Mac?",
  "timeout": 120000
}
```

Always send `provider: "amazon-rufus"`. Do not pass unsupported fields.

## Notes

- Require a product URL containing `/dp/<ASIN>` or `/gp/product/<ASIN>`.
- The prompt sent to Frevana is exactly `<URL> <question>`.
- `--question` and `--prompt` are equivalent.
- `--format` must be `text` or `json`; default is `text`.
- `--timeout` must be a positive integer when provided.
- `scripts/setup.sh` downloads and executes the latest official setup script from `https://raw.githubusercontent.com/FinpeakInc/frevana-cli-releases/refs/heads/main/skills/frevana/scripts/setup.sh`.

