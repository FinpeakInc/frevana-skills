# AGENTS.md

This file tells a general-purpose coding agent how to use the skills in this repository correctly.

Treat this document as the operational guide for the repo. Treat each skill's `SKILL.md` as the source of truth for that skill. If this file and a specific `SKILL.md` ever conflict, follow the `SKILL.md`.

## Repository Purpose

This repository contains reusable skills for four main workflow families:

- Frevana CLI auth bootstrap and local API key setup
- Amazon, eBay, Home Depot, and Walmart data lookups through Frevana-backed HTTP APIs
- Google Ads Transparency Center, Google Search, Google Forums, Google Patents, Google News, Google Related Questions, Google Shopping, Google Shopping Light, Google Immersive Product, Google Trends, YouTube Search, and Reddit Search lookups
- Chrome Extension local Frevana workflows, including URL scraping, AI platform asks, Amazon page research, social publishing, and X/Twitter topic search
- SendGrid Mail Send API workflows for transactional email sending
- Instantly API V2 lead, campaign, and email workflows for campaign enrollment and replies
- Klaviyo Campaign API workflows for campaign and audience management
- Frevana AI Factory API workflows for image generation and HTML generation
- MySQL, PostgreSQL, and Redis CRUD workflows with saved local profiles, direct connections, SSH tunnels, and remote-server database access

The repository is not a general application. It is a collection of agent instructions plus a small set of helper scripts.

## Chrome Extension Skill Group

The following skills are Chrome Extension skills:

- `url-scrape`
- `google-search-extension`
- `chatgpt-ask`, `gemini-ask`, `perplexity-ask`, `deepseek-ask`, and `doubao-ask`
- `x-topic-search`
- `reddit-search`
- `amazon-rufus-ai`, `amazon-product-info`, `amazon-top-reviews`, `amazon-price`, and `amazon-rufus-qa`
- `publish-twitter-post`, `publish-facebook-post`, and `publish-linkedin-post`

These skills use the local Frevana daemon and the user's logged-in Chrome Extension session via the Frevana Chrome Extension. They all run their bundled `scripts/setup.sh` wrapper before calling Frevana. The wrapper downloads and executes the official setup script from `https://raw.githubusercontent.com/FinpeakInc/frevana-cli-releases/refs/heads/main/skills/frevana/scripts/setup.sh`, installs the CLI when needed, starts/checks the daemon, and verifies Chrome Extension connectivity.

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
  amazon-rufus-ai/
    SKILL.md
    scripts/setup.sh
    scripts/ask_amazon_rufus.sh
  amazon-product-info/
    SKILL.md
    scripts/setup.sh
    scripts/get_amazon_product_info.sh
  amazon-top-reviews/
    SKILL.md
    scripts/setup.sh
    scripts/get_amazon_top_reviews.sh
  amazon-price/
    SKILL.md
    scripts/setup.sh
    scripts/get_amazon_price.sh
  amazon-rufus-qa/
    SKILL.md
    scripts/setup.sh
    scripts/get_amazon_rufus_qa.sh
  ebay-search/
    SKILL.md
    scripts/search_ebay.sh
  home-depot-search/
    SKILL.md
    scripts/search_home_depot.sh
  walmart-search/
    SKILL.md
    scripts/search_walmart.sh
  walmart-product-reviews/
    SKILL.md
    scripts/search_walmart_product_reviews.sh
  walmart-product-sellers/
    SKILL.md
    scripts/search_walmart_product_sellers.sh
  google-search/
    SKILL.md
    scripts/search_google.sh
  google-forums-search/
    SKILL.md
    scripts/search_google_forums.sh
  google-patents-search/
    SKILL.md
    scripts/search_google_patents.sh
  google-news-search/
    SKILL.md
    scripts/search_google_news.sh
  google-ads-transparency-center/
    SKILL.md
    scripts/search_google_ads_transparency_center.sh
  google-related-questions/
    SKILL.md
    scripts/search_google_related_questions.sh
  google-trends/
    SKILL.md
    scripts/search_google_trends.sh
  google-shopping-search/
    SKILL.md
    scripts/search_google_shopping.sh
  google-shopping-light-search/
    SKILL.md
    scripts/search_google_shopping_light.sh
  google-immersive-product/
    SKILL.md
    scripts/search_google_immersive_product.sh
  youtube-search/
    SKILL.md
    scripts/search_youtube.sh
  sendgrid-send-email/
    SKILL.md
    scripts/send_email.sh
    scripts/query_email_logs.sh
  instantly-send-email/
    SKILL.md
    scripts/lead.sh
    scripts/campaign.sh
    scripts/email.sh
  klaviyo-send-email/
    SKILL.md
    scripts/campaign.sh
    scripts/audience.sh
  mysql-crud/
    SKILL.md
    agents/openai.yaml
    scripts/mysql_crud.sh
  postgresql-crud/
    SKILL.md
    agents/openai.yaml
    scripts/postgresql_crud.sh
  redis-crud/
    SKILL.md
    agents/openai.yaml
    scripts/redis_crud.sh
  mongodb-crud/
    SKILL.md
    agents/openai.yaml
    scripts/mongodb_crud.sh
  reddit-search/
    SKILL.md
    scripts/setup.sh
    scripts/search_reddit.sh
  url-scrape/
    SKILL.md
    scripts/setup.sh
    scripts/scrape_url.sh
  google-search-extension/
    SKILL.md
    scripts/setup.sh
    scripts/search_google_extension.sh
  chatgpt-ask/
    SKILL.md
    scripts/setup.sh
    scripts/ask_chatgpt.sh
  gemini-ask/
    SKILL.md
    scripts/setup.sh
    scripts/ask_gemini.sh
  perplexity-ask/
    SKILL.md
    scripts/setup.sh
    scripts/ask_perplexity.sh
  deepseek-ask/
    SKILL.md
    scripts/setup.sh
    scripts/ask_deepseek.sh
  doubao-ask/
    SKILL.md
    scripts/setup.sh
    scripts/ask_doubao.sh
  x-topic-search/
    SKILL.md
    scripts/setup.sh
    scripts/search_x_topics.sh
  publish-twitter-post/
    SKILL.md
    scripts/setup.sh
    scripts/publish_twitter_post.sh
  publish-facebook-post/
    SKILL.md
    scripts/setup.sh
    scripts/publish_facebook_post.sh
  publish-linkedin-post/
    SKILL.md
    scripts/setup.sh
    scripts/publish_linkedin_post.sh
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
5. Do not change fixed Frevana image-skill routing contracts.
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

### Use `ebay-search`

Route here when the user wants:

- eBay search results by keyword
- product discovery through eBay
- category-specific eBay listings
- paginated eBay results
- eBay-domain-specific search results
- to call the Frevana ebay-search endpoint

Required input:

- at least one of `query` or `category_id`

Optional input:

- `ebay_domain`
- page number
- results per page
- output file path override
- one-time token override

If the user gives only "search eBay for this" without a keyword or category ID, ask for the keyword or category ID.
Do not invent optional eBay domain, page, or result-count fields when the user did not provide them.
The Frevana endpoint schema currently exposes only `query`, `category_id`, `ebay_domain`, `page`, and `results_per_page`; do not pass unsupported passthrough fields such as `engine`, `api_key`, `output`, `no_cache`, `async`, or `zero_trace`.
The script saves every successful response to a JSON file by default, so use that saved file for follow-up parsing instead of calling the search API again.

### Use `home-depot-search`

Route here when the user wants:

- Home Depot search results by keyword
- product discovery through Home Depot
- country-specific Home Depot searches for US or Canada
- store-specific Home Depot results
- delivery ZIP or postal-code-aware Home Depot results
- paginated Home Depot results
- to call the Frevana home-depot-search endpoint

Required input:

- `q` search keyword

Optional input:

- `country`
- `store`
- `delivery_zip`
- page number
- page size
- output file path override
- one-time token override

If the user says "search Home Depot for this" without a keyword, ask for the keyword.
Do not invent optional country, store, delivery ZIP, page, or page-size fields when the user did not provide them.
The Frevana endpoint schema currently exposes only `q`, `country`, `store`, `delivery_zip`, `page`, and `page_size`; do not pass unsupported passthrough fields such as `engine`, `api_key`, `output`, `no_cache`, `async`, `zero_trace`, `hd_sort`, `hd_filter_tokens`, `store_id`, `nao`, `ps`, `sort`, `filter`, `lowerbound`, `upperbound`, `minmax`, or `pagesize`.
The script saves every successful response to a JSON file by default, so use that saved file for follow-up parsing instead of calling the search API again.

### Use `walmart-search`

Route here when the user wants:

- Walmart search results by keyword
- product discovery through Walmart
- Walmart category-specific listings
- paginated Walmart results
- device-specific Walmart results
- Walmart sorting, including price low to high, price high to low, best seller, best match, rating high, or new
- Walmart facet or price-bound filtering
- to call the Frevana walmart-search endpoint

Required input:

- `query` search keyword

Optional input:

- `device`
- `cat_id`
- page number
- `sort`
- `facet`
- `min_price`
- `max_price`
- output file path override
- one-time token override

If the user says "search Walmart for this" without a keyword, ask for the keyword.
Do not invent optional device, category, page, sort, facet, or price-bound fields when the user did not provide them.
The Frevana endpoint schema currently exposes only `query`, `device`, `cat_id`, `page`, `sort`, `facet`, `min_price`, and `max_price`; do not pass unsupported passthrough fields such as `engine`, `api_key`, `output`, `no_cache`, `async`, `zero_trace`, `walmart_domain`, `soft_sort`, `store_id`, `spelling`, `nd_en`, or `include_filters`.
The script saves every successful response to a JSON file by default, so use that saved file for follow-up parsing instead of calling the search API again.

### Use `walmart-product-reviews`

Route here when the user wants:

- Walmart reviews for a known product
- Walmart review pagination
- Walmart review sorting
- Walmart reviews filtered by star rating
- top positive or negative Walmart reviews
- to call the Frevana walmart-product-reviews endpoint

Required input:

- `product_id` / Walmart `us_item_id`

Optional input:

