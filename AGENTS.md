# AGENTS.md

This file tells a general-purpose coding agent how to use the skills in this repository correctly.

Treat this document as the operational guide for the repo. Treat each skill's `SKILL.md` as the source of truth for that skill. If this file and a specific `SKILL.md` ever conflict, follow the `SKILL.md`.

## Repository Purpose

This repository contains reusable skills for four main workflow families:

- Frevana CLI auth bootstrap and local API key setup
- Frevana custom-domain publishing for local agent-generated files
- Lark/Feishu CLI installation, app configuration, OAuth login, auth verification, and shared operating rules for Lark skills
- Amazon, eBay, Home Depot, and Walmart data lookups through Frevana-backed HTTP APIs
- Google Ads Transparency Center, Google Ads Search, Google Ads keyword search volume, Google Ads keyword suggestions, Google Ads ad traffic forecasts, Backlinks API lookups, Google Search, Google Forums, Google Patents, Google News, Google Related Questions, Google Events, Google Images, Google AI Mode, Google AI Overview, Google Autocomplete, Google Short Videos, Google Videos, Google Maps Reviews, Google Local Services, Google Shopping, Google Shopping Light, Google Immersive Product, Google Trends, Bing Search, YouTube Search, YouTube Video, YouTube Transcript, Instagram Profile, Facebook Profile, and Reddit Search lookups
- Chrome Extension local Frevana workflows, including URL scraping, AI platform asks, Amazon page research, social publishing, and X/Twitter topic search
- SendGrid Mail Send API workflows for transactional email sending and SendGrid Stats API workflows for global email statistics
- SendGrid Email Logs workflows for per-message activity, opened/clicked checks, and status lookups
- Slack Incoming Webhook workflows for posting Slack messages and notifications
- Telegram Bot API workflows for bot inspection, messaging, updates, webhooks, commands, and chat/message management
- WordPress content workflows through the built-in REST API for posts, pages, media, taxonomies, menus, scheduling, and bulk operations
- Instantly API V2 lead, campaign, and email workflows for campaign enrollment and replies
- Klaviyo Campaign API workflows for campaign and audience management
- Frevana AI Factory API workflows for image generation and HTML generation
- Seedance 2.0 API workflows for text-to-video, image-to-video, reference-to-video, task polling, and result downloads
- MySQL, PostgreSQL, Redis, MongoDB, and SQLite CRUD workflows with saved local profiles; SQLite is local-file only, while the networked database skills can support direct, SSH tunnel, or remote-server access as documented per skill
- Snowflake CLI workflows for connection management, safe SQL execution, object inspection and mutation, and specialized Snowflake workload or application operations

The repository is not a general application. It is a collection of agent instructions plus a small set of helper scripts.

## Chrome Extension Skill Group

The following skills are Chrome Extension skills:

- `url-scrape`
- `google-search-extension`
- `chatgpt-ask`, `gemini-ask`, `perplexity-ask`, `deepseek-ask`, and `doubao-ask`
- `x-topic-search`
- `meta-ads-search`
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
  frevana-publish/
    SKILL.md
    agents/openai.yaml
    scripts/publish_file.sh
    tests/test_publish_file.py
  lark-cli/
    SKILL.md
    scripts/setup_lark_cli.sh
  amazon-search/
    SKILL.md
    scripts/search_amazon.sh
  amazon-product/
    SKILL.md
    scripts/fetch_product.sh
  amazon-keyword-search-volume/
    SKILL.md
    scripts/get_search_volume.sh
  amazon-related-keywords/
    SKILL.md
    agents/openai.yaml
    scripts/search_amazon_related_keywords.sh
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
  google-maps-search/
    SKILL.md
    scripts/search_google_maps.sh
  facebook-profile/
    SKILL.md
    scripts/get_facebook_profile.sh
  google-ads-transparency-center/
    SKILL.md
    scripts/search_google_ads_transparency_center.sh
  google-related-questions/
    SKILL.md
    scripts/search_google_related_questions.sh
  google-events-search/
    SKILL.md
    scripts/search_google_events.sh
  google-images-search/
    SKILL.md
    scripts/search_google_images.sh
  google-ai-mode/
    SKILL.md
    scripts/search_google_ai_mode.sh
  google-ai-overview/
    SKILL.md
    scripts/get_google_ai_overview.sh
  google-ads-search/
    SKILL.md
    scripts/search_google_ads.sh
  google-ads-keywords-search-volume/
    SKILL.md
    scripts/search_google_ads_keywords_search_volume.sh
  google-ads-keywords-for-keywords/
    SKILL.md
    scripts/search_google_ads_keywords_for_keywords.sh
  google-ads-ad-traffic-by-keywords/
    SKILL.md
    scripts/search_google_ads_ad_traffic_by_keywords.sh
  backlinks-*/
    SKILL.md
    scripts/get_backlinks_*.sh
  google-autocomplete/
    SKILL.md
    scripts/search_google_autocomplete.sh
  google-maps-reviews/
    SKILL.md
    scripts/get_google_maps_reviews.sh
  google-local-services-search/
    SKILL.md
    scripts/search_google_local_services.sh
  google-short-videos-search/
    SKILL.md
    scripts/search_google_short_videos.sh
  google-videos-search/
    SKILL.md
    scripts/search_google_videos.sh
  bing-search/
    SKILL.md
    scripts/search_bing.sh
  youtube-video/
    SKILL.md
    scripts/get_youtube_video.sh
  youtube-video-transcript/
    SKILL.md
    scripts/get_youtube_video_transcript.sh
  instagram-profile/
    SKILL.md
    scripts/get_instagram_profile.sh
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
  sendgrid-email-log/
    SKILL.md
    scripts/get_email_log.sh
    scripts/query_email_logs.sh
  sendgrid-global-email-stats/
    SKILL.md
    scripts/retrieve_global_email_stats.sh
  slack-webhook/
    SKILL.md
    scripts/send_slack_webhook.sh
  telegram-bot/
    SKILL.md
    scripts/telegram_bot.sh
  wordpress-content/
    SKILL.md
    agents/openai.yaml
    references/verbatim-publishing.md
    scripts/wordpress_rest.sh
    scripts/wordpress_verbatim.py
    tests/test_wordpress_rest.sh
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
  snowflake/
    SKILL.md
    agents/openai.yaml
    references/official-cli.md
    scripts/snowflake.sh
    tests/test_snowflake.sh
  redis-crud/
    SKILL.md
    agents/openai.yaml
    scripts/redis_crud.sh
  mongodb-crud/
    SKILL.md
    agents/openai.yaml
    scripts/mongodb_crud.sh
  sqlite-crud/
    SKILL.md
    agents/openai.yaml
    scripts/sqlite_crud.sh
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
  meta-ads-search/
    SKILL.md
    scripts/setup.sh
    scripts/search_meta_ads.sh
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
  seedance2/
    SKILL.md
    agents/openai.yaml
    references/api.md
    scripts/seedance.sh
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

