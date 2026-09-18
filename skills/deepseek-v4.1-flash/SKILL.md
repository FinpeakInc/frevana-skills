---
name: deepseek-v4.1-flash
description: Use when the user wants high-speed, cost-effective inference, rapid code generation, data extraction, high-throughput summarization, or conversational tasks using DeepSeek V4.1 Flash (deepseek/deepseek-v4.1-flash) through the Frevana OpenRouter Responses API.
---

# DeepSeek V4.1 Flash

Generate responses through Frevana's OpenRouter Responses API (`POST /openrouter/v1/responses`) using `deepseek/deepseek-v4.1-flash`.

Return the validated API response JSON unchanged, or use `--text-only` when the user requests only the final text output.

## Model Characteristics

- Model ID: `deepseek/deepseek-v4.1-flash` (DeepSeek V4.1 Flash model via OpenRouter).
- Best suited for high-speed inference, rapid code drafting, high-throughput summarization, data extraction, and cost-effective conversational workflows.
- For frontier reasoning or complex multi-turn architecture, consider `anthropic/claude-opus-5` or `gpt-5.6-sol`. For balanced enterprise workflows, consider `anthropic/claude-sonnet-5`.

## What This Skill Needs

- `input` or `prompt` via `--input` or `--input-file` (or raw JSON payload via `--raw-payload-file`)
- optional developer system instructions via `--instructions` or `--instructions-file`
- optional reasoning effort: `--reasoning-effort <low|medium|high>`
- optional sampling: `--temperature`, `--top-p`, `--max-output-tokens`
- optional multi-turn conversation continuation: `--previous-response-id`
- optional session persistence: `--session-file` or `--session`
- optional tools: `--tools` or `--tools-file`, `--tool-choice`
- optional service tier: `--service-tier <auto|default|flex|priority>`
- authentication: `FREVANA_TOKEN` (or `--token`) / `FREVANA_API_KEY` (or `--api-key`)
- optional attribution: `FREVANA_AGENT_APP_INSTANCE_ID` (or `X_FREVANA_AGENT_APP_INSTANCE_ID`, or `--agent-app-instance-id`) sent as `x-frevana-agent-app-instance-id`
- `curl`, `bash`, and `python3`

## Allowed Options

- `--model`: `deepseek/deepseek-v4.1-flash` (default; aliases `deepseek-v4.1-flash`, `deepseek-4.1-flash` accepted)
- `--input`, `--prompt`: user prompt string or JSON message array
- `--input-file`: file path containing input prompt or JSON message array
- `--instructions`: system developer instructions
- `--instructions-file`: file path containing system instructions
- `--reasoning-effort`: `low`, `medium`, `high`
- `--temperature`: `0.0 - 2.0`
- `--top-p`: `0.0 - 1.0`
- `--max-output-tokens`: positive integer
- `--session`: session name (e.g. default, chat1) saved under `~/.frevana/sessions`
- `--session-file`: path to session file to automatically save and restore conversation context across calls
- `--new-session`, `--new`: reset conversation context and start a fresh session
- `--no-session`: disable session persistence for this run
- `--previous-response-id`: ID of a previous response for multi-turn conversations
- `--chat`: start an interactive chat session in the terminal
- `--service-tier`: `auto`, `default`, `flex`, `priority`
- `--tools`: JSON array string defining available tools/functions
- `--tools-file`: path to JSON file defining tools
- `--tool-choice`: tool choice behavior (`auto`, `required`, `none`, or JSON)
- `--raw-payload-file`: path to raw JSON request body
- `--api-key`: Frevana API key (sent as `X-API-Key`)
- `--token`: Frevana Bearer token (sent as `Authorization: Bearer`)
- `--agent-app-instance-id`: Agent App instance/team ID (sent as `x-frevana-agent-app-instance-id`)
- `--text-only`, `-t`: output only the response text
- `--output`: save full response JSON to path

## Commands

```bash
# Fast text completion or code generation
bash <skill-path>/scripts/create_response.sh \
  --input "Write a fast Python script to parse and aggregate access logs by status code" \
  --text-only

# Fast structured extraction with instructions
bash <skill-path>/scripts/create_response.sh \
  --input "Extract name, company, and email from: John Doe (Acme Corp) - john@acme.com" \
  --instructions "Return strict JSON with keys: name, company, email." \
  --output ./out/extraction.json

# Multi-turn conversation with automatic session persistence (Recommended)
bash <skill-path>/scripts/create_response.sh \
  --session-file ./out/deepseek_session.json \
  --input "Let's design a high-throughput cache cluster" \
  --text-only

bash <skill-path>/scripts/create_response.sh \
  --session-file ./out/deepseek_session.json \
  --input "How should we handle cache invalidation?" \
  --text-only

# Multi-turn conversation by previous response ID
bash <skill-path>/scripts/create_response.sh \
  --input "What about Redis Sentinel vs Cluster mode?" \
  --previous-response-id "resp_abc123" \
  --text-only

# Interactive terminal chat
bash <skill-path>/scripts/create_response.sh --chat
```
