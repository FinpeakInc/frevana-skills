---
name: gpt-5.6-luna
description: Use when the user wants fast, lightweight, and cost-effective text generation, high-volume summarization, categorization, or rapid drafting using OpenAI GPT-5.6 Luna (gpt-5.6-luna) through the Frevana Responses API.
---

# GPT-5.6 Luna

Generate responses through Frevana's OpenAI Responses API (`POST /openai/v1/responses`) using `gpt-5.6-luna`.

Return the validated API response JSON unchanged, or use `--text-only` when the user requests only the final text output.

## Model Characteristics

- Model ID: `gpt-5.6-luna` (OpenAI GPT-5.6 lightweight and fastest model).
- Best suited for high-volume, low-latency tasks, customer support drafting, document summarization, data extraction, tagging, and high-frequency classification.
- For deep complex reasoning and coding, route to `gpt-5.6-sol`. For balanced capability/cost, route to `gpt-5.6-terra`. For next-generation frontier intelligence, route to `gpt-6`.

## What This Skill Needs

- `input` or `prompt` via `--input` or `--input-file` (or raw JSON payload via `--raw-payload-file`)
- optional developer system instructions via `--instructions` or `--instructions-file`
- optional reasoning effort: `--reasoning-effort <low|medium|high>`
- optional sampling: `--temperature`, `--top-p`, `--max-output-tokens`
- optional multi-turn conversation continuation: `--previous-response-id`
- optional tools: `--tools` or `--tools-file`, `--tool-choice`
- optional service tier: `--service-tier <auto|default|flex|priority>`
- authentication: `FREVANA_TOKEN` (or `--token`) / `FREVANA_API_KEY` (or `--api-key`)
- optional attribution: `FREVANA_AGENT_APP_INSTANCE_ID` (or `X_FREVANA_AGENT_APP_INSTANCE_ID`, or `--agent-app-instance-id`) sent as `x-frevana-agent-app-instance-id`
- `curl`, `bash`, and `python3`

## Allowed Options

- `--model`: `gpt-5.6-luna` (default)
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
# High-speed summarization
bash <skill-path>/scripts/create_response.sh \
  --input "Summarize this 5-page customer feedback log into 3 bullet points" \
  --text-only

# Fast structured extraction
bash <skill-path>/scripts/create_response.sh \
  --input "Extract invoice number, vendor, and amount from this text: Invoice #9921 from Acme Corp for $450.00" \
  --instructions "Respond in strict JSON with keys: invoice_number, vendor, amount." \
  --output ./out/luna-invoice.json

# Multi-turn conversation with automatic session persistence
bash <skill-path>/scripts/create_response.sh \
  --session-file ./out/chat_session.json \
  --input "I am planning a trip to Tokyo in November" \
  --text-only

bash <skill-path>/scripts/create_response.sh \
  --session-file ./out/chat_session.json \
  --input "Suggest 3 neighborhoods to stay in based on my destination" \
  --text-only

# Interactive terminal chat
bash <skill-path>/scripts/create_response.sh --chat
```
