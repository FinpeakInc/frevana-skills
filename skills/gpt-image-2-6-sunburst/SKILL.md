---
name: gpt-image-2-6-sunburst
description: Generate or edit images and generate animated GIFs through Frevana with GPT Image 2.6 Sunburst. Use when the user requests GPT Image 2.6 Sunburst for image generation, reference-image editing, or animation.
---

# GPT Image 2.6 Sunburst

Use the bundled script with fixed provider `openai`, model `gpt-image-2.6-sunburst`, and `POST /openai/image/generate`. Honor an explicit Flare request by selecting its skill instead. For GPT Image 2.6 requests without a variant, use the Flare skill by default. Do not override the model or silently fall back after a failure.

## Execution

1. Require a user-provided `--prompt` or its alias `--contents`.
2. For static edits, map local references to repeatable `--image`, remote HTTP(S) references to `--image-url`, and local directories to `--image-dir`. A PNG `--mask` requires at least one reference image. References retain command-line order across input types; directories expand at their argument position in byte-sorted path order. Put the image being masked first.
3. Set `--input-fidelity high` when preserving source details is necessary; this option requires references. `--moderation` applies only to generation without references.
4. Set `--complexity` independently of `--quality` when planning effort is requested; leave unspecified settings omitted. The server documents the upstream complexity default as `high`.
5. For animation, use `--output-format gif` and prefer `--size auto`. Apply the GIF restrictions below before downloading references or submitting a request.
6. Run the script once. It uses `FREVANA_TOKEN` or a one-run `--token` override for Bearer authentication. A missing token fails immediately in non-interactive runs; `FREVANA_API_KEY` is not a fallback. When set, `FREVANA_AGENT_APP_INSTANCE_ID` is sent as `x-frevana-agent-app-instance-id` only to Frevana.
7. Preserve the response JSON and hosted URLs. Present `data[0].image_url` as the primary image or GIF, summarize by default, and return raw JSON when requested. `--output` saves the same JSON returned on stdout.

The script requires Bash, curl, and Python 3. It defaults to `https://ai-factory.frevana.com`; `FREVANA_API_BASE_URL` can select a user-requested local or staging server.

## Options and limits

| Option | Contract |
| --- | --- |
| `--n` | Integer 1–10; for GIF, number of animations, not frames |
| `--size` | `auto` or positive `WIDTHxHEIGHT` with both dimensions divisible by 16; static aspect ratio between 1:3 and 3:1 |
| `--quality` | `auto`, `low`, `medium`, `high`, `xhigh`, `max` |
| `--complexity` | `low`, `medium`, `high`; controls planning independently of rendering quality |
| `--background` | `auto`, `opaque`, `transparent`; transparency requires PNG or WebP, defaults to PNG when format is omitted |
| `--output-format` | `png`, `jpeg`, `webp`, `gif` |
| `--output-compression` | Integer 1–100, only with explicitly selected JPEG or WebP |
| `--moderation` | `auto`, `low`; generation only |
| `--input-fidelity` | `low`, `high`; reference-image edits only |
| `--image`, `--image-url`, `--image-dir` | PNG/JPEG/WebP references under 50MB each, at most 16 total; directories are scanned recursively |
| `--mask` | Local PNG under 4MB, with reference images; match the first reference's dimensions |
| `--frame-count` | Integer 2–16, GIF only; server default 9 |
| `--frame-duration-ms` | Integer 20–2000, GIF only; server default 200, upstream rounds to 10ms |

GIF supports text-only generation. Reject all reference inputs, masks, input fidelity, compression, and transparent backgrounds for GIF. Frame options are invalid for static output. GIF input files, SVG output, and markup-guided edits are not exposed by this integration.

The provider enforces model-specific pixel, edge, and GIF request-budget limits. Prefer `auto`, `1024x1024`, `1536x1024`, or `1024x1536`; do not assume GPT Image 2.5's pixel limits apply to 2.6 GIFs. GIF generation also depends on the server's provider account having preview access.

## Examples

```bash
bash <skill-path>/scripts/generate_image.sh \
  --prompt "A matte black espresso machine on travertine" \
  --size 1536x1024 --quality high --complexity medium \
  --output ./out/gpt-image-2-6-sunburst.json

bash <skill-path>/scripts/generate_image.sh \
  --prompt "Change only the label typography, preserving the product" \
  --image ./refs/product.png --input-fidelity high \
  --quality xhigh --complexity high --background transparent \
  --output-format webp --output ./out/gpt-image-2-6-sunburst-edit.json

bash <skill-path>/scripts/generate_image.sh \
  --prompt "A paper boat bobbing gently on water, seamless loop" \
  --output-format gif --frame-count 9 --frame-duration-ms 200 \
  --size auto --quality medium \
  --output ./out/gpt-image-2-6-sunburst-animation.json
```

## Results and failures

Successful responses contain numeric `created` and `credits_consumed`, plus a non-empty `data` array of hosted `image_url` values. GIF responses also include `output_format: "gif"`. Preserve all additional response fields, including revised prompts.

This helper follows the GPT Image 2.5 synchronous flow: it waits up to 600 seconds and does not submit `job_id`, poll jobs, stream, or request partial images. Do not automatically retry errors or timeouts; a failed connection can leave generation or billing uncertain. If saving JSON fails after success, recover the returned result from stdout instead of generating again.

The server must have GPT Image 2.6 support and migration `20261105090000_add_gpt_image_2_6_models` applied. Its credit estimate is a heuristic, not a charge cap; actual usage determines `credits_consumed`. A local implementation does not establish deployment or provider access.
