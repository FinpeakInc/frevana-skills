# AGENTS.md

This file tells a general-purpose coding agent how to use the skills in this repository correctly.

Treat this document as the operational guide for the repo. Treat each skill's `SKILL.md` as the source of truth for that skill. If this file and a specific `SKILL.md` ever conflict, follow the `SKILL.md`.

## Repository Purpose

This repository contains reusable skills for three main workflow families:

- Frevana CLI auth bootstrap and local API key setup
- Amazon data lookups through Frevana-backed HTTP APIs
- Frevana AI Factory API workflows for image generation and HTML generation

The repository is not a general application. It is a collection of agent instructions plus a small set of helper scripts.

## Directory Map

```text
skills/
  frevana-auth/
    SKILL.md
    scripts/login.sh
  amazon-search/
    SKILL.md
    scripts/search_amazon.sh
  amazon-product/
    SKILL.md
    scripts/fetch_product.sh
  amazon-keyword-search-volume/
    SKILL.md
    scripts/get_search_volume.sh
  gpt-image-2/
    SKILL.md
    scripts/generate_image.sh
  nano-banana-2/
    SKILL.md
    scripts/generate_image.sh
  nano-banana-pro/
    SKILL.md
    scripts/generate_image.sh
  frevana-gen-report/
    SKILL.md
    scripts/generate_report.sh
```

## Core Agent Rules

1. Start from user intent, then route to the smallest matching skill.
2. Read the target skill's `SKILL.md` before execution if you need details on parameters, defaults, or failure handling.
3. Prefer the repository scripts over ad hoc API calls when a skill includes a script.
4. Do not invent missing required inputs. Ask for them when the skill requires them.
5. Do not change fixed provider or model contracts for Frevana image skills.
6. Do not rewrite raw API outputs unless the user explicitly asks for a transformation.
7. When returning structured results, summarize them unless the user explicitly asks for raw JSON or raw HTML.

## Skill Routing

### Use `frevana-auth`

Route here when the user wants:

- to log in to Frevana from the CLI
- to start `frevana login`
- to install the Frevana CLI before authenticating
- to obtain or store a Frevana API key for later CLI usage

Required input:

- none

Optional input:

- custom Frevana `server` URL

Important behavior:

- Start the login flow first through the wrapper script.
- If the `frevana login` command is unavailable, then attempt `npm i -g @frevana/frevana` and retry.
- If that install fails because the package is unavailable in the current registry, ask the user for the correct private registry or local package source.
- Let the CLI manage device authorization and local credential storage.
- Do not print the saved API key value back to the user unless they explicitly ask for the raw secret.

### Use `amazon-search`

Route here when the user wants:

- Amazon search results by keyword
- product discovery from a search phrase
- later pages of search results
- delivery-aware search results for a ZIP code

Required input:

- search keyword

Optional input:

- page number
- delivery ZIP code
- output file path
- one-time token override

Do not use this skill when the user gives only a product name but explicitly wants a single known product record by ASIN. Use `amazon-product` instead.

### Use `amazon-product`

Route here when the user wants:

- Amazon product details for a known ASIN
- a direct lookup of a specific listing
- delivery-aware product data for a ZIP code

Required input:

- ASIN

Optional input:

- `amazon_domain`
- `gl`
- `hl`
- customer ZIP code
- `force_refresh`
- output file path
- one-time token override

If the user gives only a product name or Amazon URL without a clear ASIN, ask for the ASIN instead of guessing.

### Use `amazon-keyword-search-volume`

Route here when the user wants:

- Amazon keyword demand
- search volume estimates
- batch keyword research
- keyword comparisons for SEO, PPC, or listing decisions

Required input:

- one or more keywords

Optional input:

- marketplace
- language
- output file path
- one-time token override

Important defaults:

- If marketplace and language are missing, default to `United States / English`.
- State that default explicitly in the user-facing response.

Supported marketplaces are limited to:

- Australia
- Austria
- Canada
- Egypt
- France
- Germany
- India
- Italy
- Mexico
- Netherlands
- Saudi Arabia
- Singapore
- Spain
- United Arab Emirates
- United Kingdom
- United States

If the user asks for an unsupported marketplace, stop and say that the skill only supports the listed marketplaces.

### Use `gpt-image-2`

Route here when the user wants:

- Frevana-hosted images generated with OpenAI
- the `gpt-image-2` model specifically
- raw JSON output from the Frevana OpenAI image backend

Required input:

- `prompt` or `contents`

Optional input:

- `n`
- `size`
- `quality`
- `background`
- `output_format`
- `output_compression`
- output file path

Fixed contract:

