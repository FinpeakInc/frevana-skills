---
name: url-scrape
description: Use when the user wants to scrape any URL or web page as Markdown/text through the local Frevana Chrome-backed browser tool, including authenticated pages using the user's Chrome login session.
---

# URL Scrape

Scrape any URL through the local Frevana daemon and Chrome session.

## Purpose

This skill is for **scraping a web page URL** using the Chrome-backed Frevana MCP tool `frevana_scrape`.

Inputs:

- `url` (required) - absolute URL to scrape
- `provider` (optional) - defaults to `url` for clean Markdown extraction via Readability.js
- `timeout` (optional) - Frevana tool timeout in milliseconds, default comes from the tool

Output:

- scraped page content, usually clean Markdown with title, author, content, and links

Summarize the scraped content unless the user asks for the raw scrape output.

## What This Skill Needs

- user-provided absolute `url`
- bundled `scripts/setup.sh` wrapper, which downloads and runs the latest official Frevana setup script
- Frevana local daemon running after setup, default port `12306`
- Chrome connected through Frevana
- `curl`
- `bash`
- `python3`

This skill uses the local daemon and Chrome session. It does not use `FREVANA_TOKEN`.

## Execution Order

Use this flow:

1. Confirm the user has provided an absolute URL with `http://` or `https://`.
2. Prefer the script over ad hoc `frevana call` commands.
3. Default `provider` to `url` when the user does not specify it.
4. Do not invent optional timeout values.
5. Let the script run bundled `scripts/setup.sh` before every Frevana tool call.
6. If setup reports Chrome disconnected, stop and tell the user to open Chrome, connect the Frevana extension, and retry.
7. Run the URL scrape only after setup succeeds.
8. If the scrape returns login/auth content or empty content, tell the user they may need to log in to that site in Chrome.
9. Return a concise summary, or the raw scraped content if requested.
10. When useful, save the output to a file.

## Commands

### Basic URL scrape

```bash
bash <skill-path>/scripts/scrape_url.sh \
  --url "https://example.com"
```

### Explicit provider and timeout

```bash
bash <skill-path>/scripts/scrape_url.sh \
  --url "https://example.com" \
  --provider url \
  --timeout 60000
```

### Save output to file

```bash
bash <skill-path>/scripts/scrape_url.sh \
  --url "https://example.com" \
  --output ./out/url-scrape-result.md
```

## Fixed Tool Call Shape

The script calls:

```bash
frevana call frevana_scrape '<json_args>'
```

The JSON arguments use this shape, omitting optional fields that were not provided:

```json
{
  "url": "https://example.com",
  "provider": "url",
  "timeout": 60000
}
```

Always send `provider`; default it to `url` when the user does not specify a value.
Do not pass unsupported fields to `frevana_scrape`.

## Output

- Success: the script prints the Frevana scrape result to stdout
- With `--output`: the same result is also written to the specified file path
- Failure: the script prints the Frevana error or preflight failure to stderr and exits non-zero

## Notes

- Require `--url`.
- URL must start with `http://` or `https://`.
- `--provider` defaults to `url`.
- `--timeout` must be a positive integer when provided.
- The script runs bundled `scripts/setup.sh` before every scrape, matching the original Frevana skill flow.
- `scripts/setup.sh` downloads and executes the latest official setup script from `https://raw.githubusercontent.com/FinpeakInc/frevana-cli-releases/refs/heads/main/skills/frevana/scripts/setup.sh`.
- If `frevana` is missing, the official setup script installs the Frevana binary before starting/checking the daemon.
- Do not ask for or echo bearer tokens; this workflow is local-daemon based.

## Example Prompts

### 中文

- "抓取 https://example.com 的内容"
- "把这个网页 scrape 成 Markdown"
- "用 Frevana 抓取这个登录后的页面，并保存原始输出"

### English

- "Scrape https://example.com"
- "Extract this web page as Markdown"
- "Scrape this authenticated page through Chrome and save the raw output"
