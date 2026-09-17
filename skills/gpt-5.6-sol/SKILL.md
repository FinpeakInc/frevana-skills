---
name: gpt-5.6-sol
description: Use when the user wants frontier reasoning, advanced coding, complex mathematical/scientific research, or autonomous agent workflows using OpenAI GPT-5.6 Sol (gpt-5.6-sol) through the Frevana Responses API.
---

# GPT-5.6 Sol

Generate responses through Frevana's OpenAI Responses API (`POST /openai/v1/responses`) using `gpt-5.6-sol`.

Return the validated API response JSON unchanged, or use `--text-only` when the user requests only the final text output.

## Model Characteristics

- Model ID: `gpt-5.6-sol` (OpenAI GPT-5.6 flagship frontier model).
- Best suited for deep reasoning, complex system architecture, autonomous code generation, cybersecurity analysis, and multi-step agentic planning.
- For high-volume or lightweight tasks, use `gpt-5.6-luna`. For balanced cost/throughput, use `gpt-5.6-terra`. For next-generation frontier intelligence, use `gpt-6`.

## What This Skill Needs

- `input` or `prompt` via `--input` or `--input-file` (or raw JSON payload via `--raw-payload-file`)
- optional developer system instructions via `--instructions` or `--instructions-file`
- optional reasoning effort: `--reasoning-effort <low|medium|high>`
- optional sampling: `--temperature`, `--top-p`, `--max-output-tokens`
- optional multi-turn conversation continuation: `--previous-response-id`
- optional tools: `--tools` or `--tools-file`, `--tool-choice`
- optional service tier: `--service-tier <auto|default|flex|priority|ultrafast>`
- authentication: `FREVANA_TOKEN` (or `--token`) / `FREVANA_API_KEY` (or `--api-key`)
- optional attribution: `FREVANA_AGENT_APP_INSTANCE_ID` (or `X_FREVANA_AGENT_APP_INSTANCE_ID`, or `--agent-app-instance-id`) sent as `x-frevana-agent-app-instance-id`
- `curl`, `bash`, and `python3`

## Allowed Options

- `--model`: `gpt-5.6-sol` (default)
- `--input`, `--prompt`: user prompt string or JSON message array
- `--input-file`: file path containing input prompt or JSON message array
- `--instructions`: system developer instructions
- `--instructions-file`: file path containing system instructions
- `--reasoning-effort`: `low`, `medium`, `high`
- `--temperature`: `0.0 - 2.0`
- `--top-p`: `0.0 - 1.0`
- `--max-output-tokens`: positive integer
- `--session-file`: path to session file to automatically save and restore conversation context across calls
- `--previous-response-id`: ID of a previous response for multi-turn conversations
- `--chat`: start an interactive chat session in the terminal
- `--service-tier`: `auto`, `default`, `flex`, `priority`, `ultrafast`
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
# Complex reasoning and coding
bash <skill-path>/scripts/create_response.sh \
  --input "Design a high-throughput distributed rate-limiter in Go using sliding window logs and Redis" \
  --instructions "Provide production-grade code with error handling, metrics, and architecture diagrams." \
  --reasoning-effort high \
  --output ./out/sol-response.json

# Multi-turn conversation with automatic session persistence (Recommended)
bash <skill-path>/scripts/create_response.sh \
  --session-file ./out/my_session.json \
  --input "Hello, I am writing a distributed consensus library in Go" \
  --text-only

bash <skill-path>/scripts/create_response.sh \
  --session-file ./out/my_session.json \
  --input "What library was I writing and in which language?" \
  --text-only

# Multi-turn conversation by previous response ID
bash <skill-path>/scripts/create_response.sh \
  --input "Refactor the previous design to use Redis Streams instead" \
  --previous-response-id "resp_677efb5139a88190b512bc3fef8e535d" \
  --text-only

# Interactive terminal chat
bash <skill-path>/scripts/create_response.sh --chat
```