- page number
- `sort`
- `rating`
- output file path override
- one-time token override

If the user gives only a product name, keyword, or Walmart URL without a clear item ID, suggest running `walmart-search` first and using the chosen result's `organic_results[].us_item_id`.
Do not invent optional page, sort, or rating fields when the user did not provide them.
The Frevana endpoint schema currently exposes only `product_id`, `page`, `sort`, and `rating`; do not pass unsupported passthrough fields such as `engine`, `api_key`, `output`, `no_cache`, `async`, or `zero_trace`.
The script saves every successful response to a JSON file by default, so use that saved file for follow-up parsing instead of calling the reviews API again.

### Use `walmart-product-sellers`

Route here when the user wants:

- Walmart sellers for a known product
- Walmart seller offers or marketplace offers
- store-specific Walmart seller availability
- seller prices, delivery dates, return policies, or seller store-front links
- to call the Frevana walmart-product-sellers endpoint

Required input:

- `product_id` / Walmart `us_item_id`

Optional input:

- `store_id`
- output file path override
- one-time token override

If the user gives only a product name, keyword, or Walmart URL without a clear item ID, suggest running `walmart-search` first and using the chosen result's `organic_results[].us_item_id`.
Do not invent `store_id` when the user did not provide it.
The Frevana endpoint schema currently exposes only `product_id` and `store_id`; do not pass unsupported passthrough fields such as `engine`, `api_key`, `output`, `no_cache`, `async`, or `zero_trace`.
The script saves every successful response to a JSON file by default, so use that saved file for follow-up parsing instead of calling the sellers API again.

### Use `google-search`

Route here when the user wants:

- Google Search results by keyword
- regular Google web search / SERP results
- organic results, related searches, related questions, answer boxes, or knowledge graph from Google Search
- country-, language-, location-, device-, safe-search-, result-count-, or pagination-specific Google Search results
- to call the Frevana google-search endpoint

Required input:

- `q` search keyword

Optional input:

- `location`
- `gl`
- `hl`
- `num`
- `start`
- `safe`
- `device`
- output file path override
- one-time token override

The user can provide only `q`. Do not invent optional location, country, language, result count, pagination, safe-search, or device fields when the user did not provide them.
The Frevana endpoint schema currently exposes only `q`, `location`, `gl`, `hl`, `num`, `start`, `safe`, and `device`; do not pass unsupported passthrough fields such as `engine`, `api_key`, `output`, `no_cache`, `async`, or `zero_trace`, and do not pass other unsupported Google Search fields unless the Frevana endpoint schema is expanded first.
The script saves every successful response to a JSON file by default, so use that saved file for follow-up parsing instead of calling the search API again.

### Use `google-forums-search`

Route here when the user wants:

- Google Forums results by keyword
- forum-style Google results from Google's Forums tab
- Reddit, Quora, Stack Overflow, community discussion, or other forum-style results surfaced through Google Forums
- country-, language-, device-, pagination-, or date-bounded Google Forums results
- to call the Frevana google-forums endpoint

Required input:

- `q` search keyword

Optional input:

- `device`
- `hl`
- `gl`
- `start`
- `start_date`
- `end_date`
- output file path override
- one-time token override

The user can provide only `q`. Do not invent optional device, language, country, pagination, or date-bound fields when the user did not provide them.
The Frevana endpoint schema currently exposes only `q`, `device`, `hl`, `gl`, `start`, `start_date`, and `end_date`; do not pass unsupported passthrough fields such as `engine`, `api_key`, `output`, `no_cache`, `async`, or `zero_trace`, and do not pass other unsupported Google Forums fields such as `location`, `uule`, `period_unit`, `period_value`, `nfpr`, `filter`, or `tbs` unless the Frevana endpoint schema is expanded first.
The script saves every successful response to a JSON file by default, so use that saved file for follow-up parsing instead of calling the search API again.

### Use `google-patents-search`

Route here when the user wants:

- Google Patents results by keyword or query
- patent or patent-application discovery through Google Patents
- paginated Google Patents results
- result-count, language, or patent-status filters
- to call the Frevana google-patents endpoint

Required input:

- `q` search query

Optional input:

- page number
- `num`
- `language`
- `status`
- output file path override
- one-time token override

The user can provide only `q`. Do not invent optional page, result-count, language, or status fields when the user did not provide them.
The Frevana endpoint schema currently exposes only `q`, `page`, `num`, `language`, and `status`; do not pass unsupported passthrough fields such as `engine`, `api_key`, `output`, `no_cache`, `async`, or `zero_trace`, and do not pass other unsupported Google Patents fields unless the Frevana endpoint schema is expanded first.
The script saves every successful response to a JSON file by default, so use that saved file for follow-up parsing instead of calling the search API again.

### Use `google-news-search`

Route here when the user wants:

- Google News search results by keyword
- current news articles from Google News
- country- or language-specific Google News results
- scoped Google News results by topic, publication, section, or story token

Required input:

- `q` search keyword

Optional input:

- `gl`
- `hl`
- `topic_token`
- `publication_token`
- `section_token`
- `story_token`
- output file path
- one-time token override

The user can provide only `q`. Do not invent optional country, language, or token fields when the user did not provide them.

### Use `google-ads-transparency-center`

Route here when the user wants:

- Google Ads Transparency Center ad creative results
- ad lookup by Google advertiser ID
- domain or text searches for ads shown in Google Ads Transparency Center
- platform-specific ad searches across Google Play, Google Maps, Google Search, Google Shopping, or YouTube
- region-specific or paginated Google Ads Transparency Center results
- to call the Frevana google-ads-transparency-center endpoint

Required input:

- at least one of `advertiser_id`, `text`, or `next_page_token`

Optional input:

- `platform`
- `region`
- output file path override
- one-time token override

If the user gives only a brand/company name and asks for a specific advertiser record by ID, ask for the advertiser ID instead of guessing. If the user wants a general ad search for that brand, use `text`.
Do not invent optional platform, region, or pagination token fields when the user did not provide them.
The Frevana endpoint schema currently exposes only `advertiser_id`, `text`, `platform`, `region`, and `next_page_token`; do not pass unsupported passthrough fields such as `engine`, `api_key`, `output`, `no_cache`, `async`, `zero_trace`, `political_ads`, `start_date`, `end_date`, `creative_format`, or `num`.
The script saves every successful response to a JSON file by default, so use that saved file for follow-up parsing instead of calling the search API again.

### Use `google-related-questions`

Route here when the user wants:

- Google Related Questions results
- People Also Ask follow-up questions
- to expand a Google Search `related_questions` item using `next_page_token`
- to call the Frevana google-related-questions endpoint

Required input:

- `next_page_token`

Optional input:

- output file path
- one-time token override

This is not a keyword search endpoint. If the user gives only a query, question, or topic without a `next_page_token`, tell them to run the regular Google Search skill first to obtain `related_questions[].next_page_token`, then continue with this skill using that token.

### Use `google-trends`

Route here when the user wants:

- Google Trends results by keyword
- search trend interest over time
- trend comparisons or demand checks through Google Trends
- country- or language-specific Google Trends results
- category-specific, date-range-specific, Google-property-specific, or timezone-aware Google Trends results

Required input:

- `q` search keyword

Optional input:

- `geo`
- `cat`
- `date`
- `gprop`
- `hl`
- `tz`
- output file path override
- one-time token override

The user can provide only `q`. Do not invent optional country, category, date range, Google property, language, or timezone fields when the user did not provide them.
The script saves every successful response to a JSON file by default, so use that saved file for follow-up parsing instead of calling the trends API again.

### Use `google-shopping-search`

Route here when the user wants:

- Google Shopping product results by keyword
- product discovery through Google Shopping
- country- or language-specific Google Shopping results
- paginated Google Shopping results by start offset
- device-specific Google Shopping results
- Google Shopping sorting, including price low to high or price high to low

Required input:

- `q` search keyword

Optional input:

- `google_domain`
- `gl`
- `hl`
- `start`
- `device`
- `sort_by`
- output file path override
- one-time token override

The user can provide only `q`. Do not invent optional Google domain, country, language, pagination, device, or sort fields when the user did not provide them.
The script saves every successful response to a JSON file by default, so use that saved file for follow-up parsing instead of calling the search API again.

### Use `google-immersive-product`

Route here when the user wants:

- Google Immersive Product details
- product details from a Google Shopping `immersive_product_page_token`
- store offers inside the Google Immersive Product popup
- the next page of stores using `stores_next_page_token`
- to call the Frevana google-immersive-product endpoint

Required input:

- `page_token`

Optional input:

- `next_page_token`
- output file path override
- one-time token override

The required `page_token` comes from a Google Shopping result item's `immersive_product_page_token`. The optional `next_page_token` comes from the current Google Immersive Product response's `product_results.stores_next_page_token` and is only for store pagination. If the user gives only a product name, keyword, or URL without a `page_token`, suggest running `google-shopping-search` first to obtain `immersive_product_page_token`, then continue with this skill using that token.

### Use `google-shopping-light-search`

Route here when the user wants:

- Google Shopping Light product results by keyword
- lightweight Google Shopping product discovery
- country- or language-specific Google Shopping Light results
- paginated Google Shopping Light results by start offset
- device-specific Google Shopping Light results

Required input:

- `q` search keyword

Optional input:

- `google_domain`
- `gl`
- `hl`
- `start`
- `device`
- output file path override
- one-time token override

The user can provide only `q`. Do not invent optional Google domain, country, language, pagination, or device fields when the user did not provide them.
The Light endpoint does not support `sort_by`; use `google-shopping-search` when the user explicitly asks for Google Shopping price sorting.
The script saves every successful response to a JSON file by default, so use that saved file for follow-up parsing instead of calling the search API again.

### Use `youtube-search`

Route here when the user wants:

- YouTube search results by keyword
- localized YouTube video results by country or language
- filtered YouTube Search results using an `sp` parameter
- paginated YouTube Search results using a follow-up `sp` token
- to call the Frevana youtube-search endpoint

Required input:

- `search_query`

Optional input:

- `sp`
- `hl`
- `gl`
- output file path
- one-time token override

