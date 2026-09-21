---
name: veo-3.1
description: Generate cinematic, production-grade video with synchronized audio using Google Veo 3.1 (google/veo-3.1) via Frevana's OpenRouter video endpoint, supporting 720p, 1080p, and 4K resolutions, durations of 4, 6, or 8 seconds, deterministic seed, and first/last frame controls.
---

# Google Veo 3.1 Video

Generate production-grade video with synchronized audio through Frevana's OpenRouter video endpoint using `google/veo-3.1`.

## Model Characteristics

- **Model ID**: `google/veo-3.1` (variants: `google/veo-3.1-fast`, `google/veo-3.1-lite`)
- **Resolutions**: `720p` (default), `1080p`, and `4K`; the Lite variant supports only `720p` and `1080p`
- **Aspect Ratios**: `16:9` (default), `9:16`
- **Durations**: `4`, `6`, `8` seconds (default: `6`)
- **Frame Control**: Supports both `first_frame` and `last_frame` (image-to-video)
- **Input References**: Reference images (`image_url`); audio and video references are unsupported
- **Audio**: Native synchronized audio generation supported (default: enabled)
- **Seed**: Deterministic integer seed supported
- **Passthrough Controls**: `negativePrompt`, `personGeneration`

## Prerequisites & Authentication

- `FREVANA_TOKEN` (or `--token`) or `FREVANA_API_KEY` (or `--api-key`) in the environment
- Optional `FREVANA_AGENT_APP_INSTANCE_ID` (or `--agent-app-instance-id`) sent as `x-frevana-agent-app-instance-id`
- `curl`, `bash`, and `python3`

## Invocation

```bash
# Text-to-video: submit and wait for video completion
bash skills/veo-3.1/scripts/generate_video.sh \
  --prompt "A golden retriever catching a frisbee on a sunny beach in slow motion, cinematic 4K" \
  --duration 6 \
  --resolution 1080p \
  --aspect-ratio 16:9 \
  --download-dir ./output

# Image-to-video with first and last frame
bash skills/veo-3.1/scripts/generate_video.sh \
  --prompt "A smooth camera zoom from wide landscape to a blooming rose" \
  --first-frame ./first.jpg \
  --last-frame ./last.jpg \
  --duration 8 \
  --download-dir ./output

# Status check
bash skills/veo-3.1/scripts/generate_video.sh status --job-id <JOB_ID>
```

## Allowed Options

- `-p, --prompt TEXT`: Text description of the video (required for create)
- `--prompt-file PATH`: Path to file containing prompt
- `--model MODEL`: Model slug (default: `google/veo-3.1`, allowed: `google/veo-3.1`, `google/veo-3.1-fast`, `google/veo-3.1-lite`)
- `--duration SEC`: Duration in seconds (`4`, `6`, `8`, default: `6`)
- `--aspect-ratio RATIO`: `16:9`, `9:16` (default: `16:9`)
- `--resolution RES`: `720p`, `1080p`, `4K` (default: `720p`); `google/veo-3.1-lite` does not support `4K`
- `--first-frame, --image PATH/URL`: Image path or URL for first frame
- `--last-frame PATH/URL`: Image path or URL for last frame
- `--reference-image PATH/URL`: Add a reference image; repeat for multiple images
- `--reference-audio URL`: Unsupported by these models
- `--reference-video URL`: Unsupported by these models
- `--audio`: Generate synchronized audio (default: true)
- `--no-audio`: Disable audio generation
- `--seed INT`: Deterministic integer seed for reproducible generation
- `--negative-prompt TEXT`: Negative prompt to guide generation away from unwanted artifacts
- `--person-generation VAL`: Policy for person generation (`allow_adult`, `dont_allow`)
- `--wait`: Wait for job completion and download/output (default in CLI)
- `--no-wait`: Submit job and return immediately with Job ID
- `--poll-interval SEC`: Seconds between status checks (default: `10`)
- `--max-wait SEC`: Maximum seconds to wait before timeout (default: `600`)
- `--download-dir DIR`: Directory to download completed MP4 video
- `-o, --output FILE`: Path to save output JSON or MP4 file
- `-t, --text-only`: Output only the video URL or downloaded file path
- `--dry-run`: Print request payload JSON and exit without network calls
- `--token TOKEN`: Frevana Bearer token override
- `--api-key KEY`: Frevana API key override
- `--agent-app-instance-id ID`: Agent App instance ID override

## Guardrails

- Validate that `--duration` is strictly one of `4`, `6`, or `8` seconds. Values like 5 or 10 will be rejected client-side.
- Validate that `--aspect-ratio` is either `16:9` or `9:16`.
- Validate resolution against the selected model; `google/veo-3.1-lite` accepts only `720p` or `1080p`.
- Frame images and input references may be sent together; OpenRouter gives `frameImages` precedence and treats the request as image-to-video.
