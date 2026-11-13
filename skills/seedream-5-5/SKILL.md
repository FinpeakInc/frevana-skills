---
name: seedream-5-5
description: Generate or edit one image through Frevana with Seedream 5.5. Use when the user requests Seedream 5.5 for text-to-image generation or reference-image editing.
---

# Seedream 5.5

Generate or edit one image through Frevana's image API using the fixed model `bytedance-seed/seedream-5-5` and `POST /openrouter/v1/images`. Do not override the model or silently fall back after a failure.

## Execution

1. Require a non-empty `--prompt` (alias `--contents`).
2. Map local references to repeatable `--image`, remote HTTP(S) references to `--image-url`, and directories to `--image-dir`. The helper preserves argument order; directory images expand in byte-sorted recursive path order.
3. Choose only documented settings: `--resolution`, `--aspect-ratio`, `--seed`, and `--n 1`. Omit settings the user did not request; the server catalog provides the default resolution.
4. Run the helper once. Bearer authentication requires `FREVANA_TOKEN` / `--token`; `FREVANA_API_KEY` / `--api-key` is only an optional supplemental header and never replaces the token. When set, `FREVANA_AGENT_APP_INSTANCE_ID` is sent as `x-frevana-agent-app-instance-id`.
5. Preserve the response JSON and hosted URLs. Present `data[0].image_url` as the primary image, summarize by default, and return raw JSON when requested. `--output` saves the same JSON.

The helper requires Bash, curl, and Python 3. It defaults to `https://ai-factory.frevana.com`; `FREVANA_API_BASE_URL` may select a user-requested local or staging server.

## Options and limits

| Option | Contract |
| --- | --- |
| `--model` | Fixed to `bytedance-seed/seedream-5-5`; alias `seedream-5-5` is accepted |
| `--n` | Must be `1` |
| `--resolution` | `1K`, `1.5K`, or `2K` |
| `--aspect-ratio` | `1:1`, `1:2`, `2:1`, `2:3`, `3:2`, `3:4`, `4:3`, `4:5`, `5:4`, `9:16`, `16:9`, `9:19.5`, `19.5:9`, `9:20`, `20:9`, `9:21`, `21:9`, or `auto` |
| `--seed` | Integer |
| `--image`, `--image-url`, `--image-dir` | PNG/JPEG/WebP references, at most 10 total; each local file must be under 50MB and the final Base64 JSON request must remain under the server's 50MB body limit |
| `--session-id` | Optional string, at most 256 characters |
| `--user` | Optional user attribution string |

Local images are encoded as data URLs. Remote URLs are sent as references without downloading. Output format, arbitrary pixel sizes, quality, background, compression, streaming, and multiple outputs are not exposed because the server catalog does not declare them for this model.

## Commands

```bash
bash <skill-path>/scripts/generate_image.sh \
  --prompt "A cinematic product photograph of a ceramic teapot on dark stone" \
  --resolution 2K --aspect-ratio 16:9 \
  --output ./out/seedream.json

bash <skill-path>/scripts/generate_image.sh \
  --prompt "Keep the product geometry and logo, replace the background with a sunlit gallery" \
  --image ./refs/product.png --resolution 1.5K --aspect-ratio 4:3 \
  --output ./out/seedream-edit.json
```

## Results and failures

A successful response contains numeric `created` and `credits_consumed`, plus one `data` item with a hosted `image_url` and `media_type`. The request is synchronous and can take up to 600 seconds.

Do not automatically retry transport errors, timeouts, storage failures, `image_cost_unknown`, or `image_billing_unknown`: the generation or billing outcome may be uncertain. The helper prints the server's `x-request-id` to stderr whenever the header is available; use it to check generation history before authorizing another paid request. The server's preflight estimate is a conservative planning value; actual usage determines `credits_consumed`.

The server must have the matching image integration deployed and `src/sqls/2026-11-13-add-seedream-fable-seedance-flash.sql` applied. A local implementation does not establish production deployment or provider access.
