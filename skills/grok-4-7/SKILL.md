---
name: grok-4-7
description: Use xAI Grok 4.7 (x-ai/grok-4.7) through Frevana for coding, agentic tasks, knowledge work, and web-grounded research, including optional web search.
---

# Grok 4.7

Generate text through `POST https://ai-factory.frevana.com/openrouter/v1/responses` with the fixed model `x-ai/grok-4.7`. Use the bundled helper; it requires `bash`, `curl`, `python3`, and `FREVANA_TOKEN` (or `--token`). A Frevana API key can supplement the Bearer token, but cannot replace it on this route.

Return the API response JSON without rewriting it. Use `--text-only` only when the user wants answer text; keep full JSON with `--output` when citations, tool calls, or accounting matter.

## Basic Use

```bash
bash <skill-path>/scripts/create_response.sh \
  --input "Analyze this design and explain the tradeoffs." \
  --reasoning-effort high \
  --max-output-tokens 8192 \
  --output ./out/grok-4-7-response.json
```

The model has a 500,000-token context window and an advertised maximum output of 450000 tokens, also bounded by the remaining context and selected endpoint. Frevana defaults to 8192 output tokens when omitted; this budget includes reasoning and visible text. Reasoning is mandatory. Supported `--reasoning-effort` values are `low|medium|high|xhigh`; the upstream default is `high` when omitted. Sampling support can vary by endpoint.

## Enable Web Search / 开启联网搜索

Search is disabled by default. Decide whether to enable it for each user request:

- Enable search when the user asks to search or browse, needs current information, or needs verification or sources beyond the material already provided. Use `--web-search` with automatic engine selection unless the user requests a specific search mode.
- Leave search disabled for rewriting, translation, summarizing supplied content, coding, calculations, or analysis that can be completed from the available context without outside information.
- An explicit instruction such as “不要联网”, “不要搜索”, “仅使用我提供的内容”, or “do not browse” takes precedence over an inferred need for fresh information or additional sources. Do not search or retrieve outside web content through another tool. If the requested fact cannot be verified under that constraint, state the limitation and use only the available context.
- For a no-search request, omit both `--web-search` and `--web-search-engine` (even `auto` enables search). Prepare the effective request without search-capable entries in `--tools`, `--tools-file`, or `--raw-payload-file`, and without the legacy `plugins` entry `{"id":"web"}`. Preserve unrelated tools and options. A prompt saying not to search is insufficient while search configuration remains enabled.

Ordinary session files do not persist search settings. An interactive `--chat` invocation does forward its startup search settings on every turn; before handling a no-search turn, restart the chat invocation without search configuration, reusing the local history file if needed.

When search is needed, add **`--web-search`**. Mentioning “search the web” only in the prompt does not configure the search tool.

```bash
bash <skill-path>/scripts/create_response.sh \
  --input "Search the web for the latest research on battery recycling. Cite sources and publication dates." \
  --web-search \
  --output ./out/grok-4-7-search.json
```

The flag adds `"tools": [{"type": "openrouter:web_search"}]`, preserving the exact model ID. It merges with an existing search tool without duplicating it or dropping function tools and unrelated plugins. The gateway executes this server tool when the model chooses to search; enabling it does not guarantee a search on every request. Do not append `:online` to this skill's model ID; Frevana validates the fixed catalog model.

To **prefer native search**, use `--web-search-engine native` (which also enables search). This sets `tools[].parameters.engine="native"`; default/`auto` delegates selection to the gateway. Native availability depends on the selected endpoint and workspace settings; the server tool may fall back to an external engine when native search is unavailable. Leave `provider` unset for normal use and testing so the server/upstream can select an available endpoint:

```bash
cat > ./search-request.json <<'JSON'
{
  "model": "x-ai/grok-4.7",
  "input": "Search the web for recent battery recycling research and cite sources.",
  "tools": [{"type": "openrouter:web_search", "parameters": {"engine": "native"}}],
  "max_output_tokens": 8192
}
JSON
bash <skill-path>/scripts/create_response.sh \
  --raw-payload-file ./search-request.json \
  --output ./out/grok-4-7-native-search.json
```

For custom search settings, use `--tools '[{"type":"openrouter:web_search","parameters":{"engine":"auto","max_results":3}}]'` or `--tools-file ./tools.json`. `--web-search-engine auto` explicitly sets the server tool's `parameters.engine` to `auto`. Search flags preserve other parameters on an existing search tool. `max_results` applies to external search engines and is ignored by native search.

The older `plugins: [{"id":"web"}]` search approach is deprecated in the Responses documentation. `--plugins` / `--plugins-file` remain available for explicit compatibility and other plugins; do not combine a legacy `web` plugin with these search switches. `web_search_options` alone is not this skill's search switch.

Search can incur additional charges. Preserve native citation annotations and usage/cost fields from the full response; do not infer that a search occurred solely from enabling the tool, and do not fabricate sources if none are returned. For Grok, web search and X/Twitter search are separate capabilities; this flag does not explicitly opt into X search.

