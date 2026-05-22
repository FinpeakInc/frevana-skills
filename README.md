# Frevana Skills

Reusable skills for Frevana auth bootstrap, Amazon research, Google Ads Transparency Center, Google News, Google Related Questions, Google Trends, Google Shopping, Google Immersive Product research, image generation, and HTML generation.

Each skill lives under `skills/`. Start with its `SKILL.md` to see what it does and what it needs. If your agent supports repo-level instructions, also read [AGENTS.md](AGENTS.md).

## Available Skills

### [`frevana-auth`](skills/frevana-auth/SKILL.md)

Authenticate the Frevana CLI and save the local API key config.

Use when:

- you need to run `frevana login`
- you are setting up Frevana CLI on a new machine
- you need to install `frevana` before authenticating
- you want to know where the saved local credentials live

Features:

- starts the device authorization flow with `frevana login`
- retries after `npm i -g @frevana/frevana` only when the login command is unavailable
- uses `https://api.frevana.com` by default and supports an optional custom `--server`
- reports the saved config path without exposing the raw API key by default

### [`amazon-search`](skills/amazon-search/SKILL.md)

Search Amazon products by keyword.

Use when:

- you want Amazon search results for a keyword
- you want to look at more than one page
- you want results for a specific ZIP code

Features:

- keyword search
- page support with `--page`
- ZIP-specific results with `--delivery-zip`
- save results with `--output`

### [`amazon-product`](skills/amazon-product/SKILL.md)

Look up a product by ASIN.

Use when:

- you already have an ASIN
- you want a quick product detail lookup
- you want delivery details for a specific ZIP code

Features:

- ASIN-based lookup
- Amazon US / English by default
- optional ZIP-specific delivery details
- save results with `--output`

### [`amazon-keyword-search-volume`](skills/amazon-keyword-search-volume/SKILL.md)

Check Amazon keyword demand.

Use when:

- you want keyword search volume
- you want to compare multiple keywords
- you want input for SEO, PPC, or listing work

Features:

- compare one or more keywords with `--keywords`
- defaults to `United States / English` when marketplace is not specified
- supported marketplaces: Australia, Austria, Canada, Egypt, France, Germany, India, Italy, Mexico, Netherlands, Saudi Arabia, Singapore, Spain, United Arab Emirates, United Kingdom, United States
- save results with `--output`

### [`google-news-search`](skills/google-news-search/SKILL.md)

Search Google News by keyword.

Use when:

- you want Google News results for a query
- you want country- or language-specific Google News results
- you have a Google News topic, publication, section, or story token

Features:

- `q` is the only required input
- optional `--gl` and `--hl`
- optional Google News token filters
- save results with `--output`

### [`google-ads-transparency-center`](skills/google-ads-transparency-center/SKILL.md)

Search Google Ads Transparency Center ad creative listings.

Use when:

- you want ad creatives for a domain or text query
- you have a Google advertiser ID and want that advertiser's creatives
- you want platform-specific results for Google Search, Shopping, YouTube, Maps, or Play
- you want to continue a paginated result with `next_page_token`

Features:

- accepts `--text`, `--advertiser-id`, or `--next-page-token`
- optional `--platform` and `--region`
- returns advertiser, advertiser ID, creative ID, format, target domain, media links, details links, and first/last shown timestamps when available
- saves every successful response to `./out/google-ads-transparency-center-<timestamp>-<pid>.json` by default
- use `--output` to choose a specific result path

### [`google-related-questions`](skills/google-related-questions/SKILL.md)

Expand Google Related Questions / People Also Ask results by token.

Use when:

- you have a `next_page_token` from a Google Search `related_questions` item
- you want follow-up People Also Ask results
- you want to save raw related question results

Features:

- requires `--next-page-token`
- returns validated JSON
- save results with `--output`

### [`google-trends`](skills/google-trends/SKILL.md)

Query Google Trends by keyword.

Use when:

- you want Google Trends results for a query
- you want trend interest over time, regional interest, or related queries
- you want country-, category-, date-range-, property-, language-, or timezone-specific Trends results

Features:

- `q` is the only required input
- optional `--geo`, `--cat`, `--date`, `--gprop`, `--hl`, and `--tz`
- saves every successful response to `./out/google-trends-<timestamp>-<pid>.json` by default
- use `--output` to choose a specific result path

### [`google-shopping-search`](skills/google-shopping-search/SKILL.md)

Search Google Shopping products by keyword.

Use when:

- you want Google Shopping product results for a query
- you want country- or language-specific Google Shopping results
- you want pagination by start offset, device-specific results, or price sorting

Features:

- `q` is the only required input
- optional `--google-domain`, `--gl`, and `--hl`
- optional `--start`, `--device`, and `--sort-by`
- saves every successful response to `./out/google-shopping-search-<timestamp>-<pid>.json` by default
- use `--output` to choose a specific result path

### [`google-immersive-product`](skills/google-immersive-product/SKILL.md)

Fetch Google Immersive Product details from a Google Shopping result token.

Use when:

- you have an `immersive_product_page_token` from Google Shopping results
- you want product detail popup data, store offers, ratings, reviews, or top insights
- you want the next page of stores using `stores_next_page_token`

Features:

- requires `--page-token`
- optional `--next-page-token` for store pagination
- saves every successful response to `./out/google-immersive-product-<timestamp>-<pid>.json` by default
- use `--output` to choose a specific result path

