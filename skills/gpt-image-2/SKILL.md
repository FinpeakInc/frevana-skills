---
name: gpt-image-2
description: Use when the user wants Frevana-hosted images generated or edited with OpenAI's gpt-image-2 model, including runs that use local or remote reference images or image directories.
---

# GPT-Image-2

Generate or edit images through Frevana's AI Factory OpenAI backend with a fixed contract:

- provider: `openai`
- model: `gpt-image-2`

This skill returns the validated API response JSON unchanged. Treat `data[0].image_url` as the primary image URL.

## What This Skill Needs

- user-provided `prompt` or `contents`
- optional reference image inputs: `--image`, `--image-url`, `--image-dir`, `--mask`
- optional OpenAI image options: `n`, `size`, `quality`, `background`, `output_format`, `output_compression`
- `FREVANA_TOKEN` in the environment, or an explicit `--token` override for the current run
- `curl`
- `bash`
- `python3`

## Execution Order

1. Confirm the user provided the image prompt.
2. If the user references one or more local image files, pass each one with `--image`.
3. If the user references one or more remote image URLs, pass each one with `--image-url`; the script downloads supported images first, then reuses the existing upload flow.
4. If the user references a local directory of images, pass it with `--image-dir`; the script recursively collects supported images from that directory.
5. If the user provides a local mask image, pass it with `--mask` and keep it PNG-only.
6. Do not ask for or pass through `provider` or `model`; this skill fixes them.
7. Prefer the script over ad hoc `curl` commands.
8. Let the script read `FREVANA_TOKEN` first.
9. In non-interactive runs, fail fast if the token is missing and tell the user to set `FREVANA_TOKEN` or pass `--token`.
10. Return the raw API response JSON, or the first image URL when the user only wants the hosted asset.
11. Save the JSON with `--output` when useful.

## Allowed Options

- `--n`: `1-10`
- `--size`: `auto`, `1024x1024`, `1536x1024`, `1024x1536`, `256x256`, `512x512`, `1792x1024`, `1024x1792`
- `--quality`: `standard`, `hd`, `low`, `medium`, `high`, `auto`
- `--background`: `transparent`, `opaque`, `auto`
- `--output-format`: `png`, `jpeg`, `webp`
- `--output-compression`: `1-100`
- `--image`: repeatable local file path, `.png`/`.jpg`/`.jpeg`/`.webp`, each under 50MB
- `--image-url`: repeatable remote `http://` or `https://` image URL; downloads supported `.png`/`.jpg`/`.jpeg`/`.webp` files first, each under 50MB
- `--image-dir`: repeatable local directory path; recursively loads supported images, up to 16 images total across `--image`, `--image-url`, and `--image-dir`
- `--mask`: optional local `.png` path, under 4MB, only when image inputs are present

## Command

```bash
bash <skill-path>/scripts/generate_image.sh \
  --prompt "A cinematic product photo of a matte black espresso machine on travertine" \
  --size 1536x1024 \
  --quality high \
  --background opaque \
  --output-format png \
  --output ./out/gpt-image-2-result.json

bash <skill-path>/scripts/generate_image.sh \
  --prompt "Turn these product references into one polished hero shot" \
  --image ./refs/front.png \
  --image-url "https://example.com/reference/detail.png" \
  --image-dir ./refs/detail-shots \
  --mask ./refs/mask.png \
  --size 1024x1024 \
  --output ./out/gpt-image-2-edit-result.json
```

## Response Shape

```json
{
  "created": 1777367067,
  "background": "opaque",
  "output_format": "png",
  "quality": "high",
  "size": "1536x1024",
  "data": [
    {
      "revised_prompt": "string",
      "image_url": "https://static.frevana.com/images/user-id/example-image-id.png"
    }
  ],
  "credits_consumed": 1
}
```

## Notes

- Do not pass `--provider` or `--model`; the wrapper rejects overrides.
- If the user says "use `/path/to/reference.png`", map that to `--image /path/to/reference.png`.
- If the user says "use `https://example.com/reference.png`", map that to `--image-url https://example.com/reference.png`.
- If the user says "use the images under `/path/to/references`", map that to `--image-dir /path/to/references`.
- Keep `prompt`/`contents` required even for image-to-image requests.
- Do not rewrite, proxy, or transform the returned Frevana image URLs unless the user asks for that.