### Use `frevana-publish`

Route here when the user wants:

- to publish or host a local file through Frevana
- a public custom-domain URL for an agent-generated app, HTML page, report, image, document, or other artifact
- to upload a local result with Frevana's custom upload URL flow

Required input:

- one local file path

Optional input:

- title
- Agent ID
- team ID
- current session/task ID
- one-time token override
- API base URL override for local testing

Important behavior:

- Check `custom_domain` from `GET /subscriptions/user` before requesting an upload URL.
- If `custom_domain` is empty or null, stop and direct the user to `https://www.frevana.com/dashboard/domain`.
- Prefer `scripts/publish_file.sh` over ad hoc API and object-storage calls.
- Keep `category=agent_app_result`, `scene_type=content_html`, and `publish_type=custom_domain` fixed.
- Try to use the current Agent ID. If none is available, let the script use its fixed `frevana-publish` fallback.
- Try to use the current team ID. If none is available, pass the current conversation/task ID as `--session-id`; omit `team_id` only when neither value is available.
- Derive `file_extension` and `content_type` from the local file. If the user does not provide a title, extract `file_title` from the article content and fall back to the filename stem.
- Pass the user-selected file path directly to the upload command and do not modify that file during publishing.
- Never forward the Frevana bearer token to the pre-signed upload host.
- After the object upload succeeds, use the returned `content_id` to call `PUT /s3/content/{content_id}/publish?op_type=publish` with the resolved title and fixed publish type/category.
- Do not print or return the pre-signed upload URL. Return only the public custom-domain URL unless the user asks for the small JSON result.
- Do not claim success unless both upload and publish return 2xx and a public URL can be resolved.

### Use `lark-cli`

Route here when the user wants:

- to install or upgrade the official Lark/Feishu `lark-cli`
- to check whether `lark-cli` is installed
- to know the local command, npm package, or native binary install location
- to run `lark-cli config init --new --brand lark|feishu`
- to run `lark-cli auth login --recommend`
- to use the correct Lark versus Feishu authorization link
- to extract and relay Lark/Feishu setup or authorization links
- to prepare bot default identity before using Lark skills
- to verify Lark auth before using another Lark skill
- to choose or explain `--as user` versus `--as bot`

Required input:

- none

Optional input:

- `--suite lark|feishu` for product suite / authorization link family during config init; defaults to `feishu` when omitted
- `--lang zh|en` for the installer or config init flow
- exact auth `scope` or auth `domain` when a downstream Lark skill requires it
- `--force-init` when setup must reinitialize app credentials instead of reusing existing config

Important behavior:

- Check first with `scripts/setup_lark_cli.sh check`; do not reinstall on every Lark request.
- Install only when `lark-cli` is missing or the user explicitly asks to upgrade/reinstall.
- Preferred install command is `npx @larksuite/cli@latest install`.
- The install flow globally installs `@larksuite/cli`; on macOS/Linux the command is normally `$(npm prefix -g)/bin/lark-cli`, the npm package is normally `$(npm root -g)/@larksuite/cli`, and the native binary is normally `$(npm root -g)/@larksuite/cli/bin/lark-cli`.
- If the user says Lark, international Lark, larksuite, global, or overseas, run setup/config with `--suite lark`; this reuses an existing Lark config but must not reuse an old Feishu or unknown config.
- If the user says Feishu, 飞书, or 国内飞书, run setup/config with `--suite feishu`; this reuses an existing Feishu config but must not reuse an old Lark or unknown config.
- If the user does not specify Lark versus Feishu, default to Feishu. `scripts/setup_lark_cli.sh config-init` passes `--brand feishu` explicitly; `setup` does the same only when it needs to initialize missing config.
- Default setup is bot-oriented and fast: it checks existing config with `lark-cli config show`, skips `config init --new` when config already exists and either no suite was specified or the existing suite matches the explicit suite, runs `lark-cli config default-as bot`, and does not run user OAuth.
- Use `scripts/setup_lark_cli.sh login` only when the user explicitly needs user OAuth or a downstream skill requires OAuth scopes.
- Do not confuse product suite `--suite lark|feishu` with auth business-domain `--domain calendar|docs|drive|all`.
- `auth login` uses the product suite saved by config init. To change Lark versus Feishu authorization links, rerun config init or setup with the intended `--suite`.
- For agent setup, run `scripts/setup_lark_cli.sh setup`, `scripts/setup_lark_cli.sh setup --suite lark`, or `scripts/setup_lark_cli.sh setup --suite feishu`; never run bare `lark-cli config init --new`.
- If using raw `lark-cli` instead of the wrapper, the init command must include explicit brand: `lark-cli config init --new --brand lark` or `lark-cli config init --new --brand feishu`.
- If a previous setup accidentally created a Feishu profile for a Lark user, rerun `scripts/setup_lark_cli.sh config-init --suite lark` or `scripts/setup_lark_cli.sh setup --suite lark`; plain `setup` keeps using the saved brand.
- If config or login prints a browser URL, relay the exact URL to the user and wait for them to finish the browser step. Do not rely on automatic browser opening.
- Do not print app secrets, OAuth tokens, cookies, or raw local credential files.
- For side-effect Lark commands, prefer `--dry-run` first when the command supports it.
- If the user asks to send a Lark message, use this skill only for setup/auth, then use `lark-im` for message sending.
- If the user provides only a person name or email for messaging, use a contact lookup skill before sending.

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

### Use `amazon-related-keywords`

Route here when the user wants:

- related Amazon keywords from one seed keyword
- Amazon keyword expansion or related search terms
- synonym-aware Amazon keyword ideas
- paginated Amazon related-keyword results
- keyword clusters for Amazon SEO, PPC, or listing optimization
- to call the Frevana Amazon related-keywords endpoint

Required input:

- `keyword`

Optional input:

- one of `location_name` or `location_code` when overriding the default location
- one of `language_name` or `language_code` when overriding the default language
- `limit`
- `offset`
- `tag`
- `depth`
- `include_seed_keyword`
- `ignore_synonyms`
- output file path override
- one-time token override

Normalize `keyword` to lowercase. If location is missing, default to `location_name=United States`. If language is missing, default to `language_name=English`. State these defaults in the user-facing response when relevant. Default `limit=1000`, `offset=0`, and `depth=4` to maximize coverage. Let the API apply `include_seed_keyword=false` and `ignore_synonyms=false` when omitted.

Validate `limit` as `1..1000`, `offset` as at least `0`, `depth` as `0..4`, and `tag` as no more than 255 characters. Do not pass unsupported fields or local-only values such as tokens and output paths in the request payload.

When a page contains `limit` items, automatically increase `offset` by `limit` and continue. Stop when a page is not full or `total_count` is reached. Preserve each raw response page under the aggregate output's `pages` array. The script saves the aggregate JSON by default, so use that file for follow-up parsing instead of calling the API again.

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