- provider: `openai`
- model: `gpt-image-2`

Do not pass or ask for alternate provider/model values.

### Use `nano-banana-2`

Route here when the user wants:

- `Nano Banana 2`
- `nano banana 2`
- Gemini image generation through Frevana using `gemini-3.1-flash-image-preview`

Required input:

- `prompt` or `contents`

Optional input:

- `seed`
- `max-output-tokens`
- `response-modality`
- `aspect-ratio`
- `image-size` (`1K`, `2K`, `4K`; numeric values like `1800` and `WxH` values like `1024x1024` are normalized to the nearest tier, using the larger edge for `WxH`; defaults to `1K`)
- output file path

Fixed contract:

- provider: `gemini`
- model: `gemini-3.1-flash-image-preview`

### Use `nano-banana-pro`

Route here when the user wants:

- `Nano Banana Pro`
- `nano banana pro`
- Gemini image generation through Frevana using `gemini-3-pro-image-preview`

Required input:

- `prompt` or `contents`

Optional input:

- `seed`
- `max-output-tokens`
- `response-modality`
- `aspect-ratio`
- `image-size` (`1K`, `2K`, `4K`; numeric values like `1800` and `WxH` values like `1024x1024` are normalized to the nearest tier, using the larger edge for `WxH`; defaults to `1K`)
- output file path

Fixed contract:

- provider: `gemini`
- model: `gemini-3-pro-image-preview`

### Use `frevana-gen-report`

Route here when the user wants:

- final HTML generated from a Frevana template
- server-side rendering through the Frevana report endpoint
- raw final HTML without post-processing

Required input:

- `template_id`
- exactly one of `content` or `content_file`

Optional input:

- output HTML path
- one-time token override

Do not modify the returned HTML unless the user explicitly asks for edits after generation.

## Ambiguity Handling

Use these rules to avoid bad assumptions:

- If the user wants Frevana CLI login and does not provide a server URL, use `https://api.frevana.com`.
- If the user says "search Amazon for this" but does not provide a keyword, ask for the keyword.
- If the user wants Amazon product details but does not provide an ASIN, ask for the ASIN.
- If the user says only `nano banana` without specifying `2` or `pro`, ask which variant they want.
- If the user asks for Frevana report generation without `template_id`, ask for `template_id`.
- If the user does not provide prompt/content required by a skill, ask for it before execution.

## Execution Order Rules

### Frevana auth bootstrap

For `frevana-auth`:

1. Prefer `scripts/login.sh` over manual shell commands.
2. Run `frevana login --server <effective-server>`, using `https://api.frevana.com` when the user does not provide a custom server.
3. If the command is unavailable, attempt `npm i -g @frevana/frevana`.
4. If `npm` is missing and the command is unavailable, fail fast and tell the user to install Node.js/npm first.
5. If the install step fails because the package is unavailable in the current registry, stop and ask the user for the correct private registry or local package source.
6. Retry `frevana login --server <effective-server>` after a successful install.
7. Let the CLI complete the device authorization flow and save credentials locally.
8. Report the saved config path, but do not echo the raw API key unless the user explicitly asks for it.

### Amazon skills

For `amazon-search`, `amazon-product`, and `amazon-keyword-search-volume`:

1. Extract the user inputs.
2. Prefer the repo script over ad hoc `curl`.
3. Let the script use `FREVANA_TOKEN` from the environment first.
4. In non-interactive agent runs, fail fast if the token is missing.
5. Return either the raw JSON payload or a summary, depending on what the user asked for.
6. Save output with `--output` when a file is useful.

### Frevana image skills

For `gpt-image-2`, `nano-banana-2`, and `nano-banana-pro`:

1. Confirm the user supplied `prompt` or `contents`.
2. Prefer the repo script over ad hoc `curl`.
3. Let the script use `FREVANA_TOKEN` from the environment first.
4. In non-interactive agent runs, fail fast if the token is missing.
5. Return either the raw JSON payload or the primary hosted image URL, depending on what the user asked for.
6. Save output with `--output` when a file is useful.

### Frevana report generation

For `frevana-gen-report`:

1. Confirm `template_id` and exactly one content source.
2. Prefer `scripts/generate_report.sh` over manual API calls.
3. Let the script use `FREVANA_TOKEN` from the environment first.
4. In non-interactive agent runs, fail fast if the token is missing.
5. Extract the response JSON `content` field and treat it as the final HTML.
6. Return that HTML unchanged unless the user asks for a later transformation.

## Dependency Rules

### Frevana auth bootstrap

Needed:

- `bash`
- `frevana` or `npm`
- browser access or a manual way to open the authorization URL

