---
name: seedance2
description: Create and retrieve Seedance 2.0 AI video jobs through the Seevio API with fixed 10-second polling, including text-to-video, image-to-video, and reference-to-video generation with image, video, or audio URLs. Use when the user asks to generate a Seedance 2.0 video, check or wait for a Seedance task, download its result, or integrate the Seedance asynchronous video API without webhooks.
---

# Seedance 2.0

Create asynchronous Seedance 2.0 video jobs, query their state, wait for terminal results, and download completed videos. Use the bundled shell script instead of writing ad hoc requests.

## Invocation

Resolve `{baseDir}` to the directory containing this `SKILL.md`, then run:

```bash
bash {baseDir}/scripts/seedance.sh <create|status|wait> [options]
```

Require Bash, curl, Python 3, and `SEEDANCE_API_KEY` in the environment. Never print the key or place it directly in a command line. The script accepts only an HTTPS `SEEDANCE_API_BASE_URL` override; otherwise it uses `https://api.seevio.ai`.

## Workflow

1. Confirm the prompt and generation mode before creating a billable job.
2. Confirm ambiguous model, duration, media, or output choices instead of submitting a trial job.
3. Map the request to one mode:
   - `text-to-video`: prompt only.
   - `image-to-video`: prompt plus exactly 1 or 2 public image URLs. The first image is the first frame; the second is the last frame.
   - `reference-to-video`: prompt plus at least one public image or video URL. Audio cannot be the only reference.
4. Use only public `http://` or `https://` media URLs. This API does not upload local files; ask the user for hosted URLs if only local files are available.
5. Run `create --wait` for the normal generation flow. Polling is fixed at one status check every 10 seconds; add `--download-dir` when the user wants local files.
6. For an existing task, use `status` for a single read or `wait` for fixed 10-second polling.
7. Return the task ID, terminal status, credits, and downloaded path or result URL. Do not fabricate completion when the task remains queued or generating.

## Commands

```bash
# Text to video; submit and return the accepted task JSON
bash {baseDir}/scripts/seedance.sh create \
  --prompt "A cat surfing on a neon wave, cinematic lighting" \
  --generation-type text-to-video \
  --duration 5 \
  --aspect-ratio 16:9 \
  --resolution 720p

# Image to video; wait for completion and download the result
bash {baseDir}/scripts/seedance.sh create \
  --prompt "The subject turns toward camera with soft studio motion" \
  --generation-type image-to-video \
  --image-url "https://example.com/first-frame.jpg" \
  --wait \
  --download-dir ./output

# Reference to video with mixed media
bash {baseDir}/scripts/seedance.sh create \
  --prompt "Use the product and match the reference camera movement" \
  --generation-type reference-to-video \
  --image-url "https://example.com/product.jpg" \
  --video-url "https://example.com/camera-motion.mp4" \
  --duration 8 \
  --resolution 1080p

# Query or wait for an existing task
bash {baseDir}/scripts/seedance.sh status --task-id TASK_ID
bash {baseDir}/scripts/seedance.sh wait --task-id TASK_ID --download-dir ./output
```

Run `bash {baseDir}/scripts/seedance.sh --help` for all flags.

## Guardrails

- Treat every `create` call as billable. Never auto-resubmit after a timeout, transport error, or unexpected response.
- Keep the model to `seedance-2-0`, `seedance-2-0-fast`, or `seedance-2-0-mini`.
- Keep duration within 4-15 seconds, seed at `-1` or `0-4294967295`, and use only documented aspect ratios and resolutions.
- For `reference-to-video`, allow at most 9 images, 3 videos, 3 audio files, and 12 total assets. Video references and audio references each have a documented combined duration limit of 15 seconds; the CLI cannot inspect remote durations, so confirm this from the user when necessary.
- Do not pass `callback_url`; this skill intentionally uses polling only.
- Poll exactly once every 10 seconds. Do not expose a configurable polling interval.
- Download completed videos before `video_expires_at`; result URLs expire.
- On `429`, respect `Retry-After`. On failed jobs, report `failed_reason`; do not retry without user approval.
- Preserve API response JSON. Summarize it for the user unless raw JSON was requested.

## API Reference

Read [references/api.md](references/api.md) when handling errors or checking exact fields and limits. The source contract is the [Seedance 2.0 API documentation](https://seedance2.ai/zh/api-docs).
