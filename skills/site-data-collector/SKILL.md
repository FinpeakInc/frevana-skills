---
name: site-data-collector
description: Use when the user wants a REUSABLE script that collects all of a website's data (e.g. every listing/product/row across pages) through their logged-in Frevana Chrome Extension session. Explores the site once, auto-detects its JSON API, and returns a ready-to-run Python collector script — no code is written by the model, and the script is not executed here. Also supports a URL-LIST mode: given a list of website URLs (e.g. from a Google Map Search), visit each site through the extension and extract its social/contact links — Facebook page, Instagram, LinkedIn, X, email — into a CSV.
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
- **Layer 2 (DOM)** — if there is no JSON API, the tool no longer fails: it returns a DOM collector whose fetch layer is still `frevana fetch` (raw HTML) and whose **selector config** defaults to extracting links, with a captured HTML sample embedded in the script.
- **Layer 3 (your job)** — when you get a Layer-2 script, tighten its `ITEM` / `FIELDS` / pagination **selector config** into the real item rows/columns using that sample (see Execution Order step 6).

Important: this skill **returns a script; it does not run it and it does not return the data directly.** The user runs the script themselves when they want the full dataset (or on a schedule). To get data right now for a single URL instead, use the **Authenticated Fetch** skill.

Inputs:

- `url` (required) - absolute URL of a page whose data feed you want to collect
- `intent` (optional) - what data the user wants (recorded in the script header)
- `duration` (optional) - explore capture window in milliseconds (default comes from the tool)

Output:

- a Python collector script (text). Save it to a `.py` file; the user runs it with `python3` to produce a CSV.

## URL-list mode — visit a list of websites and extract their social/contact links

Use this when the user already has a **list of website URLs** (e.g. the `website` column from a **Google Map Search**) and wants to visit each site and pull its **social / contact links** — Facebook page first, plus Instagram, LinkedIn, X, and email — into a CSV. This is different from the single-site collectors above: it maps over a batch of URLs instead of paginating one site.

Use the bundled `scripts/extract_links.py`. It fetches each site **exactly once** through the logged-in browser (`frevana fetch` = the user's own IP — so there is nothing to rate-limit and block risk is low), extracts the links, and writes a CSV with columns `website, facebook_url, instagram_url, linkedin_url, twitter_url, email, status`.

How to deliver it (fits the file card's **Run** button):

1. **Get the URL list.** From the user directly, or run the **Google Map Search** skill first and take `local_results[].website` (each place record also has `phone`, `address`, `rating`).
2. **Bake the URLs into the script.** Copy `scripts/extract_links.py` into the workspace and fill the `URLS = [...]` list at the top with the website URLs. Baking them in means the file card's **Run** works with no arguments. (Alternatively the user can pass `--input urls.csv`, a CSV with a `website` column, or `--input urls.txt`, one URL per line.)
3. **Deliver via `save_artifacts`** → the user clicks **Run** on the file card → the CSV lands in Downloads.

Honest limits (tell the user):

- **Do NOT scrape Google Maps itself this way.** Maps is heavily anti-bot and scraping it from one IP is exactly what gets blocked — use the **Google Map Search** skill for the place list, then this mode for the websites.
- Coverage is realistic, not 100%. Some sites' WAF returns **HTTP 403** to the lightweight fetch, and some put their Facebook link in **JS-rendered** content the raw fetch can't see. The `status` column records the reason per row (`ok` / `no facebook` / `HTTP 403` / `Failed to fetch`) so misses are visible, not silent. The script auto-retries transient connection blips.

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
   - Tighten it by editing **only the SELECTOR CONFIG** near the top of the script — `ITEM`, `FIELDS`, and the pagination (`PAGE_PARAM` or `NEXT_LINK`). **Do NOT rewrite the parser or subclass `HTMLParser`.** The engine below the config is already void-element-safe and correct; hand-rolling a parser (naive tag-depth counting, grabbing an attribute off the wrong `<a>`) is the #1 source of silent 0-row bugs. This is Layer 3.
     - `ITEM` = the repeating row container, e.g. `{"tag": "article", "class": ["product_pod"]}`.
     - `FIELDS` = one column each, found WITHIN each item: `{"tag": ..., "class": [...], "attr": ...}`. Omit `attr` to read the element's text; `href`/`src` are auto-resolved to absolute URLs. First match in document order wins.
     - Pagination: set `PAGE_PARAM` for `?page=N` sites, or `NEXT_LINK` — e.g. `{"container": {"tag": "li", "class": ["next"]}, "tag": "a"}` — to follow a "next" link. Use `--max-pages` while testing.
   - Keep it deterministic — the config drives a stdlib parser; do **not** call an LLM at run time, so reruns stay ~0-token.
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

### URL-list mode: extract social/contact links from a batch of websites → CSV

Copy `scripts/extract_links.py`, fill its `URLS = [...]` with the website URLs (or use `--input`), then run:

```bash
# URLs baked into URLS[] (what the file card's Run uses):
python3 extract_links.py --output leads.csv

# or read them from a CSV (needs a 'website' column) / a .txt (one URL per line):
python3 extract_links.py --input websites.csv --output leads.csv
```

Output CSV columns: `website, facebook_url, instagram_url, linkedin_url, twitter_url, email, status`.