### [`google-shopping-light-search`](skills/google-shopping-light-search/SKILL.md)

Search Google Shopping Light products by keyword.

Use when:

- you want lightweight Google Shopping product results for a query
- you want country- or language-specific Google Shopping Light results
- you want pagination by start offset or device-specific results

Features:

- `q` is the only required input
- optional `--google-domain`, `--gl`, and `--hl`
- optional `--start` and `--device`
- saves every successful response to `./out/google-shopping-light-search-<timestamp>-<pid>.json` by default
- use `--output` to choose a specific result path

### [`gpt-image-2`](skills/gpt-image-2/SKILL.md)

Generate or edit Frevana-hosted images with OpenAI's `gpt-image-2` model.

Use when:

- you want to generate an image from a prompt
- you want to edit from one or more local reference images
- you want to edit from one or more remote reference image URLs
- you want to use a local directory of reference images
- you want to use `gpt-image-2`
- you may want to save the result to a file

Features:

- accepts prompt input via `--prompt` or `--contents`
- supports image-to-image input via `--image`, `--image-url`, `--image-dir`, and `--mask`
- returns a hosted image link
- supported options: `--n`, `--size`, `--quality`, `--background`, `--output-format`, `--output-compression`

### [`nano-banana-2`](skills/nano-banana-2/SKILL.md)

Generate Frevana-hosted images with Gemini's `gemini-3.1-flash-image-preview` model.

Use when:

- the user mentions `Nano Banana 2` or `nano banana`
- you want to generate an image with the lighter Nano Banana model
- you may want to save the result to a file

Features:

- accepts image input via `--prompt` or `--contents`
- returns a hosted image link
- supported options: `--seed`, `--max-output-tokens`, `--response-modality`, `--aspect-ratio`, `--image-size` (`1K`, `2K`, `4K`; numeric values like `1800` and `WxH` values like `1024x1024` are normalized to the nearest tier, using the larger edge for `WxH`; defaults to `1K`)

### [`nano-banana-pro`](skills/nano-banana-pro/SKILL.md)

Generate Frevana-hosted images with Gemini's `gemini-3-pro-image-preview` model.

Use when:

- the user mentions `Nano Banana Pro` or `nano banana`
- you want the higher-end Nano Banana model
- you may want to save the result to a file

Features:

- accepts image input via `--prompt` or `--contents`
- returns a hosted image link
- supported options: `--seed`, `--max-output-tokens`, `--response-modality`, `--aspect-ratio`, `--image-size` (`1K`, `2K`, `4K`; numeric values like `1800` and `WxH` values like `1024x1024` are normalized to the nearest tier, using the larger edge for `WxH`; defaults to `1K`)

### [`frevana-gen-report`](skills/frevana-gen-report/SKILL.md)

Generate final HTML by combining content with a Frevana template.

Use when:

- you already have a `template_id` and content
- you want finished HTML
- you want to save that HTML to a file

Features:

- accepts either `--content` or `--content-file`
- requires `--template-id`
- returns final HTML directly
- supports saving the output with `--output`

## Installation

Install the skill pack with:

```bash
npx skills add FinpeakInc/frevana-skills
```

If you also plan to run the helper scripts from a local checkout, set:

```bash
export FREVANA_TOKEN="your-bearer-token"
```

Requirements:

- Frevana auth skill: `bash`, `frevana` or `npm`, browser/manual access to the authorization URL, and the correct npm/private package source if the CLI is unavailable when login starts
- Amazon, Google Ads Transparency Center, Google News, Google Related Questions, Google Trends, Google Shopping, and Google Immersive Product skills: `bash`, `curl`, `python3`, `FREVANA_TOKEN`
- Frevana image/report skills: `bash`, `curl`, `python3`, `FREVANA_TOKEN`

## Usage

After installation, use the skill through your agent. If your agent supports repo-level instructions, also load `AGENTS.md`.

Example prompts:

```text
Authenticate Frevana CLI on this machine. If `frevana login` is unavailable, install it and retry.
Search Amazon for wireless earbuds
Fetch Amazon product details for B0D5XWJQ5R
Get Amazon keyword demand for wireless earbuds,gaming headset in United States
Search Google News for artificial intelligence
Search Google Ads Transparency Center for ads from frevana.com
Expand Google Related Questions with next_page_token eyJvbnMiOiIxMDA0MSI...
Search Google Trends for home treadmill with geo=US and date=today 12-m
Search Google Shopping for wireless earbuds with gl=US and hl=en
Fetch Google Immersive Product details with page_token eyJlaSI6Im5ZVmxaOX...
Search Google Shopping Light for wireless earbuds with gl=US and hl=en
Generate an image with gpt-image-2 for a matte black espresso machine
Use gpt-image-2 with the images under ./refs/product to create one polished hero shot
Use gpt-image-2 with https://example.com/reference.png as the reference image
Generate a dashboard illustration with Nano Banana Pro
Generate final HTML from template annual_summary_v2 and this content
```

## Skill Structure

Each skill currently contains:
- `SKILL.md` - Instructions for the agent
- `scripts/` - Helper scripts for automation
- `tests/` - Script-level verification when a skill includes runnable tests

Some skills may also include `evals/` for reusable skill test prompts.

## License

MIT
