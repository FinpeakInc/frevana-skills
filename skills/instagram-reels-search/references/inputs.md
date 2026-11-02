# Instagram reel search inputs

Only `query` is required. Omitted options stay omitted. The bundled schema declares all accepted JSON fields, exact enums, types and bounds. The helper validates those rules; the backend owns detailed feature combinations and date-string semantics. CLI aliases are normalized before payload persistence; unknown JSON keys are rejected.

## Search, time and pagination

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `query` / `--query` | string | Nonempty keyword or phrase. Preserve the user's original query; do not append market names yourself. |
| `cursor` / `--cursor` | string | Opaque `pagination.next_cursor` from the preceding result. Copy unchanged; omit for page 1. |
| `page` / `--page` | integer | Native page parameter. Prefer universal cursor; never send both. No numeric bound is declared, so the backend owns page-number validity. |
| `since` / `--since` | string | Inclusive start date at UTC midnight (`YYYY-MM-DD`) or ISO 8601 timestamp. Older rows are omitted; undated rows are retained. The search is not chronological: reaching an older row does not end pagination. CLI aliases `--published-after`, `--start-date`, `--from-date` become `since`. |
| `until` / `--until` | string | Inclusive end: the entire UTC date or an ISO timestamp. Newer rows are omitted and undated rows remain; the walk does not stop at that date. CLI aliases `--published-before`, `--end-date`, `--to-date` become `until`. |
| `date_posted` / `--date-posted` | string enum | `last-week`, `last-month` or `last-year`. Preserve the literal value rather than recomputing dates. |
| `max_age_days` / `--max-age-days` | integer 1–3650 | Keeps sufficiently recent `post.published_at` values; unknown dates are discarded. This is a declared field and stays an integer, even though the date description also discusses it as a date alias. |
| `min_views` / `--min-views` | integer ≥0 | Keeps `post.engagement.views` at or above the floor; unknown view counts are discarded. Filtering happens after a page is fetched, so it does not make walked pages free. |
| `sort_rows` / `--sort-rows` | string `views` | Backend orders kept rows by descending views within the result it produces; unknown counts go last. The helper does not sort or merge additional requests. |
| `seen` / `--seen` | string | User-chosen deduplication ID: 1–64 letters/digits or `._-` per description. Account-private row-ID memory expires 24 hours after its last use. Reuse for related searches only when requested; it is independent of task/client identity. |
| `async` / `--async` | boolean/integer/string | Exact JSON variants: booleans, integers 0/1 or strings `"true"`, `"false"`, `"1"`, `"0"`. CLI true/false becomes boolean; 1/0 becomes integer. JSON input preserves string variants. Independent of wrapper `response_mode="json"`. |

A date-filtered page can be empty and still have `next_cursor`. One helper invocation never walks extra pages. For an explicitly requested next page, keep filters and `seen` when applicable, pass the cursor unchanged and use a new operation state/client ID. Retries of that page keep its original state. Preserve `data.walk.discarded`, `repeats` and `request_ids` when returned. The schema's description mentions `max_pages`, but it is not a declared field: do not send it. `publish_time` is also undeclared; use `since` or a declared date field, without inventing ambiguous relative-date conversions.

The supplied description discounts the page price under `seen` by the fraction of new rows, rounded up; a page consisting entirely of repeats has no base-page charge. It does not discount joined data. Do not promise a total free request when enrichment/labels are requested; report returned accounting.

## Market localization and creator data

Both market fields accept exactly **ES, MX, DE, BR, KR, FR, ZA, NG, KE, AE, SA**. Codes are case sensitive; do not silently replace an unsupported country with a supported one.

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `region` / `--region` | market enum | Localizes the search query, normally by adding a market-specific name unless already localized. It favors relevant creators but does not prove creator location. The actual query appears in `data.region.query_sent`. Same base price as a plain call according to the supplied description. |
| `country` / `--country` | market enum | Keeps creators whose published account country matches. It implies full creator-card lookups and, if region is absent, query localization. Preserve `data.country.kept`, `dropped_other`, `dropped_unknown` and hydration accounting. Do not add `include` in the client payload: the backend records the implied enrichment. |
| `include` / `--include` | string | Documented values: `creator`, `country`, `creator,country`. `channel`, `audio` and `tags` are not documented for this endpoint. Enable only on request. |

The description states country filtering costs a base 1 credit plus 2 per creator looked up, kept or not, up to 61 per page. It can return `items: []` and `country_no_match` while still charging lookups; a page empty solely due to failed creator lookups is described as free. Use region alone for localization without those lookups. These are supplied endpoint descriptions, not verified live billing.

Creator enrichment adds available account country, follower/following/post counts, public contact fields, missing name/avatar/verification. Declared country is not filming location; unknown country remains null. The supplied description prices `include=creator` at 2 extra credits per creator lookup, shares lookups among multiple reels from one creator, refunds unfound creators and makes a creator looked up in the prior 15 minutes free. `include=country` adds only declared country: 1 extra credit when returned, refunded for unavailable country/creator and free for a creator looked up in the prior 30 days. `creator,country` is equivalent to creator. Preserve returned values and refund/cache accounting; do not infer identity, location or contact information.

