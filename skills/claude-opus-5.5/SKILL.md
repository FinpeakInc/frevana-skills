---
name: claude-opus-5.5
description: Use when the user wants demanding reasoning, large codebase changes, code review, scientific analysis, or long-horizon agentic work with Anthropic Claude Opus 5.5 (anthropic/claude-opus-5.5) through the Frevana OpenRouter Responses API.
---

# Claude Opus 5.5

Generate responses through Frevana's OpenRouter Responses API (`POST /openrouter/v1/responses`) using `anthropic/claude-opus-5.5`.

Return the validated API response JSON unchanged for a single response. When automatic continuation occurs, return the stitched result with original responses under `continuation.responses`, or use `--text-only` for the joined text.

## Model Characteristics

- Model ID: `anthropic/claude-opus-5.5` (Anthropic Claude Opus 5.5 via OpenRouter).
- Best suited for demanding reasoning, multi-step changes in large codebases, code review, scientific analysis, and long-horizon agentic work.
- Use `--reasoning-effort` to trade off depth, latency, and cost; this model uses adaptive thinking.

## What This Skill Needs

- `input` or `prompt` via `--input` or `--input-file` (or raw JSON payload via `--raw-payload-file`)
- optional developer system instructions via `--instructions` or `--instructions-file`
- optional reasoning effort: `--reasoning-effort <low|medium|high|xhigh|max>`
- optional sampling: `--temperature` (provider-dependent), `--max-output-tokens`
- optional multi-turn conversation continuation: `--previous-response-id`
- optional session persistence: `--session-file` or `--session`
- optional tools: `--tools` or `--tools-file`, `--tool-choice`
- optional service tier: `--service-tier default`
- authentication: `FREVANA_TOKEN` (or `--token`) / `FREVANA_API_KEY` (or `--api-key`)
- optional attribution: `FREVANA_AGENT_APP_INSTANCE_ID` (or `X_FREVANA_AGENT_APP_INSTANCE_ID`, or `--agent-app-instance-id`) sent as `x-frevana-agent-app-instance-id`
- `curl`, `bash`, and `python3`

## Allowed Options

- `--model`: `anthropic/claude-opus-5.5` (default; aliases `claude-opus-5.5`, `claude-ops-5.5` accepted)
- `--input`, `--prompt`: user prompt string or JSON message array
- `--input-file`: file path containing input prompt or JSON message array
- `--instructions`: system developer instructions
- `--instructions-file`: file path containing system instructions
- `--reasoning-effort`: `low`, `medium`, `high`, `xhigh`, `max`
- `--temperature`: `0.0 - 2.0` (currently available only on some OpenRouter endpoints)
- `--max-continuations`: maximum extra requests after output truncation, `0..32`, default `8` (`0` disables automatic continuation)
- `--max-output-tokens`: integer from 1 to 128000
- `--session`: session name (e.g. default, chat1) saved under `~/.frevana/sessions`
- `--session-file`: path to session file to automatically save and restore conversation context across calls
- `--new-session`, `--new`: start fresh and replace the saved session only after a successful response
- `--no-session`: skip loading and saving a session, even when `--session-file` is supplied
- `--previous-response-id`: ID of a previous response for multi-turn conversations
- `--chat`: start an interactive chat session in the terminal
- `--service-tier`: `default`
- `--tools`: JSON array string defining tools; availability varies by OpenRouter endpoint
- `--tools-file`: path to JSON file defining tools
- `--tool-choice`: `auto` or `none` (string or JSON object); forced tool use is unsupported
- `--raw-payload-file`: path to raw JSON request body
- `--api-key`: Frevana API key (sent as `X-API-Key`)
- `--token`: Frevana Bearer token (sent as `Authorization: Bearer`)
- `--agent-app-instance-id`: Agent App instance/team ID (sent as `x-frevana-agent-app-instance-id`)
- `--text-only`, `-t`: output only the response text
- `--output`: save full response JSON to path

The skill accepts only default service tier. The current Frevana Server checkout rejects fast and priority tiers for Claude 5.5. OpenRouter endpoints for these models require reasoning and do not support `top_p` or forced tool choice; temperature support varies by provider. For raw payloads, use `reasoning.effort` rather than a fixed reasoning-token budget. Session files store the last response ID and model, not the conversation transcript; continuation uses OpenRouter's `previous_response_id`. Reusing a file for a different model or loading a malformed file fails with an error; use `--new-session` to intentionally start over.

## Automatic Output Continuation

When `status=incomplete` and `incomplete_details.reason=max_output_tokens`, the script carries the original input and generated assistant text into another request and asks for only the remaining content. For stateless OpenRouter calls, automatic continuation sends message history. If the initial request uses `previous_response_id` through a stateful compatible API, retain that original ID as the earlier-conversation anchor on every continuation; do not switch to the latest truncated response ID, because the current turn is already included in message history. Preserve the original `store` setting as well. Request instructions, model, token limit, tools, sampling, authentication, and attribution are preserved; this works with `--no-session`, raw non-streaming payloads, and chat mode.

Completed hosted tool items (such as web search) are replayed as context and preserved in the combined output. A completed client function call still requires a corresponding `function_call_output`; the script never executes client tools automatically.

For raw JSON structured-output requests (`text.format` or `response_format`), the initial request retains the format constraint. Subsequent requests generate plain-text suffixes, with the original format included in the continuation prompt. Validate the final concatenated JSON syntax (and object shape for `json_object`); malformed output returns nonzero with partial results preserved. Full JSON Schema validation is the caller's responsibility after continuation.

Text chunks are concatenated without inserting separators, preserving split words, JSON, and code. The stitched JSON uses the last response ID/status, combined `output_text` and message `output`, summed numeric usage fields, and `continuation.responses` containing every original response. Single responses remain unchanged. Continuation adds latency and billable requests; the model may still repeat content despite the continuation instruction.

Stop after `--max-continuations` extra requests, an empty truncated text, an unfinished hosted tool or a client tool still awaiting its result, a different incomplete reason, or an API/transport error. Preserve available partial text/JSON on stdout and in `--output`, return nonzero, and do not advance the saved session after a failed chain. Raw `stream=true` is unsupported. On success, persist the final response ID using the existing session behavior. Existing explicit response-ID sessions are separate from this stateless continuation; OpenRouter currently rejects non-null `previous_response_id` unless the configured API supplies its own state support.

## Commands

```bash
# Frontier reasoning and research
bash <skill-path>/scripts/create_response.sh \
  --input "Evaluate the theoretical scalability bounds and consensus guarantees of DAG-based vs BFT blockchain protocols" \
  --instructions "Provide a rigorous comparative breakdown with formal definitions." \
  --reasoning-effort high \
  --output ./out/opus-analysis.json

# Multi-turn conversation with automatic session persistence (Recommended)
bash <skill-path>/scripts/create_response.sh \
  --session-file ./out/opus_session.json \
  --input "I am architecting a multi-tenant telemetry ingestion platform for 10M events/sec" \
  --text-only

bash <skill-path>/scripts/create_response.sh \
  --session-file ./out/opus_session.json \
  --input "Detail the Kafka partitioning, Flink state backend, and storage tiering strategy" \
  --text-only

# Multi-turn conversation by previous response ID
bash <skill-path>/scripts/create_response.sh \
  --input "Summarize the failure modes and recovery procedures for the architecture" \
  --previous-response-id "resp_opus_123" \
  --text-only

# Interactive terminal chat
bash <skill-path>/scripts/create_response.sh --chat
```