The user can provide only `search_query`. Do not invent optional `sp`, country, or language fields when the user did not provide them.
The Frevana endpoint schema currently exposes only `search_query`, `sp`, `hl`, and `gl`; do not pass unsupported passthrough fields such as `engine`, `api_key`, `output`, `no_cache`, `async`, or `zero_trace`.

### Use `reddit-search`

Route here when the user wants:

- Reddit search results by keyword or query
- recent Reddit link posts for a topic
- top Reddit link posts for a topic
- paginated Reddit search using an `after` token
- to call `https://www.reddit.com/search.json`

Required input:

- `q` search query

Optional input:

- `sort` (`new` or `top`, defaults to `new`)
- `limit` (defaults to `25`, max `100`)
- `after`
- output file path

The user can provide only `q`. Always keep `type` fixed to `link`. Do not invent optional sort, limit, or pagination fields when the user did not provide them, except for the documented defaults `sort=new` and `limit=25`.
The script uses the local Frevana daemon and Chrome Extension session through `frevana_scrape`; it does not require `FREVANA_TOKEN`. It supports only `q`, fixed `type=link`, `sort`, `limit`, `after`, timeout, and output path; do not pass unsupported Reddit Search fields.
The script first scrapes `https://www.reddit.com/` to warm up the browser/extension session, then scrapes the `search.json` URL and extracts validated JSON. Do not ask the user to pass Reddit cookies manually.

### Use `mysql-crud`

Route here when the user wants:

- to configure and save reusable MySQL database connection profiles
- MySQL schema inspection, table listing, or column listing
- MySQL `select`, `insert`, `update`, or `delete` operations
- safe MySQL CRUD with dry-run previews and explicit write execution
- to connect directly to MySQL
- to connect to MySQL through an SSH tunnel
- to SSH to a remote server first, read a remote `.env` `DATABASE_URL`, and run the remote `mysql` client there
- to SSH to a remote server, `cd` into an application directory, read `.env`, and then connect to MySQL
- to query a production-style database through a saved SSH alias without re-entering connection details

Required input:

- for configuration: profile name and connection mode (`direct`, `ssh-tunnel`, or `ssh-remote`)
- for `direct`: a MySQL URL or explicit MySQL host/database/user fields
- for `ssh-tunnel`: SSH target plus MySQL host/database/user fields
- for `ssh-remote`: SSH target plus either a remote `env_file`/`env_key`, a MySQL URL, or explicit MySQL fields; use `remote_cwd` when `.env` is relative to an application directory
- for CRUD: a saved profile or an existing default profile

Important behavior:

- Prefer `skills/mysql-crud/scripts/mysql_crud.sh` over ad hoc `mysql`, SSH, or SQL commands.
- Connection profiles are saved locally under `~/.config/mysql-crud/profiles/` with `0600` permissions; do not store secrets in this repository.
- Do not print passwords or full database URLs. Use `list-profiles` for redacted profile output.
- Use `readonly` profiles for production or sensitive databases by default.
- `readonly` profiles block `insert`, `update`, `delete`, and raw write SQL.
- `insert`, `update`, and `delete` dry-run by default. Run with `--execute` only after explicit user confirmation.
- `update` and `delete` require `--where` unless the user explicitly confirms a full-table operation and `--allow-full-table` is passed.
- Use named parameters in filters, such as `--where "email = :email" --param email=user@example.com`.
- Do not invent table or column names. Run `schema` first when uncertain.
- For `ssh-remote`, the remote server needs `bash` and the `mysql` client.
- For `ssh-remote`, pass `--remote-cwd` when the `.env` file exists only after changing into a project directory; pass `--env-file .env` for a relative file or an absolute env path when no working directory is needed.
- For `direct` and `ssh-tunnel`, the local `mysql` client is required.

### Use `postgresql-crud`

Route here when the user wants:

- to configure and save reusable PostgreSQL database connection profiles
- PostgreSQL schema inspection, table listing, or column listing
- PostgreSQL table listing across all non-system schemas
- PostgreSQL `select`, `insert`, `update`, or `delete` operations
- PostgreSQL table operations in a specific schema, defaulting to `public`
- safe PostgreSQL CRUD with dry-run previews and explicit write execution
- to connect directly to PostgreSQL
- to connect to PostgreSQL through an SSH tunnel
- to SSH to a remote server first, read a remote `.env` `DATABASE_URL`, and run the remote `psql` client there
- to SSH to a remote server, `cd` into an application directory, read `.env`, and then connect to PostgreSQL
- to query a production-style PostgreSQL database through a saved SSH alias without re-entering connection details

Required input:

- for configuration: profile name and connection mode (`direct`, `ssh-tunnel`, or `ssh-remote`)
- for `direct`: a PostgreSQL URL or explicit PostgreSQL host/database/user fields
- for `ssh-tunnel`: SSH target plus PostgreSQL host/database/user fields
- for `ssh-remote`: SSH target plus either a remote `env_file`/`env_key`, a PostgreSQL URL, or explicit PostgreSQL fields; use `remote_cwd` when `.env` is relative to an application directory
- for CRUD: a saved profile or an existing default profile

Important behavior:

- Prefer `skills/postgresql-crud/scripts/postgresql_crud.sh` over ad hoc `psql`, SSH, or SQL commands.
- Connection profiles are saved locally under `~/.config/postgresql-crud/profiles/` with `0600` permissions; do not store secrets in this repository.
- Do not print passwords or full database URLs. Use `list-profiles` for redacted profile output.
- Use `readonly` profiles for production or sensitive databases by default.
- `readonly` profiles block `insert`, `update`, `delete`, and raw write SQL.
- `insert`, `update`, and `delete` dry-run by default. Run with `--execute` only after explicit user confirmation.
- Raw write SQL requires both `--execute` and `--allow-raw-write`; do not treat `WITH` queries as read-only.
- `update` and `delete` require `--where` unless the user explicitly confirms a full-table operation and `--allow-full-table` is passed.
- Use named parameters in filters, such as `--where "email = :email" --param email=user@example.com`.
- Do not invent schema, table, or column names. Run `schema` first when uncertain.
- Default PostgreSQL CRUD operations to schema `public` when the user gives only a table name.
- Use `--schema <name>` for non-public schemas, or accept schema-qualified tables such as `auth.users`.
- Use `schema --all-schemas` for database-wide table discovery.
- Use `configure --test-connection` when the user asks to verify a profile before saving/relying on it.
- Preserve full PostgreSQL URLs by passing them to `psql`; query parameters such as `sslmode=require` should not be stripped.
- For `ssh-remote`, the remote server needs `bash` and the `psql` client.
- For `ssh-remote`, pass `--remote-cwd` when the `.env` file exists only after changing into a project directory; pass `--env-file .env` for a relative file or an absolute env path when no working directory is needed.
- For `direct` and `ssh-tunnel`, the local `psql` client is required.

### Use `redis-crud`

Route here when the user wants:

- to configure and save reusable Redis connection profiles
- Redis key inspection, string value lookup, hash lookup, or key scanning
- Redis `GET`, `SET`, `DEL`, `HGET`, `HSET`, `HGETALL`, `SCAN`, or `PING`
- safe Redis writes with dry-run previews and explicit write execution
- to connect directly to Redis
- to connect to Redis through an SSH tunnel
- to SSH to a remote server first, read a remote `.env` `REDIS_URL`, and run the remote `redis-cli` there
- to SSH to a remote server, `cd` into an application directory, read `.env`, and then connect to Redis
- to query a production-style Redis instance through a saved SSH alias without re-entering connection details

Required input:

- for configuration: profile name and connection mode (`direct`, `ssh-tunnel`, or `ssh-remote`)
- for `direct`: a Redis URL or explicit Redis host/port/db fields
- for `ssh-tunnel`: SSH target plus Redis host/port/db fields
- for `ssh-remote`: SSH target plus either a remote `env_file`/`env_key`, a Redis URL, or explicit Redis fields; use `remote_cwd` when `.env` is relative to an application directory
- for key operations: a saved profile or existing default profile, plus the key/field/value required by the operation

Important behavior:

- Prefer `skills/redis-crud/scripts/redis_crud.sh` over ad hoc `redis-cli`, SSH, or Redis commands.
- Connection profiles are saved locally under `~/.config/redis-crud/profiles/` with `0600` permissions; do not store secrets in this repository.
- Do not print passwords or full Redis URLs. Use `list-profiles` for redacted profile output.
- Use `readonly` profiles for production or sensitive Redis instances by default.
- `readonly` profiles block `SET`, `DEL`, `HSET`, and raw write commands.
- `SET`, `DEL`, and `HSET` dry-run by default. Run with `--execute` only after explicit user confirmation.
- Raw write commands require both `--execute` and `--allow-raw-write`.
- Prefer structured commands over `raw-command`.
- Prefer repeated `raw-command --arg` values over `--command` when values contain spaces or complex quoting.
- Use `scan --cursor <cursor>` for paginated scans, or `scan --all` only when the user explicitly wants to scan all matching keys.
- Use `configure --test-connection` when the user asks to verify a profile before saving/relying on it.
- Preserve full Redis URLs by passing them to `redis-cli`; username, password, database, and TLS-style forms supported by `redis-cli` should not be stripped.
- `ssh-tunnel` port checks use `nc`, `lsof`, `ss`, or `netstat` fallbacks instead of Bash `/dev/tcp`, so the script can run on macOS and Windows shell environments such as Git Bash or WSL.
- For `ssh-remote`, the remote server needs `bash` and `redis-cli`.
- For `direct` and `ssh-tunnel`, the local `redis-cli` client is required.

### Use `mongodb-crud`

Route here when the user wants:

- to configure and save reusable MongoDB connection profiles
- MongoDB database or collection inspection
- MongoDB document lookup, counting, insertion, update, or deletion
- MongoDB `ping`, `databases`, `collections`, `find`, `count`, `insert`, `update`, `delete`, or guarded raw JavaScript evaluation
- safe MongoDB writes with dry-run previews and explicit write execution
- to connect directly to MongoDB
- to connect to MongoDB through an SSH tunnel
- to SSH to a remote server first, read a remote `.env` `MONGODB_URI`, and run the remote `mongosh` there
- to SSH to a remote server, `cd` into an application directory, read `.env`, and then connect to MongoDB
- to query a production-style MongoDB instance through a saved SSH alias without re-entering connection details