### Use `google-maps-search`

Route here when the user wants:

- Google Maps place search results
- Google Maps results biased by a location, coordinates, or nearby area
- Google Maps price, rating, opening-state, or pagination filtering
- a Google Maps place lookup from `place_id` or `data_cid`

Required input:

- for a search: `q` and `type=search`
- for a direct place lookup: `place_id` or `data_cid`

Optional input:

- `ll`, `location`, `lat`, `lon`, `z`, `m`, `nearby`
- `data`, `google_domain`, `hl`, `gl`
- `min_price`, `max_price`, `min_rating`
- `open_state`, `open_on_day`, `open_at_hour`, `start`
- output file path and one-time token override

Do not invent optional map origin or filter values. `place_id` and `data_cid` are mutually exclusive. A location or latitude/longitude origin needs `z` or `m`; latitude and longitude must be supplied together. `open_state` cannot be combined with `open_on_day` or `open_at_hour`.

### Use `facebook-profile`

Route here when the user wants:

- a Facebook profile lookup by ID
- a Facebook profile lookup by username

Required input:

- `profile_id`

Optional input:

- output file path
- one-time token override

Do not guess a Facebook profile ID or username when the user does not provide one.

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

### Use `google-ads-keywords-search-volume`

Route here when the user wants:

- keyword search-volume estimates
- to query search volume for one or more keywords
- Google Ads keyword search-volume estimates
- keyword demand checks for Google Ads
- batch keyword comparisons for SEO, PPC, or ad planning
- to call the Frevana google-ads-search-volume endpoint

Required input:

- one or more `keywords`

Optional input:

- `search_partners`
- output file path override
- one-time token override

Important defaults:

- If `search_partners` is missing, default to `true`.
- State that default explicitly in the user-facing response when it matters.

Do not invent optional fields. The Frevana endpoint schema currently exposes only `keywords` and `search_partners`; do not pass unsupported passthrough fields such as `engine`, `api_key`, `output`, `no_cache`, `async`, or `zero_trace`.
The script saves every successful response to a JSON file by default, so use that saved file for follow-up parsing instead of calling the search API again.

### Use `google-ads-keywords-for-keywords`

Route here when the user wants:

- keywords related to a keyword
- to query related keywords or keyword ideas
- Google Ads keyword suggestions from seed keywords
- related keyword ideas from Google Ads data
- keyword expansion for SEO, PPC, or ad planning
- to call the Frevana google-ads-keywords-for-keywords endpoint

Required input:

- one or more seed `keywords`

Optional input:

- location name, location code, or location coordinate
- language name or language code
- `search_partners`
- `date_from` and/or `date_to`
- `sort_by`
- `include_adult_keywords`
- `tag`
- output file path override
- one-time token override

Important defaults:

- If `search_partners` is missing, default to `false`.
- If `include_adult_keywords` is missing, default to `false`.

Do not invent optional fields. The Frevana endpoint schema currently exposes only `keywords`, location, language, `search_partners`, `date_from`, `date_to`, `sort_by`, `include_adult_keywords`, and `tag`; do not pass unsupported passthrough fields such as `engine`, `api_key`, `output`, `no_cache`, `async`, or `zero_trace`.
The script saves every successful response to a JSON file by default, so use that saved file for follow-up parsing instead of calling the search API again.

### Use `google-ads-ad-traffic-by-keywords`

Route here when the user wants:

- Google Ads ad traffic forecasts for keywords
- projected clicks, CPC, or ad cost for a keyword set
- forecast metrics based on a bid and match type
- to call the Frevana google-ads-ad-traffic-by-keywords endpoint

Required input:

- one or more `keywords`
- `bid`
- `match`

Optional input:

- location name, location code, or location coordinate
- language name or language code
- `date_from` plus `date_to`
- `date_interval`
- `sort_by`
- `tag`
- output file path override
- one-time token override

Important defaults:

- If no forecast date range or interval is provided, DataForSEO defaults to `next_month`.
- `match` must be `exact`, `broad`, or `phrase`.
- `date_interval` must not be combined with `date_from` or `date_to`.
- `date_from` and `date_to` must be provided together.

Do not invent optional fields. The Frevana endpoint schema currently exposes only `keywords`, `bid`, `match`, location, language, `date_from`, `date_to`, `date_interval`, `sort_by`, and `tag`; do not pass unsupported passthrough fields such as `engine`, `api_key`, `output`, `no_cache`, `async`, or `zero_trace`.
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

### Use `snowflake`

Route here when the user wants:

- to install, verify, or use the official Snowflake CLI
- to list, add, test, remove, or select a default Snowflake connection
- to execute Snowflake SQL strings or SQL files
- to inspect, create, describe, list, or drop Snowflake objects
- to operate Snowflake Native Apps, stages, Snowpark, Streamlit, notebooks, Git repositories, Cortex, data pipelines, or Snowpark Container Services through `snow`

Required input:

- for connection creation: connection name and the authentication-specific account/user or workload identity fields
- for SQL: a SQL string or SQL file
- for object inspection: object type and, when describing, an identifier
- for object creation: object type and a reviewed JSON definition file
- for object deletion: object type and identifier

Important behavior:

