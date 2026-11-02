# Threads search inputs

Only query is required. Omitted options stay omitted; expand's described backend default is true, so query-only can permit relaxation. Choose explicit false for a user's exact-phrase-only request. The helper validates types/enums/bounds and rejects include=engagement with limit>20. Backend validation owns detailed dates/feature combinations. CLI hyphens map to snake_case JSON fields.

## Scope, windows and shape

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `query` / `--query` | string | Nonempty search keyword or phrase. Preserve the exact string; do not invent word pairs or borrow another platform's query operators. |
| `limit` / `--limit` | integer 1–100 | At-least target of unique posts, not page size. Backend reads whole result windows until target or exhaustion; can return more, or fewer on exhaustion. Omit for one window. Never truncate overage, round the target or assume no continuation. |
| `cursor` / `--cursor` | string | Opaque pagination.next_cursor from a compatible prior response, copied verbatim. Carries date bounds; next older window cannot escape the period. A cursor request is never query-relaxed, irrespective of expand. Do not decode/construct/coerce it or change period/query while continuing. |
| `expand` / `--expand` | boolean | Backend default true relaxes an unrecognized query into adjacent word pairs and merges results, billing each relaxed search returning in-period posts. False searches exact phrase only. Ignored with cursor. If credits cover false but not the requested call, backend may use false and report data._warnings instead of 402. Do not recreate the expanded call or infer a lower charge without returned accounting. |
| `trim` / `--trim` | boolean | Real stripped shape, same described base price: source carries id/text/shortcode/likes/timestamp/author; media, reply/share/view counts, topic tag, pinned flag and quoted post become null. Preserve nulls rather than zero/false or local refill; select only when those fields are unnecessary. Combination precedence with enrichment is not specified. |
| `include` / `--include` | string engagement | Explicit native enrichment for at most first 20 posts: engagement.views and post.flags.pinned, with possible display-name fill. Incompatible with limit>20; helper rejects before submission without changing either option. No channel token or CSV combinations. |
| `start_date` / `--start-date` | string | Inclusive native search-period start, YYYY-MM-DD per description. Pagination does not walk past it; relaxed searches discard older posts. Undated posts are outside the native period. This is a declared field, not a since alias. |
| `end_date` / `--end-date` | string | Inclusive native search-period end, YYYY-MM-DD per description. Pagination starts here and relaxed searches discard newer posts. This is a declared field, not an until alias. |
| `since` / `--since` | string | Inclusive UTC midnight date or ISO timestamp. Per-window row filter, keeps undated rows and does not end this nonchronological walk. CLI --published-after/--from-date map here; --start-date does not. |
| `until` / `--until` | string | Inclusive whole UTC date or ISO timestamp. Filters newer rows, keeps undated rows and does not end the walk. CLI --published-before/--to-date map here; --end-date does not. |
| `async` / `--async` | boolean/integer/string | JSON exact variants: booleans, integers 0/1, strings "true"/"false"/"1"/"0". CLI true/false becomes boolean and 1/0 integer. Independent of fixed wrapper response_mode=json. |
| `seen` / `--seen` | string | Caller-selected 1–64 letters/digits/`.`/`_`/`-` per description. Account-private row-ID memory expires 24h after last use, removes repeats under the same ID, reports data.walk.repeats. Separate from client_task_id; never generate automatically. |

One helper operation can include backend collection explicitly requested by limit; it never creates extra helper page requests. Ordinary explicit continuation uses a new state/client ID, exact opaque cursor and unchanged query/options, retaining cursor provenance. A READY task is not complete search coverage while a cursor remains. Do not infer exhaustion from empty/old filtered windows. Native date bounds differ from since/until: the backend enforces the native period because source dates are ranking hints, and excludes undated posts. Do not map declared native fields into row filters, locally enforce dates or guess precedence if both were supplied.

Described base price is 1 credit per result window (about 15–20 posts), with unused window budget refunded; whole windows can exceed the target and are not trimmed. Sequential windows add latency (roughly 3.4s each in the description), and historical production counts/timings are not guarantees. Include adds a described 3–12s and up to 20 fresh per-post charges: 1 credit if fresh lookup fills views or display name; 10-minute cached lookups/no published views are described as free, with pin still filled when views are unavailable. Preserve returned accounting; missing values or posts after the first 20 do not authorize more lookups. Keep runtime deadlines large enough for the requested scope instead of changing payload after timeout.

Seen discounts only page price as ceil(page credits × new rows / page rows); all-repeat pages are described as free. Joined-data charges apply to new rows separately and are not discounted. Preserve actual billing/window/lookup metadata rather than assuming all calls or enrichment are free. Date filters retain normal consumed-window costs.

Only static noncolliding CLI aliases above are implemented. Publish_time/max_age_days and undeclared alias JSON keys are rejected despite descriptions mentioning them. Resolve requested relative dates before invocation with timezone/date context and retain the original payload on retry. No sort/sort_by/sort_rows, after, max_cursor, max_items, page, region/country, min_views, user profile or media download controls are declared.

## Relevance, goal fitting and previews

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `relevance` / `--relevance` | score/filter | Omission can still add free query relevance without dropping/reordering. Score explicitly waits for judgments; filter drops unrelated rows under data.relevance.dropped_ids. Unjudged rows remain with null relevance; pagination is unchanged. |
| `relevant_to` / `--relevant-to` | string | Custom judgment topic with relevance, up to 200 characters per description, instead of query. Does not rewrite search query. Adds 1 credit per started 25 newly judged rows; prior same-topic judgments/cached pages described as free. |
| `relevance_threshold` / `--relevance-threshold` | string | Probability 0–1, described default 0.5. Lower keeps more rows. Preserve string; no numeric type or formal bounds declared. |
| `fit` / `--fit` | string goal | Retains relevant/uncertain content plus first/last blocks, stubs the rest. Preserve data.held_back IDs/recall ID; no recall API supplied. |
| `goal` / `--goal` | string | Objective required for meaningful fit=goal, up to 300 characters per description. |
| `fit_tokens` / `--fit-tokens` | integer | Soft retained-content budget; uncertain/first/last blocks may exceed it. No numeric bounds declared. |
| `dry_run` / `--dry-run` | string 1 | Preview without fetching/judging, described as 0 credits. Preserve data.estimate rows_expected/rows_cached/label_credits_min/max/base_credits; never automatically proceed to a paid fetch. |

## Labels and exclusions


| JSON / CLI flag | Type | Meaning |
| --- | --- | --- |
| `label` / `--label` | string CSV | Adds named labels alongside defaults. Options described below. `none` disables default judgments. No token enum is declared; the backend remains authoritative. |
| `judgments` / `--judgments` | string `on` or `off` | Server defaults to on: free sponsored/intent/niche judgments, with complete/partial/skipped status and pending rows. They do not alter existing fields, drop or reorder rows. Pending labels may be null until a later read. Off disables those additions; the helper does not add this option by default. |
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
