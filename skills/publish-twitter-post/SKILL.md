---
name: publish-twitter-post
description: Use when the user explicitly wants to publish a post to Twitter/X through Frevana using the Frevana Chrome Extension session.
---

# Publish Twitter/X Post

Publish a post to Twitter/X through the local Frevana daemon and Chrome Extension session.

## Purpose

This skill uses the Chrome Extension-backed Frevana MCP tool `frevana_publish` with fixed provider `twitter`.

Inputs:

- `text` (required) - final post text
- `format` (optional) - `text` or `json`, defaults to `text`
- `timeout` (optional) - Frevana tool timeout in milliseconds

Publishing is a side effect. Use this skill only when the user explicitly asks to publish.

## What This Skill Needs

- final post text
- bundled `scripts/setup.sh` wrapper, which downloads and runs the latest official Frevana setup script
- Frevana local daemon running after setup, default port `12306`
- Chrome connected through the Frevana Chrome Extension
- active Twitter/X login in Chrome
- `curl`
- `bash`
- `python3`

This is a Chrome Extension skill. It uses the local daemon and Chrome Extension session.

## Execution Order

1. Confirm the user explicitly asked to publish and provided final text.
2. Prefer the script over ad hoc `frevana call` commands.
3. Let the script run bundled `scripts/setup.sh` before every Frevana tool call.
4. If setup reports Chrome disconnected, stop and tell the user to open Chrome, connect the Frevana extension, and retry.
5. If publishing fails because Twitter/X is unavailable or not logged in, tell the user to log in to Twitter/X in Chrome.
6. Return text output by default. If `format` is `json`, return structured JSON with `tool`, `provider`, and `result`.
7. Save output with `--output` when useful.

## Commands

```bash
bash <skill-path>/scripts/publish_twitter_post.sh \
  --text "Just shipped a new feature."
```

```bash
bash <skill-path>/scripts/publish_twitter_post.sh \
  --text-file ./post.txt \
  --format json \
  --output ./out/publish-twitter-post-result.json
```

## Fixed Tool Call Shape

The script calls:

```bash
frevana call frevana_publish '<json_args>'
```

The JSON arguments use this shape:

```json
{
  "provider": "twitter",
  "text": "Just shipped a new feature.",
  "timeout": 30000
}
```

Always send `provider: "twitter"`. Do not pass unsupported fields.

## Notes

- `--text` and `--text-file` are mutually exclusive.
- Use final plain text.
- `--format` must be `text` or `json`; default is `text`.
- `--timeout` must be a positive integer when provided.
- `scripts/setup.sh` downloads and executes the latest official setup script from `https://raw.githubusercontent.com/FinpeakInc/frevana-cli-releases/refs/heads/main/skills/frevana/scripts/setup.sh`.