- Prefer `skills/snowflake/scripts/snowflake.sh` for connection, SQL, and common object operations.
- Before every wrapped operation, check whether `snow` is installed and verify that both its help and version identify a working Snowflake CLI. Reject an unrelated or broken executable with the same name. The wrapper automatically runs `uv tool install snowflake-cli` when it is missing.
- Automatic installation requires `uv` and Python 3.10 or later. If `uv` is unavailable, stop and surface that prerequisite instead of silently falling back to system `pip`.
- Use `setup-pat` as the primary initial connection flow. Use `connection-add-pat` when the user already has a reviewed owner-only token file and wants to provide all connection fields explicitly.
- For the easiest initial setup, require only `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, and `SNOWFLAKE_PAT` or `SNOWFLAKE_TOKEN`. Default the connection name to `default`; prefer official `SNOWFLAKE_DEFAULT_CONNECTION_NAME` when supplied, while retaining `SNOWFLAKE_CONNECTION_NAME` as a compatibility alias.
- During `setup-pat`, prefer connection-specific `SNOWFLAKE_CONNECTIONS_<NAME>_*` values over generic `SNOWFLAKE_*` values. Reuse an existing protected token file from `--token-file`, `SNOWFLAKE_CONNECTIONS_<NAME>_TOKEN_FILE_PATH`, or `SNOWFLAKE_TOKEN_FILE_PATH`; otherwise persist a raw token from the connection-specific token variable, `SNOWFLAKE_PAT`, or `SNOWFLAKE_TOKEN`.
- Infer connection-specific environment variables only when the connection name contains letters, digits, and underscores. For names containing dots or hyphens, require explicit options or generic variables rather than applying a lossy name transformation.
- During `setup-pat`, persist the PAT to a separate `0600` file and let `snow connection add` write only `token_file_path` and non-secret connection settings to Snowflake configuration. Never embed the PAT value in TOML.
- Create missing PAT directories with `0700`, but never chmod an existing parent directory. Require an existing directory to be current-user-owned, non-symlinked, and not group- or world-writable.
- Resolve the Snowflake configuration location in official precedence order: `--config-file`, `SNOWFLAKE_HOME`, existing `~/.snowflake`, then the platform default (`${XDG_CONFIG_HOME:-$HOME/.config}/snowflake` on Linux, `%USERPROFILE%\AppData\Local\snowflake` on Windows, or `~/Library/Application Support/snowflake` on macOS). Store the default PAT file in a `pat` subdirectory beside that configuration.
- If an active sibling `connections.toml` exists, do not let `setup-pat` write an ignored connection into `config.toml`. Stop and direct the user to add the shared connection to `connections.toml` or choose an isolated `--config-file`.
- When `connections.toml` is active, allow `connection-set-default` but refuse `connection-remove`, because the official removal command edits `config.toml`; require a separately reviewed edit of the shared file.
- Initial setup must preview first and require `--execute`; refuse to overwrite an existing PAT file. Set the new connection as default and test it automatically unless the user requests `--no-default` or `--skip-test`.
- Require PAT token files to be non-empty regular files with `0400` or `0600` permissions. Never read, print, or copy their contents into the repository.
- Before configuring PAT, confirm account/authentication-policy support and applicable network-policy requirements. Prefer a service user and a least-privilege PAT role restriction.
- Run `check`, `config-info`, then `connection-list` before setup. Run `connection-test` before relying on an unfamiliar connection; `setup-pat --execute` performs that test automatically.
- Never place Snowflake passwords, raw tokens, OAuth client secrets, private-key contents, or passphrases in the repository or command-line arguments.
- Validate every token and private-key file used by connection creation as a readable, non-empty, non-symlink regular file with `0400` or `0600` permissions, including generic `connection-add`.
- Prefer key-pair authentication, workload identity federation, token files, or protected environment variables for AI processes.
- The wrapper executes clearly read-only SQL automatically; other SQL, connection changes, and object mutations return a preview and require `--execute` after explicit user confirmation.
- Use `--preview` for untrusted SQL or `SELECT` statements that invoke UDFs, external functions, stored logic, or unfamiliar system functions.
- Preview every SQL statement containing a `SYSTEM$` function regardless of its leading keyword.
- Before DML, query and verify the intended target rows; after execution, query them again to verify the result.
- Treat Snowflake CLI template variables as textual substitution, not bound SQL parameters.
- Keep `--local-only` enabled for SQL execution unless the user explicitly approves reviewed remote sources; this option only blocks URL-based SQL include/load directives.
- Use `--single-transaction` for multi-statement writes when supported.
- Keep `object-create` JSON definitions at or below 32768 bytes and reject secret objects or sensitive-looking fields because the official CLI accepts JSON only through a command argument. Use reviewed DDL with `query --file` for larger or sensitive definitions.
- Read `skills/snowflake/references/official-cli.md` and inspect live command help before specialized workload or application commands.
- Prefer `JSON_EXT` output and enhanced exit codes. Do not report success until the command completes and any asynchronous resource reaches the requested state.
- Save command outputs only to current-user-owned, non-symlink regular files with `0600` permissions, and reject unsafe explicit output targets before invoking Snowflake.

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

### Use `sqlite-crud`

Route here when the user wants:

- to configure and save reusable local SQLite database file profiles
- SQLite table or column inspection
- SQLite row lookup, insertion, update, or deletion
- SQLite `schema`, `select`, `insert`, `update`, `delete`, or guarded raw SQL
- safe SQLite writes with dry-run previews and explicit write execution
- to query a local `.sqlite`, `.sqlite3`, or `.db` file without re-entering the file path

Required input:

- for configuration: profile name and local SQLite file path
- for row operations: a saved profile, existing default profile, or explicit user-provided `--path`; plus table and filter/value details required by the operation

Important behavior:

- Prefer `skills/sqlite-crud/scripts/sqlite_crud.sh` over ad hoc `sqlite3` commands.
- Connection profiles are saved locally under `~/.config/sqlite-crud/profiles/` with `0600` permissions; do not store database files or generated copies in this repository unless explicitly requested.
- This skill supports local SQLite file paths only. Do not add SSH, remote `.env`, host, user, password, or tunnel behavior.
- If no profile/default profile is configured, ask the user for the exact local database file path and pass it with `--path`; do not scan the repository, home directory, temp directory, or filesystem to discover SQLite files.
- When `--path` is used, the script saves that path to the default profile for later commands.
- Do not add `--readonly` by default; only use it when the user explicitly asks for a read-only profile.
- `readonly` profiles block `insert`, `update`, `delete`, and raw write SQL.
- `insert`, `update`, and `delete` dry-run by default. Run with `--execute` only after explicit user confirmation.
- Raw write SQL requires both `--execute` and `--allow-raw-write`.
- `update` and `delete` require `--where` unless the user explicitly confirms a full-table operation and `--allow-full-table` is passed.
- Prefer structured commands over `raw-sql`.
- Do not invent table or column names. Run `schema` first when uncertain.
- The local `sqlite3` client is required and should support JSON output mode.

### Use `wordpress-content`

Route here when the user wants:

- to create, inspect, update, schedule, publish, or trash WordPress posts, pages, or custom post types
- to upload WordPress media, set featured images, or edit media metadata
- to manage WordPress categories, tags, custom taxonomies, post meta, or custom fields
- to manage classic navigation menus or inspect block-theme navigation
- to preserve or edit Gutenberg block content
- to perform a scoped WordPress bulk content update through REST endpoints
- to use the WordPress REST API for content management without local PHP or WP-CLI

Required input:

- an HTTPS WordPress site URL, resolved from explicit input, environment, config, or an interactive prompt
- the requested operation and enough content details to perform it
- the exact object ID for changes to existing objects; when only a title or search term is provided, search and resolve ambiguity before writing
- for authenticated REST operations, a WordPress username and Application Password resolved through the same supported sources

Important behavior:

- Use the built-in WordPress REST API directly. Do not install or invoke WP-CLI, and do not require local PHP.
- Require `bash`, `curl`, and Python 3 for the deterministic verbatim publishing helper.
- Prefer `skills/wordpress-content/scripts/wordpress_rest.sh` over ad hoc authenticated `curl`.
- Run its `status` action on first use; it must authenticate against the current-user REST endpoint rather than treating the presence of credential strings as proof of validity.
- Publish user-supplied body content without local rewriting or format conversion. Read `skills/wordpress-content/references/verbatim-publishing.md` before body writes and use `verbatim-create` or `verbatim-update`; never use generic `request` or direct `curl` for body writes.
- Resolve `WORDPRESS_URL`, `WORDPRESS_USERNAME`, and `WORDPRESS_APP_PASSWORD` independently in this order: explicit `--url`/`--username`/`--app-password`, environment variables, local config file, then interactive prompt when a terminal is available.
- If any credential is missing, direct the user to `https://frevana.gitbook.io/frevana-docs/cms-integrations/wordpress-integration` to obtain the required values; do not invent them.
- Use `${WORDPRESS_CONFIG_FILE:-${XDG_CONFIG_HOME:-$HOME/.config}/wordpress-content/config}` by default, or `--config FILE` / `WORDPRESS_CONFIG_FILE` when overridden.
- Save configuration only through the explicit `configure` action or `--save-config`. Keep the directory at `0700` and the file at `0600`; never print the Application Password.
- GET, HEAD, and OPTIONS may execute immediately. POST, PUT, PATCH, and DELETE must dry-run by default and require `--execute`.
- Inspect the REST index and use `OPTIONS` before relying on site-specific, custom-post-type, meta, menu, or navigation routes.
- Use `curl --fail-with-body --silent --show-error` or an equivalent HTTP client so WordPress JSON errors remain visible.
- Read the current object before updating it and verify the result after every write.
- Submit new body content and its requested status directly through the deterministic helper. Compare the returned `content.raw` when possible, but treat mismatches as warnings; do not stop, change status, or roll back an otherwise successful request solely because WordPress stored a different representation.
- Treat a requested publication status that WordPress did not apply as a real failure. The lenient mismatch rule applies only to the stored body representation.
- Preserve Gutenberg block comments and the site's existing editor format. Do not convert block content to Classic HTML or vice versa unless requested.
- Resolve exact IDs before writes. Do not guess a post, page, media, term, or menu item ID from a title alone.
- Treat publishing, scheduling, navigation changes, taxonomy renames, deletes, and bulk updates as externally visible actions. Preview exact targets when they are not already unambiguous.
- Trash by default. Permanently delete only when the user explicitly requests it.
- For bulk writes, build an explicit endpoint-and-ID target list, send minimal payloads, stop on the first unexpected error, and verify every changed object.
- For REST, use HTTPS and Application Passwords. Never use, print, or persist the user's interactive WordPress password.
- For scheduled content, inspect `/wp-json/wp/v2/settings` when permitted; otherwise ask for the intended timezone instead of guessing.
- Discover `/wp-json/wp/v2/menus`, `/menu-items`, `/menu-locations`, and `/navigation` before managing classic or block-theme navigation.