Required input:

- for configuration: profile name and connection mode (`direct`, `ssh-tunnel`, or `ssh-remote`)
- for `direct`: a MongoDB URI or explicit MongoDB host/port/database fields
- for `ssh-tunnel`: SSH target plus MongoDB host/port/database fields
- for `ssh-remote`: SSH target plus either a remote `env_file`/`env_key`, a MongoDB URI, or explicit MongoDB fields; use `remote_cwd` when `.env` is relative to an application directory
- for document operations: a saved profile or existing default profile, plus collection and JSON filter/document/update values required by the operation

Important behavior:

- Prefer `skills/mongodb-crud/scripts/mongodb_crud.sh` over ad hoc `mongosh`, SSH, or MongoDB commands.
- Connection profiles are saved locally under `~/.config/mongodb-crud/profiles/` with `0600` permissions; do not store secrets in this repository.
- Do not print passwords or full MongoDB URIs. Use `list-profiles` for redacted profile output.
- Use `readonly` profiles for production or sensitive MongoDB instances by default.
- `readonly` profiles block `insert`, `update`, `delete`, and raw write JavaScript.
- `insert`, `update`, and `delete` dry-run by default. Run with `--execute` only after explicit user confirmation.
- Raw write JavaScript requires both `--execute` and `--allow-raw-write`.
- Prefer structured commands over `raw-eval`, especially when user input contains complex quoting.
- Pass filters, documents, updates, projections, and sort options as JSON strings.
- Use `configure --test-connection` when the user asks to verify a profile before saving/relying on it.
- Preserve full MongoDB URIs by passing them to `mongosh`; query parameters such as `authSource`, `replicaSet`, `tls`, and `retryWrites` should not be stripped.
- For `ssh-remote`, the remote server needs `bash` and `mongosh`.
- For `direct` and `ssh-tunnel`, the local `mongosh` client is required.

### Use `sendgrid-send-email`

Route here when the user wants:

- to send transactional email through SendGrid
- to call the Twilio SendGrid v3 Mail Send API
- to query SendGrid Email Logs / send status by recipient, optional subject, sent-at lower bound, and message ID
- a SendGrid dry-run payload before sending
- SendGrid plain text, HTML, dynamic template, attachment, sandbox, or scheduled-send email

Required input:

- sender email through `--from`; this address should be a verified sender in the user's Twilio SendGrid account
- one or more recipient emails
- subject, unless provided by a dynamic template
- message content through plain text, HTML, or `template_id`

For status lookup:

- `to_email`, `sent_at`, and `message_id` for lower-bound lookup plus fuzzy `sg_message_id` matching
- optional `subject` to narrow Email Logs results
- or raw Email Logs `query`

Optional input:

- cc or bcc recipients
- reply-to
- dynamic template data JSON
- attachments
- business correlation ID through `--business-id`; auto-generated when omitted
- categories
- custom args
- `batch_id`
- `send_at` Unix seconds
- sandbox mode
- private recipients
- API region (`global` or `eu`)
- output file path
- one-time API key override

Important behavior:

- Use `SENDGRID_API_KEY`, not `FREVANA_TOKEN` and not Twilio Account SID/Auth Token credentials.
- API key lookup order is `--api-key`, then `SENDGRID_API_KEY`, then the locally saved key at `~/.config/sendgrid-send-email/api_key`.
- Require the user to provide `from`. This address should be a verified sender in the user's Twilio SendGrid account.
- If no API key is available, the scripts prompt once in interactive runs and save the key locally for future runs. In non-interactive runs, guide the user to read `https://frevana.gitbook.io/frevana-docs/email-integrations/sendgrid-integration` to get the required configuration.
- Use `--api-key <key> --save-api-key` or `--configure-api-key` to update the saved key. Use `--clear-api-key` to remove it.
- Prefer `scripts/send_email.sh` over ad hoc `curl`.
- For status lookup, prefer `scripts/query_email_logs.sh` over ad hoc `curl`.
- The script dry-runs by default and requires `--send` to call SendGrid.
- After a successful send with `x-message-id`, the script returns `status_query.prompt_example` as a concise user-facing example for querying Email Logs later, plus `status_query.query_params` for agent use. Do not display shell scripts unless the user asks.
- For dynamic template sends, do not include `--subject` when querying Email Logs status. The template may override the request subject, so subject filtering can hide matching messages.
- Every request includes `custom_args.business_id` for application-side correlation. Use `--business-id` when the user provides a business-specific ID; otherwise let the script generate one.
- Do not pass `business_id` through `--custom-arg`; it is reserved for the generated or explicit business ID.
- Confirm recipients, subject, and content before running with `--send`.
- Treat HTTP `202` as queued, not delivered. Sandbox validation may return HTTP `200`.
- Do not print or log the API key. If the user shares a key in chat, advise them to rotate it.
- Use `--private-recipients` when multiple `to` recipients should not see each other.

### Use `instantly-send-email`

Route here when the user wants:

- to send cold/outbound first-touch email through an existing Instantly campaign
- to check whether an Instantly lead exists, create it if missing, then enroll or move it into a selected campaign
- to list or create Instantly campaigns
- to inspect campaign sending status after lead enrollment
- to list a lead email address's Instantly emails and reply to the exact email chosen by the user

Do not use this for:

- SendGrid, SMTP, or generic transactional email
- the Instantly test email endpoint `POST /api/v2/emails/test`
- arbitrary direct sends without a campaign or existing email
- forwarding, listing, patching, or deleting Unibox emails

Required flow for cold outbound:

1. Use `scripts/lead.sh list --email <email>` to check whether the lead exists.
2. Use `scripts/campaign.sh list` to show campaigns and let the user choose, or `scripts/campaign.sh create` when the user wants a new campaign.
3. If the lead is missing, use `scripts/lead.sh create --email <email> --campaign-id <campaign_id> [lead fields] --send` after dry-run and approval.
4. If the lead exists, use `scripts/lead.sh move --email <email> --to-campaign-id <campaign_id> --send` after dry-run and approval.
5. Use `scripts/campaign.sh sending-status --campaign-id <campaign_id>` to explain whether/when sending can proceed.

Required flow for replies:

1. Use `scripts/email.sh list --lead <email>` to fetch the lead email address's emails.
2. Show the user a compact list and ask them to choose the exact email.
3. Use `scripts/email.sh reply --reply-to-uuid <selected_email_id> ...` after dry-run and approval.

Optional input:

- lead first name, last name, company, title, website, phone, personalization, and custom variables
- reply additional recipients, cc, bcc, reminder timestamp, and assigned user
- output file path
- one-time API key override

Important behavior:

- Use `INSTANTLY_API_KEY`, not `FREVANA_TOKEN` and not `SENDGRID_API_KEY`.
- API key lookup order is `--api-key`, then `INSTANTLY_API_KEY`, then the locally saved key at `~/.config/instantly-send-email/api_key`.
- For cold outbound, the API key should have one of these Instantly API V2 scopes: `leads:create`, `leads:all`, `all:create`, or `all:all`.
- For replies, the API key should have `emails:create`; if using `thread_id` lookup, it also needs `emails:read`, or broader equivalent scopes.
- If no API key is available, the script prompts once in interactive runs and saves the key locally for future runs. In non-interactive runs, tell the user to create an Instantly API V2 key by following `https://developer.instantly.ai/getting-started/getting-started`.
- Use `--api-key <key> --save-api-key` or `--configure-api-key` to update the saved key. Use `--clear-api-key` to remove it.
- Prefer `scripts/lead.sh`, `scripts/campaign.sh`, and `scripts/email.sh` over ad hoc `curl`.
- Write actions dry-run by default and require `--send`; read actions call the API immediately.
- Do not invent campaign IDs. Let the user select a campaign from `campaign.sh list` or explicitly ask to create one.
- For campaign creation, collect required fields together before calling the script: `name` and `campaign_schedule`. Prefer a full `--campaign-json` when the user has sequences/templates/senders ready.
- For lead creation in the send-email workflow, collect required fields together before calling the script: lead `email` and selected `campaign_id`; also ask for personalization fields such as first name, last name, company, title, website, and custom variables if the campaign templates need them.
- For replies, `POST /api/v2/emails/reply` requires `reply_to_uuid`, which is an email `id`; list emails first and let the user choose.
- Treat lead creation or movement as campaign enrollment, not immediate delivery confirmation. Sending depends on campaign status, schedule, sender accounts, duplicate checks, background job completion, and plan limits.
- Do not print or log the API key. If the user shares a key in chat, advise them to rotate it.

### Use `klaviyo-send-email`

Route here when the user wants:

- to manage Klaviyo marketing campaigns through the Klaviyo Campaign API
- to list, get, create, update, delete, or clone Klaviyo campaigns
- to send/schedule campaigns, check send status, or cancel scheduled sends
- to assign email templates to campaign messages
- to list, get, or update campaign messages
- to refresh or get recipient estimations for campaigns
- to create, get, or update campaign audiences
- to send email through Klaviyo campaign workflows

Required input:

- for campaign listing: `--filter` (channel filter)
- for campaign get/update/delete/clone/send/refresh-estimation/get-estimation/list-messages: campaign ID
- for campaign create: `--name`, `--audience-json`, `--message-json`
- for campaign clone: `--campaign-id`, `--name`
- for assign-template: `--message-id`, `--template-id`
- for send-status/cancel: send job ID
- for get-message/update-message: message ID
- for get-estimation-job: estimation job ID
- for audience operations: audience ID or campaign ID plus definition JSON

Optional input:

- `--limit`, `--sort` for listing
- `--send` for write actions (dry-run by default)
- output file path
- one-time API key override

Important behavior:

