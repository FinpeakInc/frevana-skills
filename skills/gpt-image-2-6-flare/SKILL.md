---
name: gpt-image-2-6-flare
description: Generate or edit images and generate animated GIFs through Frevana with GPT Image 2.6 Flare. Use for explicit Flare requests or GPT Image 2.6 requests without a specified variant.
---

# GPT Image 2.6 Flare

Use the bundled script with fixed provider `openai`, model `gpt-image-2.6-flare`, and `POST /openai/image/generate`. Honor an explicit Sunburst request by selecting its skill instead. Do not override the model or silently fall back after a failure.

## Execution

1. Require a user-provided `--prompt` or its alias `--contents`.
2. For static edits, map local references to repeatable `--image`, remote HTTP(S) references to `--image-url`, and local directories to `--image-dir`. A PNG `--mask` requires at least one reference image. References retain command-line order across input types; directories expand at their argument position in byte-sorted path order. Put the image being masked first.
3. Set `--input-fidelity high` when preserving source details is necessary; this option requires references. `--moderation` applies only to generation without references.
4. Set `--complexity` independently of `--quality` when planning effort is requested; leave unspecified settings omitted. The server documents the upstream complexity default as `high`.
5. For animation, use `--output-format gif --size auto` unless the user explicitly requires a native frame size. An omitted GIF size is sent as `auto`; explicit sizes are passed through unchanged. Apply the GIF restrictions and sizing guidance below before submitting.
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

For static images, prefer `auto`, `1024x1024`, `1536x1024`, or `1024x1536`; provider pixel and edge limits still apply. GIF generation depends on the server's provider account having preview access.

## GIF sizing and recovery

- `size` is the finished size of each frame. OpenAI also validates an internal frame sheet. Its layout is not a simple `width × height × frame_count` rule: a rejected 4-frame request at `1024x1024` reported candidate sheets of `4096x2048` and `2048x4096`. Do not assume fewer frames make a requested size valid or invent a universal GIF pixel cap.
- Use `size=auto` for adaptive frame dimensions. Frevana production logs on 2026-11-05 recorded Flare succeeding with `auto`, 16 frames, 150ms, `quality=high`, and both variants with `auto`, 12 frames, 150ms, quality omitted; all returned `size=512x512`. These are observed working configurations, not a fixed resolution limit or a guarantee for every request.
- If OpenAI returns HTTP 400 / `invalid_value` with `No supported sheet fits`, preserve its original error. Stop the 16 → 9 → 4 guessing cycle. If adaptive dimensions fit the user's requirements, use `--size auto` for the next authorized request while retaining desired frame count and timing. Do not silently replace an explicitly required native size. If `auto` also fails, stop and report the upstream error instead of probing more combinations. The script never retries automatically.
- Report the actual returned `size` when present. `quality=max` does not guarantee 1024px frames. If the user needs a 1024×1024 deliverable and accepts resizing, reuse the generated GIF for local resizing, preserving frame timing and looping, and identify the result as upscaled. For crisp stationary brand text with only decorative motion, a high-resolution static image plus local animation is an alternative; it changes the generation method and must fit the user's request. Neither path establishes native 1024×1024 GIF support.

See the [official GIF guide](https://developers.openai.com/api/docs/guides/image-generation#generate-animated-gif-output) for per-frame size semantics. Preserve original API JSON and hosted URLs when creating any separately identified local derivative.

## Examples

```bash
bash <skill-path>/scripts/generate_image.sh \
  --prompt "A matte black espresso machine on travertine" \
  --size 1536x1024 --quality high --complexity medium \
  --output ./out/gpt-image-2-6-flare.json

bash <skill-path>/scripts/generate_image.sh \
  --prompt "Change only the label typography, preserving the product" \
  --image ./refs/product.png --input-fidelity high \
  --quality xhigh --complexity high --background transparent \
  --output-format webp --output ./out/gpt-image-2-6-flare-edit.json

bash <skill-path>/scripts/generate_image.sh \
  --prompt "A paper boat bobbing gently on water, seamless loop" \
  --output-format gif --frame-count 16 --frame-duration-ms 150 \
  --size auto --quality high \
  --output ./out/gpt-image-2-6-flare-animation.json
```

## Results and failures

Successful responses contain numeric `created` and `credits_consumed`, plus a non-empty `data` array of hosted `image_url` values. GIF responses also include `output_format: "gif"`. Preserve all additional response fields, including revised prompts.

This helper follows the GPT Image 2.5 synchronous flow: it waits up to 600 seconds and does not submit `job_id`, poll jobs, stream, or request partial images. Do not automatically retry errors or timeouts; a failed connection can leave generation or billing uncertain. If saving JSON fails after success, recover the returned result from stdout instead of generating again.

The server must have GPT Image 2.6 support and migration `20261105090000_add_gpt_image_2_6_models` applied. Its credit estimate is a heuristic, not a charge cap; actual usage determines `credits_consumed`. A local implementation does not establish deployment or provider access.