### Use `sendgrid-send-email`

Route here when the user wants:

- to send transactional email through SendGrid
- to call the Twilio SendGrid v3 Mail Send API
- a SendGrid dry-run payload before sending
- SendGrid plain text, HTML, dynamic template, attachment, sandbox, or scheduled-send email

Required input:

- sender email through `--from`; this address should be a verified sender in the user's Twilio SendGrid account
- one or more recipient emails
- subject, unless provided by a dynamic template
- message content through plain text, HTML, or `template_id`

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
- The script dry-runs by default and requires `--send` to call SendGrid.
- After a successful send with `x-message-id`, the script returns `status_query.prompt_example` as a concise user-facing example for querying Email Logs later with `sendgrid-email-log`, plus `status_query.query_params` for agent use. Do not display shell scripts unless the user asks.
- For dynamic template sends, do not include `--subject` when querying Email Logs status. The template may override the request subject, so subject filtering can hide matching messages.
- Every request includes `custom_args.business_id` for application-side correlation. Use `--business-id` when the user provides a business-specific ID; otherwise let the script generate one.
- Do not pass `business_id` through `--custom-arg`; it is reserved for the generated or explicit business ID.
- Confirm recipients, subject, and content before running with `--send`.
- Treat HTTP `202` as queued, not delivered. Sandbox validation may return HTTP `200`.
- Do not print or log the API key. If the user shares a key in chat, advise them to rotate it.
- Use `--private-recipients` when multiple `to` recipients should not see each other.

### Use `sendgrid-email-log`

Route here when the user wants:

- SendGrid Email Logs status lookup
- to check whether a specific email was opened or clicked
- per-message SendGrid event activity or timeline
- delivery, bounce, drop, defer, spam report, unsubscribe, open, or click status for a known message
- to call `GET /v3/logs/{sg_message_id}` or `POST /v3/logs`

Required input:

- for direct by-ID activity: full Email Logs `sg_message_id`
- for search-then-detail lookup: one or more Email Logs search filters such as `to_email`, `from_email`, `sent_at`, `subject`, `status`, `start_time`, `end_time`, raw `query`, and optional Mail Send `message_id`
- or a raw Email Logs `query`

Optional input:

- `subject` to narrow Email Logs results, except for dynamic template sends
- sender email
- status filters
- start/end time filters
- raw Email Logs query
- `sent_at_lookback_seconds`
- `limit`
- `subuser` for `POST /v3/logs`
- `on_behalf_of` header value for parent-account by-ID calls
- API region (`global` or `eu`)
- output file path
- one-time API key override

Important behavior:

- Use `SENDGRID_API_KEY`, not `FREVANA_TOKEN` and not Twilio Account SID/Auth Token credentials.
- API key lookup order is `--api-key`, then `SENDGRID_API_KEY`, then the locally saved key at `~/.config/sendgrid-send-email/api_key`.
- The saved API key path is shared with `sendgrid-send-email`.
- Prefer `scripts/get_email_log.sh` for both known full `sg_message_id` lookups and search-then-detail lookups. Use `scripts/query_email_logs.sh` only when the user wants raw `POST /v3/logs` search results without fetching details.
- The Mail Send `x-message-id` can be incomplete for `GET /v3/logs/{sg_message_id}`. When the user has only that ID, or does not know the message ID, call `scripts/get_email_log.sh` with all available filters such as `--to`, `--from`, `--sent-at`, `--message-id`, `--subject`, `--status`, `--start-time`, `--end-time`, or `--query`; the script searches `POST /v3/logs` first, resolves the full `sg_message_id`, then calls `GET /v3/logs/{sg_message_id}`.
- `scripts/get_email_log.sh` calls `GET /v3/logs/{sg_message_id}` and adds an `event_summary` with booleans for delivered, opened, clicked, bounced, deferred, dropped, processed, spam_reported, and unsubscribed. When it resolves the ID first, it also returns `log_resolution`.
- `scripts/query_email_logs.sh` calls `POST /v3/logs`, subtracts 5 seconds from `--sent-at` by default, and fuzzy-matches returned `messages[].sg_message_id` against the Mail Send `x-message-id`, including `.recvd-...` suffix variants.
- For dynamic template sends, do not include `--subject` when querying Email Logs status. The template may override the request subject, so subject filtering can hide matching messages.
- Do not query by `custom_args.business_id`; use `--to`, `--sent-at`, and `--message-id` to narrow by recipient/time and fuzzy-match returned `sg_message_id`, or pass an account-supported raw `--query`.
- If no API key is available, the scripts prompt once in interactive runs and save the key locally for future runs. In non-interactive runs, guide the user to read `https://frevana.gitbook.io/frevana-docs/email-integrations/sendgrid-integration` to get the required configuration.
- Return raw JSON when requested; otherwise summarize `event_summary`, `log_resolution.resolved_sg_message_id`, `messages[].status`, `to_email`, `from_email`, `subject`, `reason`, and `sg_message_id`.
- If Email Logs returns no data, no fuzzy `sg_message_id` match, or by-ID lookup returns not found, ask the user to review `https://app.sendgrid.com/email_logs` manually.
- Do not print or log the API key. If the user shares a key in chat, advise them to rotate it.

