---
name: authenticated-fetch
description: Use when the user wants to fetch a URL's raw response (JSON/API or page body) THROUGH their logged-in Frevana Chrome Extension session, so it reaches data behind a login that a plain HTTP client cannot. First-party in-page fetch that carries the browser session (including cookies).
---

# Authenticated Fetch

Fetch any URL through the local Frevana daemon and Chrome Extension session, returning the raw response body — useful for JSON/API endpoints or pages that require the user's login.

## Purpose

This skill fetches a URL using the Chrome Extension-backed Frevana MCP tool `frevana_fetch`. The request runs first-party inside the user's logged-in Chrome, so it carries the browser session (cookies included) and can reach data behind a login that a plain HTTP client (curl, requests) cannot.

Inputs:

- `url` (required) - absolute URL to fetch (must be a public host; localhost/LAN/cloud-metadata are refused by the tool)
- `method` (optional) - HTTP method, defaults to `GET`
- `timeout` (optional) - Frevana tool timeout in milliseconds, default comes from the tool

Output:

- the raw response body as returned by the server (often JSON for an API endpoint)

Return the body as-is when the user wants the raw data; summarize only if asked.

## What This Skill Needs

- user-provided absolute `url`
- bundled `scripts/setup.sh` wrapper, which downloads and runs the latest official Frevana setup script
- Frevana local daemon running after setup, default port `12306`
- Chrome connected through the Frevana Chrome Extension
- `curl`
- `bash`
- `python3`

This is a Chrome Extension skill. It uses the local daemon and Chrome Extension session.

## When to use this vs Web Content Scraper

- Use **Authenticated Fetch** (`frevana_fetch`) to get a **raw response body** — a JSON/API endpoint, a data feed, or any URL where you want the bytes the server returns.
- Use **Web Content Scraper** (`frevana_scrape`) to get a **page as clean Markdown** (Readability.js extraction of an article/page).

## Execution Order

Use this flow:

1. Confirm the user has provided an absolute URL with `http://` or `https://`.
2. Prefer the script over ad hoc `frevana call` commands.
3. Default `method` to `GET` when the user does not specify it.
4. Do not invent optional timeout values.
5. Let the script run bundled `scripts/setup.sh` before every Frevana tool call.
6. If setup reports Chrome disconnected, stop and tell the user to open Chrome, connect the Frevana extension, and retry.
7. Run the fetch only after setup succeeds.
8. If the fetch returns login/auth content or an error status, tell the user they may need to log in to that site in Chrome.
9. Return the raw body, or a concise summary if the user asked for one.
10. When useful, save the output to a file.

## Commands

### Basic authenticated fetch

```bash
bash <skill-path>/scripts/fetch_url.sh \
  --url "https://example.com/api/data.json"
```

### With an explicit method and a saved output file

```bash
bash <skill-path>/scripts/fetch_url.sh \
  --url "https://example.com/api/data.json" \
  --method GET \
  --output ./data.json
```