- Use `KLAVIVO_API_KEY`, not `FREVANA_TOKEN`, `INSTANTLY_API_KEY`, or `SENDGRID_API_KEY`.
- API key lookup order is `--api-key`, then `KLAVIVO_API_KEY`, then the locally saved key at `~/.config/klaviyo-send-email/api_key`.
- If no API key is available, the script prompts once in interactive runs and saves the key locally for future runs. In non-interactive runs, tell the user to create a Klaviyo API key by following `https://developers.klaviyo.com/en/docs/getting-started#quick-start-guide`.
- Use `--api-key <key> --save-api-key` or `--configure-api-key` to update the saved key. Use `--clear-api-key` to remove it.
- Prefer `scripts/campaign.sh` and `scripts/audience.sh` over ad hoc `curl`.
- Write actions dry-run by default and require `--send`; read actions call the API immediately.
- The Klaviyo API uses `Klaviyo-API-Key` in the `Authorization` header (not `Bearer`).
- Audience endpoints are in beta and require the `2026-04-15.pre` revision header. All campaign endpoints use stable `2026-04-15`.
- For campaign creation, collect required fields together before calling the script: `name`, `audience-json` (included/excluded segment IDs), and `message-json` (subject, from_email, from_label).
- For sending a campaign, the flow is: (1) `create` campaign with message, (2) `list-messages` to get message ID, (3) `assign-template` to add email template content, (4) optionally `refresh-estimation`, (5) `send` to schedule. Use `send-status` to check the async send job.
- For campaign clone (needed after a cancelled send): `clone --campaign-id C --name NEWNAME --send`.
- Do not invent campaign IDs, audience IDs, segment IDs, API keys, template IDs, or message IDs.
- Treat campaign creation as campaign setup, not immediate delivery confirmation. Sending depends on campaign status and send strategy.
- Do not print or log the API key. If the user shares a key in chat, advise them to rotate it.

### Use `x-topic-search`

Route here when the user wants:

- X/Twitter search results by topic, keyword, hashtag, query, or trend
- recent/live X posts for a topic
- top X posts for a topic
- paginated X topic search using a cursor
- to call the local Frevana `frevana_x_search_topic` tool

Required input:

- `topic`

Optional input:

- `sort`
- `count`
- `fetchMode` (defaults to `quick`)
- `cursor`
- `includeReplies`
- `includeQuotes`
- `includeMedia`
- `maxScrollRounds`
- `minCount`
- `timeout`
- output file path

The user can provide only `topic`. Default `fetchMode` to `quick` when the user does not provide it. Do not invent optional sort, count, cursor, reply, quote, media, scroll, minimum-count, or timeout fields when the user did not provide them.
This is a Chrome Extension skill. It uses the local Frevana daemon and Chrome Extension login state. The user must be logged in to X/Twitter in Chrome.

### Use `url-scrape`

Route here when the user wants:

- to scrape any URL or web page
- web page content as Markdown or text
- Chrome Extension-authenticated page scraping using the user's logged-in Chrome Extension session
- to call the local Frevana `frevana_scrape` tool

Required input:

- `url`

Optional input:

- `provider` (defaults to `url`)
- `timeout`
- output file path

The user can provide only `url`. Default `provider` to `url` when the user does not provide it. Do not invent timeout values.
This is a Chrome Extension skill. It uses the local Frevana daemon and Chrome Extension login state. If a scrape returns login/auth content, tell the user to log in to that site in Chrome.

### Use `google-search-extension`

Route here when the user wants to search Google through Frevana using the Chrome Extension/local daemon session, rather than using the HTTP API `google-search` skill.

Required input:

- one or more `prompt` or query values, or `prompt_file`

Optional input:

- `timeout`
- `format` (`text` or `json`, defaults to `text`)
- output file path

Always use provider `google`. Do not route browser-session Google Search requests through the HTTP API `google-search` skill.

### Use `chatgpt-ask`

Route here when the user wants to ask ChatGPT a question through Frevana using Chrome Extension login state.

Required input:

- one or more `prompt` values, or `prompt_file`

Optional input:

- `timeout`
- `format` (`text` or `json`, defaults to `text`)
- output file path

Always use provider `chatgpt`. Do not route ChatGPT requests through the generic old Frevana skill.

### Use `gemini-ask`

Route here when the user wants to ask Gemini a question through Frevana using Chrome Extension login state.

Required input:

- one or more `prompt` values, or `prompt_file`

Optional input:

- `timeout`
- `format` (`text` or `json`, defaults to `text`)
- output file path

Always use provider `gemini`. Do not route Gemini requests through the generic old Frevana skill.

### Use `perplexity-ask`

Route here when the user wants to ask Perplexity a question through Frevana using Chrome Extension login state.

Required input:

- one or more `prompt` values, or `prompt_file`

Optional input:

- `timeout`
- `format` (`text` or `json`, defaults to `text`)
- output file path

Always use provider `perplexity`. Do not route Perplexity requests through the generic old Frevana skill.

### Use `deepseek-ask`

Route here when the user wants to ask DeepSeek a question through Frevana using Chrome Extension login state.

Required input:

- one or more `prompt` values, or `prompt_file`

Optional input:

- `timeout`
- `format` (`text` or `json`, defaults to `text`)
- output file path

Always use provider `deepseek`. Do not route DeepSeek requests through the generic old Frevana skill.

### Use `doubao-ask`

Route here when the user wants to ask Doubao a question through Frevana using Chrome Extension login state.

Required input:

- one or more `prompt` values, or `prompt_file`

Optional input:

- `timeout`
- `format` (`text` or `json`, defaults to `text`)
- output file path

Always use provider `doubao`. Do not route Doubao requests through the generic old Frevana skill.

### Use `amazon-rufus-ai`

Route here when the user wants to ask Amazon Rufus AI a question about a specific product through the Chrome Extension/local daemon session.

Required input:

- full Amazon product page `url`
- `question`

Optional input:

- `timeout`
- `format` (`text` or `json`, defaults to `text`)
- output file path

The URL must contain `/dp/<ASIN>` or `/gp/product/<ASIN>`. Do not accept Amazon search pages, category pages, home pages, or bare product names. Always use provider `amazon-rufus`.

### Use `amazon-product-info`

Route here when the user wants product page details through the Chrome Extension/local daemon session and provides a full Amazon product URL.

Required input:

- full Amazon product page `url`

Optional input:

- `timeout`
- `format` (`text` or `json`, defaults to `text`)
- output file path

Use this for Chrome Extension product page extraction. Use the existing `amazon-product` skill instead when the user wants the Frevana HTTP API ASIN lookup.

### Use `amazon-top-reviews`

Route here when the user wants top helpful Amazon reviews for a product through the Chrome Extension/local daemon session.

Required input:

- full Amazon product page `url`

Optional input:

- `max_reviews`
- `sort_by`
- `reviewer_type`
- `filter_by_star`
- `timeout`
- `format` (`text` or `json`, defaults to `text`)
- output file path

The URL must be a product page. Do not search Amazon to find a product URL. Optional review settings are appended as the JSON config expected by provider `amazon-product-reviews`.

### Use `amazon-price`

Route here when the user wants price, discount, or coupon info from an Amazon product page through the Chrome Extension/local daemon session.

Required input:

- full Amazon product page `url`

Optional input:

- `timeout`
- `format` (`text` or `json`, defaults to `text`)
- output file path

Always use provider `amazon-price`.

### Use `amazon-rufus-qa`

Route here when the user wants suggested Q&A pairs from the Amazon Rufus widget through the Chrome Extension/local daemon session.

Required input:

- full Amazon product page `url`

Optional input:

- `timeout`
- `format` (`text` or `json`, defaults to `text`)
- output file path

Always use provider `amazon-rufus-qa`.

### Use `publish-twitter-post`

Route here only when the user explicitly asks to publish a post to Twitter/X through Frevana using Chrome Extension login state.

Required input:

- final `text` or `text_file`

Optional input:

- `timeout`
- `format` (`text` or `json`, defaults to `text`)
- output file path

Publishing is a side effect. Do not route draft-writing, editing, or review requests here unless the user explicitly asks to publish the final post. Always use provider `twitter`.

### Use `publish-facebook-post`

Route here only when the user explicitly asks to publish a post to Facebook through Frevana using Chrome Extension login state.

Required input:

- final `text` or `text_file`

Optional input:

- `timeout`
- `format` (`text` or `json`, defaults to `text`)
- output file path

Publishing is a side effect. Do not route draft-writing, editing, or review requests here unless the user explicitly asks to publish the final post. Always use provider `facebook`.

### Use `publish-linkedin-post`

Route here only when the user explicitly asks to publish a LinkedIn post or article through Frevana using Chrome Extension login state.

Required input:

- final `text` or `text_file`

Optional input:

- `mode` (`post` or `article`, defaults to `post`)
- `title` for article mode
- `cover_image` for article mode
- `timeout`
- `format` (`text` or `json`, defaults to `text`)
- output file path

Publishing is a side effect. Do not route draft-writing, editing, or review requests here unless the user explicitly asks to publish the final post or article. Always use provider `linkedin`.

### Use `gpt-image-2`

Route here when the user wants:

- Frevana-hosted image generation
- the `gpt-image-2` model specifically
- image-to-image runs that use one or more local reference images
- image-to-image runs that use one or more remote reference image URLs
- image-to-image runs that use a local directory of images
- raw JSON output from the Frevana image API

Required input:

- `prompt` or `contents`

Optional input:

- `n`
- `size`
- `quality`
- `background`
- `output_format`
- `output_compression`
- reference image path(s)
- reference image URL(s)
- reference image directory path(s)
- mask path
- output file path

Fixed Frevana routing contract:

- use the `gpt-image-2` skill script

Do not pass or ask for alternate image routing values.

### Use `nano-banana-2`

Route here when the user wants:

- `Nano Banana 2`
- `nano banana 2`
- Frevana-hosted image generation with Nano Banana 2

Required input:

- `prompt` or `contents`

Optional input:

- `seed`
- `max-output-tokens`
- `response-modality`
- `aspect-ratio`
- `image-size` (`1K`, `2K`, `4K`; numeric values like `1800` and `WxH` values like `1024x1024` are normalized to the nearest tier, using the larger edge for `WxH`; defaults to `1K`)
- output file path