### Use `sendgrid-global-email-stats`

Route here when the user wants:

- SendGrid global email statistics
- aggregate SendGrid stats across a date range
- account-level SendGrid metrics such as requests, processed, delivered, bounces, opens, clicks, spam reports, or unsubscribes
- to call the Twilio SendGrid Stats API `GET /v3/stats`
- SendGrid stats grouped by day, week, or month

Required input:

- `start_date` in `YYYY-MM-DD` format

Optional input:

- `end_date` in `YYYY-MM-DD` format
- `aggregated_by`, one of `day`, `week`, or `month`
- `limit`
- `offset`
- `on_behalf_of` header value for parent-account subuser or customer-account calls
- API region (`global` or `eu`)
- output file path
- one-time API key override

Important behavior:

- Use `SENDGRID_API_KEY`, not `FREVANA_TOKEN` and not Twilio Account SID/Auth Token credentials.
- API key lookup order is `--api-key`, then `SENDGRID_API_KEY`, then the locally saved key at `~/.config/sendgrid-send-email/api_key`.
- The saved API key path is shared with `sendgrid-send-email`.
- If no API key is available, the script prompts once in interactive runs and saves the key locally for future runs. In non-interactive runs, guide the user to read `https://frevana.gitbook.io/frevana-docs/email-integrations/sendgrid-integration` to get the required configuration.
- Prefer `scripts/retrieve_global_email_stats.sh` over ad hoc `curl`.
- This is a read-only `GET /v3/stats` lookup; it does not send email and does not query per-message Email Logs.
- Do not invent optional query parameters. The endpoint schema currently exposes only `start_date`, `end_date`, `aggregated_by`, `limit`, and `offset`.
- For parent account calls, pass the complete `on-behalf-of` header value through `--on-behalf-of`. Use a subuser username for subusers or `account-id <account-id>` for customer accounts.
- Return raw JSON when requested; otherwise summarize the most useful metrics by date bucket.

### Use `slack-webhook`

Route here when the user wants:

- to post a Slack message through an incoming webhook
- to send a Slack notification
- a Slack webhook dry-run payload before posting
- Slack mrkdwn, links, Block Kit blocks, attachments, or thread replies through an incoming webhook

Do not use this for:

- reading Slack messages
- deleting Slack messages
- listing or managing channels, users, or conversations
- Slack Bot Token Web API workflows

Required input:

- message text through `--text` or `--text-file`
- or a complete Slack webhook payload through `--payload-json` or `--payload-file`

Optional input:

- Block Kit `blocks` JSON array
- Slack `attachments` JSON array
- `thread_ts`
- `unfurl_links` or `unfurl_media`
- output file path
- one-time webhook URL override

Important behavior:

- Use `SLACK_WEBHOOK_URL`, not `FREVANA_TOKEN`, `SENDGRID_API_KEY`, `INSTANTLY_API_KEY`, or `KLAVIVO_API_KEY`.
- Webhook URL lookup order is `SLACK_WEBHOOK_URL`, then `--webhook-url`, then the locally saved URL at `~/.config/slack-webhook/webhook_url`.
- If no webhook URL is available, dry-run payload preview still works. Sending requires a webhook URL.
- Use `--webhook-url <url> --save-webhook-url` or `--configure-webhook-url` to update the saved URL. Use `--clear-webhook-url` to remove it.
- Prefer `scripts/send_slack_webhook.sh` over ad hoc `curl`.
- The script dry-runs by default and requires `--send` to call Slack.
- Confirm the channel/workspace implied by the webhook URL and the final message content before running with `--send`.
- Treat HTTP `200` and response body `ok` as posted. Report Slack error strings such as `invalid_payload`, `no_text`, `no_service`, `channel_not_found`, `channel_is_archived`, or `action_prohibited`.
- Do not print or log the webhook URL. If the user shares a webhook URL in chat, advise them to rotate it.
- Incoming webhooks are send-only and are normally bound to one configured Slack destination.

### Use `telegram-bot`

Route here when the user wants:

- to inspect a Telegram bot through the Telegram Bot API
- to send Telegram bot messages, photos, documents, or locations
- to get Telegram updates or discover a chat ID
- to set, get, or delete a Telegram bot webhook
- to set or get Telegram bot commands
- to inspect chats, administrators, or member counts
- to ban or unban users from a Telegram chat
- to edit, delete, pin, or forward Telegram messages
- to answer callback queries

Required input:

- Telegram bot token from `--bot-token`, `TELEGRAM_BOT_TOKEN`, or saved local config
- `--action`
- method-specific inputs such as `chat_id`, `text`, `message_id`, `user_id`, `url`, media path, or payload JSON

Optional input:

- parse mode (`HTML`, `Markdown`, or `MarkdownV2`)
- reply markup JSON
- commands JSON
- allowed updates JSON
- output file path
- raw Bot API method through `--action raw --method <METHOD> --payload-json <JSON>`

Important behavior:

- Use `TELEGRAM_BOT_TOKEN`, not `FREVANA_TOKEN`, `SLACK_WEBHOOK_URL`, `SENDGRID_API_KEY`, `INSTANTLY_API_KEY`, or `KLAVIVO_API_KEY`.
- Token lookup order is `--bot-token`, then `TELEGRAM_BOT_TOKEN`, then the locally saved token at `~/.config/telegram-bot/bot_token`.
- Use `--bot-token <token> --save-bot-token` or `--configure-bot-token` to update the saved token. Use `--clear-bot-token` to remove it.
- Prefer `scripts/telegram_bot.sh` over ad hoc `curl`.
- Read actions call Telegram immediately by default unless `--dry-run` is passed.
- Write actions dry-run by default and require `--execute` to call Telegram.
- Treat `--action raw` as a write action unless the user passes `--dry-run` or explicitly requests execution.
- Confirm target `chat_id`, message content, moderation target, webhook URL, or message ID before running write actions with `--execute`.
- Do not print or log the bot token. If the user shares a token in chat, advise them to rotate it with BotFather.
- Telegram bots cannot message users first; the user must start the bot or otherwise expose a chat to the bot.

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
- If no API key is available, the script prompts once in interactive runs and saves the key locally for future runs. In non-interactive runs, tell the user to create an Instantly API V2 key by following `https://frevana.gitbook.io/frevana-docs/email-integrations/instantly-integration`.
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
- If no API key is available, the script prompts once in interactive runs and saves the key locally for future runs. In non-interactive runs, tell the user to create a Klaviyo API key by following `https://frevana.gitbook.io/frevana-docs/email-integrations/klaviyo-integration`.
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

