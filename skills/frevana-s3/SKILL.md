---
name: frevana-s3
description: Upload any local file (images, videos, PDFs, documents, archives, data files) to S3 via Frevana's universal upload flow (POST /s3/custom-upload-url with scene_type=universal) and return its public URL, file key, and content ID. Use this skill whenever the user asks to upload, host, share, or store arbitrary files in Frevana S3 storage, or update previously uploaded files via file_key.
---

# Frevana S3

Upload any local file to S3 storage through Frevana's `POST /s3/custom-upload-url` universal API and return its public URL, file key, and content ID.

## Prerequisites & Authentication

- One local file path (`--file <path>`)
- `FREVANA_TOKEN` (or `--token`) or `FREVANA_API_KEY` (or `--api-key`) in the environment
- `curl`, `bash`, and `python3`
- Network access to `${FREVANA_API_BASE_URL:-https://api.frevana.com}`

## Universal API Contract

The skill communicates with `POST /s3/custom-upload-url`:

- **`scene_type`**: Fixed to `universal`.
- **`file_extension`**: Required by API. Auto-detected from filename (e.g. `jpg`, `png`, `pdf`, `mp4`, `json`), or overridden with `--file-extension`.
- **`content_type`**: Required by API. Auto-detected MIME type (e.g. `image/png`, `video/mp4`, `application/pdf`), or overridden with `--content-type`.
- **`file_key`**: Pass only when updating existing content (`--file-key <key>`). Omitted for new uploads.
- **`file_title`**: Optional. Defaults to filename stem without extension, or overridden with `--title`.
- **Optional Metadata (can be omitted)**:
  - `agent_id`, `task_id`, `team_id`
  - `publish_type` (`frevana_community`, `only_share_link`, `custom_domain`, `custom_domain_and_frevana_community`)
  - `tags` (string array or comma-separated list)
  - `category` (`faq`, `guides`, `report`, `product_comparison`, `landing_page`, `knowledge_page`, `agent_app_result`)
  - `preview_image_url`, `description`, `language_code`

## Execution Workflow

1. **Detect File Properties**: Inspect the target file and resolve its extension, MIME type, and title.
2. **Request Presigned Upload URL**: Send `POST /s3/custom-upload-url` with `scene_type=universal` and the Frevana Bearer token.
3. **Upload to S3**: Upload the file payload directly to `presigned_url` using `curl -X PUT` with `Content-Type: <content_type>`. The Frevana Bearer token is never sent to the S3 presigned URL.
4. **Return Result**: Output JSON containing `url`, `file_key`, and `content_id`.

## Invocation Examples

```bash
# Basic upload: upload an image or document to S3
bash skills/frevana-s3/scripts/upload_file.sh \
  --file ./charts/revenue_q3.png

# Update an existing object using its previous file_key
bash skills/frevana-s3/scripts/upload_file.sh \
  --file ./charts/revenue_q3_updated.png \
  --file-key "images-dev/user123/revenue_q3.png"

# Upload with custom title and tags
bash skills/frevana-s3/scripts/upload_file.sh \
  --file ./reports/annual_analysis.pdf \
  --title "Annual Financial Analysis 2026" \
  --tags "finance,report,q3" \
  --category "report"

# Output only the public URL (convenient for agent pipelines)
bash skills/frevana-s3/scripts/upload_file.sh \
  --file ./assets/banner.webp \
  --text-only
```

## Options

```text
-f, --file PATH           Local file to upload (required)
-k, --file-key KEY        Previous file_key; pass only when updating existing content
-t, --title TITLE         File title (default: filename stem)
--content-type MIME       Override MIME type (default: auto-detected)
--file-extension EXT      Override file extension (default: auto-detected)

Optional Metadata:
--agent-id ID             Agent ID (or FREVANA_AGENT_ID env)
--task-id ID              Task/Thread ID (or FREVANA_TASK_ID / CODEX_THREAD_ID env)
--team-id ID              Team ID (or FREVANA_TEAM_ID / CODEX_TEAM_ID env)
--publish-type TYPE       Publish type (e.g. only_share_link, custom_domain, frevana_community)
--tags TAGS               Tags, comma-separated or JSON array (e.g. "report,v1")
--category CAT            Category (e.g. report, guides, faq, agent_app_result)
--preview-image-url URL   Preview image URL
--description DESC        File description
--language-code CODE      Language code (e.g. en, zh, ja)

Output & Auth:
--text-only               Output only the public URL
-o, --output FILE         Save output JSON to specified file
--dry-run                 Print payload JSON and exit without network requests
--token TOKEN             Frevana Bearer token (or FREVANA_TOKEN env)
--api-key KEY             Frevana API key (or FREVANA_API_KEY env)
--api-base-url URL        API base URL override (default: https://api.frevana.com)
-h, --help                Show this help message
```

## Output Format

By default, the script prints a JSON object:

```json
{
  "url": "https://dxxxxx.cloudfront.net/images-dev/user123/abc-123.png",
  "file_key": "images-dev/user123/abc-123.png",
  "content_id": "121212"
}
```

- When `--text-only` is provided, only the `url` is printed to stdout.
- To update the content later, callers should persist and reuse the returned `file_key` with `--file-key`.
