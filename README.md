# Frevana Skills

Reusable skills for Frevana auth bootstrap, Frevana-backed HTTP API lookups, Chrome Extension workflows, SendGrid and Instantly email sending, MySQL/PostgreSQL/Redis CRUD, image generation, and HTML generation.

Each skill lives under `skills/`. Start with its `SKILL.md` to see what it does and what it needs. If your agent supports repo-level instructions, also read [AGENTS.md](AGENTS.md).

## Quick Start

Install the skill pack:

```bash
npx skills add FinpeakInc/frevana-skills
```

For API-backed script usage from this repository, set a Frevana bearer token:

```bash
export FREVANA_TOKEN="your-bearer-token"
```

Then run a skill script directly:

```bash
bash skills/google-patents-search/scripts/search_google_patents.sh --q "ai"
bash skills/walmart-search/scripts/search_walmart.sh --query "wireless earbuds"
bash skills/home-depot-search/scripts/search_home_depot.sh --q "cordless drill"
```

Most API-backed scripts validate the response as JSON, save it under `./out/`, and print the same JSON to stdout. Chrome Extension skills instead use the local Frevana daemon plus the user's logged-in Chrome Extension session, and run their bundled `scripts/setup.sh` before calling Frevana.

## Skill Index

Choose a top-level group first: [Data Skills](#data-skills) for retrieving or managing data, [Action Skills](#action-skills) for performing a task, and [Chrome Extension Skills](#chrome-extension-skills) for workflows that use the local Frevana daemon and a logged-in Chrome session.

### Data Skills

#### Commerce and marketplaces

| Family | Skill | Use for | Required input |
| --- | --- | --- | --- |
| Amazon | [`amazon-search`](skills/amazon-search/SKILL.md) | Amazon product search and discovery | keyword |
| Amazon | [`amazon-product`](skills/amazon-product/SKILL.md) | Amazon product detail lookup | ASIN |
| Amazon | [`amazon-keyword-search-volume`](skills/amazon-keyword-search-volume/SKILL.md) | Amazon keyword demand and comparison | one or more keywords |
| Marketplace | [`ebay-search`](skills/ebay-search/SKILL.md) | eBay listing search by keyword or category | query or category ID |
| Marketplace | [`home-depot-search`](skills/home-depot-search/SKILL.md) | Home Depot product search | query |
| Walmart | [`walmart-search`](skills/walmart-search/SKILL.md) | Walmart product search and filtering | query |
| Walmart | [`walmart-product-reviews`](skills/walmart-product-reviews/SKILL.md) | Walmart reviews for a known product | product ID / `us_item_id` |
| Walmart | [`walmart-product-sellers`](skills/walmart-product-sellers/SKILL.md) | Walmart seller offers for a known product | product ID / `us_item_id` |

#### Search, research, and social data

| Family | Skill | Use for | Required input |
| --- | --- | --- | --- |
| Google Search | [`google-search`](skills/google-search/SKILL.md) | Regular Google web search / SERP results | query |
| Google Search | [`google-forums-search`](skills/google-forums-search/SKILL.md) | Forum-style Google results | query |
| Google Search | [`google-related-questions`](skills/google-related-questions/SKILL.md) | Expand People Also Ask / related questions | `next_page_token` |
| Google Search | [`google-events-search`](skills/google-events-search/SKILL.md) | Google Events search | query |
| Google Search | [`google-images-search`](skills/google-images-search/SKILL.md) | Google Images search and filters | query |
| Google Search | [`google-ai-mode`](skills/google-ai-mode/SKILL.md) | Google AI Mode answers | query |
| Google Search | [`google-ai-overview`](skills/google-ai-overview/SKILL.md) | Google AI Overview by page token | page token |
| Google Search | [`google-autocomplete`](skills/google-autocomplete/SKILL.md) | Google Autocomplete suggestions | query prefix |
| Google Search | [`google-short-videos-search`](skills/google-short-videos-search/SKILL.md) | Google Short Videos results | query |
| Google Search | [`google-videos-search`](skills/google-videos-search/SKILL.md) | Google Videos results | query |
| Google Ads | [`google-ads-search`](skills/google-ads-search/SKILL.md) | Google sponsored search ads | query and location |
| Google Maps | [`google-maps-reviews`](skills/google-maps-reviews/SKILL.md) | Google Maps place reviews | data ID or place ID |
| Google Local Services | [`google-local-services-search`](skills/google-local-services-search/SKILL.md) | Google Local Services results | query and data CID |
| Bing | [`bing-search`](skills/bing-search/SKILL.md) | Bing web search results | query |
| YouTube | [`youtube-video`](skills/youtube-video/SKILL.md) | YouTube video details | video ID |
| YouTube | [`youtube-video-transcript`](skills/youtube-video-transcript/SKILL.md) | YouTube video transcripts | video ID |
| Instagram | [`instagram-profile`](skills/instagram-profile/SKILL.md) | Instagram profile lookup | profile ID |
| Google News | [`google-news-search`](skills/google-news-search/SKILL.md) | Google News search | query |
| Google Maps | [`google-maps-search`](skills/google-maps-search/SKILL.md) | Google Maps place search and lookup | search query with type, or place ID / CID |
| Google Trends | [`google-trends`](skills/google-trends/SKILL.md) | Google Trends interest and comparison data | query |
| Google Shopping | [`google-shopping-search`](skills/google-shopping-search/SKILL.md) | Google Shopping product search | query |
| Google Shopping | [`google-shopping-light-search`](skills/google-shopping-light-search/SKILL.md) | Lightweight Google Shopping product search | query |
| Google Shopping | [`google-immersive-product`](skills/google-immersive-product/SKILL.md) | Google Shopping immersive product details | page token |
| Google Ads | [`google-ads-transparency-center`](skills/google-ads-transparency-center/SKILL.md) | Google Ads Transparency Center creatives | advertiser ID, text, or next page token |
| Google Patents | [`google-patents-search`](skills/google-patents-search/SKILL.md) | Google Patents search | query |
| YouTube | [`youtube-search`](skills/youtube-search/SKILL.md) | YouTube search results | search query |
| Facebook | [`facebook-profile`](skills/facebook-profile/SKILL.md) | Facebook profile lookup | profile ID or username |
| Reddit | [`reddit-url-mentions`](skills/reddit-url-mentions/SKILL.md) | Reddit mentions of specific URLs through Frevana | one or more target URLs |

#### Databases

| Family | Skill | Use for | Required input |
| --- | --- | --- | --- |
| Database | [`mysql-crud`](skills/mysql-crud/SKILL.md) | MySQL CRUD with saved profiles and SSH support | saved profile or connection details |
| Database | [`postgresql-crud`](skills/postgresql-crud/SKILL.md) | PostgreSQL CRUD with saved profiles and SSH support | saved profile or connection details |
| Database | [`redis-crud`](skills/redis-crud/SKILL.md) | Redis key operations with saved profiles and SSH support | saved profile or connection details |
| Database | [`mongodb-crud`](skills/mongodb-crud/SKILL.md) | MongoDB document operations with saved profiles and SSH support | saved profile or connection details |
| Database | [`sqlite-crud`](skills/sqlite-crud/SKILL.md) | SQLite local file CRUD with saved profiles | local SQLite file path |

### Action Skills

| Family | Skill | Use for | Required input |
| --- | --- | --- | --- |
| Auth | [`frevana-auth`](skills/frevana-auth/SKILL.md) | Frevana CLI login and local credential setup | none |
| Email | [`sendgrid-send-email`](skills/sendgrid-send-email/SKILL.md) | Send transactional email through SendGrid Mail Send API | sender, recipients, and content |
| Email | [`instantly-send-email`](skills/instantly-send-email/SKILL.md) | Manage Instantly leads, campaigns, and replies | lead email, campaign choice, or selected email |
| Email | [`klaviyo-send-email`](skills/klaviyo-send-email/SKILL.md) | Manage Klaviyo campaigns and audiences | campaign or audience details |
| Image | [`gpt-image-2`](skills/gpt-image-2/SKILL.md) | Frevana-hosted image generation or editing | prompt or contents |
| Image | [`nano-banana-2`](skills/nano-banana-2/SKILL.md) | Frevana-hosted image generation with Nano Banana 2 | prompt or contents |
| Image | [`nano-banana-pro`](skills/nano-banana-pro/SKILL.md) | Frevana-hosted image generation with Nano Banana Pro | prompt or contents |
| Report | [`frevana-gen-report`](skills/frevana-gen-report/SKILL.md) | Generate final HTML from a Frevana template | template ID and content |

### Chrome Extension Skills

These skills use the local Frevana daemon and the user's logged-in Chrome Extension session.

#### Amazon

| Skill | Use for | Required input |
| --- | --- | --- |
| [`amazon-rufus-ai`](skills/amazon-rufus-ai/SKILL.md) | Ask Amazon Rufus AI about a product | product URL and question |
| [`amazon-product-info`](skills/amazon-product-info/SKILL.md) | Extract Amazon product page details | product URL |
| [`amazon-top-reviews`](skills/amazon-top-reviews/SKILL.md) | Fetch top helpful Amazon reviews | product URL |
| [`amazon-price`](skills/amazon-price/SKILL.md) | Extract Amazon price, discount, and coupon info | product URL |
| [`amazon-rufus-qa`](skills/amazon-rufus-qa/SKILL.md) | Extract Amazon Rufus suggested Q&A pairs | product URL |

#### Browser, AI platforms, and social

| Family | Skill | Use for | Required input |
| --- | --- | --- | --- |
| Browser | [`url-scrape`](skills/url-scrape/SKILL.md) | Scrape any URL through Chrome Extension | URL |
| Browser | [`google-search-extension`](skills/google-search-extension/SKILL.md) | Search Google through Chrome Extension | one or more queries |
| AI Platform | [`chatgpt-ask`](skills/chatgpt-ask/SKILL.md) | Ask ChatGPT through Chrome Extension | one or more prompts |
| AI Platform | [`gemini-ask`](skills/gemini-ask/SKILL.md) | Ask Gemini through Chrome Extension | one or more prompts |
| AI Platform | [`perplexity-ask`](skills/perplexity-ask/SKILL.md) | Ask Perplexity through Chrome Extension | one or more prompts |
| AI Platform | [`deepseek-ask`](skills/deepseek-ask/SKILL.md) | Ask DeepSeek through Chrome Extension | one or more prompts |
| AI Platform | [`doubao-ask`](skills/doubao-ask/SKILL.md) | Ask Doubao through Chrome Extension | one or more prompts |
| Social | [`reddit-search`](skills/reddit-search/SKILL.md) | Search Reddit link posts by query | query |
| Social | [`x-topic-search`](skills/x-topic-search/SKILL.md) | Search X/Twitter posts by topic | topic |
| Social | [`meta-ads-search`](skills/meta-ads-search/SKILL.md) | Search Meta Ads Library ads by keyword or advertiser text | keyword |
| Social publishing | [`publish-twitter-post`](skills/publish-twitter-post/SKILL.md) | Publish to Twitter/X | final text |
| Social publishing | [`publish-facebook-post`](skills/publish-facebook-post/SKILL.md) | Publish to Facebook | final text |
| Social publishing | [`publish-linkedin-post`](skills/publish-linkedin-post/SKILL.md) | Publish to LinkedIn | final text |

Use the index to choose a skill quickly. Use the detailed sections below for options, defaults, and save behavior.

## Chrome Extension Setup

Every skill in the [Chrome Extension Skills](#chrome-extension-skills) group runs its bundled `scripts/setup.sh` wrapper before calling Frevana. The wrapper downloads and executes the official Frevana setup script, installs the CLI when needed, starts/checks the daemon, and verifies Chrome Extension connectivity.

## Skill Details

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

### Amazon Chrome Extension Skills

Use Amazon's product page and Rufus features through the local Frevana daemon and Chrome Extension session.

Skills:

- [`amazon-rufus-ai`](skills/amazon-rufus-ai/SKILL.md) uses provider `amazon-rufus`
- [`amazon-product-info`](skills/amazon-product-info/SKILL.md) uses provider `amazon-product`
- [`amazon-top-reviews`](skills/amazon-top-reviews/SKILL.md) uses provider `amazon-product-reviews`
- [`amazon-price`](skills/amazon-price/SKILL.md) uses provider `amazon-price`
- [`amazon-rufus-qa`](skills/amazon-rufus-qa/SKILL.md) uses provider `amazon-rufus-qa`

Use when:

- you have a full Amazon product page URL
- you want Rufus answers, product page details, top reviews, price/coupon info, or suggested Q&A
- you want local Frevana Chrome Extension automation using the user's Chrome Extension session

Features:

- requires a URL containing `/dp/<ASIN>` or `/gp/product/<ASIN>`
- does not accept product names, Amazon search pages, category pages, or the Amazon homepage
- `amazon-rufus-ai` also requires `--question`
- `amazon-top-reviews` supports `--max-reviews`, `--sort-by`, `--reviewer-type`, and `--filter-by-star`
- `--format` supports `text` or `json`, defaulting to `text`
- optional `--timeout`
- runs bundled `scripts/setup.sh` before every call, matching the original Frevana skill flow
- setup downloads and executes the latest official Frevana setup script, which installs the CLI if missing and starts/checks the daemon
- requires the local Frevana daemon, Chrome Extension connection, and Amazon login in Chrome
- save output with `--output`

### [`ebay-search`](skills/ebay-search/SKILL.md)

Search eBay listings by keyword or category.

Use when:

- you want eBay search results for a keyword
- you want category-specific eBay results
- you want eBay-domain, pagination, or result-count controls

Features:

- accepts `--query` or `--category-id`
- optional `--ebay-domain`
- optional `--page` and `--results-per-page`
- saves every successful response to `./out/ebay-search-<timestamp>-<pid>.json` by default
- use `--output` to choose a specific result path

### [`home-depot-search`](skills/home-depot-search/SKILL.md)

Search Home Depot products by keyword.

Use when:

- you want Home Depot product results for a keyword
- you want US or Canada Home Depot results
- you want store-specific, delivery ZIP, pagination, or page-size controls

Features:

- `q` is the only required input
- optional `--country`, `--store`, and `--delivery-zip`
- optional `--page` and `--page-size`
- saves every successful response to `./out/home-depot-search-<timestamp>-<pid>.json` by default
- use `--output` to choose a specific result path

### [`walmart-search`](skills/walmart-search/SKILL.md)

Search Walmart products by keyword.

Use when:

- you want Walmart product results for a keyword
- you want category-specific Walmart results
- you want device, pagination, sorting, facet, or price-bound controls

Features:

- `query` is the only required input
- optional `--device`, `--cat-id`, and `--page`
- optional `--sort`, `--facet`, `--min-price`, and `--max-price`
- supported sort values include `price_low`, `price_high`, `best_seller`, `best_match`, `rating_high`, and `new`
- saves every successful response to `./out/walmart-search-<timestamp>-<pid>.json` by default
- use `--output` to choose a specific result path

### [`walmart-product-reviews`](skills/walmart-product-reviews/SKILL.md)

Fetch Walmart reviews for a known product.

Use when:

- you already have a Walmart `product_id` or `us_item_id`
- you want review pagination, sorting, or star-rating filters
- you want top positive or negative review data

Features:

- requires `--product-id`
- accepts `--product_id`, `--us-item-id`, and `--us_item_id` aliases
- optional `--page`, `--sort`, and `--rating`
- saves every successful response to `./out/walmart-product-reviews-<timestamp>-<pid>.json` by default
- use `walmart-search` first when you only have a product name or keyword

### [`walmart-product-sellers`](skills/walmart-product-sellers/SKILL.md)

Fetch Walmart seller offers for a known product.

Use when:

- you already have a Walmart `product_id` or `us_item_id`
- you want marketplace seller offers, prices, availability, delivery dates, or return policies
- you want store-specific seller availability from a provided `store_id`

Features:

- requires `--product-id`
- accepts `--product_id`, `--us-item-id`, and `--us_item_id` aliases
- optional `--store-id`
- saves every successful response to `./out/walmart-product-sellers-<timestamp>-<pid>.json` by default
- use `walmart-search` first when you only have a product name or keyword

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

### [`google-maps-search`](skills/google-maps-search/SKILL.md)

Search Google Maps places or retrieve a known place.

Use when:

- you want Google Maps results for a query
- you need location-, coordinate-, rating-, price-, opening-state-, or pagination-filtered results
- you have a Google Maps `place_id` or `data_cid`

Features:

- accepts Google Maps search, map-origin, and place-filter fields
- supports `search` and `place` request types
- supports `FREVANA_API_BASE_URL` to override the default API host
- saves results with `--output`

### [`facebook-profile`](skills/facebook-profile/SKILL.md)

Retrieve a Facebook profile by profile ID or username.

Features:

- requires `--profile-id`
- supports `FREVANA_API_BASE_URL` to override the default API host
- saves results with `--output`

### [`google-search`](skills/google-search/SKILL.md)

Search regular Google web results by keyword.

Use when:

- you want Google Search / SERP results for a query
- you want organic results, related searches, related questions, answer boxes, or knowledge graph
- you want country-, language-, location-, result-count-, pagination-, safe-search-, or device-specific Google Search results

Features:

- `q` is the only required input
- optional `--location`, `--gl`, and `--hl`
- optional `--num`, `--start`, `--safe`, and `--device`
- saves every successful response to `./out/google-search-<timestamp>-<pid>.json` by default
- use `--output` to choose a specific result path

### [`google-forums-search`](skills/google-forums-search/SKILL.md)

Search Google Forums results by keyword.

Use when:

- you want forum-style Google results for a query
- you want Reddit, Quora, Stack Overflow, or community discussion results surfaced through Google Forums
- you want country-, language-, device-, pagination-, or date-bounded Google Forums results

Features:

- `q` is the only required input
- optional `--device`, `--hl`, and `--gl`
- optional `--start`, `--start-date`, and `--end-date`
- saves every successful response to `./out/google-forums-search-<timestamp>-<pid>.json` by default
- use `--output` to choose a specific result path

### [`google-patents-search`](skills/google-patents-search/SKILL.md)

Search Google Patents results by query.

Use when:

- you want Google Patents results for a query
- you want patent or patent-application discovery
- you want page, result-count, language, or patent-status filters

Features:

- `q` is the only required input
- optional `--page`, `--num`, `--language`, and `--status`
- saves every successful response to `./out/google-patents-search-<timestamp>-<pid>.json` by default
- use `--output` to choose a specific result path

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

### [`youtube-search`](skills/youtube-search/SKILL.md)

Search YouTube videos by keyword.

Use when:

- you want YouTube search results for a keyword
- you want country- or language-specific YouTube results
- you have an `sp` filter or pagination token

Features:

- `search_query` is the only required input
- optional `--sp`, `--hl`, and `--gl`
- save results with `--output`

### [`reddit-search`](skills/reddit-search/SKILL.md)

Search Reddit link posts by query.

Use when:

- you want Reddit search results for a query
- you want recent or top Reddit link posts
- you have an `after` token from a previous Reddit Search response and want the next page

Features:

- `q` is the only required input
- `type` is fixed to `link`
- optional `--sort` supports `new` and `top`, defaulting to `new`
- optional `--limit` defaults to `25` and is capped at `100`
- optional `--after` continues pagination using `data.after` from the previous response
- uses the local Frevana Chrome Extension session
- first scrapes `https://www.reddit.com/` to warm up the browser session, then scrapes the `search.json` URL
- save results with `--output`

### [`x-topic-search`](skills/x-topic-search/SKILL.md)

Search X/Twitter posts by topic through the local Frevana daemon and Chrome Extension session.

Use when:

- you want X/Twitter posts for a topic, keyword, hashtag, query, or trend
- you want top or live X results
- you have a cursor from a previous X topic result

Features:

- `--topic` is the only required input
- optional `--sort`, `--count`, `--fetch-mode`, `--cursor`, `--timeout`; `--fetch-mode` defaults to `quick`
- optional flags for replies, quotes, and media metadata
- runs bundled `scripts/setup.sh` before every search, matching the original Frevana skill flow
- setup downloads and executes the latest official Frevana setup script, which installs the CLI if missing and starts/checks the daemon
- requires the local Frevana daemon, Chrome Extension connection, and X/Twitter login in Chrome
- save output with `--output`

### [`meta-ads-search`](skills/meta-ads-search/SKILL.md)

Search Meta Ads Library through the local Frevana daemon and Chrome Extension session.

Use when:

- you want Meta/Facebook ad records for a keyword, brand, or advertiser text
- you want to filter Meta Ads Library results by country, active status, or date range
- you want Chrome Extension-backed ad research through the user's connected Chrome session

Features:

- `--keyword` is the only required input; `--query`, `--q`, and `--text` are accepted aliases
- defaults to 20 active ads across all countries (`--country ALL`, `--active-status active`); use `--max-results`, `--country`, or `--active-status` to override those defaults
- optional `--date-from`, `--date-to`, and `--timeout`
- `--country` accepts `ALL` or a two-letter uppercase country code; `--active-status` accepts `active`, `inactive`, or `all`
- runs bundled `scripts/setup.sh` before every search, matching the original Frevana skill flow
- setup downloads and executes the latest official Frevana setup script, which installs the CLI if missing and starts/checks the daemon
- requires the local Frevana daemon and Chrome Extension connection
- save output with `--output`

### [`url-scrape`](skills/url-scrape/SKILL.md)

Scrape any URL through the local Frevana daemon and Chrome Extension session.

Use when:

- you want web page content from a URL
- you want clean Markdown extraction from a page
- you need Chrome Extension-authenticated scraping using the user's logged-in Chrome Extension session

Features:

- `--url` is the only required input
- `--provider` defaults to `url`
- optional `--timeout`
- runs bundled `scripts/setup.sh` before every scrape, matching the original Frevana skill flow
- setup downloads and executes the latest official Frevana setup script, which installs the CLI if missing and starts/checks the daemon
- save output with `--output`

### AI Platform Chrome Extension Skills

Ask AI platforms through the local Frevana daemon and Chrome Extension session.

Skills:

- [`google-search-extension`](skills/google-search-extension/SKILL.md) uses provider `google`
- [`chatgpt-ask`](skills/chatgpt-ask/SKILL.md) uses provider `chatgpt`
- [`gemini-ask`](skills/gemini-ask/SKILL.md) uses provider `gemini`
- [`perplexity-ask`](skills/perplexity-ask/SKILL.md) uses provider `perplexity`
- [`deepseek-ask`](skills/deepseek-ask/SKILL.md) uses provider `deepseek`
- [`doubao-ask`](skills/doubao-ask/SKILL.md) uses provider `doubao`

Use when:

- you want to ask one of these AI platforms a prompt
- you want to search Google through the user's Chrome Extension session
- you want to use the user's logged-in Chrome Extension session
- you want local Frevana Chrome Extension automation rather than API-key access

Features:

- `--prompt` / `--question` may be repeated for multiple prompts
- `--prompt-file` reads one prompt per non-empty line
- `--format` supports `text` or `json`, defaulting to `text`
- optional `--timeout`
- each skill fixes the provider and does not ask for a provider value
- runs bundled `scripts/setup.sh` before every ask, matching the original Frevana skill flow
- setup downloads and executes the latest official Frevana setup script, which installs the CLI if missing and starts/checks the daemon
- save output with `--output`

### Social Publishing Chrome Extension Skills

Publish to social platforms through the local Frevana daemon and Chrome Extension session.

Skills:

- [`publish-twitter-post`](skills/publish-twitter-post/SKILL.md) uses provider `twitter`
- [`publish-facebook-post`](skills/publish-facebook-post/SKILL.md) uses provider `facebook`
- [`publish-linkedin-post`](skills/publish-linkedin-post/SKILL.md) uses provider `linkedin`

Use when:

- the user explicitly asks to publish a final post
- the target is Twitter/X, Facebook, or LinkedIn
- you need to publish with the user's logged-in Chrome Extension session

Features:

- each skill fixes the provider and does not ask for a provider value
- requires final `--text` or `--text-file`
- `publish-linkedin-post` article mode supports `--mode article`, `--title`, and `--cover-image`
- `--format` supports `text` or `json`, defaulting to `text`
- optional `--timeout`
- runs bundled `scripts/setup.sh` before every publish call, matching the original Frevana skill flow
- setup downloads and executes the latest official Frevana setup script, which installs the CLI if missing and starts/checks the daemon
- requires the local Frevana daemon, Chrome Extension connection, and target-platform login in Chrome
- save output with `--output`

### [`reddit-url-mentions`](skills/reddit-url-mentions/SKILL.md)

Check Reddit mentions of one or more URLs through Frevana.

Use when:

- you want to find Reddit posts that mention a specific URL
- you want to check multiple URLs for Reddit mentions (max 10)
- you want to see what subreddits are discussing a particular page

Features:

- `--targets` is the only required input (comma-separated absolute URLs, max 10)
- optional `--tag` for a user-defined task identifier (max 255 chars)
- returns subreddit name, author, post title, permalink, and member count
- URLs with no Reddit mentions return `reddit_reviews: null`
- save results with `--output`

### [`gpt-image-2`](skills/gpt-image-2/SKILL.md)

Generate or edit Frevana-hosted images with `gpt-image-2`.

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

Generate Frevana-hosted images with Nano Banana 2.

Use when:

- the user mentions `Nano Banana 2` or `nano banana`
- you want to generate an image with the lighter Nano Banana model
- you may want to save the result to a file

Features:

- accepts image input via `--prompt` or `--contents`
- returns a hosted image link
- supported options: `--seed`, `--max-output-tokens`, `--response-modality`, `--aspect-ratio`, `--image-size` (`1K`, `2K`, `4K`; numeric values like `1800` and `WxH` values like `1024x1024` are normalized to the nearest tier, using the larger edge for `WxH`; defaults to `1K`)

### [`nano-banana-pro`](skills/nano-banana-pro/SKILL.md)

Generate Frevana-hosted images with Nano Banana Pro.

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

### [`sendgrid-send-email`](skills/sendgrid-send-email/SKILL.md)

Send transactional email through the Twilio SendGrid v3 Mail Send API.

Use when:

- you want to send email with a SendGrid API key
- you need a dry-run payload preview before sending
- you want plain text, HTML, dynamic template, attachment, sandbox, or scheduled-send fields

Features:

- calls `POST /v3/mail/send` directly with `SENDGRID_API_KEY` and a user-provided verified sender
- dry-runs by default and requires `--send` for the actual side effect
- can save the SendGrid API key locally after the first input, and supports later updates with `--api-key <key> --save-api-key`
- automatically includes `custom_args.business_id` for application-side correlation, with `--business-id` override support
- supports multiple recipients, cc, bcc, reply-to, categories, custom args, attachments, global region, and EU region
- queries SendGrid Email Logs with `scripts/query_email_logs.sh` by recipient, optional subject, sent-at lower bound, status, and fuzzy `message_id` matching
- subtracts a 5-second default lookback from `--sent-at` for Email Logs queries to handle SendGrid response/log timestamp skew
- omits subject from suggested status lookups for template sends, because templates can override the final subject
- reports SendGrid HTTP status, message ID metadata, and one suggested prompt example for querying status when available
- points users to <https://frevana.gitbook.io/frevana-docs/email-integrations/sendgrid-integration> when SendGrid configuration is missing

### [`instantly-send-email`](skills/instantly-send-email/SKILL.md)

Send through Instantly's real API V2 workflow paths.

Use when:

- you want cold/outbound first-touch email handled by a prebuilt Instantly campaign
- you want to add a lead to a campaign with `POST /api/v2/leads`
- you want to reply to an existing email with `POST /api/v2/emails/reply`
- you need a dry-run payload preview before the side effect

Features:

- uses `scripts/lead.sh`, `scripts/campaign.sh`, and `scripts/email.sh`
- checks existing leads with `POST /api/v2/leads/list`
- lists or creates campaigns with `GET/POST /api/v2/campaigns`
- creates missing leads with `POST /api/v2/leads`, or moves existing leads with `POST /api/v2/leads/move`
- prompts for campaign `name` and `campaign_schedule` together when creating a campaign
- prompts for lead `email` and selected `campaign_id` together when creating a campaign lead
- checks campaign sending health with `GET /api/v2/campaigns/{id}/sending-status`
- lists emails by lead address with `GET /api/v2/emails`, then replies with `POST /api/v2/emails/reply`
- write actions dry-run by default and require `--send`
- can save the Instantly API key locally after the first input, and supports later updates with `--api-key <key> --save-api-key`
- points users to <https://frevana.gitbook.io/frevana-docs/email-integrations/instantly-integration> when the Instantly API key is missing
- explicitly does not use `POST /api/v2/emails/test` for user-requested sending

### [`mysql-crud`](skills/mysql-crud/SKILL.md)

Inspect, query, and safely change MySQL data through saved profiles.

Use when:

- you want to save database connection details so they do not need to be re-entered
- you need MySQL schema inspection, selects, inserts, updates, deletes, or read-only raw SQL
- you need to connect directly, through an SSH tunnel, or by SSHing to a server and using its remote `DATABASE_URL`

Features:

- stores profiles locally under `~/.config/mysql-crud/profiles/` with `0600` permissions
- supports `direct`, `ssh-tunnel`, and `ssh-remote` modes
- supports remote `.env` lookup for `DATABASE_URL` in `ssh-remote` mode, including `cd` into a remote app directory first
- redacts passwords and full database URLs from profile listings
- blocks writes on `readonly` profiles
- dry-runs `insert`, `update`, and `delete` by default and requires `--execute` for actual writes
- requires `--where` for `update` and `delete` unless explicitly overridden
- saves JSON results under `./out/mysql-crud-*.json`

### [`postgresql-crud`](skills/postgresql-crud/SKILL.md)

Inspect, query, and safely change PostgreSQL data through saved profiles.

Use when:

- you want to save PostgreSQL connection details so they do not need to be re-entered
- you need PostgreSQL schema inspection, selects, inserts, updates, deletes, or read-only raw SQL
- you need table operations in `public` by default, or in another schema with `--schema`
- you need to connect directly, through an SSH tunnel, or by SSHing to a server and using its remote `DATABASE_URL`

Features:

- stores profiles locally under `~/.config/postgresql-crud/profiles/` with `0600` permissions
- supports `direct`, `ssh-tunnel`, and `ssh-remote` modes
- supports remote `.env` lookup for `DATABASE_URL` in `ssh-remote` mode, including `cd` into a remote app directory first
- redacts passwords and full database URLs from profile listings
- blocks writes on `readonly` profiles
- defaults CRUD table operations to schema `public` when only a table name is provided
- can list all non-system schemas with `schema --all-schemas`
- can verify profiles with `configure --test-connection`
- dry-runs `insert`, `update`, and `delete` by default and requires `--execute` for actual writes
- requires both `--execute` and `--allow-raw-write` for raw write SQL
- requires `--where` for `update` and `delete` unless explicitly overridden
- saves JSON results under `./out/postgresql-crud-*.json`

### [`redis-crud`](skills/redis-crud/SKILL.md)

Inspect and safely change Redis keys through saved profiles.

Use when:

- you want to save Redis connection details so they do not need to be re-entered
- you need Redis `PING`, `GET`, `SET`, `DEL`, `HGET`, `HSET`, `HGETALL`, `SCAN`, or guarded raw commands
- you need to connect directly, through an SSH tunnel, or by SSHing to a server and using its remote `REDIS_URL`

Features:

- stores profiles locally under `~/.config/redis-crud/profiles/` with `0600` permissions
- supports `direct`, `ssh-tunnel`, and `ssh-remote` modes
- supports remote `.env` lookup for `REDIS_URL` in `ssh-remote` mode, including `cd` into a remote app directory first
- redacts passwords and full Redis URLs from profile listings
- blocks writes on `readonly` profiles
- dry-runs `SET`, `DEL`, and `HSET` by default and requires `--execute` for actual writes
- requires both `--execute` and `--allow-raw-write` for raw write commands
- supports paginated `SCAN` with `--cursor`, full scans with `--all`, and quoted raw command arguments with repeated `--arg`
- avoids Bash `/dev/tcp`; SSH tunnel port checks use `nc`, `lsof`, `ss`, or `netstat` so macOS and Windows shell environments can work
- can verify profiles with `configure --test-connection`
- saves JSON results under `./out/redis-crud-*.json`

### [`mongodb-crud`](skills/mongodb-crud/SKILL.md)

Inspect and safely change MongoDB documents through saved profiles.

Use when:

- you want to save MongoDB connection details so they do not need to be re-entered
- you need MongoDB `ping`, database listing, collection listing, `find`, `count`, `insert`, `update`, `delete`, or guarded raw JavaScript evaluation
- you need to connect directly, through an SSH tunnel, or by SSHing to a server and using its remote `MONGODB_URI`

Features:

- stores profiles locally under `~/.config/mongodb-crud/profiles/` with `0600` permissions
- supports `direct`, `ssh-tunnel`, and `ssh-remote` modes
- supports remote `.env` lookup for `MONGODB_URI` in `ssh-remote` mode, including `cd` into a remote app directory first
- redacts passwords and full MongoDB URIs from profile listings
- blocks writes on `readonly` profiles
- accepts MongoDB filters, documents, updates, projections, and sort options as JSON strings
- dry-runs `insert`, `update`, and `delete` by default and requires `--execute` for actual writes
- requires both `--execute` and `--allow-raw-write` for raw write JavaScript
- can verify profiles with `configure --test-connection`
- saves JSON results under `./out/mongodb-crud-*.json`

### [`sqlite-crud`](skills/sqlite-crud/SKILL.md)

Inspect and safely change local SQLite database files through saved profiles.

Use when:

- you want to save a local SQLite file path so it does not need to be re-entered
- you need SQLite table/column inspection, selects, inserts, updates, deletes, or read-only raw SQL
- you only need local file access, without SSH, remote `.env`, host, user, password, or tunnel behavior

Features:

- stores profiles locally under `~/.config/sqlite-crud/profiles/` with `0600` permissions
- supports local SQLite file paths only
- does not add `--readonly` by default; writes are allowed only after dry-run plus explicit `--execute`
- supports explicit `--path` usage when no profile/default profile exists, and saves that path to the default profile for later commands
- never scans the repository, home directory, temp directory, or filesystem to discover SQLite files; the user must provide the path
- requires the configured file to exist, avoiding accidental empty database creation from a mistyped path
- blocks writes on `readonly` profiles
- dry-runs `insert`, `update`, and `delete` by default and requires `--execute` for actual writes
- requires both `--execute` and `--allow-raw-write` for raw write SQL
- requires `--where` for `update` and `delete` unless explicitly overridden
- can verify profiles with `configure --test-connection`
- saves JSON results under `./out/sqlite-crud-*.json`

## Requirements

- Frevana auth skill: `bash`, `frevana` or `npm`, browser/manual access to the authorization URL, and the correct npm/private package source if the CLI is unavailable when login starts.
- Amazon, eBay, Home Depot, Walmart, Google Ads Transparency Center, Google Search, Google Forums, Google Patents, Google News, Google Related Questions, Google Trends, Google Shopping, Google Shopping Light, Google Immersive Product, YouTube Search, and Reddit URL Mentions skills: `bash`, `curl`, `python3`, `FREVANA_TOKEN`.
- Chrome Extension skills: `bash`, `curl`, `python3`, bundled `scripts/setup.sh`, network access to the official Frevana setup URL, local `frevana` binary or network access to GitHub Releases when setup needs to install it, Frevana daemon, Chrome Extension connection, and login to the target site/platform in Chrome when required.
- SendGrid email skill: `bash`, `curl`, `python3`, `SENDGRID_API_KEY`.
- Instantly email skill: `bash`, `curl`, `python3`, `INSTANTLY_API_KEY`.
- MySQL CRUD skill: `bash`; plus local `mysql` for `direct` and `ssh-tunnel`; plus `ssh`, remote `bash`, and remote `mysql` for `ssh-remote`.
- PostgreSQL CRUD skill: `bash`; plus local `psql` for `direct` and `ssh-tunnel`; plus `ssh`, remote `bash`, and remote `psql` for `ssh-remote`.
- Redis CRUD skill: `bash`; plus local `redis-cli` for `direct` and `ssh-tunnel`; plus `ssh`, remote `bash`, and remote `redis-cli` for `ssh-remote`.
- MongoDB CRUD skill: `bash`; plus local `mongosh` for `direct` and `ssh-tunnel`; plus `ssh`, remote `bash`, and remote `mongosh` for `ssh-remote`.
- SQLite CRUD skill: `bash`; plus local `sqlite3` with JSON output support.
- Frevana image/report skills: `bash`, `curl`, `python3`, `FREVANA_TOKEN`.

## Local Script Conventions

- Prefer the script in each skill's `scripts/` directory over ad hoc API calls.
- For API-backed scripts, let scripts read `FREVANA_TOKEN` from the environment unless you intentionally pass a one-time `--token`.
- Treat bearer tokens as secrets. Do not paste them into logs, docs, or shared examples.
- Most search scripts save successful responses to `./out/<skill>-<UTC timestamp>-<pid>.json` by default.
- Use `--output` only when you need a deterministic result path.
- For follow-up parsing or summaries, read the saved JSON file instead of calling the same endpoint again.

## Usage

After installation, use the skill through your agent. If your agent supports repo-level instructions, also load `AGENTS.md`.

Example prompts:

```text
Authenticate Frevana CLI on this machine. If `frevana login` is unavailable, install it and retry.
Search Amazon for wireless earbuds
Fetch Amazon product details for B0D5XWJQ5R
Get Amazon keyword demand for wireless earbuds,gaming headset in United States
Search eBay for vintage watch
Search Home Depot for cordless drill with country=us and delivery_zip=10001
Search Walmart for wireless earbuds sorted by price_low with min_price=25 and max_price=100
Get Walmart product reviews for product_id 5689919121
Get Walmart product sellers for product_id 10543894 and store_id 5888
Search Google for coffee with location=Austin, Texas, United States gl=us hl=en
Search Google Forums for vibe coding with gl=us and hl=en
Search Google Patents for (Coffee) with status=GRANT and language=en
Search Google News for artificial intelligence
Search Google Ads Transparency Center for ads from frevana.com
Expand Google Related Questions with next_page_token eyJvbnMiOiIxMDA0MSI...
Search Google Trends for home treadmill with geo=US and date=today 12-m
Search Google Shopping for wireless earbuds with gl=US and hl=en
Fetch Google Immersive Product details with page_token eyJlaSI6Im5ZVmxaOX...
Search Google Shopping Light for wireless earbuds with gl=US and hl=en
Search YouTube for mrbeast with gl=us and hl=en
Search Reddit for mentions of https://example.com
Configure mysql-crud profile frevana-prod through SSH alias fr, cd to /server/frevana-server-prod, and use .env DATABASE_URL as readonly
Use mysql-crud to inspect the users table schema
Use mysql-crud to query users where email is test@example.com
Configure postgresql-crud profile prod through SSH alias app-prod, cd to /server/app, and use .env DATABASE_URL as readonly
Use postgresql-crud to inspect the public.users table schema
Use postgresql-crud to query users where email is test@example.com
Use postgresql-crud to query auth.users where email is test@example.com
Configure redis-crud profile prod through SSH alias app-prod, cd to /server/app, and use .env REDIS_URL as readonly
Use redis-crud to get session:123
Use redis-crud to scan keys matching session:*
Configure mongodb-crud profile prod through SSH alias app-prod, cd to /server/app, and use .env MONGODB_URI as readonly
Use mongodb-crud to list collections in the app database
Use mongodb-crud to find users where email is test@example.com
Configure sqlite-crud profile local with path /Users/me/app/data.sqlite
Use sqlite-crud to inspect tables
Use sqlite-crud to query users where email is test@example.com
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

Some skills may also include:

- `tests/` - Script-level verification when runnable tests are available
- `evals/` - Reusable skill evaluation prompts

## License

MIT
