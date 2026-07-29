# Verbatim Publishing Contract

Use this contract whenever a WordPress create or update operation includes body content.

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

## Exactness Preflight

For a new post, page, or custom post type:

1. Save the supplied body as the comparison source.
2. Create the object with `status=draft`, even when the final requested state is `publish` or `future`.
3. Fetch the new object with `context=edit` and read `content.raw`.
4. Compare the returned raw string with the submitted body after JSON decoding.
5. Publish or schedule only when they match exactly.
6. If they differ, keep the object as a draft, identify the first difference when practical, and report that WordPress transformed or sanitized the body.

For an existing object:

1. Fetch and save its current editable representation before writing.
2. Preview the exact replacement body and target ID.
3. Update only after the user's request authorizes that exact replacement.
4. Fetch `content.raw` immediately and compare it with the submitted source.
5. If they differ, report the mismatch and offer restoration from the saved representation. Do not silently rewrite or automatically roll back without authorization.

Do not use rendered `content.rendered` for equality checks.

## WordPress Transformations

WordPress core, user capabilities, KSES filtering, plugins, or block validation may remove or alter scripts, styles, iframes, unsafe attributes, malformed HTML, or unsupported blocks. A successful HTTP status does not prove verbatim preservation.

When a mismatch occurs:

- report that exact preservation failed
- distinguish server sanitization from local conversion
- show a concise structural diff without exposing secrets
- do not claim the content was published exactly

## Visual Fidelity

Verbatim `content.raw` does not guarantee matching appearance. WordPress themes and templates control typography, width, spacing, metadata, headers, and surrounding layout. CSS from an external editor preview is not part of the post body unless the user explicitly supplies it and the site permits it.

If the user requires matching presentation, treat that as a separate styling task involving theme styles, block styles, a page template, or approved CSS. Do not inject styling during verbatim publication without explicit authorization.
