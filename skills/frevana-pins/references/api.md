# Server API contract

Source: `src/modules/user-pins/{user-pins.controller.ts,user-pins.service.ts,user-pins.library.ts,user-pins.paths.ts}`.
All six routes use JWT Bearer authentication and scope storage to `req.user.id`.
The Nest bootstrap does not set a global `/api` prefix; supply the actual deployment base URL.

| Method | Route | Input | Output |
| --- | --- | --- | --- |
| GET | `/user-pins` | None | Snapshot |
| PUT | `/user-pins` | `{pins?, collections?}` | Snapshot |
| POST | `/user-pins/present` | `{urls?: string[]}` | `{urls: {original_ref: signed_url}}` |
| POST | `/user-pins/assets` | multipart field `file` | `{path, url}` |
| POST | `/user-pins/assets/upload-url` | `{fileName, contentType?}` | `{path, signedUrl, token: ""}` |
| GET | `/user-pins/assets` | Query `src` or `path`; optional `proxy=1` | Proxy bytes when `proxy=1`; otherwise JSON `{url}` with Accept application/json, or 302 |

Snapshot: `{version: 1, updatedAt: epoch_ms, pins: Pin[], collections: Collection[]}`.

Pin:
```json
{"id":"pin-id","kind":"image","title":"Optional title","sourceUrl":"https://example.com/source","sourcePageUrl":"https://example.com/page","mediaUrl":"assets/file.png","posterUrl":"assets/poster.png","contentType":"image/png","savedAt":1720000000000}
```
Required valid values are kind image/video and nonempty mediaUrl; the CLI supplies id, sourceUrl and savedAt. Optional fields may be omitted.

Collection:
```json
{"id":"collection-id","title":"References","createdAt":1720000000000,"updatedAt":1720000000000,"pinIds":["pin-id"]}
```

PUT replaces each provided array; omitted arrays are preserved. Collections are sorted by updatedAt descending. References to missing Pins and repeated membership across collections are pruned. Server truncates Pins to 100 and collections to 40, so the CLI refuses additions beyond the limits.

Private S3 paths are stored beneath `pins/{user}/` in production and `pins-dev/{user}/` otherwise. The library stores stable relative `assets/...` refs and presents signed URLs valid for one hour. Owner-scoped upload paths can also be passed to add/present. External media URLs are retained as supplied; this API does not materialize external media.

Allowed MIME types: image/png, image/jpeg, image/webp, image/gif, video/webm, video/mp4, video/quicktime. Multipart file limit: 100 MiB. The presigned-upload endpoint does not apply the multipart size check. Getting an upload URL alone does not create an object or Pin.

Missing file, unsupported MIME type, invalid owned path: 400. Missing proxy media: 404. Authentication failures follow JwtAuthGuard. The CLI does not automatically retry writes or expose response bodies in errors.

No separate Pin/collection CRUD, S3 object deletion, server-side search, atomic compare-and-swap or pagination exists in this controller.