Live validation on 2026-11-16 confirmed that default/auto search and `--web-search-engine native` requests completed when `provider` was left unset. Returned `web_search_call` items included completed searches, and `url_citation` annotations had valid nonempty text spans. Preserve those annotations when displaying the answer.

One run reported three searches despite `parameters.max_uses=1` and top-level `max_tool_calls=2`; another reported four searches. Do not treat those parameters as a hard cap on native queries. Inspect the returned search usage. Leave endpoint selection to Frevana for normal use and testing; provider pinning constrains model routing and does not universally disable search-engine fallback.

## Inputs and Options

- `--model`: `x-ai/grok-4.7` or alias `grok-4-7`; other models and suffix variants are rejected, including in raw JSON.
- `--input` / `--prompt`: text or a JSON array of Responses input items. `--input-file` reads the same formats and supports multimodal item arrays without local media conversion or downloads.
- `--instructions` / `--instructions-file`: developer instructions.
- `--reasoning-effort`: `low|medium|high|xhigh`. Use `reasoning.effort` in raw payloads; disabling reasoning or supplying a fixed reasoning-token budget is rejected.
- `--temperature`: number `0..2`; `--top-p`: number `0..1`.
- `--max-output-tokens`: integer `1..450000`.
- `--tools` / `--tools-file`: JSON array of tool objects. Responses function definitions use flat `type`, `name`, `description`, and `parameters` fields rather than a nested `function` wrapper.
- `--tool-choice`: `auto`, `none`, `required`, or `'{"type":"function","name":"lookup"}'`. The helper returns client function calls; it never executes them. Supply `function_call_output` in the next input after the caller executes a tool.
- `--web-search`, `--web-search-engine auto|native`: configure the `openrouter:web_search` server tool as described above.
- `--plugins`, `--plugins-file`: explicit JSON plugin configuration, including legacy web-plugin compatibility; CLI plugins replace raw `plugins`. Use only one of these options.
- `--raw-payload-file`: JSON object for advanced parameters such as `provider`, `text.format` structured output, and `include`. CLI request options override corresponding raw fields; the effective payload is validated. Provider-specific parameters remain subject to endpoint validation; use `provider.require_parameters=true` when they must be honored.
- `--service-tier`: `default` only. Frevana rejects fast/priority routes.
- `--session-file`: persist full local history; `--session NAME` uses `~/.frevana/sessions` (or `FREVANA_SESSION_DIR`). A supplied `FREVANA_SESSION_ID`, `CONVERSATION_ID`, or `SESSION_ID` also selects a model-specific file.
- `--new-session` / `--new`: intentionally start fresh; saved history is replaced only after a successful response. `--no-session` disables loading/saving explicit or environment-selected sessions.
- `--chat`: interactive terminal chat; it forwards request/search settings on each turn and retains history for the run even without a persistent file.
- `--token` / `FREVANA_TOKEN`: required Bearer authentication. `--api-key` / `FREVANA_API_KEY`: optional supplemental header.
- `--agent-app-instance-id` / `FREVANA_AGENT_APP_INSTANCE_ID` / `X_FREVANA_AGENT_APP_INSTANCE_ID`: forward `x-frevana-agent-app-instance-id` for attribution.
- `--text-only` / `-t`: print extracted answer text. `--output`: save full JSON to a different path from the session file.
- `FREVANA_API_BASE_URL`: override the Frevana origin; default `https://ai-factory.frevana.com`.

## SDK Compatibility

These CLI switches belong to this helper. Frevana's HTTP extension fields may be absent from a compatible SDK's standard request/tool types; missing autocomplete does not determine transport support. The current Frevana Server forwards these request fields without removing extensions. Use an explicitly extended request type or the SDK's low-level `client.post("/responses", {body: ...})`. In compatible Python clients, extra HTTP fields go in `extra_body`; do not invent `extra_body` as a Node.js request option.

## Conversations and Failures

The route is stateless: every request sends `store:false`. Use local history rather than `previous_response_id` or stored `conversation`, which the helper rejects. Session files retain input/output items in order, including tool items and returned reasoning data, plus instructions, and are bound to model and API origin. They contain conversation content; writes are atomic with private permissions. Invalid, legacy ID-only, or mismatched sessions stop before transport; use `--new-session` to intentionally replace them.

```bash
bash <skill-path>/scripts/create_response.sh \
  --session-file ./out/grok-4-7-session.json \
  --input "Search for recent battery recycling research." --web-search
bash <skill-path>/scripts/create_response.sh \
  --session-file ./out/grok-4-7-session.json \
  --input "Compare the methods in those sources." --text-only
```

Search and other request options are not saved as session defaults; pass them again when the next turn should use them. The helper never automatically retries, executes client tools, or continues truncated output. HTTP/transport errors and failed or invalid response objects return nonzero. An `incomplete` response is returned intact; inspect `status` and `incomplete_details` before claiming completion. A local save failure after a valid response reports a recovery file with the response/history; use it instead of resubmitting the same billable turn.

## Validation

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s <skill-path>/tests -v
```

Tests use mocked transport and make no paid requests. Model parameters were checked against the Frevana Server catalog migration dated 2026-11-16; this does not establish production deployment status.