### Use `meta-ads-search`

Route here when the user wants:

- Meta Ads Library or Facebook ad records by keyword, brand, or advertiser text
- Meta Ads Library results filtered by country, active status, or date range
- Chrome Extension-backed Meta advertising research through the local Frevana daemon

Required input:

- `keyword`

Optional input:

- `country` (`ALL` by default, or an uppercase ISO 3166-1 alpha-2 code)
- `active_status` (defaults to `active`; `inactive` or `all` when specified)
- `date_from`
- `date_to`
- `maxResults` (defaults to 20; 1 through 500)
- `timeout`
- output file path

The user can provide only `keyword`; the script searches active ads in all countries and returns up to 20 ads by default. Let a user-provided `country`, `active_status`, or `maxResults` override those defaults. Do not invent optional date range or timeout values. This is a Chrome Extension skill: it uses the local Frevana daemon and the user's connected Chrome session.

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

`gpt-image-2` does not currently support transparent backgrounds. Do not pass `background: "transparent"` or `--background transparent`; use `opaque`, `auto`, or omit the background option.

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

### Use `seedance2`

Route here when the user wants:

- Seedance 2.0 or Seedance2 AI video generation
- text-to-video, image-to-video, or reference-to-video generation through `api.seevio.ai`
- to query, wait for, or download the result of an existing Seedance task

Required input:

- for creation: a non-empty prompt and any media URLs required by the selected generation mode
- for status or wait: a Seedance task ID

Optional input:

- model (`seedance-2-0`, `seedance-2-0-fast`, or `seedance-2-0-mini`)
- generation type, duration, aspect ratio, resolution, audio generation, watermark, web search, last-frame return, and seed
- public image, video, or audio URLs as allowed by the selected generation mode
- wait timeout, download directory, and output JSON path

Important behavior:

- Prefer `skills/seedance2/scripts/seedance.sh` over ad hoc API calls.
- Require `SEEDANCE_API_KEY`; never print it or pass it directly in command-line arguments.
- Require HTTPS for the API base URL. Do not allow an HTTP `SEEDANCE_API_BASE_URL` override.
- Do not pass or ask for `callback_url`; this skill uses polling only.
- Poll task status at the fixed API minimum interval of 10 seconds. Do not expose a custom interval.
- Treat every create request as billable. Do not submit trial jobs or automatically resubmit failed or timed-out jobs.
- Use only public HTTP(S) media URLs; the Seedance API does not upload local files.

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
- If the user wants to publish through Frevana but does not provide a local file path, ask for it.
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
- If the user asks to create a Seedance video without a prompt, ask for the prompt. If the selected mode requires media, ask for the required public media URLs instead of guessing.
- If the user asks for keyword search volume or Google Ads keyword search volume but does not provide keywords, ask for the keywords.
- If the user asks for Google Immersive Product details without a `page_token`, suggest running `google-shopping-search` first to obtain `immersive_product_page_token`, then continue with this skill using that token.
- If the user says "search Google Trends for this" but does not provide a keyword, ask for the keyword.
- If the user asks for Google Related Questions or People Also Ask expansion without a `next_page_token`, suggest running the regular Google Search skill first to obtain `related_questions[].next_page_token`, then continue with this skill using that token.
- If the user says only `nano banana` without specifying `2` or `pro`, ask which variant they want.
- If the user asks for Frevana report generation without `template_id`, use the default `mckinsey-style-report-2`.
- If the user asks to send SendGrid email without sender, recipient, or content details, ask for the missing fields before execution.
- If the user asks for SendGrid global email stats without a `start_date`, ask for the start date.
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

### Frevana custom-domain publishing

For `frevana-publish`:

1. Confirm the user provided one readable local file with an extension.
2. Prefer `scripts/publish_file.sh` over manual requests.
3. Let the script use `FREVANA_TOKEN` from the environment first.
4. Let the script check `custom_domain` before it requests a pre-signed upload destination.
5. If the domain is not configured, relay `https://www.frevana.com/dashboard/domain` and stop.
6. Let the script upload the file with PUT to the returned `presigned_url`.
7. Let the script publish the returned `content_id` with `op_type=publish`.
8. Return the public URL only after publishing succeeds, and do not expose the bearer token or pre-signed URL.

### Amazon, eBay, Home Depot, Walmart, Google Ads Transparency Center, Google Ads Keywords Search Volume, Google Ads Keywords For Keywords, Google Ads Ad Traffic By Keywords, Google Search, Google Forums, Google Patents, Google News, Google Maps, Facebook Profile, Google Related Questions, Google Trends, Google Shopping, Google Shopping Light, Google Immersive Product, and YouTube Search skills

For `amazon-search`, `amazon-product`, `amazon-keyword-search-volume`, `amazon-related-keywords`, `ebay-search`, `home-depot-search`, `walmart-search`, `walmart-product-reviews`, `walmart-product-sellers`, `google-ads-transparency-center`, `google-ads-keywords-search-volume`, `google-ads-keywords-for-keywords`, `google-ads-ad-traffic-by-keywords`, `google-search`, `google-forums-search`, `google-patents-search`, `google-news-search`, `google-maps-search`, `facebook-profile`, `google-related-questions`, `google-trends`, `google-shopping-search`, `google-shopping-light-search`, `google-immersive-product`, and `youtube-search`:

1. Extract the user inputs.
2. Prefer the repo script over ad hoc `curl`.
3. Let the script use `FREVANA_TOKEN` from the environment first.
4. In non-interactive agent runs, fail fast if the token is missing.
5. Return either the raw JSON payload or a summary, depending on what the user asked for.
6. For `amazon-related-keywords`, `ebay-search`, `home-depot-search`, `walmart-search`, `walmart-product-reviews`, `walmart-product-sellers`, `google-ads-transparency-center`, `google-ads-keywords-search-volume`, `google-ads-keywords-for-keywords`, `google-ads-ad-traffic-by-keywords`, `google-search`, `google-forums-search`, `google-patents-search`, `google-trends`, `google-shopping-search`, `google-shopping-light-search`, and `google-immersive-product`, rely on the default saved JSON file or pass `--output` only to choose a specific path. Do not call the script twice just to save and summarize results.
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

