---
name: frevana-publish
description: Publish a local file to the user's Frevana custom domain and return its public URL. Use this skill whenever the user asks to publish, host, share, or upload an agent-generated app, HTML page, report, image, document, or other local artifact through Frevana.
---

# Frevana Publish

Publish one local file through Frevana's custom-domain upload flow.

The script first checks `custom_domain` from `GET /subscriptions/user`. When no custom domain is configured, it stops before requesting an upload URL and directs the user to:

https://www.frevana.com/dashboard/domain

## What This Skill Needs

- one user-specified local file path
- `FREVANA_TOKEN` in the environment, or a one-time `--token` override
- `curl`
- `bash`
- `python3`
- network access to `https://api.frevana.com`

Do not guess the file path. If the user has not identified a file, ask for it.

## Fixed Publishing Contract

The bundled script owns these request values:

- `category`: `agent_app_result`
- `scene_type`: `content_html`
- `publish_type`: `custom_domain`
- `agent_id`: use the available Agent ID; fall back to `frevana-publish`
- `team_id`: use the available team ID; otherwise use the current session/task ID; omit only when neither is available
- `file_extension`: derived from the local filename without the leading dot
- `content_type`: derived from the local filename
- `file_title`: use `--title` when provided; otherwise extract it from the article and fall back to the filename stem

Do not override or reproduce this payload with ad hoc API calls.

## Execution Order

1. Confirm the requested path exists and is a regular file.
2. Prefer the bundled script over manual HTTP calls.
3. Let the script read `FREVANA_TOKEN`.
4. Run:

```bash
bash <skill-path>/scripts/publish_file.sh \
  --file /absolute/path/to/result.html
```

5. If the script reports that `custom_domain` is not configured, give the user the exact configuration link it prints and stop. Do not request a pre-upload URL or upload the file.
6. If the custom domain is configured, let the script call `POST /s3/custom-upload-url` and upload the file to the returned pre-signed destination.
7. After the upload succeeds, let the script call `PUT /agents/workflow-result/content/{content_id}/publish?op_type=publish`.
8. Return the public URL only after both upload and publish succeed. Do not expose the pre-signed upload URL, its query parameters, the bearer token, or raw credential files.

## Options

```text
--token <token>          One-time Frevana bearer token override
--file <path>            Local file to publish
--title <title>          Optional title override
--agent-id <id>          Optional Frevana Agent ID
--team-id <id>           Optional team ID
--session-id <id>        Session/task ID fallback when team ID is unavailable
```

`FREVANA_API_BASE_URL` can override the API host for local testing.

## ID Resolution

- Resolve `agent_id` in this order: `--agent-id`, `FREVANA_AGENT_ID`, `CODEX_AGENT_ID`, then fixed fallback `frevana-publish`.
- Resolve `team_id` in this order: `--team-id`, `FREVANA_TEAM_ID`, `CODEX_TEAM_ID`, then the session fallback.
- Resolve the session fallback in this order: `--session-id`, `FREVANA_SESSION_ID`, `CODEX_THREAD_ID`, `CODEX_SESSION_ID`.
- If neither a team ID nor session ID is available, omit optional `team_id`.

## Title Resolution

1. Use `--title` when the user explicitly provides a title.
2. For HTML, use the first non-empty `<h1>`, then `<title>`, then `og:title` or `twitter:title`.
3. For Markdown, use frontmatter `title`, then the first level-one heading.
4. For JSON, use the top-level `title`, `headline`, or `name`.
5. For other text files, use the first non-empty line.
6. If the file does not contain a usable title, use the filename without its final extension.

## Upload Behavior

- The script uploads the file with PUT to the returned `presigned_url`.
- It sends the detected MIME type during the upload.
- It never forwards the Frevana authorization header to the object-storage upload URL.
- It reads `content_id` from the custom upload URL response.
- After a successful object upload, it sends `title`, fixed `publish_type=custom_domain`, and fixed `category=agent_app_result` to the publish endpoint with `op_type=publish`.
- It treats the operation as successful only when both upload and publish return 2xx.
- It uses the public URL returned by the API. If the API returns only a file key, it builds the URL from the configured custom domain and that key.
- It prints only the final public URL by default.

## Error Handling

- Missing or unreadable file: ask the user for a valid local file path.
- Filename without an extension: ask the user to rename the file with its real extension because the API requires `file_extension`.
- Missing token in a non-interactive run: tell the user to set `FREVANA_TOKEN` or use `--token`.
- Missing custom domain: direct the user to `https://www.frevana.com/dashboard/domain`.
- Unexpected API response: report the error without printing credentials or a pre-signed URL.
- Upload failure: do not claim the file was published.
- Publish failure after upload: report that the file was uploaded but publishing failed, and do not return the public URL as a successful result.