Fixed Frevana routing contract:

- use the `nano-banana-2` skill script

### Use `nano-banana-pro`

Route here when the user wants:

- `Nano Banana Pro`
- `nano banana pro`
- Frevana-hosted image generation with Nano Banana Pro

Required input:

- `prompt` or `contents`

Optional input:

- `seed`
- `max-output-tokens`
- `response-modality`
- `aspect-ratio`
- `image-size` (`1K`, `2K`, `4K`; numeric values like `1800` and `WxH` values like `1024x1024` are normalized to the nearest tier, using the larger edge for `WxH`; defaults to `1K`)
- output file path

Fixed Frevana routing contract:

- use the `nano-banana-pro` skill script

### Use `frevana-gen-report`

Route here when the user wants:

- final HTML generated from a Frevana template
- server-side rendering through the Frevana report endpoint
- raw final HTML without post-processing

Required input:

- exactly one of `content` or `content_file`

Optional input:

- `template_id` (defaults to `mckinsey-style-report-2` when omitted)
- output HTML path
- one-time token override

Do not modify the returned HTML unless the user explicitly asks for edits after generation.

## Ambiguity Handling

Use these rules to avoid bad assumptions:

- If the user wants Frevana CLI login and does not provide a server URL, use `https://api.frevana.com`.
- If the user says "search Amazon for this" but does not provide a keyword, ask for the keyword.
- If the user wants Amazon product details but does not provide an ASIN, ask for the ASIN.
- If the user says "search eBay for this" but does not provide a keyword or category ID, ask for the keyword or category ID.
- If the user says "search Home Depot for this" but does not provide a keyword, ask for the keyword.
- If the user says "search Walmart for this" but does not provide a keyword, ask for the keyword.
- If the user asks for Walmart product reviews without `product_id` or a clear Walmart `us_item_id`, suggest running `walmart-search` first to obtain one.
- If the user asks for Walmart product sellers without `product_id` or a clear Walmart `us_item_id`, suggest running `walmart-search` first to obtain one.
- If the user says "search Google for this" or wants regular Google Search results but does not provide a keyword, ask for the keyword.
- If the user says "search Google Forums for this" or wants forum-style Google results but does not provide a keyword, ask for the keyword.
- If the user says "search Google Patents for this" or wants patent results but does not provide a keyword, ask for the keyword.
- If the user says "search Google Shopping for this" but does not provide a keyword, ask for the keyword.
- If the user says "search Google Shopping Light for this" but does not provide a keyword, ask for the keyword.
- If the user says "search YouTube for this" but does not provide a keyword, ask for the keyword.
- If the user says "search X for this", "search Twitter for this", or wants X/Twitter topic search but does not provide a topic, ask for the topic.
- If the user says "scrape this", "scrape URL", or wants URL scraping but does not provide a URL, ask for the URL.
- If the user asks ChatGPT, Gemini, Perplexity, DeepSeek, or Doubao a question without providing a prompt/question, ask for the prompt.
- If the user asks for Google Ads Transparency Center search without `advertiser_id`, `text`, or `next_page_token`, ask for one of those inputs.
- If the user asks for Google Immersive Product details without a `page_token`, suggest running `google-shopping-search` first to obtain `immersive_product_page_token`, then continue with this skill using that token.
- If the user says "search Google Trends for this" but does not provide a keyword, ask for the keyword.
- If the user asks for Google Related Questions or People Also Ask expansion without a `next_page_token`, suggest running the regular Google Search skill first to obtain `related_questions[].next_page_token`, then continue with this skill using that token.
- If the user says only `nano banana` without specifying `2` or `pro`, ask which variant they want.
- If the user asks for Frevana report generation without `template_id`, use the default `mckinsey-style-report-2`.
- If the user asks to send SendGrid email without sender, recipient, or content details, ask for the missing fields before execution.
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

### Amazon, eBay, Home Depot, Walmart, Google Ads Transparency Center, Google Search, Google Forums, Google Patents, Google News, Google Related Questions, Google Trends, Google Shopping, Google Shopping Light, Google Immersive Product, and YouTube Search skills

For `amazon-search`, `amazon-product`, `amazon-keyword-search-volume`, `ebay-search`, `home-depot-search`, `walmart-search`, `walmart-product-reviews`, `walmart-product-sellers`, `google-ads-transparency-center`, `google-search`, `google-forums-search`, `google-patents-search`, `google-news-search`, `google-related-questions`, `google-trends`, `google-shopping-search`, `google-shopping-light-search`, `google-immersive-product`, and `youtube-search`:

1. Extract the user inputs.
2. Prefer the repo script over ad hoc `curl`.
3. Let the script use `FREVANA_TOKEN` from the environment first.
4. In non-interactive agent runs, fail fast if the token is missing.
5. Return either the raw JSON payload or a summary, depending on what the user asked for.
6. For `ebay-search`, `home-depot-search`, `walmart-search`, `walmart-product-reviews`, `walmart-product-sellers`, `google-ads-transparency-center`, `google-search`, `google-forums-search`, `google-patents-search`, `google-trends`, `google-shopping-search`, `google-shopping-light-search`, and `google-immersive-product`, rely on the default saved JSON file or pass `--output` only to choose a specific path. Do not call the script twice just to save and summarize results.
7. For the other skills, save output with `--output` when a file is useful.

### SendGrid email sending

For `sendgrid-send-email`:

1. Extract sender, recipients, subject, content, and any optional SendGrid fields. The sender should be a verified sender in the user's Twilio SendGrid account.
2. Prefer `scripts/send_email.sh` over ad hoc `curl`.
3. Run a dry run first unless the user has already explicitly approved the exact final send.
4. Before using `--send`, confirm the final recipients, subject, content, sender, and whether sandbox mode is enabled.
5. Let the script use `--api-key`, `SENDGRID_API_KEY`, or the locally saved key.
6. In non-interactive agent runs, fail fast if the API key is missing from all supported sources, and point the user to `https://frevana.gitbook.io/frevana-docs/email-integrations/sendgrid-integration`.
7. Report SendGrid HTTP status, queued/sandbox status, business ID, `x-message-id`, and a concise prompt example for querying status when available.
8. Do not present `202 Accepted` as delivery confirmation.

For SendGrid status lookup:

1. Extract `to_email`, `sent_at`, and `message_id`; include `subject` only when available.
2. Prefer `scripts/query_email_logs.sh`.
3. Let the script use `--api-key`, `SENDGRID_API_KEY`, or the locally saved key.
4. In non-interactive agent runs, fail fast if the API key is missing from all supported sources, and point the user to `https://frevana.gitbook.io/frevana-docs/email-integrations/sendgrid-integration`.
5. Return matching Email Logs JSON or summarize `messages[].status`, `to_email`, `from_email`, `subject`, `reason`, and `sg_message_id`.
6. Do not query by `custom_args.business_id`; use `--to`, `--sent-at`, and `--message-id` to narrow by recipient/time and fuzzy-match returned `sg_message_id`. Add `--subject` when available, except for template sends. Email Logs can append suffixes such as `.recvd-...` to `sg_message_id`, so treat the user-provided message ID as a prefix/substring match, not only an exact match.
7. `--sent-at` is only a lower bound, but the script subtracts a 5-second default lookback before building `sg_message_id_created_at >= ...` to absorb SendGrid response/log timestamp skew. Do not use a time-window parameter.
8. If Email Logs returns no data or no fuzzy `sg_message_id` match, ask the user to review `https://app.sendgrid.com/email_logs` manually.

### Instantly campaign enrollment and replies

For `instantly-send-email`:

1. Classify the user intent: cold outbound/campaign enrollment, reply to existing email, campaign management, or lead movement/removal.
2. Prefer `scripts/lead.sh`, `scripts/campaign.sh`, and `scripts/email.sh` over ad hoc `curl`.
3. For cold outbound, run `lead.sh list`, then `campaign.sh list` or `campaign.sh create`, then dry-run `lead.sh create` or `lead.sh move`.
4. For replies, run `email.sh list --lead <email>`, ask the user to select the email, then dry-run `email.sh reply`.
5. For moving/removing a lead from a campaign, use `lead.sh move`; the Instantly move API requires a destination campaign or list.
6. Let the script use `--api-key`, `INSTANTLY_API_KEY`, or the locally saved key.
7. In non-interactive agent runs, fail fast if the API key is missing from all supported sources, and tell the user to create an Instantly API V2 key by following `https://developer.instantly.ai/getting-started/getting-started`.
8. Report Instantly HTTP status, response body, and the operational meaning: lead enrollment is not immediate delivery confirmation; reply response represents the created/sent email object; campaign sending status explains blockers and health.
9. Do not use `POST /api/v2/emails/test` for user-requested sending.

### Klaviyo campaign management

For `klaviyo-send-email`:

1. Classify the user intent: campaign listing/inspection, campaign creation, campaign update, or audience management.
2. Prefer `scripts/campaign.sh` and `scripts/audience.sh` over ad hoc `curl`.
3. For campaign listing, run `campaign.sh list --filter 'equals(messages.channel,"email")'` with optional `--sort` and `--limit`.
4. For campaign creation, collect `name`, `audience-json` (included/excluded segment IDs), and `message-json` (subject, from_email, from_label, optional preview_text/reply_to/cc/bcc) together. Dry-run `campaign.sh create` first, then send with `--send` after approval.
5. For campaign updates, use `campaign.sh update --campaign-id <id> --name <name> [--audience-json <json>]` with dry-run before `--send`.
6. For audience management, use `audience.sh get/create/update` as appropriate. Audience endpoints use beta revision `2026-04-15.pre`.
7. Let the script use `--api-key`, `KLAVIVO_API_KEY`, or the locally saved key.
8. In non-interactive agent runs, fail fast if the API key is missing from all supported sources, and tell the user to create a Klaviyo API key by following `https://developers.klaviyo.com/en/docs/getting-started#quick-start-guide`.
9. Report Klaviyo HTTP status and the campaign/audience resource details. Campaign creation is campaign setup, not delivery confirmation.

