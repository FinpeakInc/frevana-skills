---
name: nano-banana-2-1
description: Use when the user asks for Nano Banana 2.1 or gemini-nano-banana-2.1 image generation or editing through Frevana, including reference images and thinking-level control.
---

# Nano Banana 2.1

Generate or edit hosted images through `POST /gemini/image/generate`. The script fixes provider `gemini` and model `gemini-nano-banana-2.1`; do not pass routing overrides. This model uses the server's Interactions API path, so the older Nano Banana 2 config fields do not apply.

## Workflow

1. Require a user-provided image prompt or editing instruction. Prefer `scripts/generate_image.sh` over ad hoc API requests.
2. Map local references to repeatable `--image`, remote HTTP(S) references to `--image-url`, and directories to `--image-dir`. Up to 14 PNG/JPEG/WebP references are supported in total, each under 50MB.
3. Use `FREVANA_TOKEN`, or a one-time `--token` override. Send it as `Authorization: Bearer`; ignore `FREVANA_API_KEY`. Missing credentials fail fast in non-interactive runs. Never print credentials.
4. The script sends `x-frevana-agent-app-instance-id` when `FREVANA_AGENT_APP_INSTANCE_ID` is present. It also supports `X_FREVANA_AGENT_APP_INSTANCE_ID` and the explicit `--agent-app-instance-id` override.
5. Return a concise result and the primary hosted URL at `data[0].image_url` (or `generated_images[0].image_url` for compatible responses). Preserve API fields and URLs; return full JSON when requested. `--output` saves the validated response JSON locally.
6. If `--job-id` is supplied, the response acknowledges an asynchronous job; it does not confirm successful generation. Follow the async instructions below before claiming completion.

## Options

- `--prompt` / `--contents`: required text, both map to backend `prompt`.
- `--thinking-level`: `minimal`, `medium`, `high`; omitted by default so the backend chooses.
- `--aspect-ratio`: `1:1`, `1:4`, `1:8`, `2:3`, `3:2`, `3:4`, `4:1`, `4:3`, `4:5`, `5:4`, `8:1`, `9:16`, `16:9`, `21:9`.
- `--image-size`: `1K`, `2K`, `4K`; omitted by default. Numeric pixel sizes are not supported.
- `--candidate-count` / `--n`: `1` only, for both generation and editing.
- `--system-instruction`: optional system prompt.
- `--seed`: nonnegative integer.
- `--image`, `--image-url`, `--image-dir`: repeatable reference inputs; directory discovery is recursive and sorted.
- `--job-id`: client UUID for async execution and seven-day deduplication. Empty or malformed values are rejected before any network request.
- `--output`: response JSON save path.
- `--token`, `--agent-app-instance-id`: auth and attribution overrides.

Do not pass `--temperature`, `--top-p`, `--top-k`, `--max-output-tokens`, or `--response-modality`. Nano Banana 2.1 does not support those options on this endpoint. `FREVANA_API_BASE_URL` optionally overrides the API base (default `https://ai-factory.frevana.com`).

## Examples

Text-to-image:

```bash
bash <skill-path>/scripts/generate_image.sh \
  --prompt "A ceramic coffee cup on a sunlit wooden table" \
  --thinking-level high --aspect-ratio 16:9 --image-size 2K \
  --output ./out/nano-banana-2-1-result.json
```

Reference editing:

```bash
bash <skill-path>/scripts/generate_image.sh \
  --prompt "Keep the product intact and replace the background with a sunny beach" \
  --image ./refs/product.png --thinking-level medium --image-size 1K \
  --output ./out/nano-banana-2-1-edit.json
```

## Asynchronous jobs

Omit `--job-id` for synchronous generation. When async execution is requested, generate a UUID (for example with `python3 -c 'import uuid; print(uuid.uuid4())'`) and keep it for recovery. Poll `GET /gemini/image/jobs/{id}` with the same credentials until `status` becomes `completed`, `failed`, or `unknown`. The returned job uses `id`, not `job_id`, and completed image output is under `data`. Extract `data[0].image_url` from the completed job. Report `failed` or `unknown` without automatically submitting a new paid generation. Job data is retained for seven days.

## Response

Synchronous response example:

```json
{
  "created": 1791417600,
  "data": [{"image_url": "https://static.frevana.com/images/example.png", "mime_type": "image/png"}],
  "credits_consumed": 1
}
```

The script validates response structure and preserves the returned JSON values. An HTTP error, empty body, malformed JSON, or invalid image result is a failure; do not claim a hosted image was generated.
