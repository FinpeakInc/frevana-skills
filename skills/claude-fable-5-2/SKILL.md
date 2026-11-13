---
name: claude-fable-5-2
description: Use Anthropic Claude Fable 5.2 through Frevana for frontier reasoning, long-context analysis, coding, structured output, and tool-enabled work.
---

# Claude Fable 5.2

Generate responses through Frevana's Responses API (`POST /openrouter/v1/responses`) using the fixed model `anthropic/claude-fable-5.2`. Do not override the model or silently fall back after failure.

Return the validated response JSON unchanged by default, or use `--text-only` to return the extracted assistant text.

## Model characteristics

- 1,000,000-token context window and up to 128,000 output tokens.
- Supports reasoning effort, tools, tool choice, and structured output.
- Accepts text, image, and file inputs through native Responses API message objects; use `--raw-payload-file` for multimodal or advanced request shapes.
- Does not expose `temperature` or `top_p` because the verified model endpoints do not declare those parameters.

## Execution

1. Require `--input`, `--input-file`, or `--raw-payload-file`.
2. Use `--input` for plain text or a JSON message array. Use `--instructions` for developer instructions.
3. Choose a reasoning effort only when useful: `low`, `medium`, `high`, `xhigh`, or `max`.
4. Use `--tools` / `--tools-file` and `--tool-choice auto|none` for tool-enabled requests. The helper sends definitions but never executes client tools.
5. Run once. Bearer authentication requires `FREVANA_TOKEN` / `--token`; `FREVANA_API_KEY` / `--api-key` is only an optional supplemental header and never replaces the token. Optional Agent App attribution uses `FREVANA_AGENT_APP_INSTANCE_ID`.
6. Preserve the response ID and incomplete state. The helper never retries or automatically continues a truncated response; use a new authorized request when continuation is appropriate.

The helper requires Bash, curl, and Python 3. It defaults to `https://ai-factory.frevana.com`; `FREVANA_API_BASE_URL` may select a user-requested local or staging server.

## Options

- `--model`: fixed model; alias `claude-fable-5.2` is accepted
- `--input`, `--prompt`: prompt text or JSON message array
- `--input-file`: file containing prompt text or a JSON message array
- `--instructions`, `--instructions-file`: developer instructions
- `--reasoning-effort`: `low`, `medium`, `high`, `xhigh`, `max`
- `--max-output-tokens`: integer `1..128000`
- `--previous-response-id`: previous response ID for a compatible stateful continuation
- `--session-file`: load/save the last successful response ID and fixed model
- `--new-session`: ignore existing session state and replace it only after success
- `--no-session`: disable session loading and saving
- `--service-tier`: `default` only
- `--tools`, `--tools-file`: JSON tool array
- `--tool-choice`: `auto` or `none`
- `--raw-payload-file`: complete JSON body; model is normalized to the fixed model and streaming is rejected
- `--token`: required Frevana Bearer token
- `--api-key`: optional supplemental API key header, valid only alongside Bearer authentication
- `--text-only`, `-t`: print only extracted assistant text
- `--output`: save the full response JSON

Fast and priority service tiers are rejected by the current server. Session files store only response identity, not the transcript. Reusing a session created for another model or loading malformed state fails; use `--new-session` to intentionally start fresh.

## Commands

```bash
bash <skill-path>/scripts/create_response.sh \
  --input "Review this architecture for consistency and failure isolation" \
  --instructions "State assumptions and rank risks by severity." \
  --reasoning-effort high --max-output-tokens 16000 \
  --output ./out/fable-review.json

bash <skill-path>/scripts/create_response.sh \
  --session-file ./out/fable-session.json \
  --input "Design a multi-region event processing system" \
  --text-only
```

## Results and failures

A successful result is a Responses API object with an `id`, status, output items, usage, and Frevana billing fields when supplied by the server. In text-only mode, the helper prefers `output_text` and otherwise joins output text content in order.

Do not automatically retry transport errors, timeouts, or ambiguous billing failures. For HTTP errors, the helper prints the original response body. If `status=incomplete`, preserve the partial result and response ID; the helper returns nonzero so truncation cannot be mistaken for completion. After any successful API response, stdout is emitted before optional local output/session persistence so a local write failure cannot erase the paid result.

The server must have the matching model record from `src/sqls/2026-11-13-add-seedream-fable-seedance-flash.sql`. A local skill does not establish production deployment or provider access.