### X/Twitter Chrome Extension topic search

For `x-topic-search`:

1. Extract `topic` and any user-provided optional fields.
2. Prefer `scripts/search_x_topics.sh` over ad hoc `frevana call`.
3. Use the local Frevana daemon and Chrome Extension session.
4. Let `scripts/search_x_topics.sh` run bundled `scripts/setup.sh` before every Frevana tool call, matching the original Frevana skill flow.
   `scripts/setup.sh` downloads and executes the latest official setup script from `https://raw.githubusercontent.com/FinpeakInc/frevana-cli-releases/refs/heads/main/skills/frevana/scripts/setup.sh`.
5. If setup reports Chrome disconnected, stop and tell the user to open Chrome, connect the Frevana extension, and retry.
6. If the daemon health check still fails after setup, report that setup already ran but the daemon is not healthy.
7. If X returns auth/login content or the call fails because X is unavailable, tell the user to log in to X/Twitter in Chrome.
8. Return either the raw tool output or a summary, depending on what the user asked for.
9. Save output with `--output` when a file is useful.

### URL scrape through Chrome Extension

For `url-scrape`:

1. Extract `url` and any user-provided optional fields.
2. Require an absolute URL starting with `http://` or `https://`.
3. Prefer `scripts/scrape_url.sh` over ad hoc `frevana call`.
4. Use the local Frevana daemon and Chrome Extension session.
5. Let `scripts/scrape_url.sh` run bundled `scripts/setup.sh` before every Frevana tool call, matching the original Frevana skill flow.
   `scripts/setup.sh` downloads and executes the latest official setup script from `https://raw.githubusercontent.com/FinpeakInc/frevana-cli-releases/refs/heads/main/skills/frevana/scripts/setup.sh`.
6. If setup reports Chrome disconnected, stop and tell the user to open Chrome, connect the Frevana extension, and retry.
7. If the daemon health check still fails after setup, report that setup already ran but the daemon is not healthy.
8. If scrape returns empty or login/auth content, tell the user to log in to that site in Chrome.
9. Return either the raw scrape output or a summary, depending on what the user asked for.
10. Save output with `--output` when a file is useful.

### AI platform asks through Chrome Extension

For `google-search-extension`, `chatgpt-ask`, `gemini-ask`, `perplexity-ask`, `deepseek-ask`, and `doubao-ask`:

1. Extract one or more prompts and any user-provided optional timeout/output format. Accept repeated `--prompt`/`--question` values or `--prompt-file` with one prompt per non-empty line.
2. Use the matching fixed-provider script: `search_google_extension.sh`, `ask_chatgpt.sh`, `ask_gemini.sh`, `ask_perplexity.sh`, `ask_deepseek.sh`, or `ask_doubao.sh`.
3. Use the local Frevana daemon and Chrome Extension session.
4. Let the script run bundled `scripts/setup.sh` before every Frevana tool call, matching the original Frevana skill flow.
   `scripts/setup.sh` downloads and executes the latest official setup script from `https://raw.githubusercontent.com/FinpeakInc/frevana-cli-releases/refs/heads/main/skills/frevana/scripts/setup.sh`.
5. If setup reports Chrome disconnected, stop and tell the user to open Chrome, connect the Frevana extension, and retry.
6. If the daemon health check still fails after setup, report that setup already ran but the daemon is not healthy.
7. If the platform returns login/auth content or the call fails because that platform is unavailable, tell the user to log in to that platform in Chrome.
8. Return text output by default. If the user asks for JSON, pass `--format json` and return structured JSON with `provider`, `count`, and `results`.
9. Save output with `--output` when useful.

### Amazon page research through Chrome Extension

For `amazon-rufus-ai`, `amazon-product-info`, `amazon-top-reviews`, `amazon-price`, and `amazon-rufus-qa`:

1. Extract the full Amazon product page URL and any user-provided optional fields.
2. Require a URL containing `/dp/<ASIN>` or `/gp/product/<ASIN>`. If the user gives only a product name, ASIN, search page, category page, or homepage, ask for the full product page URL.
3. Use the matching fixed-provider script: `ask_amazon_rufus.sh`, `get_amazon_product_info.sh`, `get_amazon_top_reviews.sh`, `get_amazon_price.sh`, or `get_amazon_rufus_qa.sh`.
4. Use the local Frevana daemon and Chrome Extension session.
5. Let the script run bundled `scripts/setup.sh` before every Frevana tool call, matching the original Frevana skill flow.
   `scripts/setup.sh` downloads and executes the latest official setup script from `https://raw.githubusercontent.com/FinpeakInc/frevana-cli-releases/refs/heads/main/skills/frevana/scripts/setup.sh`.
6. If setup reports Chrome disconnected, stop and tell the user to open Chrome, connect the Frevana extension, and retry.
7. If the daemon health check still fails after setup, report that setup already ran but the daemon is not healthy.
8. If Amazon returns login/auth content or the call fails because Amazon is unavailable, tell the user to log in to Amazon in Chrome.
9. Amazon calls are slow. If a call errors or times out, report the error and do not immediately retry in the same turn.
10. Return text output by default. If the user asks for JSON, pass `--format json` and return structured JSON with `provider`, `prompt`, and `answer`.
11. Save output with `--output` when useful.

### Social publishing through Chrome Extension

For `publish-twitter-post`, `publish-facebook-post`, and `publish-linkedin-post`:

1. Confirm the user explicitly asked to publish, not just draft or edit.
2. Extract final post `text` or `text_file`, and any LinkedIn article fields.
3. Use the matching fixed-provider script: `publish_twitter_post.sh`, `publish_facebook_post.sh`, or `publish_linkedin_post.sh`.
4. Use the local Frevana daemon and Chrome Extension session.
5. Let the script run bundled `scripts/setup.sh` before every Frevana tool call, matching the original Frevana skill flow.
   `scripts/setup.sh` downloads and executes the latest official setup script from `https://raw.githubusercontent.com/FinpeakInc/frevana-cli-releases/refs/heads/main/skills/frevana/scripts/setup.sh`.
6. If setup reports Chrome disconnected, stop and tell the user to open Chrome, connect the Frevana extension, and retry.
7. If publishing fails because the platform is unavailable or not logged in, tell the user to log in to that platform in Chrome.
8. Return text output by default. If the user asks for JSON, pass `--format json`.
9. Save output with `--output` when useful.

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

1. Confirm exactly one content source.
2. Prefer `scripts/generate_report.sh` over manual API calls.
3. If the user does not provide `template_id`, let the script default to `mckinsey-style-report-2`.
4. Let the script use `FREVANA_TOKEN` from the environment first.
5. In non-interactive agent runs, fail fast if the token is missing.
6. Extract the response JSON `content` field and treat it as the final HTML.
7. Return that HTML unchanged unless the user asks for a later transformation.

## Dependency Rules

### Frevana auth bootstrap

Needed:

- `bash`
- `frevana` or `npm`
- browser access or a manual way to open the authorization URL

Attempt `frevana login` first. If the command is unavailable, attempt `npm i -g @frevana/frevana`. If that package is unavailable in the current registry, stop and ask for the correct source instead of guessing.

### Amazon, eBay, Home Depot, Walmart, Google Ads Transparency Center, Google Search, Google Forums, Google Patents, Google News, Google Related Questions, Google Trends, Google Shopping, Google Shopping Light, Google Immersive Product, and YouTube Search workflows

Needed:

- `bash`
- `curl`
- `python3`
- `FREVANA_TOKEN`

### Chrome Extension workflows

Needed:

- `bash`
- `curl`
- `python3`
- bundled `scripts/setup.sh`, which downloads and executes the latest official Frevana setup script
- `frevana` local binary, or network access to GitHub Releases when setup needs to install it
- Frevana local daemon
- Chrome connected through the Frevana Chrome Extension
- active login in the target site/platform in Chrome when the skill needs authenticated browser state

### Frevana image and report workflows

Needed:

- `bash`
- `curl`
- `python3` for image scripts
- `FREVANA_TOKEN`

For token-backed workflows, if `FREVANA_TOKEN` is missing in a non-interactive run, stop and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly when the script supports it.

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

### eBay outputs

- The endpoint script returns validated JSON to stdout and saves the same JSON to a file on every successful run.
- Summarize the results by default.
- Highlight listing title, product ID, price, condition, shipping, seller, link, and follow-up pagination when available.
- Preserve the raw JSON when the user asks for it.

### Home Depot outputs

- The endpoint script returns validated JSON to stdout and saves the same JSON to a file on every successful run.
- Summarize the results by default.
- Highlight product title, product ID, brand, price, rating, reviews, delivery, pickup, link, and follow-up pagination when available.
- Preserve the raw JSON when the user asks for it.

### Walmart outputs

- The endpoint script returns validated JSON to stdout and saves the same JSON to a file on every successful run.
- Summarize the results by default.
- Highlight product title, item ID, product ID, price, currency, rating, reviews, seller, shipping signals, link, thumbnail, and follow-up pagination when available.
- Preserve the raw JSON when the user asks for it.

### Walmart product reviews outputs

- The endpoint script returns validated JSON to stdout and saves the same JSON to a file on every successful run.
- Summarize the results by default.
- Highlight product name, overall rating, total review count, rating counts, top positive and negative reviews, review title, text, rating, date, reviewer, customer type, feedback counts, and follow-up pagination when available.
- Preserve the raw JSON when the user asks for it.

### Walmart product sellers outputs

- The endpoint script returns validated JSON to stdout and saves the same JSON to a file on every successful run.
- Summarize the results by default.
- Highlight product name, shipping destination, seller name, seller type, availability, offer type, price, delivery date, delivery price, return policy, seller store-front URL, and store-specific context when available.
- Preserve the raw JSON when the user asks for it.

### Google Search outputs

- The endpoint script returns validated JSON to stdout and saves the same JSON to a file on every successful run.
- Summarize the results by default.
- Highlight organic result title, source/domain, link, snippet, answer box, knowledge graph, related questions, related searches, and follow-up pagination when available.
- Preserve the raw JSON when the user asks for it.

### Google Forums outputs

