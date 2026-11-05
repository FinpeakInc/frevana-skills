# OpenRouter request contract and model metadata

Checked on 2026-11-05 using public metadata and documentation; no generation was submitted.

- [OpenRouter video model catalog](https://openrouter.ai/api/v1/videos/models): model ID, supported resolutions/durations/ratios, first-frame capability, seed, and allowed passthrough key.
- [OpenRouter model endpoint metadata](https://openrouter.ai/api/v1/models/heygen/heygen-video-1/endpoints): provider slug `heygen`; text/image/video/audio inputs.
- [OpenRouter video API guide](https://openrouter.ai/docs/guides/overview/multimodal/video-generation): asynchronous jobs, normalized inputs, and provider options.
- [OpenRouter submit API](https://openrouter.ai/docs/api/api-reference/video-generation/submit-a-video-generation-request) and [OpenAPI schema](https://openrouter.ai/docs/openapi/openapi.yaml): exact wire field names and types.
- [OpenRouter provider-options guide](https://openrouter.ai/docs/cookbook/video-generation/provider-specific-video-options): verify allowed passthrough names in metadata; consult the provider documentation for enum values.

Primary request and capability requirements come from OpenRouter. Additional native-provider safeguards are identified separately below; do not present them as requirements published by OpenRouter.

Frevana casing and routing were checked against `src/modules/openrouter/dto/openrouter-video.dto.ts` and `openrouter-video.service.ts` in the sibling `frevana-server` source. The local `20261105100000_add_heygen_video_1` migration contains this model's catalog metadata; its presence does not establish production deployment.

## Direct OpenRouter requirements

`POST https://openrouter.ai/api/v1/videos` uses `Authorization: Bearer $OPENROUTER_API_KEY`. This is the upstream API contract for comparison; the bundled helper calls Frevana and uses Frevana authentication instead.

| Wire field | OpenRouter requirement for this model |
| --- | --- |
| `model` | `heygen/heygen-video-1` |
| `prompt` | String; supply a scene prompt. Image-only prompting has not been verified for this model |
| `duration` | Optional integer; model catalog lists every integer from 5 through 30 |
| `resolution` | Optional: `480p`, `768p`, `1080p`, `2K` (case-sensitive) |
| `aspect_ratio` | Optional: `21:9`, `16:9`, `4:3`, `1:1`, `3:4`, `9:16` |
| `size` | Optional `WIDTHxHEIGHT`, alternative to resolution + ratio; `supported_sizes` is null |
| `frame_images` | Optional image parts with `frame_type: "first_frame"`; model catalog does not advertise a last frame |
| `input_references` | Optional `image_url`, `video_url`, `audio_url` parts. The model page advertises all three inputs |
| `generate_audio` | Optional boolean in the generic schema; this model's capability is false, so the helper omits it |
| `seed` | Optional integer; model capability is true. OpenRouter declares no integer range |
| `callback_url` | Optional HTTPS webhook URL in OpenRouter; not exposed by this helper |
| `provider.options.heygen.prompt_enhancement` | The only passthrough key advertised for this model. OpenRouter does not publish its enum/default in the catalog |

Example direct OpenRouter JSON (not the Frevana request casing):

```json
{
  "model": "heygen/heygen-video-1",
  "prompt": "A ceramic mug turns slowly on a wooden table, with quiet room ambience.",
  "duration": 10,
  "resolution": "768p",
  "aspect_ratio": "16:9",
  "provider": {
    "options": {
      "heygen": { "prompt_enhancement": "quality" }
    }
  }
}
```

Here `quality` is an optional provider value, not an OpenRouter-required setting. The helper chooses it explicitly by default. OpenRouter's schema requires `model`; `prompt` is optional only for models supporting generation from images alone. Keep a prompt for this skill.

OpenRouter explicitly accepts `frame_images` and `input_references` together: frames select image-to-video and take precedence. The helper preserves both fields and reports this behavior; reference-mode safeguards apply only when no first frame is supplied. The generic schema contains no 15-second reference limit, per-type reference count, 32,000-character prompt limit, or resolution/ratio cross-constraint. Their native-provider provenance is below.

## Frevana requests

Create: `POST https://ai-factory.frevana.com/openrouter/v1/videos`

```json
{
  "model": "heygen/heygen-video-1",
  "prompt": "A potter shapes a bowl in a sunlit workshop, with soft room ambience.",
  "duration": 20,
  "resolution": "768p",
  "aspectRatio": "16:9",
  "seed": 42,
  "provider": {
    "options": {
      "heygen": { "prompt_enhancement": "quality" }
    }
  }
}
```

Poll: `GET /openrouter/v1/videos/{job_id}` on the same Frevana origin, using the same Frevana authentication. Use the ID returned by create (`id` or `jobId`); do not forward Frevana credentials to an upstream `polling_url`.

The current Server controller uses `JwtAuthGuard`, not `ApiKeyOrJwtAuthGuard`. Send a Frevana JWT as `Authorization: Bearer ...` using `FREVANA_TOKEN` / `--token`. Ordinary Frevana API keys (`sk_...`) and an `X-API-Key` header do not satisfy this route. The helper does not fall back to `FREVANA_API_KEY`.

| Frevana body field | Direct OpenRouter wire field |
| --- | --- |
| `aspectRatio` | `aspect_ratio` |
| `frameImages` | `frame_images` |
| `frameType` | `frame_type` |
| `imageUrl`, `videoUrl`, `audioUrl` | `image_url`, `video_url`, `audio_url` |
| `inputReferences` | `input_references` |

The Frevana server calls the OpenRouter SDK, which converts the camelCase properties. Passthrough keys remain provider-native: `provider.options.heygen.prompt_enhancement` is a string, with no extra `parameters` nesting. OpenRouter confirms the key and nesting; HeyGen's documentation supplies the string enum.

For a first-frame request, add:

```json
{
  "frameImages": [
    {"type": "image_url", "frameType": "first_frame", "imageUrl": {"url": "https://example.com/start.png"}}
  ]
}
```

For reference-guided generation, use:

```json
{
  "inputReferences": [
    {"type": "image_url", "imageUrl": {"url": "https://example.com/product.png"}},
    {"type": "video_url", "videoUrl": {"url": "https://example.com/motion.mp4"}},
    {"type": "audio_url", "audioUrl": {"url": "https://example.com/sound.wav"}}
  ]
}
```

The helper preserves order within each reference type. The `<Picture 1>` / `<Video 1>` label convention comes from HeyGen's documentation; OpenRouter's general schema does not define those labels.

## Server compatibility findings

Checked against the local sibling Server and its installed `@openrouter/sdk` 1.3.19 on 2026-11-05, using fake HTTP responses only:

- The controller body emits runtime type `Object`; its current global `ValidationPipe` preserves the payload. `createVideo` wraps the flat body in `videoGenerationRequest`. Actual SDK serialization passed text, first-frame, image/audio/video references, and mixed-frame/reference requests with size and seed. Wire fields use snake_case, and `provider.options.heygen.prompt_enhancement` is preserved.
- Server's `src/main.ts` configures `express.json({ limit: '50mb' })`. Several individually valid 5 MiB images can exceed this after Base64 encoding. The helper rejects encoded JSON larger than 50 MiB before any HTTP call; use smaller images or public HTTPS URLs. This is a Frevana limit, separate from OpenRouter/provider media limits.
- The Server calls `videoGeneration.generate(normalizedRequest)` without retry options. The installed SDK defaults to retrying 5xx and connection errors. A simulated 500 followed by 202 produced **two identical POSTs without an idempotency key**. Therefore one helper submission does not guarantee one upstream submission. The Server can disable submission retries with `generate(normalizedRequest, { retries: { strategy: 'none' } })`; this was verified to make one attempt in the same simulation. No Server change was made by this skill task.
- The database must contain a published `heygen/heygen-video-1` catalog row with usable video pricing metadata. Otherwise Server validation rejects the request before forwarding. A local migration file is present, but its application to production was not checked. The inspected production deployment workflow runs `prisma db pull` / `generate`, not `migrate deploy`.
- The existing generic credit estimator uses base `duration_seconds_*` rates. It does not select HeyGen's `long_duration_seconds_*`, `reference_duration_seconds_*`, or `reference_input_images` rates, so long/reference requests can pass admission with an underestimate. Actual settlement uses upstream cost separately; do not present the admission estimate as the final charge.

## Upstream safeguards and verification boundary

The live OpenRouter catalog advertises durations 5–30, resolutions `480p`, `768p`, `1080p`, `2K`, six ratios, first-frame only, seed support, and `prompt_enhancement`. Its `generate_audio: false` capability does not mean silent output: the model description promises native sound. Omit the optional audio toggle.

The following helper checks are based on the [HeyGen model guide](https://developers.heygen.com/docs/models/heygen-video) and [HeyGen create API](https://developers.heygen.com/reference/create-heygen-video), following OpenRouter's recommendation to consult provider documentation for passthrough values. They are native-provider safeguards, not independently verified OpenRouter combinations:

- Text/first-frame mode supports 16–30 seconds with `turbo` or `quality`. Reference mode without a first frame, and `disabled`/`ultraquality` enhancement, stop at 15 seconds. The helper explicitly sends `quality` unless overridden.
- At 1080p/2K, text/reference mode requires landscape or portrait (`16:9`, `9:16`). First-frame mode uses the source shape.
- Reference mode needs an image or video; audio alone is insufficient. Up to 9 images, 3 videos, and 3 audio inputs are documented. Video references share a 15-second source budget, separate from output duration.
- Public media URLs should be direct HTTPS links. HeyGen documents limits of 16 MB for URL images and 32 MB for URL audio/video. The helper does not fetch remote media to measure them.
- Seeds are unsigned 32-bit integers; prompts have a 32,000-character limit. These bounds are not specified by OpenRouter's generic schema. Reproducibility is deployment-dependent.

OpenRouter's `supported_sizes` is null; `--size` checks syntax only and is not a guarantee of arbitrary output dimensions. `auto` duration, adaptive ratio, direct HeyGen asset IDs, native `mode`, callbacks, and avatar fields are not exposed by this helper. Do not mix direct HeyGen JSON with Frevana JSON.

The helper validates OpenRouter's advertised choices plus the explicitly identified upstream safeguards. Catalog membership alone does not guarantee every cross-product combination succeeds. Offline serialization checks do not verify live provider acceptance, generation, current account access, or production deployment. Public SKU prices can change and are not a Frevana credit quote.
