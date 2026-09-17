---
name: gemini-3.1-flash-image
description: Use when the user wants Frevana-hosted image generation or editing with Gemini 3.1 Flash Image (gemini-3.1-flash-image), optimized for fast iteration, high throughput, and multi-image editing.
---

# Gemini 3.1 Flash Image

Generate or edit images through Frevana's Gemini image endpoint using `gemini-3.1-flash-image`.

Return the validated API response JSON unchanged. Treat `generated_images[0].image_url` (or `data[0].image_url`) as the primary image URL.

## Model Characteristics

- Uses `gemini-3.1-flash-image`.
- Best suited for fast iteration, social and creator content, prototypes, product workflows, and high-volume generation.
- For maximum detail, complex multi-object composition, or high-fidelity photorealism, route to `gemini-3-pro-image` instead.

## What This Skill Needs

- user-provided `prompt` or `contents`
- optional reference image inputs: `--image`, `--image-url`, `--image-dir` (up to 14 reference images, PNG/JPG/WebP, <50MB each)
- optional image settings: `--aspect-ratio`, `--image-size`, `--candidate-count`, `--system-instruction`, `--seed`
- optional sampling settings (text-to-image only): `--temperature`, `--top-p`, `--top-k`
- optional async execution / deduplication: `--job-id`
- authentication: `FREVANA_API_KEY` (or `--api-key`) / `FREVANA_TOKEN` (or `--token`)
- optional attribution: `FREVANA_AGENT_APP_INSTANCE_ID` (or `X_FREVANA_AGENT_APP_INSTANCE_ID`, or `--agent-app-instance-id`) sent as `x-frevana-agent-app-instance-id`
- `curl`, `bash`, and `python3`

## Execution Order

1. Confirm the user supplied an image prompt.
2. If the user provides local reference images, map them to repeatable `--image`.
3. If the user provides remote reference URLs, map them to repeatable `--image-url`.
4. If the user points to an image directory, map it to repeatable `--image-dir`.
5. Enforce Gemini image editing rules:
   - When reference images are present, `candidate_count` supports `1` only.
   - Text-to-image sampling parameters (`--temperature`, `--top-p`, `--top-k`) are only allowed when no reference images are attached.
6. The script reads `FREVANA_API_KEY` / `FREVANA_TOKEN` from the environment, or CLI overrides `--api-key` / `--token`.
7. When `FREVANA_AGENT_APP_INSTANCE_ID` is set, the script attaches it as the `x-frevana-agent-app-instance-id` header.
8. Return raw JSON, or extract `generated_images[0].image_url` (or `data[0].image_url`) if the user only requested the URL.
9. Save JSON with `--output` when useful.

## Allowed Options

- `--model`: `gemini-3.1-flash-image` (default)
- `--aspect-ratio`: `1:1`, `1:4`, `1:8`, `2:3`, `3:2`, `3:4`, `4:1`, `4:3`, `4:5`, `5:4`, `8:1`, `9:16`, `16:9`, `21:9`
- `--image-size`: `1K`, `2K`, `4K` (defaults to `1K`)
- `--candidate-count`, `--n`: `1-8` (image editing supports `1` only)
- `--system-instruction`: system instruction prompt
- `--temperature`: `0.0 - 2.0` (text-to-image only)
- `--top-p`: `0.0 - 1.0` (text-to-image only)
- `--top-k`: integer `>= 1` (text-to-image only)
- `--seed`: random seed integer for reproducible results
- `--job-id`: client UUID for async generation and 7-day deduplication
- `--image`: repeatable local file path (`.png`, `.jpg`, `.jpeg`, `.webp`), under 50MB
- `--image-url`: repeatable remote HTTP(S) image; downloaded before upload, under 50MB
- `--image-dir`: repeatable local directory, recursively searched for images; up to 14 total reference images
- `--api-key`: Frevana API key override (sent as `X-API-Key`)
- `--token`: Frevana Bearer token override (sent as `Authorization: Bearer`)
- `--agent-app-instance-id`: Agent App instance/team ID override (sent as `x-frevana-agent-app-instance-id`)
- `--output`: optional local path to save returned JSON

## Commands

### Text-to-Image Generation

```bash
bash <skill-path>/scripts/generate_image.sh \
  --prompt "A vibrant futuristic city with neon lights and flying vehicles at dusk" \
  --aspect-ratio 16:9 \
  --image-size 2K \
  --candidate-count 1 \
  --temperature 1.0 \
  --output ./out/gemini-flash-result.json
```

### Image Editing / Reference-to-Image

```bash
bash <skill-path>/scripts/generate_image.sh \
  --prompt "Change the background to a sunny beach while keeping the product style intact" \
  --image ./refs/product.png \
  --aspect-ratio 1:1 \
  --image-size 1K \
  --candidate-count 1 \
  --output ./out/gemini-flash-edit-result.json
```

## Response Shape

```json
{
  "generated_images": [
    {
      "image_url": "https://static.frevana.com/images/user-id/example-image-id.png",
      "enhanced_prompt": "string",
      "rai_filtered_reason": "string",
      "mime_type": "image/png"
    }
  ],
  "credits_consumed": 1
}
```

## Notes

- The backend route is `POST /gemini/image/generate`.
- Keep `prompt` required for both generation and editing.
- Up to 14 reference images are supported across `--image`, `--image-url`, and `--image-dir`.
- When reference images are attached, `candidate_count` must be 1, and `--temperature`, `--top-p`, `--top-k` are rejected.
- Do not rewrite or proxy returned Frevana image URLs unless requested.
