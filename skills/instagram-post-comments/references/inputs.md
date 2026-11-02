# Instagram post comment inputs

Only `url` is required. Unspecified options stay omitted. The helper validates the schema's declared types, enums and numeric bounds, the supported post/share URL paths and since/sort compatibility. The backend owns other detailed date/feature-combination validation; do not invent missing goals or paired labels.

## Post, ordering and pagination

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `url` / `--url` | string | Full Instagram `/p/`, `/reel/`, `/reels/`, `/tv/` or `/share/` link. Preserve its complete string, including query/fragment. HTTP(S) Instagram hosts without embedded credentials are accepted. Share links are resolved by the backend; profile-share refusals return a handle per description, and dead links are described as free 404s. Do not resolve, normalize or fetch another endpoint locally. |
| `sort` / `--sort` | `top` or `recent` | Top is the backend default and ranks the most-liked head; deeper pages can repeat comments. Recent is newest-first and is appropriate for an explicitly requested whole-thread walk. The helper adds no default. Keep the same ordering with continuation cursors. |
| `since` / `--since` | string | Inclusive start: `YYYY-MM-DD` at UTC midnight or ISO 8601 timestamp. The backend selects recent when sort is omitted; another explicit sort is invalid. Reaching older comments ends the walk with no next cursor and `pagination.stopped_at="since"`. Undated rows remain. CLI aliases `--published-after`, `--start-date`, `--from-date` become since. |
| `until` / `--until` | string | Inclusive end: a whole UTC date or ISO timestamp. Newer rows are omitted but the walk does not stop; undated rows remain. CLI aliases `--published-before`, `--end-date`, `--to-date` become until. |
| `cursor` / `--cursor` | string | Copy previous `pagination.next_cursor` verbatim. No cursor construction/decoding or numeric page inference. Use a new state/client ID for an explicitly requested continuation. |
| `scan_pages` / `--scan-pages` | integer 1–3 | Description default 1. Explicit 2/3 asks the backend to read that many pages, remove cross-page duplicates and sort by likes (top) or newest-first (recent). The helper does not issue multiple create requests or perform deduplication itself. Preserve `data.scan` read/billed/end metadata. |
| `safe_url` / `--safe-url` | boolean | True requests URL-safe profile-picture links suitable for embedding. No durable-media lifetime guarantee is supplied; no local fetching/hosting. |
| `async` / `--async` | boolean/integer/string | Exact JSON variants: booleans, integers 0/1, strings `"true"`, `"false"`, `"1"`, `"0"`. CLI true/false becomes boolean and 1/0 integer. JSON input preserves string variants. Independent of wrapper JSON response mode. |

A scan is one task operation and can still have a continuation cursor. The supplied description prices each scanned page that adds comments at 5 credits; a page containing only repeats is not billed. Do not report a fixed total solely from the requested scan count: use returned accounting. Do not automatically increase scan_pages or switch ordering after a sparse/repeated result. Date filters do not erase normal page costs. Preserve stop/cursor metadata and do not claim full thread or reply coverage from a READY task alone. All pricing statements come from the supplied description, not verified live billing.

## Comment judgments and exclusions

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `label` / `--label` | string CSV | Comment presets: sentiment, spam, question, purchase_intent, complaint, toxic, low_quality, injection. Defaults keep running when explicit labels are added. `none` disables default judgments. No token enum is declared; the backend remains authoritative. |
| `judgments` / `--judgments` | `on` or `off` | Server default on adds free sentiment/question/purchase_intent/complaint judgments, with complete/partial/skipped/pending metadata where returned. Defaults do not change existing fields or drop/reorder rows. Off disables additions; the helper does not set it automatically. |
| `exclude` / `--exclude` | string CSV | Documented spam/low_quality exclusions require the same explicit preset in label. Probability ≥0.8 drops the comment and records its ID in `data.labels.dropped_ids`. Unjudged comments are never dropped. Do not automatically add a paid label to make exclusion work; collect the intended paired options first. |
| `label_evidence` / `--label-evidence` | string `1` | With explicit labels, returns supporting verbatim quote/sentence index under `computed.labels_evidence.<preset>`. Absent/null when no single supporting sentence exists. |

Each comment can have `computed.labels` probabilities 0–1, or null when unjudged. Sentiment, question, purchase_intent and complaint are described as free even when explicitly requested. Spam, toxic, low_quality and injection add 1 credit per started 25 newly judged comments; previously labeled comments and cached pages are described as free for judgment. Preserve `data.labels` billing/status and nulls; do not infer a zero total page cost from free labels. Injection flags attempts to direct an AI system and does not itself remove or rewrite rows. These are model judgments, not findings about people. Post-specific sponsored/intent/niche/ai-style presets must not be inherited as comment defaults.

## Goal fitting and preview

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `fit` / `--fit` | string `goal` | With goal, retains useful rows/fields, uncertain content and first/last blocks; stubs the rest. Preserve `data.held_back` IDs and recall ID. No recall route was supplied: do not invent a follow-up API call. |
| `goal` / `--goal` | string | Required for meaningful fit=goal; user's objective up to 300 characters per description. |
| `fit_tokens` / `--fit-tokens` | integer | Soft retained-content budget with fit=goal. Uncertain/first/last blocks may exceed it. No numeric bounds are declared. |
| `dry_run` / `--dry-run` | string `1` | Cost preview without fetching a page or judging rows, described as 0 credits. Preserve `data.estimate` (including expected/cached rows, label-credit min/max and base credits when returned). Never automatically proceed to a paid operation. |

Date aliases are CLI-only and are normalized into since/until before the original request is saved. Although the date description mentions publish_time/max_age_days, neither is a declared input property here, and no ambiguous relative-time alias is exposed. There is no include, limit, page, max_pages, seen, account/region selector, post-media download or cache-age control. Accept only the 16 declared fields; do not import unrelated options from other skills.
