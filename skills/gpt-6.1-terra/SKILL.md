---
name: gpt-6.1-terra
description: Use when the user wants visual reasoning, computer-use planning, focused coding, and clear writing using OpenAI GPT-6.1 Terra (gpt-6.1-terra) through the Frevana Responses API.
---

# GPT-6.1 Terra

Generate responses using fixed model `gpt-6.1-terra` through Frevana's OpenAI Responses API: `POST https://ai-factory.frevana.com/openai/v1/responses`.

The helper follows the `gpt-6` workflow: prompt or JSON input, developer instructions, tools, local-history sessions, interactive chat, and JSON or text output. Summarize the result unless the user asks for raw JSON or only the final text (`--text-only`).

## Model and parameters

- Use for interpreting images and technical drawings, planning screen interactions, focused code fixes, and drafting or revising text.
- Supports text and image input, with text output. Supply image input as a Responses message array through `--input-file` or `--raw-payload-file`.
- `--model` accepts only `gpt-6.1-terra`; the helper also forces that model in raw payloads.
- `--reasoning-effort`: `none`, `low`, `medium` (default), `high`, `xhigh`, `max`. Omitted effort is left to the server.
- `--max-output-tokens`: integer 1–128000; omitted limits are left to the server.
- `--service-tier`: `auto`, `default`, `flex`, `priority`. These are upstream options; availability through Frevana depends on the gateway and account. Do not silently retry with a different tier.
- `--temperature` (0–2) and `--top-p` (0–1) are available only when `reasoning.effort` is explicitly `none`. Omitted effort defaults to `medium`, so sampling is rejected unless `none` is selected. The same check applies to raw payloads.

Model constraints were checked against [the official model page](https://developers.openai.com/api/docs/models/gpt-6.1-terra) and [the GPT-6 parameter guidance](https://developers.openai.com/api/docs/guides/latest-model) on 2026-11-03. These sources describe upstream behavior, not a live Frevana availability check.

## Requirements and options

Requires `bash`, `curl`, `python3`, and Frevana authentication. Use `FREVANA_TOKEN` / `--token` for `Authorization: Bearer`, or `FREVANA_API_KEY` / `--api-key` for `X-API-Key`. Explicit flags override the corresponding environment values. An OpenAI API key is not used by this Frevana endpoint.

- `--input`, `--prompt`: prompt text or a JSON message array.
- `--input-file`: UTF-8 prompt or JSON input file.
- `--instructions`, `--instructions-file`: developer instructions.
- `--tools`, `--tools-file`: JSON tool definitions; `--tool-choice`: `auto`, `required`, `none`, or JSON. Returned client tool calls still need a caller-supplied tool implementation; the helper does not execute them.
- `--raw-payload-file`: complete JSON object; explicit CLI fields override corresponding raw fields. Requests always force `store:false`, including raw payloads. Use non-streaming, foreground requests; stored `conversation` and `previous_response_id` are rejected.
- `--session-file`: save and replay local conversation history. With a session, supply only the new turn or new tool-result items; the helper prepends earlier input and output items.
- `--session`: named session under `~/.frevana/sessions`; automatic session identity can also come from `FREVANA_SESSION_ID`, `CONVERSATION_ID`, or `SESSION_ID`. `FREVANA_SESSION_DIR` overrides the directory. Automatic filenames include the model.
- `--previous-response-id`: recognized only to return an explicit error. Frevana forces `store:false`, so an upstream response ID cannot recover context; use a local session file.
- `--new-session`, `--new`: intentionally start with empty history and replace the old file only after a successful response. This also lets you replace a legacy ID-only or damaged file.
- `--no-session`: disable persistent session loading and saving, including an explicit session file. In chat mode, retain history only in the temporary current-run session and discard it on exit.
- `--chat`: interactive terminal chat with local-history replay, using the selected session or a temporary session for the current run.
- `--agent-app-instance-id`: attribution header `x-frevana-agent-app-instance-id`; otherwise read `FREVANA_AGENT_APP_INSTANCE_ID`, then `X_FREVANA_AGENT_APP_INSTANCE_ID`.
- `--text-only`, `-t`: print extracted response text. `--output`: save the full response JSON, including when text-only output is selected.
- `FREVANA_API_BASE_URL`: optional API origin override, with trailing slashes normalized. The `/openai/v1/responses` route stays fixed.

## Local conversation state

Each request uses `store:false`. When a local session is enabled, the helper sends earlier input/output items followed by the new input. It saves every returned output item in order, including assistant phase, encrypted reasoning, hosted tool calls, and client function calls. Return client tool results as new `function_call_output` items with the original `call_id`; the helper never runs tools automatically. The helper requests `reasoning.encrypted_content` alongside any caller-supplied `include` values for compatibility. See [OpenAI's stateless reasoning guidance](https://developers.openai.com/api/docs/guides/reasoning#preserve-reasoning-without-stored-responses).

Session files now contain conversation content, including image references or inline image data, plus developer instructions. They use private file permissions (0600) and atomic replacement. Authentication headers and API keys are not saved. Instructions persist until explicitly overridden or reset; other request options, including tool definitions, must be passed again on later non-chat calls. Request-level `instructions` are reused, rather than inserted repeatedly into message history.

The versioned file is bound to the model and API origin. Legacy response-ID-only files cannot reconstruct the conversation and fail with an explanation; use a new file or intentionally pass `--new-session`. Invalid state stops before any API call. Run only one invocation per session file at a time. A state change detected during a request stops persistence rather than overwriting another turn.

API errors and failed responses do not update the session or existing output. If local persistence fails after a valid response, the helper returns nonzero and prints a private recovery-file path containing the response and completed history; keep that file and do not resubmit the same turn. A recovery file with `schema_version:1` can be used directly as `--session-file` to continue with the next turn.

The helper makes one request per turn, with no automatic retries, history truncation, summarization, or output continuation. History grows until explicitly reset and is subject to the model's context limit. With `--no-session`, callers can manage history themselves by passing the full input array.

## Commands

```bash
bash <skill-path>/scripts/create_response.sh \
  --input "Review this API design and suggest focused improvements." \
  --reasoning-effort high \
  --output ./out/gpt-6.1-terra-response.json

# Continue a conversation using the same session file
bash <skill-path>/scripts/create_response.sh \
  --session-file ./out/gpt-6.1-terra-session.json \
  --input "Review this API design and suggest focused improvements." \
  --text-only

bash <skill-path>/scripts/create_response.sh \
  --session-file ./out/gpt-6.1-terra-session.json \
  --input "Rewrite the recommendations as a concise implementation checklist." \
  --text-only

bash <skill-path>/scripts/create_response.sh --chat
```

## Offline validation

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s <skill-path>/tests -v
```

All HTTP transport in the tests is mocked; validation does not generate billable model requests.
