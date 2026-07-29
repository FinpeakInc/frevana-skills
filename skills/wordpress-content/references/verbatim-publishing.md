# Verbatim Publishing Contract

Use this contract whenever a WordPress create or update operation includes body content.

Use `wordpress_rest.sh verbatim-create` for new objects and `wordpress_rest.sh verbatim-update` for existing objects. Do not use the generic `request` action or direct `curl` for body writes.

## Source Is Authoritative

Preserve the supplied body after JSON decoding as the canonical source:

- keep every character, heading, paragraph, block comment, tag, attribute, shortcode, URL, whitespace choice, and ordering
- perform only the JSON escaping required to transport the same string
- do not improve grammar, typography, accessibility, SEO, structure, or style unless requested
- do not infer title, excerpt, taxonomy, dates, or featured media from the body
- do not insert title, excerpt, category, author, date, reading time, or publication status into the body unless they were part of the supplied body

If the user provides separate title, excerpt, taxonomy, date, or media values, map them to their WordPress fields without changing `content`.

## Format Handling

Preserve the detected or declared source format:

- Gutenberg block source: retain block comments, JSON attributes, inner HTML, and block order exactly.
- Classic HTML or an HTML fragment: submit the fragment unchanged.
- Plain text: submit the literal text unchanged. Do not wrap it in paragraphs or add line-break tags.
- Markdown: submit literal Markdown unchanged. Warn that WordPress will not render Markdown unless the site has compatible processing.
- Shortcodes or plugin blocks: retain them unchanged; do not expand or emulate their output.
- A full HTML document containing `html`, `head`, or `body`: do not silently reduce it to a fragment. Explain that WordPress post content is not a complete page document and ask whether to publish it literally or adapt it.
- Binary documents such as DOCX or PDF: upload the original file as media when requested. Do not extract or convert it into post content without explicit instructions.

Never convert one format into another merely because the destination is WordPress.

## Publish and Advisory Verification

For a new post, page, or custom post type:

1. Save the supplied body in the JSON payload.
2. Run `verbatim-create` without `--execute` and review the plan.
3. Add `--execute`; the wrapper submits that JSON file directly without changing its `content`, `status`, or other fields.
4. The wrapper then fetches `content.raw` and compares it after JSON decoding when possible.
5. If they differ, report that WordPress transformed or sanitized the body. Treat this as a warning: do not stop, unpublish, return to draft, or roll back an otherwise successful request.
6. Verify the requested `status` separately. A request for `publish` that remains `draft` is a publication failure, not a body-format mismatch.

For an existing object:

1. Run `verbatim-update` with the exact object endpoint, payload, and `--backup FILE`.
2. Review the dry-run, then add `--execute`.
3. Let the wrapper save the editable object, update it, fetch `content.raw`, and compare it with the submitted source.
4. If they differ, report the mismatch and the backup location. Do not fail or automatically roll back an otherwise successful update.

Do not use rendered `content.rendered` for equality checks.

## WordPress Transformations

WordPress core, user capabilities, KSES filtering, plugins, or block validation may remove or alter scripts, styles, iframes, unsafe attributes, malformed HTML, or unsupported blocks. A successful HTTP status does not prove verbatim preservation.

When a mismatch occurs:

- report that WordPress stored a different raw representation
- distinguish server sanitization from local conversion
- show a concise structural diff without exposing secrets
- do not treat the difference alone as a publication failure
- do not automatically change status or roll back

These lenient rules apply only to body representation. Authentication errors, HTTP errors, and a requested publication status that was not applied remain failures.

## Visual Fidelity

Verbatim `content.raw` does not guarantee matching appearance. WordPress themes and templates control typography, width, spacing, metadata, headers, and surrounding layout. CSS from an external editor preview is not part of the post body unless the user explicitly supplies it and the site permits it.

If the user requires matching presentation, treat that as a separate styling task involving theme styles, block styles, a page template, or approved CSS. Do not inject styling during verbatim publication without explicit authorization.
