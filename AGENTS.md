# AGENTS.md

This file tells a general-purpose coding agent how to use the skills in this repository correctly.

Treat this document as the operational guide for the repo. Treat each skill's `SKILL.md` as the source of truth for that skill. If this file and a specific `SKILL.md` ever conflict, follow the `SKILL.md`.

## Repository Purpose

This repository contains reusable skills for four main workflow families:

- Frevana CLI auth bootstrap and local API key setup
- Amazon, eBay, Home Depot, and Walmart data lookups through Frevana-backed HTTP APIs
- Google Ads Transparency Center, Google Search, Google Forums, Google Patents, Google News, Google Related Questions, Google Shopping, Google Shopping Light, Google Immersive Product, Google Trends, and YouTube Search lookups through Frevana-backed HTTP APIs
- Chrome Extension local Frevana workflows, including URL scraping, AI platform asks, Amazon page research, social publishing, and X/Twitter topic search
- Frevana AI Factory API workflows for image generation and HTML generation

The repository is not a general application. It is a collection of agent instructions plus a small set of helper scripts.

## Chrome Extension Skill Group

The following skills are Chrome Extension skills:

- `url-scrape`
- `google-search-extension`
- `chatgpt-ask`, `gemini-ask`, `perplexity-ask`, `deepseek-ask`, and `doubao-ask`
- `x-topic-search`
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
