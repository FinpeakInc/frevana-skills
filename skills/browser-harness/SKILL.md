---
name: browser-harness
description: Control Chrome via CDP for clicking, typing, navigation, logged-in sessions, JS-rendered pages, screenshots, uploads, downloads and browser task recordings. Also install or upgrade browser-harness with uv and Python 3.12 and connect the browser. Use plain HTTP for static public content.
---

# Browser Harness

This is the bootstrap entrypoint for the official browser-harness CLI skill in
Frevana. Use local Shell execution; no MCP server or Frevana Chrome Extension.

Read [references/integration.md](references/integration.md) for setup, registration,
recording consent and CLI commands. Read
[references/browser-workflow.md](references/browser-workflow.md) for connection
recovery and task execution rules.

For a browser task, check installation with
`bash <skill-path>/scripts/browser_harness.sh check`. If missing, follow setup in
the integration reference. If installed, run
`bash <skill-path>/scripts/browser_harness.sh register --skill-dir <skill-path>`
to generate the official entrypoint in this installed skill folder, then read
the resulting `SKILL.md` before acting. For a read-only/vendor cache, register to
the active Agent's writable skill folder instead; do not modify plugin caches.

Registration uses the installed CLI's `browser-harness skill` frontmatter and
complete body, preceded by a short integration directive. It retains a verbatim
copy at `references/upstream-skill.md`. This avoids substituting a reduced list
of actions for the official operating instructions. Refresh registration after
CLI upgrades; refresh the host's skill loader if required.