## Relevance, goal fitting and previews

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `relevance` / `--relevance` | `score` or `filter` | Default query relevance is free and may be pending/null without dropping rows. Explicit score waits for judgments; filter also removes irrelevant rows and lists dropped IDs. Unjudged rows remain. Pagination does not change. |
| `relevant_to` / `--relevant-to` | string | With relevance: disambiguates the topic, up to 200 characters per description. Custom-topic judgment can add credits; do not infer it from `goal` or automatically enable it. |
| `relevance_threshold` / `--relevance-threshold` | string | With relevance filtering: kept-row probability threshold 0–1, description default 0.5. Lower retains more; higher retains fewer. Preserve the string type. |
| `fit` / `--fit` | string `goal` | Retain rows/fields needed for the supplied goal, uncertain blocks and first/last blocks; stub other content. Preserve `data.held_back` IDs and recall ID. No recall route was supplied: do not invent a recall call. |
| `goal` / `--goal` | string | Required for meaningful goal fitting; user's objective, up to 300 characters per description. |
| `fit_tokens` / `--fit-tokens` | integer | Soft retained-content token budget with goal fitting. Uncertain/first/last blocks can exceed it. No numeric bounds are declared. |
| `dry_run` / `--dry-run` | string `1` | Cost preview without fetching the page or judging rows; description states 0 credits. Preserve `data.estimate` and do not automatically start a paid search afterward. |

Query-topic relevance is described as free; `relevant_to` adds 1 credit per started 25 newly judged rows, with same-topic cached judgments free. Preserve dropped/pending IDs and native relevance scores. A relevance score is a model judgment, not a guarantee.

## Labels and exclusions


| JSON / CLI flag | Type | Meaning |
| --- | --- | --- |
| `label` / `--label` | string CSV | Adds named labels alongside defaults. Options described below. `none` disables default judgments. No token enum is declared; the backend remains authoritative. |
| `judgments` / `--judgments` | string `on` or `off` | Server defaults to on: free sponsored/intent/niche judgments and query relevance, with complete/partial/skipped status and pending rows. They do not alter existing fields, drop or reorder rows. Pending labels may be null until a later read. Off disables those additions; the helper does not add this option by default. |
| `brand` / `--brand` | string | For `label=mention`, the target brand/product, up to 300 characters per description. Missing brand makes mention skip with `label_mention_needs_brand`, without billing that label. Do not invent the target. |
| `brand_description` / `--brand-description` | string | For mention: one sentence disambiguating the target brand/product. |
| `offer` / `--offer` | string | With intent: 1–2 sentences describing the offer, up to 300 characters; adds `fits_offer`. Without it that field is null. |
| `label_evidence` / `--label-evidence` | string `1` | With explicit labels: adds verbatim supporting quote and sentence index to `computed.labels_evidence`; absent/null if there is no single supporting sentence. |
| `exclude` / `--exclude` | string CSV | `engagement_bait` with quality drops probability ≥0.8; `ai_style` with ai_style drops pattern count ≥2; `ai_written` with ai_written drops likely rows or those reaching the configured threshold. Preserve `data.labels.dropped_ids`. Unjudged rows and too-short AI-written rows are never dropped. |
| `ai_written_threshold` / `--ai-written-threshold` | string | Only with ai_written label and exclusion: probability 0–1, description default 0.95. A lower 0.71 threshold also includes possible cases and more human false positives. Omit unless requested. |

Label meanings:

- `sponsored`: probability of paid/gifted promotion, disclosure markers, possible undisclosed promotion and promoted account. These are review signals, never findings.
- `mention`: target relevance, five-level sentiment (null if unrelated), sarcasm, aspect and first-hand use.
- `intent`: caption purpose, buyer/seller likelihood, urgency and optional offer fit.
- `niche`: caption-only taxonomy assignment with confidence; no video inspection. Insufficient/uncertain captions can have null labels.
- `quality`: checkable detail, engagement bait, rage bait (writing style, not viewpoint), secondhand content and post aim.
- `ai_style`: six judged writing patterns plus text counts. Describes style rather than authorship; people can match it. Short text is counted without judged patterns.
- `ai_written`: calibrated model probability and likely/possible/unlikely/too_short level. Model names identify a scale; shorter text is less certain. This is not proof of authorship.
- `injection`: flags text attempting to direct an AI system. It does not itself drop or rewrite rows.

The description states sponsored/intent/niche are free; mention, quality, ai_style, intent with offer, and injection add 1 credit per started 25 newly judged posts. It does not explicitly specify the ai_written label rate: use a requested preview or returned accounting instead of guessing. Cached pages and previously labeled posts are described as free for labeling; do not infer that every future page fetch is free. Preserve `data.labels` billing information and row-level nulls/warnings.
