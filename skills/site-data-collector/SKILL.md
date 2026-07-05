---
name: site-data-collector
description: Use when the user wants a REUSABLE script that collects all of a website's data (e.g. every listing/product/row across pages) through their logged-in Frevana Chrome Extension session. Explores the site once, auto-detects its JSON API, and returns a ready-to-run Python collector script — no code is written by the model, and the script is not executed here.
---

# Site Data Collector

Explore a site once and get back a ready-to-run **Python collector script** that pulls all of its data through the local Frevana daemon and Chrome Extension session.

## Purpose

This skill runs the Chrome Extension-backed Frevana MCP tool `frevana_generate`. It:

1. Opens the page in the user's logged-in Chrome and records the site's own XHR/API traffic.
2. Auto-detects the top JSON data endpoint, its pagination parameter, and the fields (deterministic — no LLM).
3. Returns a **Python script** whose fetch layer is `frevana fetch` (so every run goes through the user's logged-in browser, at near-zero cost).

It uses a three-layer fallback so most sites produce a working script:

- **Layer 1 (JSON API)** — the deterministic collector above, when the site has a clean JSON feed.
- **Layer 2 (DOM)** — if there is no JSON API, the tool no longer fails: it returns a DOM collector whose fetch layer is still `frevana fetch` (raw HTML) and whose `parse_rows()` defaults to extracting links, with a captured HTML sample embedded in the script.
- **Layer 3 (your job)** — when you get a Layer-2 script, tighten `parse_rows()` + `FIELDS` into the real item rows/columns using that sample (see Execution Order step 6).

Important: this skill **returns a script; it does not run it and it does not return the data directly.** The user runs the script themselves when they want the full dataset (or on a schedule). To get data right now for a single URL instead, use the **Authenticated Fetch** skill.

Inputs:

- `url` (required) - absolute URL of a page whose data feed you want to collect
- `intent` (optional) - what data the user wants (recorded in the script header)
- `duration` (optional) - explore capture window in milliseconds (default comes from the tool)

Output:

- a Python collector script (text). Save it to a `.py` file; the user runs it with `python3` to produce a CSV.

## What This Skill Needs

- user-provided absolute `url`
- bundled `scripts/setup.sh` wrapper, which downloads and runs the latest official Frevana setup script
- Frevana local daemon running after setup, default port `12306`
- Chrome connected through the Frevana Chrome Extension
- `curl`
- `bash`
- `python3`

This is a Chrome Extension skill. It uses the local daemon and Chrome Extension session.

## Execution Order

Use this flow:

1. Confirm the user has provided an absolute URL with `http://` or `https://`.
2. Prefer the script over ad hoc `frevana call` commands.
3. Let the script run bundled `scripts/setup.sh` before every Frevana tool call.
4. If setup reports Chrome disconnected, stop and tell the user to open Chrome, connect the Frevana extension, and retry.
5. Run the generate step only after setup succeeds.
6. If there is no JSON API, `frevana_generate` returns a **Layer 2 DOM collector** instead of failing. When you get one (its header says "Layer 2 (DOM) collector"):
   - Read the captured HTML sample embedded at the bottom of the script.
   - Rewrite `parse_rows()` and `FIELDS` so they select the real item rows/columns the user asked for (this is Layer 3). Keep it deterministic — use CSS/selector or `html.parser` logic in Python; do **not** call an LLM at run time, so reruns stay ~0-token.
   - Set `PAGE_PARAM` (and use `--max-pages`) if the listing paginates.
   - If the page is truly not parseable (heavy anti-bot, canvas/image-only, non-HTML), say so and suggest the Web Content Scraper skill instead.
7. Hand the user the generated script as a saved artifact (via `save_artifacts`) so it appears as a downloadable file card in the chat. Do NOT tell the user to run a bare filename like `python3 collector.py` — the file lives in the session workspace, not their current directory, so that command fails. Instead tell them: click **Save to local** on the file card to save it (e.g. to `~/Downloads`), then run it from there with an absolute path, e.g. `python3 ~/Downloads/collector.py --output data.csv` (on Windows use `python` or `py` and a Windows path, e.g. `python %USERPROFILE%\Downloads\collector.py --output data.csv`). It requires the Frevana CLI (already installed by setup) on the machine.
8. Do not execute the generated script yourself.

## Commands

### Generate a collector script and save it to a file

```bash
bash <skill-path>/scripts/generate_collector.sh \
  --url "https://example.com/products" \
  --intent "all products with price and rating" \
  --output ./collector.py
```

### Print the script to stdout

```bash
bash <skill-path>/scripts/generate_collector.sh --url "https://example.com/products"
```
