# Instagram profile post inputs

Only `handle` is required. Unspecified options are omitted. All string fields remain strings, including the literal `"1"` flags and `ai_written_threshold`. The helper validates the bundled schema's declared types, enums and numeric bounds; the server owns feature-combination and date-string validation. Collect meaningful paired options from the user rather than automatically adding features.

## Fields and filters

| JSON / CLI flag | Type | Meaning |
| --- | --- | --- |
| `handle` / `--handle` | string | Username without `@`. |
| `since` / `--since` | string | Inclusive start: `YYYY-MM-DD` at UTC midnight or an ISO 8601 timestamp. Older non-pinned posts end the walk: no next cursor and `pagination.stopped_at="since"`. Pinned posts do not end this date walk. |
| `until` / `--until` | string | Inclusive end: a whole UTC date or ISO 8601 timestamp. Newer rows are omitted, but older pages can follow; undated rows remain. CLI aliases `--published-before`, `--end-date`, `--to-date` map to `until`. Those aliases are not JSON properties. |
| `recent_days` / `--recent-days` | integer 1–3650 | Keeps the last N days. Removes older pinned posts too; reaching older posts stops pagination. Preserve the integer on retries instead of recomputing an absolute date. |
| `stop_at_id` / `--stop-at-id` | string | A known post ID or URL. Stop before that post and the rows after it; `stopped_at="known_id"`, without next cursor. Pinned posts are not stop points. `stopped_at="end"` means the list ran out; null means more may remain. |
| `cursor` / `--cursor` | string | Copy `pagination.next_cursor` verbatim from the prior page. Omit for page 1. |
| `next_max_id` / `--next-max-id` | string | Native cursor, supported by schema; prefer universal `cursor`. Never send both. |
| `exclude_pinned` / `--exclude-pinned` | boolean | True excludes confirmed pins, at the same page price. Unknown pin states remain and generate warnings. Without it pin state is often null; cursor pages may mark rows false because pins normally occur only on page 1. |
| `trim` / `--trim` | boolean | Requests a lighter record at the same price. A trimmed page served without fallback omits `post.ext.coauthors` and may have null pin state. Do not promise that every response is narrower: the API may return full fields from a fallback source. |
| `async` / `--async` | boolean, integer or string | Schema accepts booleans, integers 0/1, or strings `"true"`, `"false"`, `"1"`, `"0"`. CLI true/false becomes boolean and 1/0 becomes integer; use JSON input to preserve string variants. Independent of wrapper response mode. |

Each page still has its normal page cost even if filtering removes rows. Never promise that the returned page covers the account's full history.

## Goal fitting and enrichment

| JSON / CLI flag | Type | Meaning |
| --- | --- | --- |
| `fit` / `--fit` | string `goal` | With `goal`, retain rows/fields relevant to that goal, uncertain content, and the first/last block; replace other content with stubs. `data.held_back` reports held IDs and a recall ID for rereading the full cached page without extra charge. No recall endpoint was supplied: preserve it without inventing an API call. |
| `goal` / `--goal` | string | Required for meaningful `fit=goal`; user's objective, up to 300 characters per description. |
| `fit_tokens` / `--fit-tokens` | integer | Soft retained-content token cap, only with `fit=goal`. First/last and uncertain content can exceed it. No numeric bounds are declared; do not invent them. |
| `include` / `--include` | string | Documented tokens: `audio`, `tags`, or `audio,tags`. Audio adds music fields to video rows via a second lookup: 1 extra credit per video filled, refunded if unreadable; photos/carousels are not looked up. Tags adds tagged usernames: 1 extra credit per post with tags, refunded for no tags or failed lookup. Adds latency; preserve `data.hydration` usage details. `channel` is not documented. |
| `dry_run` / `--dry-run` | string `1` | Requests a cost preview without fetching a page or judging rows. Description states 0 credits; `data.estimate` can include expected/cached rows, label credit min/max and base credits. Never automatically proceed to the real fetch. |

Enrichment is opt-in. Never hide the possibility of extra feature costs or report an estimate as settled billing.

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