Attempt `frevana login` first. If the command is unavailable, attempt `npm i -g @frevana/frevana`. If that package is unavailable in the current registry, stop and ask for the correct source instead of guessing.

### Amazon workflows

Needed:

- `bash`
- `curl`
- `python3`
- `FREVANA_TOKEN`

### Frevana image and report workflows

Needed:

- `bash`
- `curl`
- `python3` for image scripts
- `FREVANA_TOKEN`

If `FREVANA_TOKEN` is missing in a non-interactive run, stop and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly when the script supports it.

Never echo bearer tokens back to the user.

## Output Rules

### Frevana auth outputs

- The main output is the interactive `frevana login` flow.
- Summarize the authorization result and where credentials were saved.
- Treat the API key as sensitive and do not print it unless the user explicitly asks for the raw value.

### Amazon outputs

- The endpoint scripts return validated JSON to stdout.
- Summarize the results by default.
- If comparing products, highlight title, ASIN, price, rating, and delivery notes when available.
- If comparing keywords, highlight the highest-volume and lowest-volume items and notable gaps.

### Frevana image outputs

- Preserve the raw JSON response when returning structured output.
- Treat the first image URL as the primary asset:
  - `gpt-image-2`: `data[0].image_url`
  - `nano-banana-2`: `generated_images[0].image_url`
  - `nano-banana-pro`: `generated_images[0].image_url`
- Do not proxy, rewrite, or transform returned image URLs unless the user asks for it.

### Frevana report outputs

- The final output is HTML from the API response `content` field.
- Do not optimize, rewrite, or post-process the HTML unless the user explicitly requests that after generation.

## Script Paths

Use these paths when executing repo scripts:

```bash
bash skills/amazon-search/scripts/search_amazon.sh
bash skills/amazon-product/scripts/fetch_product.sh
bash skills/amazon-keyword-search-volume/scripts/get_search_volume.sh
bash skills/frevana-auth/scripts/login.sh
bash skills/gpt-image-2/scripts/generate_image.sh
bash skills/nano-banana-2/scripts/generate_image.sh
bash skills/nano-banana-pro/scripts/generate_image.sh
bash skills/frevana-gen-report/scripts/generate_report.sh
```

## Common Examples

### Frevana auth

```bash
bash skills/frevana-auth/scripts/login.sh

# Uses https://api.frevana.com by default

bash skills/frevana-auth/scripts/login.sh \
  --server "http://localhost:3001"
```

### Amazon search

```bash
bash skills/amazon-search/scripts/search_amazon.sh \
  --query "wireless earbuds"

bash skills/amazon-search/scripts/search_amazon.sh \
  --query "wireless earbuds" \
  --page 2 \
  --delivery-zip 10001
```

### Amazon product

```bash
bash skills/amazon-product/scripts/fetch_product.sh \
  --asin B0D5XWJQ5R

bash skills/amazon-product/scripts/fetch_product.sh \
  --asin B0D5XWJQ5R \
  --customer-zipcode 10001
```

### Amazon keyword search volume

```bash
bash skills/amazon-keyword-search-volume/scripts/get_search_volume.sh \
  --keywords "wireless earbuds,gaming headset" \
  --location-name "United States"
```

### GPT-Image-2

```bash
bash skills/gpt-image-2/scripts/generate_image.sh \
  --prompt "A cinematic product photo of a matte black espresso machine on travertine" \
  --size 1536x1024 \
  --quality high \
  --background opaque \
  --output-format png \
  --output ./out/gpt-image-2-result.json
```

### Nano Banana Pro

```bash
bash skills/nano-banana-pro/scripts/generate_image.sh \
  --prompt "A bright SaaS dashboard scene" \
  --seed 7 \
  --max-output-tokens 1024 \
  --response-modality IMAGE \
  --response-modality TEXT \
  --aspect-ratio 4:3 \
  --image-size 2K \
  --output ./out/nano-banana-pro-result.json
```

### Frevana report generation

```bash
bash skills/frevana-gen-report/scripts/generate_report.sh \
  --content-file ./report-content.md \
  --template-id "medium-article-template-v2" \
  --output ./out/frevana-report.html
```

## Final Behavior Checklist

Before acting, the agent should verify:

- Is the user intent mapped to the correct skill?
- Are all required inputs present?
- Is there a repo script that should be used instead of a custom command?
- If this is an auth request, does `frevana` need to be installed before login starts?
- Is the provider/model fixed for this skill?
- Should the result be summarized, or does the user want raw output?
- Is there any missing dependency or login step that should be surfaced clearly?
