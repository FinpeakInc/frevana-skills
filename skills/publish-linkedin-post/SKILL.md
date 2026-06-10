---
name: publish-linkedin-post
description: Use when the user explicitly wants to publish a LinkedIn post or article through Frevana using the Frevana Chrome Extension session.
---

# Publish LinkedIn Post

Publish a LinkedIn feed post or long-form article through the local Frevana daemon and Chrome Extension session.

## Purpose

This skill uses the Chrome Extension-backed Frevana MCP tool `frevana_publish` with fixed provider `linkedin`.

Inputs:

- `text` (required) - final post text; for article mode this is the article body
- `mode` (optional) - `post` or `article`, defaults to `post`
- `title` (optional) - required when `mode` is `article`
- `cover_image` (optional) - article cover image URL or data URL
- `format` (optional) - `text` or `json`, defaults to `text`
- `timeout` (optional) - Frevana tool timeout in milliseconds

Publishing is a side effect. Use this skill only when the user explicitly asks to publish.

## What This Skill Needs

- final post or article text
- bundled `scripts/setup.sh` wrapper, which downloads and runs the latest official Frevana setup script
- Frevana local daemon running after setup, default port `12306`
- Chrome connected through the Frevana Chrome Extension
- active LinkedIn login in Chrome
- `curl`
- `bash`
- `python3`

This is a Chrome Extension skill. It uses the local daemon and Chrome Extension session.

## Execution Order

1. Confirm the user explicitly asked to publish and provided final text.
2. For article mode, require `title`.
3. Prefer the script over ad hoc `frevana call` commands.
4. Let the script run bundled `scripts/setup.sh` before every Frevana tool call.
5. If setup reports Chrome disconnected, stop and tell the user to open Chrome, connect the Frevana extension, and retry.
6. If publishing fails because LinkedIn is unavailable or not logged in, tell the user to log in to LinkedIn in Chrome.
7. Return text output by default. If `format` is `json`, return structured JSON with `tool`, `provider`, and `result`.
8. Save output with `--output` when useful.

## Commands

```bash
bash <skill-path>/scripts/publish_linkedin_post.sh \
  --text "Just shipped a new feature."
```

```bash
bash <skill-path>/scripts/publish_linkedin_post.sh \
  --mode article \
  --title "My article title" \
  --text-file ./article.txt \
  --cover-image "https://example.com/cover.jpg" \
  --timeout 180000
```

## Fixed Tool Call Shape

The script calls:

```bash
frevana call frevana_publish '<json_args>'
```

The JSON arguments use this shape:

```json
{
  "provider": "linkedin",
  "mode": "article",
  "title": "My article title",
  "text": "Article body...",
  "cover_image": "https://example.com/cover.jpg",
  "timeout": 180000
}
```

Always send `provider: "linkedin"`. Do not pass unsupported fields. LinkedIn article bodies are typed into LinkedIn's editor; do not expect HTML tags to render as rich formatting.

## Notes

- `--text` and `--text-file` are mutually exclusive.
- Use plain text for feed posts.
- Use plain text with newlines for LinkedIn articles.
- `--mode` must be `post` or `article`; default is `post`.
- `--title` is required for article mode.
- `--format` must be `text` or `json`; default is `text`.
- `--timeout` must be a positive integer when provided.
- `scripts/setup.sh` downloads and executes the latest official setup script from `https://raw.githubusercontent.com/FinpeakInc/frevana-cli-releases/refs/heads/main/skills/frevana/scripts/setup.sh`.
