---
name: gpt-5.6-terra
description: Use when the user wants balanced general-purpose reasoning, production workflows, conversational intelligence, and enterprise tasks using OpenAI GPT-5.6 Terra (gpt-5.6-terra) through the Frevana Responses API.
---

# GPT-5.6 Terra

Generate responses through Frevana's OpenAI Responses API (`POST /openai/v1/responses`) using `gpt-5.6-terra`.

Return the validated API response JSON unchanged, or use `--text-only` when the user requests only the final text output.

## Model Characteristics

- Model ID: `gpt-5.6-terra` (OpenAI GPT-5.6 balanced tier model).
- Best suited for everyday production workloads, report drafting, business logic, customer interaction, code reviews, and structured data generation that require a strong balance of intelligence, speed, and cost.
- For demanding frontier reasoning, architecture, or complex autonomous coding, route to `gpt-5.6-sol` or `gpt-6`. For fastest, high-volume classification or summarization, route to `gpt-5.6-luna`.

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

- `--model`: `gpt-5.6-terra` (default)
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
# Business workflow drafting
bash <skill-path>/scripts/create_response.sh \
  --input "Draft a Q3 customer success review highlighting churn reduction and expansion opportunities" \
  --instructions "Use a professional, data-driven tone with clear executive takeaways." \
  --output ./out/terra-review.json

# Tool-enabled workflow
bash <skill-path>/scripts/create_response.sh \
  --input "What is the status of shipment #TR-9982?" \
  --tools '[{"type":"function","name":"get_shipment_status","parameters":{"type":"object","properties":{"shipment_id":{"type":"string"}},"required":["shipment_id"]}}]' \
  --tool-choice auto \
  --text-only

# Multi-turn conversation with automatic session persistence
bash <skill-path>/scripts/create_response.sh \
  --session-file ./out/my_session.json \
  --input "Let's create a database schema for an e-commerce catalog" \
  --text-only

bash <skill-path>/scripts/create_response.sh \
  --session-file ./out/my_session.json \
  --input "Now add index definitions and foreign keys to it" \
  --text-only

# Interactive terminal chat
bash <skill-path>/scripts/create_response.sh --chat
```