For SendGrid email log and status lookup:

1. Extract full `sg_message_id` for direct by-ID lookups. If the user only has a Mail Send `x-message-id`, an incomplete ID, or no message ID, extract as many filters as available: `to_email`, `from_email`, `sent_at`, `message_id`, `subject`, `status`, `start_time`, `end_time`, or raw `query`; include `subject` only when available.
2. Prefer `sendgrid-email-log/scripts/get_email_log.sh`. It can perform direct detail lookup by full `sg_message_id`, or search `POST /v3/logs` first to resolve the full `sg_message_id` before fetching details.
3. Let the script use `--api-key`, `SENDGRID_API_KEY`, or the locally saved key.
4. In non-interactive agent runs, fail fast if the API key is missing from all supported sources, and point the user to `https://frevana.gitbook.io/frevana-docs/email-integrations/sendgrid-integration`.
5. Return matching Email Logs JSON or summarize `event_summary`, `log_resolution.resolved_sg_message_id`, `messages[].status`, `to_email`, `from_email`, `subject`, `reason`, and `sg_message_id`.
6. Do not query by `custom_args.business_id`; use `--to`, `--sent-at`, and `--message-id` to narrow by recipient/time and fuzzy-match returned `sg_message_id`. Add `--subject` when available, except for template sends. Email Logs can append suffixes such as `.recvd-...` to `sg_message_id`, so treat the user-provided message ID as a prefix/substring match, not only an exact match.
7. `--sent-at` is only a lower bound, but the script subtracts a 5-second default lookback before building `sg_message_id_created_at >= ...` to absorb SendGrid response/log timestamp skew. Do not use a time-window parameter.
8. If Email Logs returns no data, no fuzzy `sg_message_id` match, or by-ID lookup returns not found, ask the user to review `https://app.sendgrid.com/email_logs` manually.

### SendGrid global email stats

For `sendgrid-global-email-stats`:

1. Extract `start_date`, optional `end_date`, optional `aggregated_by`, optional pagination, optional `on_behalf_of`, and optional region.
2. Prefer `scripts/retrieve_global_email_stats.sh` over ad hoc `curl`.
3. Let the script use `--api-key`, `SENDGRID_API_KEY`, or the locally saved key shared with `sendgrid-send-email`.
4. In non-interactive agent runs, fail fast if the API key is missing from all supported sources, and point the user to `https://frevana.gitbook.io/frevana-docs/email-integrations/sendgrid-integration`.
5. Return either raw JSON or summarize metrics such as `requests`, `processed`, `delivered`, `bounces`, `opens`, `unique_opens`, `clicks`, `unique_clicks`, `spam_reports`, and `unsubscribes`.
6. Do not pass unsupported query fields beyond `start_date`, `end_date`, `aggregated_by`, `limit`, and `offset`.

### Instantly campaign enrollment and replies

For `instantly-send-email`:

1. Classify the user intent: cold outbound/campaign enrollment, reply to existing email, campaign management, or lead movement/removal.
2. Prefer `scripts/lead.sh`, `scripts/campaign.sh`, and `scripts/email.sh` over ad hoc `curl`.
3. For cold outbound, run `lead.sh list`, then `campaign.sh list` or `campaign.sh create`, then dry-run `lead.sh create` or `lead.sh move`.
4. For replies, run `email.sh list --lead <email>`, ask the user to select the email, then dry-run `email.sh reply`.
5. For moving/removing a lead from a campaign, use `lead.sh move`; the Instantly move API requires a destination campaign or list.
6. Let the script use `--api-key`, `INSTANTLY_API_KEY`, or the locally saved key.
7. In non-interactive agent runs, fail fast if the API key is missing from all supported sources, and tell the user to create an Instantly API V2 key by following `https://frevana.gitbook.io/frevana-docs/email-integrations/instantly-integration`.
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
8. In non-interactive agent runs, fail fast if the API key is missing from all supported sources, and tell the user to create a Klaviyo API key by following `https://frevana.gitbook.io/frevana-docs/email-integrations/klaviyo-integration`.
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
bash skills/amazon-related-keywords/scripts/search_amazon_related_keywords.sh
bash skills/ebay-search/scripts/search_ebay.sh
bash skills/home-depot-search/scripts/search_home_depot.sh
bash skills/walmart-search/scripts/search_walmart.sh
bash skills/walmart-product-reviews/scripts/search_walmart_product_reviews.sh
bash skills/walmart-product-sellers/scripts/search_walmart_product_sellers.sh
bash skills/google-search/scripts/search_google.sh
bash skills/google-forums-search/scripts/search_google_forums.sh
bash skills/google-patents-search/scripts/search_google_patents.sh
bash skills/google-news-search/scripts/search_google_news.sh
bash skills/google-maps-search/scripts/search_google_maps.sh
bash skills/facebook-profile/scripts/get_facebook_profile.sh
bash skills/google-ads-transparency-center/scripts/search_google_ads_transparency_center.sh
bash skills/google-ads-keywords-search-volume/scripts/search_google_ads_keywords_search_volume.sh
bash skills/google-ads-keywords-for-keywords/scripts/search_google_ads_keywords_for_keywords.sh
bash skills/google-ads-ad-traffic-by-keywords/scripts/search_google_ads_ad_traffic_by_keywords.sh
bash skills/google-related-questions/scripts/search_google_related_questions.sh
bash skills/google-trends/scripts/search_google_trends.sh
bash skills/google-shopping-search/scripts/search_google_shopping.sh
bash skills/google-shopping-light-search/scripts/search_google_shopping_light.sh
bash skills/google-immersive-product/scripts/search_google_immersive_product.sh
bash skills/youtube-search/scripts/search_youtube.sh
bash skills/sendgrid-send-email/scripts/send_email.sh
bash skills/slack-webhook/scripts/send_slack_webhook.sh
bash skills/telegram-bot/scripts/telegram_bot.sh
bash skills/wordpress-content/scripts/wordpress_rest.sh status
bash skills/klaviyo-send-email/scripts/campaign.sh
bash skills/klaviyo-send-email/scripts/audience.sh
bash skills/frevana-auth/scripts/login.sh
bash skills/frevana-publish/scripts/publish_file.sh
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

### Frevana publish

```bash
bash skills/frevana-publish/scripts/publish_file.sh \
  --file ./out/result.html
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

### Amazon related keywords

```bash
bash skills/amazon-related-keywords/scripts/search_amazon_related_keywords.sh \
  --keyword "wireless earbuds"
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

### Google Maps search

```bash
bash skills/google-maps-search/scripts/search_google_maps.sh \
  --q "coffee shops" \
  --type search \
  --location "San Francisco, CA" \
  --z 12 \
  --open-state now
```

### Facebook profile

```bash
bash skills/facebook-profile/scripts/get_facebook_profile.sh \
  --profile-id "zuck"
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
