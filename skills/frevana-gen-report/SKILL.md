---
name: frevana-gen-report
description: Generate final HTML using Frevana by combining your content with a selected template ID. Use this when you need server-side rendering through Frevana templates or want the system to return ready-to-use raw HTML without additional processing.
---

# Frevana Report Generator

Generate final HTML by calling Frevana's `POST https://ai-factory.frevana.com/report/generate`.

## Purpose

This skill is for **backend HTML generation**.

Inputs:
- `content`
- `template_id`

Output:
- final HTML extracted from the Frevana API response JSON's `content` field

The API returns JSON in the shape `{"content": "<html>..."}`. This skill extracts the `content` value and treats that HTML as the final API result. Do **not** modify, optimize, rewrite, or post-process it unless the user explicitly asks for that.

## What This Skill Needs

- user-provided `content` or `content_file`
- user-provided `template_id`
- `FREVANA_TOKEN` in the environment, or an explicit `--token` override for the current run
- `curl`
- `bash`

## Execution Order

Use this flow so the request stays simple and reliable:

1. Confirm the user has provided `template_id` and either `content` or `content_file`.
2. Prefer the script over ad hoc `curl` commands.
3. Let the script read `FREVANA_TOKEN` first.
4. In interactive shell usage, if `FREVANA_TOKEN` is missing, the script may prompt for it.
5. In non-interactive or agent workflows, fail fast if the token is missing and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly.
6. Parse the response JSON and extract its `content` field.
7. Return that extracted HTML exactly as provided in `content`.
8. When useful, also save it to an `.html` file.

## Commands

### Inline content

```bash
bash <skill-path>/scripts/generate_report.sh \
  --content "report content" \
  --template-id "report template id"
```

### Content from file

Use this for long or multi-line content.

```bash
bash <skill-path>/scripts/generate_report.sh \
  --content-file ./report-content.md \
  --template-id "report template id"
```

### Save returned HTML to a file

```bash
bash <skill-path>/scripts/generate_report.sh \
  --content-file ./report-content.md \
  --template-id "report template id" \
  --output ./out/frevana-report.html
```

### Token override for the current run

Use a token override only when the user explicitly gives one for the current run.

```bash
bash <skill-path>/scripts/generate_report.sh \
  --content "report content" \
  --template-id "report template id" \
  --token "your bearer token"
```

## Fixed Request Shape

The script sends this payload shape:

```json
{
  "content": "report content",
  "template_id": "report template id",
  "target_platform": "generate_auto_formating_content"
}
```

`target_platform` is fixed and should not be changed unless the API contract changes.

## Response Shape

The API response is expected to be JSON like:

```json
{
  "content": "<html>...</html>"
}
```

This skill extracts `content` and returns only that HTML.

## Output

- Success: the script parses the response JSON, extracts `content`, and prints that HTML string to stdout
- With `--output`: the extracted HTML is also written to the specified file path
- Failure: the script prints the response body or parsing error and exits non-zero
- The extracted HTML is the final API result and should be passed through unchanged unless the user explicitly requests edits

## Notes

- Require exactly one of `--content` or `--content-file`
- If either content input or `template_id` is missing, stop and ask for it
- If `curl` is missing, stop and tell the user to install `curl`
- If `bash` is unavailable, stop and tell the user to run the script in a Bash environment
- Do not echo the Bearer token back to the user
- Prefer `--content-file` for long content because it is more stable than shell-quoted multi-line strings

## Example Prompts

### 中文

- "用 Frevana 的模板 `tpl_123` 生成一个 HTML 报告，内容是这段市场分析"
- "用 `medium-article-template-v2` 把这篇文章内容生成最终 HTML，直接返回原始结果，不要改写"
- "帮我调用 `/report/generate`，`template_id` 是 `annual_summary_v2`，把结果保存成 HTML 文件"
- "给你 template_id 和正文内容，调用 Frevana 后端 API 生成最终 HTML"

### English

- "Use Frevana template `tpl_123` to generate an HTML report from this market analysis content"
- "Use `medium-article-template-v2` to turn this article into final HTML and return the raw result without rewriting it"
- "Call `/report/generate` with template_id `annual_summary_v2` and save the result as an HTML file"
- "Given a template ID and article content, call the Frevana backend API and return the final HTML"
