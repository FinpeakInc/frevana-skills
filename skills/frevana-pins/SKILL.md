---
name: frevana-pins
description: Manage the Frevana My Pins image and video library. Use when the user wants to list, upload, save, or download media, create, rename, or delete collections, or move Pins between collections.
---

# Frevana Pins

Start with `bash <skill-path>/scripts/pins.sh --help` to inspect the available commands. You can also run `python3 <skill-path>/scripts/pins.py` directly in environments without Bash. `<skill-path>` is the actual installation directory of this skill.

## Configuration

Requires `FREVANA_TOKEN` (the current user's JWT), or a one-time `--token` override. Prefer environment injection to keep tokens out of shell history and process arguments. Never include real tokens in output, examples, or logs. A missing token causes a noninteractive failure; the skill does not read or modify local login state. This API accepts JWTs only and does not use `FREVANA_API_KEY`.

`FREVANA_API_BASE_URL` defaults to `https://api.frevana.com` and can be overridden with `--api-base-url`. Use the server root URL, including any deployment path prefix, without `/user-pins`. Send the JWT only to the specified Frevana API address. API redirects are rejected.

Requires Python 3.9+ and its standard library. The shell entry point also requires Bash. The skill does not install dependencies or require curl or jq. When the user has not specified a required file, Pin ID, or collection ID, list the relevant records to identify a unique match. Ask when multiple records match; do not guess or expand the operation's scope.

## Common Options

| Option | Purpose |
| --- | --- |
| `--token TOKEN` | One-time JWT override; takes precedence over `FREVANA_TOKEN` |
| `--api-base-url URL` | One-time API root override; takes precedence over the environment variable |
| `--timeout SECONDS` | Per-request timeout; a positive integer, defaulting to 60 seconds |
| `--output-json PATH` | Also save the stdout JSON to a file; refuse to overwrite an existing file and create it with permissions 0600 |

Common options may appear before the command or after a subcommand. `download --output` specifies the media file; `--output-json` specifies the result JSON file. Keep these paths separate. Output path errors are checked before any API request. The skill does not automatically create output or history directories or store tokens. JSON files may contain temporary signed URLs; generate them only when needed by the user.

## Operations

- List media: `list [--kind image|video] [--collection-id ID]`. List collections: `collection list`.
- Upload and save a Pin: `upload /absolute/file.png [--title TITLE] [--source-url URL] [--source-page-url URL] [--collection-id ID]`. The script uploads the media, adds a Pin, and verifies the saved result.
- Upload media only: `upload /absolute/file.png --asset-only`. This does not create a Pin.
- Save an existing media link: `add --kind image|video --media-url URL [--title TITLE] [--source-url URL] [--source-page-url URL] [--poster-url URL] [--content-type MIME] [--collection-id ID]`. External links are recorded without fetching or copying the media to S3. Confirm the intended media link before executing.
- Remove a record: `remove PIN_ID`. Also remove its collection memberships, but do not delete the S3 file.
- Manage collections: `collection create TITLE [--pin-ids ID ...]`, `collection rename ID TITLE`, and `collection delete ID`.
- Move Pins: `collection move COLLECTION_ID --pin-ids ID ...`. Remove Pins from their collections: `collection ungroup --pin-ids ID ...`. A Pin can belong to at most one collection. Deleting a collection preserves its Pins.
- Get temporary URLs: `present REF [REF ...]`.
- Download: `download PIN_ID --output /absolute/file.png`. Read the user's own S3 media through the server proxy and refuse to overwrite an existing output file. External media cannot be downloaded through this proxy; the skill does not automatically fetch arbitrary external links.
- Advanced direct upload: `upload-url FILE_NAME [--content-type MIME]`. After obtaining the upload URL, the caller must still upload the bytes and run `add` to save a record. Obtaining a URL alone does not mean an upload succeeded.

On success, print one JSON object to stdout. Runtime errors produce JSON on stderr and a nonzero exit code; argument parsing uses standard CLI help and errors. New script output fields use snake_case. `data` preserves the original API fields, including `signedUrl` from `upload-url`. Query filtering runs on the client only. Summarize results for the user; display raw JSON or temporary signed URLs only when explicitly requested.

For example, a successful upload returns `{ "ok": true, "action": "upload", "pin_id": "...", "asset_path": "user/assets/...", "data": { ... } }`. For `list`, `data` is a snapshot; for `collection list`, it is a collection array. Removal and collection edits return the saved snapshot in `data`.

## Save Semantics

Writes modify the latest library snapshot, submit only the affected arrays, then read the library again to verify the result. The limits are 100 Pins and 40 collections. Refuse additions at the limit to avoid silent server truncation. Check the file type, 100 MB size limit, and target collection before uploading.

The server has no atomic version check. Before writing, the script compares complete snapshots to detect some concurrent edits. It ignores signed URL query parameters and, when both Pins and collections are empty, the server's dynamically generated `updatedAt`. This does not eliminate the race between checking and writing. Serialize writes for the same user. Save verification compares equivalent media references across S3 and legacy Supabase Pins paths.

Skip PUT when there is no actual change. Stop after a write or verification failure; do not automatically replay write requests. If uploading succeeds but a later step fails, the error includes `asset_path`; once Pin saving has begun, it also includes `pin_id`. Run `list` first to check whether that ID exists. If it does, do not add it again. Only after confirming that it was not saved should you run `add` with the uploaded path to avoid another upload. If PUT succeeded but verification could not finish, return `save_status: submitted_unverified`; do not describe the operation as safely retryable.

A connection interruption or truncated response during a write returns `save_status: outcome_unknown`. Inspect the library before deciding what to do; do not replay the request. If the operation completed but writing, flushing, or closing `--output-json` fails, stdout still contains the successful result. Stderr returns `operation_status: completed`, `output_json_status: failed`, and available recovery fields such as `pin_id`, `asset_path`, and `collection_id`, with a nonzero exit code. Save the result separately; do not repeat the upload or library edit.

Read [references/api.md](references/api.md) for API fields, formats, and error semantics.

## Examples

```bash
bash <skill-path>/scripts/pins.sh list --kind image
bash <skill-path>/scripts/pins.sh upload /absolute/reference.png --title "Product reference"
bash <skill-path>/scripts/pins.sh collection create "Ad assets"
bash <skill-path>/scripts/pins.sh collection move COLLECTION_ID --pin-ids PIN_ID
bash <skill-path>/scripts/pins.sh download PIN_ID --output /absolute/reference-copy.png
bash <skill-path>/scripts/pins.sh list --output-json /absolute/pins-result.json
```

Offline validation: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s <skill-path>/tests -p 'test_*.py' -v`. Offline tests do not establish that live authentication or deployment works.
