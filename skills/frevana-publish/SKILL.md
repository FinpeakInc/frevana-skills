---
name: frevana-publish
description: Publish or update a local file on the user's Frevana custom domain and return its public URL, file key, and content ID to the caller. Use this skill whenever the user asks to publish, update, host, share, or upload an agent-generated app, HTML page, report, image, document, or other local artifact through Frevana.
---

# Frevana Publish

Publish one local file through Frevana's custom-domain upload flow.

The script first checks `custom_domain` from `GET /subscriptions/user`. When no custom domain is configured, it stops before requesting an upload URL and directs the user to:

https://www.frevana.com/dashboard/domain

## What This Skill Needs

- one user-specified local file path
- the previous `file_key` supplied by the caller when the user wants to update existing content
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
- source file: pass the user-specified path directly to the upload command
- `file_key`: omit for a new publication; for an update, pass the exact value from the previous publication

Do not override or reproduce this payload with ad hoc API calls.
Do not modify the specified file as part of the publishing workflow.

## Execution Order

1. Confirm the requested path exists and is a regular file.
2. Determine whether the user wants a new publication or an update. For an update, require the previous `file_key` from the caller; do not guess it or silently create new content.
3. Prefer the bundled script over manual HTTP calls.
4. Let the script read `FREVANA_TOKEN`.
5. For a new publication, run:

```bash
bash <skill-path>/scripts/publish_file.sh \
  --file /absolute/path/to/result.html
```

6. For an update, run:

```bash
bash <skill-path>/scripts/publish_file.sh \
  --file /absolute/path/to/result.html \
  --file-key "previous/file_key.html"
```

7. If the script reports that `custom_domain` is not configured, give the user the exact configuration link it prints and stop. Do not request a pre-upload URL or upload the file.
8. If the custom domain is configured, let the script call `POST /s3/custom-upload-url`. For an update, the request includes the previous `file_key`; for a new publication, it omits `file_key`.
9. Upload the specified file directly to the returned pre-signed destination.
10. After the upload succeeds, let the script call `PUT /s3/content/{content_id}/publish?op_type=publish`.
11. After both upload and publish succeed, return a JSON object containing `url`, `file_key`, and `content_id` to the caller.
12. Explicitly tell the caller that a later update must send the returned `file_key` value unchanged as the `file_key` request parameter, which the script accepts through `--file-key`.
13. Let the caller associate and persist that result with its own Agent App ID. The skill must not save publication state locally.
14. Do not expose the pre-signed upload URL, its query parameters, the bearer token, or raw credential files.

## Options

```text
--token <token>          One-time Frevana bearer token override
--file <path>            Local file to publish
--file-key <key>         Previous file_key; include only when updating existing content
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

- For a new publication, the custom upload URL request omits `file_key`.
- For an update, the custom upload URL request includes the exact previous `file_key` so Frevana updates the existing content instead of creating a new item.
- The script uploads the file with PUT to the returned `presigned_url`.
- It passes the original path directly to `curl --upload-file`; it does not create or upload a transformed copy.
- Title extraction and MIME detection only produce request metadata and never write to the source file.
- It sends the detected MIME type during the upload.
- It never forwards the Frevana authorization header to the object-storage upload URL.
- It reads `content_id` from the custom upload URL response.
- After a successful object upload, it sends `title`, fixed `publish_type=custom_domain`, and fixed `category=agent_app_result` to `PUT /s3/content/{content_id}/publish?op_type=publish`.
- It treats the operation as successful only when both upload and publish return 2xx.
- It uses the public URL returned by the API. If the API returns only a file key, it builds the URL from the configured custom domain and that key.
- It prints one JSON object containing only `url`, `file_key`, and `content_id`.

## Caller-Owned State

- The skill is stateless and must not create a history file, sidecar file, or app-state directory.
- The caller owns the mapping between its Agent App ID and the returned `url`, `file_key`, and `content_id`.
- Treat the returned `file_key` as the update handle. For a later update, pass that exact value as the `file_key` field to `POST /s3/custom-upload-url`, or equivalently through `--file-key` when using the bundled script.
- If an update response omits `key`/`file_key`, the result retains the previous `file_key` supplied by the caller.

Example:

```bash
bash <skill-path>/scripts/publish_file.sh \
  --file /absolute/path/to/updated.html \
  --file-key "<file_key returned by the previous publish>"
```

## Error Handling

- Missing or unreadable file: ask the user for a valid local file path.
- Update requested without a caller-supplied previous `file_key`: ask the caller for it and stop before any API request.
- Filename without an extension: ask the user to rename the file with its real extension because the API requires `file_extension`.
- Missing token in a non-interactive run: tell the user to set `FREVANA_TOKEN` or use `--token`.
- Missing custom domain: direct the user to `https://www.frevana.com/dashboard/domain`.
- Unexpected API response: report the error without printing credentials or a pre-signed URL.
- Upload failure: do not claim the file was published.
- Publish failure after upload: report that the file was uploaded but publishing failed, and do not return the public URL as a successful result.
