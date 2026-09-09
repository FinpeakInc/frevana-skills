---
name: gpt-image-2.5
description: Use when the user wants Frevana-hosted image generation or editing with GPT Image 2.5, including automatic or explicit selection between Flare and Sunburst and local or remote reference images.
---

# GPT Image 2.5

Generate or edit images through Frevana's AI Factory OpenAI image endpoint.

Return the validated API response JSON unchanged. Treat `data[0].image_url` as the primary image URL.

## Model Selection

- Honor an explicit user choice of `gpt-image-2.5-flare` or `gpt-image-2.5-sunburst`.
- Otherwise use `gpt-image-2.5-flare` for most requests, especially fast iteration, social/creator content, prototypes, visual search, product experiences, or high-volume generation.
- Use `gpt-image-2.5-sunburst` when the request prioritizes maximum precision over latency: demanding reference preservation, tightly controlled or repeated edits, production-ready campaign creative, polished product imagery, complex layouts, or exact text/detail work.
- When the request does not clearly justify Sunburst, use Flare. Do not ask the user to choose unless the speed-versus-precision tradeoff materially affects their request.

The script defaults to Flare when `--model` is omitted. Pass the chosen model explicitly when the agent selected Sunburst.

## What This Skill Needs

- user-provided `prompt` or `contents`
- optional reference inputs: `--image`, `--image-url`, `--image-dir`, `--mask`
- optional image settings: `n`, `size`, `quality`, `background`, `output_format`, `output_compression`, `moderation`, `input_fidelity`
- `FREVANA_TOKEN`, or a one-run `--token` override
- `curl`, `bash`, and `python3`

## Execution

1. Confirm the user supplied a prompt.
2. Select the model using the rules above and prefer the bundled script over ad hoc requests.
3. Map local images to repeatable `--image`, remote image URLs to repeatable `--image-url`, and directories to repeatable `--image-dir`.
4. Use `--input-fidelity` only for editing/reference-image requests. Use `high` when exact faces, products, typography, or other source details must be preserved; otherwise omit it and let the API default apply.
5. Use `--moderation` only for text-to-image generation without reference images.
6. Let the script use `FREVANA_TOKEN` first. In a non-interactive run, report the missing token instead of prompting indefinitely.
7. Return raw JSON, or only the first hosted URL when that is all the user requested. Save JSON with `--output` when useful.

## Allowed Options

- `--model`: `gpt-image-2.5-flare` or `gpt-image-2.5-sunburst`; defaults to Flare
- `--n`: `1-10`
- `--size`: `auto` or `WIDTHxHEIGHT`; each edge at most 3840 and divisible by 16, aspect ratio at most 3:1, total pixels from 655360 through 8294400
- `--quality`: `auto`, `low`, `medium`, `high`, `xhigh`, `max`
- `--background`: `auto`, `opaque`, `transparent`; transparent output requires PNG or WebP
- `--output-format`: `png`, `jpeg`, `webp`
- `--output-compression`: `1-100`, only with JPEG or WebP
- `--moderation`: `auto`, `low`, generation only
- `--input-fidelity`: `low`, `high`, editing/reference-image requests only
- `--image`: repeatable `.png`/`.jpg`/`.jpeg`/`.webp` local file under 50MB
- `--image-url`: repeatable remote HTTP(S) image; downloaded before upload, under 50MB
- `--image-dir`: repeatable local directory, recursively loaded; at most 16 total reference images
- `--mask`: optional local PNG under 4MB, only with reference images

Resolutions above 3686400 pixels are experimental. Prefer common sizes such as `1024x1024`, `1536x1024`, `1024x1536`, `2048x2048`, `2048x1152`, `3840x2160`, or `2160x3840` unless the user needs a custom canvas.

## Commands

```bash
bash <skill-path>/scripts/generate_image.sh \
  --prompt "A cinematic product photo of a matte black espresso machine on travertine" \
  --size 2048x1152 \
  --quality high \
  --output-format png \
  --output ./out/gpt-image-2.5-result.json

bash <skill-path>/scripts/generate_image.sh \
  --model gpt-image-2.5-sunburst \
  --prompt "Change only the label typography and preserve the product exactly" \
  --image ./refs/product.png \
  --input-fidelity high \
  --quality xhigh \
  --background transparent \
  --output-format webp \
  --output ./out/gpt-image-2.5-edit-result.json
```

## Notes

- Keep the backend route fixed at `POST /openai/image/generate`; only the two GPT Image 2.5 model IDs are selectable.
- Keep `prompt` required for both generation and editing.
- Do not rewrite, proxy, or transform returned Frevana image URLs unless asked.
- The script intentionally does not implement streaming or `partial_images`, because the Frevana endpoint currently returns one completed JSON response.