- The endpoint script returns validated JSON to stdout and saves the same JSON to a file on every successful run.
- Summarize the results by default.
- Highlight forum result title, source/community, link, snippet, displayed metadata, sitelinks, answer/comment counts, dates, related searches, and follow-up pagination when available.
- Preserve the raw JSON when the user asks for it.

### Google Patents outputs

- The endpoint script returns validated JSON to stdout and saves the same JSON to a file on every successful run.
- Summarize the results by default.
- Highlight patent title, publication number, assignee, inventor, priority date, filing date, publication date, grant date, snippet, link, and follow-up pagination when available.
- Preserve the raw JSON when the user asks for it.

### Google News outputs

- The endpoint script returns validated JSON to stdout.
- Summarize the results by default.
- Highlight headline/title, source, publication time, URL, and snippet when available.
- Preserve the raw JSON when the user asks for it.

### Google Ads Transparency Center outputs

- The endpoint script returns validated JSON to stdout and saves the same JSON to a file on every successful run.
- Summarize the results by default.
- Highlight advertiser, advertiser ID, ad creative ID, format, target domain, first shown, last shown, creative media link, details link, and follow-up `pagination.next_page_token` when available.
- Preserve the raw JSON when the user asks for it.

### Google Related Questions outputs

- The endpoint script returns validated JSON to stdout.
- Summarize the results by default.
- Highlight question, answer snippet, source title, link, and follow-up `next_page_token` when available.
- Preserve the raw JSON when the user asks for it.

### Google Trends outputs

- The endpoint script returns validated JSON to stdout and saves the same JSON to a file on every successful run.
- Summarize the results by default.
- Highlight interest over time, compared keywords, regional interest, related topics, and related queries when available.
- Preserve the raw JSON when the user asks for it.

### Google Shopping and Google Shopping Light outputs

- The endpoint script returns validated JSON to stdout and saves the same JSON to a file on every successful run.
- Summarize the results by default.
- Highlight product title, price, rating, source merchant, product link, and thumbnail when available.
- Preserve the raw JSON when the user asks for it.

### Google Immersive Product outputs

- The endpoint script returns validated JSON to stdout and saves the same JSON to a file on every successful run.
- Summarize the results by default.
- Highlight product title, brand, rating, review count, price range, store offers, top insights, and follow-up `stores_next_page_token` when available.
- Preserve the raw JSON when the user asks for it.

### YouTube Search outputs

- The endpoint script returns validated JSON to stdout.
- Summarize the results by default.
- Highlight video title, channel, published time, views, duration, URL, thumbnail, and follow-up pagination token when available.
- Preserve the raw JSON when the user asks for it.

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
bash skills/ebay-search/scripts/search_ebay.sh
bash skills/home-depot-search/scripts/search_home_depot.sh
bash skills/walmart-search/scripts/search_walmart.sh
bash skills/walmart-product-reviews/scripts/search_walmart_product_reviews.sh
bash skills/walmart-product-sellers/scripts/search_walmart_product_sellers.sh
bash skills/google-search/scripts/search_google.sh
bash skills/google-forums-search/scripts/search_google_forums.sh
bash skills/google-patents-search/scripts/search_google_patents.sh
bash skills/google-news-search/scripts/search_google_news.sh
bash skills/google-ads-transparency-center/scripts/search_google_ads_transparency_center.sh
bash skills/google-related-questions/scripts/search_google_related_questions.sh
bash skills/google-trends/scripts/search_google_trends.sh
bash skills/google-shopping-search/scripts/search_google_shopping.sh
bash skills/google-shopping-light-search/scripts/search_google_shopping_light.sh
bash skills/google-immersive-product/scripts/search_google_immersive_product.sh
bash skills/youtube-search/scripts/search_youtube.sh
bash skills/sendgrid-send-email/scripts/send_email.sh
bash skills/klaviyo-send-email/scripts/campaign.sh
bash skills/klaviyo-send-email/scripts/audience.sh
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

### eBay search

```bash
bash skills/ebay-search/scripts/search_ebay.sh \
  --query "vintage watch"

bash skills/ebay-search/scripts/search_ebay.sh \
  --query "sony headphones" \
  --page 2 \
  --results-per-page 100
```

### Home Depot search

```bash
bash skills/home-depot-search/scripts/search_home_depot.sh \
  --q "patio chairs"

bash skills/home-depot-search/scripts/search_home_depot.sh \
  --q "cordless drill" \
  --country us \
  --delivery-zip 10001 \
  --page 2 \
  --page-size 40
```

### Walmart search

```bash
bash skills/walmart-search/scripts/search_walmart.sh \
  --query "coffee maker"

bash skills/walmart-search/scripts/search_walmart.sh \
  --query "wireless earbuds" \
  --device mobile \
  --sort price_low \
  --min-price 25 \
  --max-price 100 \
  --page 2
```

### Walmart product reviews

```bash
bash skills/walmart-product-reviews/scripts/search_walmart_product_reviews.sh \
  --product-id 5689919121

bash skills/walmart-product-reviews/scripts/search_walmart_product_reviews.sh \
  --product-id 5689919121 \
  --rating 5 \
  --sort submission-desc \
  --page 2
```

### Walmart product sellers

```bash
bash skills/walmart-product-sellers/scripts/search_walmart_product_sellers.sh \
  --product-id 10543894

bash skills/walmart-product-sellers/scripts/search_walmart_product_sellers.sh \
  --product-id 10543894 \
  --store-id 5888
```

### Google Search

```bash
bash skills/google-search/scripts/search_google.sh \
  --q "coffee"

bash skills/google-search/scripts/search_google.sh \
  --q "coffee" \
  --location "Austin, Texas, United States" \
  --gl us \
  --hl en \
  --num 20 \
  --start 20 \
  --safe off \
  --device mobile
```

### Google Forums search

```bash
bash skills/google-forums-search/scripts/search_google_forums.sh \
  --q "vibe coding"

bash skills/google-forums-search/scripts/search_google_forums.sh \
  --q "vibe coding" \
  --gl us \
  --hl en \
  --device mobile \
  --start 10 \
  --start-date 20260101 \
  --end-date 20260525
```

### Google Patents search

```bash
bash skills/google-patents-search/scripts/search_google_patents.sh \
  --q "(Coffee)"

bash skills/google-patents-search/scripts/search_google_patents.sh \
  --q "(Coffee)" \
  --status GRANT \
  --language en \
  --page 0 \
  --num 10
```

### Google News search

```bash
bash skills/google-news-search/scripts/search_google_news.sh \
  --q "artificial intelligence"

bash skills/google-news-search/scripts/search_google_news.sh \
  --q "artificial intelligence" \
  --gl US \
  --hl en
```

### Google Ads Transparency Center search

```bash
bash skills/google-ads-transparency-center/scripts/search_google_ads_transparency_center.sh \
  --text "apple.com"

bash skills/google-ads-transparency-center/scripts/search_google_ads_transparency_center.sh \
  --advertiser-id "AR17828074650563772417" \
  --region 2840 \
  --platform YOUTUBE

bash skills/google-ads-transparency-center/scripts/search_google_ads_transparency_center.sh \
  --text "apple.com" \
  --next-page-token "CgoAP7zn5TAzVgIz..."
```

### Google Related Questions

```bash
bash skills/google-related-questions/scripts/search_google_related_questions.sh \
  --next-page-token "eyJvbnMiOiIxMDA0MSI..."

bash skills/google-related-questions/scripts/search_google_related_questions.sh \
  --next-page-token "eyJvbnMiOiIxMDA0MSI..." \
  --output ./out/google-related-questions-result.json
```

### Google Immersive Product

```bash
bash skills/google-immersive-product/scripts/search_google_immersive_product.sh \
  --page-token "eyJlaSI6Im5ZVmxaOX..."

bash skills/google-immersive-product/scripts/search_google_immersive_product.sh \
  --page-token "eyJlaSI6Im5ZVmxaOX..." \
  --next-page-token "f69uOnica15aklmSk3pT0..." \
  --output ./out/google-immersive-product-result.json
```

### Google Trends

```bash
bash skills/google-trends/scripts/search_google_trends.sh \
  --q "home treadmill"

bash skills/google-trends/scripts/search_google_trends.sh \
  --q "home treadmill" \
  --geo US \
  --date "today 12-m" \
  --hl en \
  --tz 420
```

### Google Shopping search

```bash
bash skills/google-shopping-search/scripts/search_google_shopping.sh \
  --q "wireless earbuds"

bash skills/google-shopping-search/scripts/search_google_shopping.sh \
  --q "wireless earbuds" \
  --gl US \
  --hl en \
  --device mobile \
  --sort-by 1
```

### Google Shopping Light search

```bash
bash skills/google-shopping-light-search/scripts/search_google_shopping_light.sh \
  --q "wireless earbuds"

bash skills/google-shopping-light-search/scripts/search_google_shopping_light.sh \
  --q "wireless earbuds" \
  --gl US \
  --hl en \
  --device mobile
```

### YouTube search

```bash
bash skills/youtube-search/scripts/search_youtube.sh \
  --search-query "mrbeast"

bash skills/youtube-search/scripts/search_youtube.sh \
  --search-query "mrbeast" \
  --sp "EgIQAQ%253D%253D" \
  --hl en \
  --gl us
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

bash skills/gpt-image-2/scripts/generate_image.sh \
  --prompt "Turn these product references into one polished hero shot" \
  --image ./refs/front.png \
  --image-url "https://example.com/reference/detail.png" \
  --image-dir ./refs/detail-shots \
  --mask ./refs/mask.png \
  --size 1024x1024 \
  --output ./out/gpt-image-2-edit-result.json
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
  --output ./out/frevana-report.html
```

## Final Behavior Checklist

Before acting, the agent should verify:

- Is the user intent mapped to the correct skill?
- Are all required inputs present?
- Is there a repo script that should be used instead of a custom command?
- If this is an auth request, does `frevana` need to be installed before login starts?
- Is the Frevana routing fixed for this skill?
- Should the result be summarized, or does the user want raw output?
- Is there any missing dependency or login step that should be surfaced clearly?
