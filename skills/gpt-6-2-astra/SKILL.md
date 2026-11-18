---
name: gpt-6-2-astra
description: Use OpenAI GPT-6.2 Astra (gpt-6.2-astra) through the Frevana Responses API when the user requests this model for demanding software engineering, deep reasoning, and professional analysis.
---

# GPT-6.2 Astra

Use the bundled `scripts/create_response.sh` with `POST https://ai-factory.frevana.com/openai/v1/responses`. The script fixes the model to `gpt-6.2-astra`, including when a raw payload supplies another model.

## Run a request

Requires Bash, curl, Python 3, and the `FREVANA_TOKEN` environment variable. The script sends it as a Bearer token for single requests and interactive chat.

```bash
bash <skill-path>/scripts/create_response.sh \
  --input "Design a migration plan for this service and analyze data consistency risks." \
  --reasoning-effort high \
  --text-only --output ./out/gpt-6-2-astra-response.json
```

- Use `--input` or `--prompt` for text or a Responses input array. Use `--input-file` for UTF-8 text or JSON input, including messages with `input_image` content. The model returns text and structured Responses items.
- Use `--instructions` or `--instructions-file` for developer instructions. Use `--tools` or `--tools-file` for a JSON array of tool definitions and `--tool-choice` for a choice string or JSON object. To continue after a client function call, submit a `function_call_output` item with the original `call_id`.
- Use `--raw-payload-file` for a complete JSON object, including options such as `text.format` for structured output. Explicit CLI fields take precedence. The helper handles synchronous, foreground requests.
- The script prints full response JSON by default. Use `--text-only` (or `-t`) to extract text when present, and `--output` to save full JSON independently of the stdout format. The script preserves partial responses and reports `incomplete_details.reason` on stderr, including in interactive chat. Summarize the result unless the user requests raw JSON or final text.
- Set `--agent-app-instance-id` to send `x-frevana-agent-app-instance-id`. The fallback is `FREVANA_AGENT_APP_INSTANCE_ID`, then `X_FREVANA_AGENT_APP_INSTANCE_ID`. `FREVANA_API_BASE_URL` can override the API origin.

## Model parameters

- `--reasoning-effort` accepts `low`, `medium`, `high`, `xhigh`, and `max`. Start with `low` or `medium` and let the API choose its default when omitted.
- `--max-output-tokens` accepts integers from 16 to 128000, including reasoning tokens. The Frevana model catalog configures 8192 when omitted. The model has a 1,050,000-token context window and a 922,000-token input limit.
- `--service-tier` forwards `auto`, `default`, `flex`, `fast`, `priority`, or `ultrafast`. Availability depends on the model, gateway, and account.
- Omit `temperature`, `top_p`, `top_logprobs`, and the include value `message.output_text.logprobs`. Reasoning effort `none` is unsupported.

## Continue a conversation

Frevana forces `store:false`. Use the same `--session-file PATH` on each turn and supply just the new text or input items. The helper replays prior input and output items in order, requests encrypted reasoning for replay, and retains developer instructions. Pass request options such as tools again on subsequent turns. The helper makes one request per turn and leaves execution of client tool calls to the caller.

Use `--session NAME` for a model-specific file under `FREVANA_SESSION_DIR` (default `~/.frevana/sessions`). Automatic session names come from `FREVANA_SESSION_ID`, `CONVERSATION_ID`, or `SESSION_ID`. Use `--chat` for interactive chat. `--no-session` disables persistent history and keeps chat history only for the current run.

Session files contain prompts, replies, tool items, and image references or inline data. They use private permissions and atomic replacement and are bound to the model and API origin. Use one invocation per session file at a time. The `--output` and `--session-file` paths must point to different files. Use `--new-session` to intentionally reset a session or replace a legacy ID-only file after a successful response. Stored `conversation` and `previous_response_id` are unsupported.

If saving fails after a response, use the private recovery file path printed by the helper to retrieve the response and history. A recovery file with `schema_version:1` can continue with the next turn via `--session-file`. Keep this file to avoid submitting the same turn again.
