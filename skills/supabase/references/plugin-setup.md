# Install the Supabase agent plugin when needed

This is the official Supabase **AI agent plugin**, not a required extension to the Supabase CLI. Management API and CLI project/DB/resource operations work without it. Install it when the requested workflow needs its agent guidance or MCP integration, or the user asks for plugin setup. Do not require it for ordinary API/CLI calls.

## Detect, install, verify

1. Inspect the active agent's loaded plugin/skill catalog and available Supabase tools. An already loaded official Supabase plugin is sufficient evidence of installation; reuse it. If uncertain, use the host's supported installed-plugin listing. A cached source folder alone does not prove the plugin is enabled. Do not install again just because MCP authentication is missing.
2. If the plugin is needed and missing, automatically install it under the user's existing bootstrap authorization; do not stop to ask the same installation question again. Prefer a supported native installation tool if available. Obey that tool's eligibility and approval rules; don't turn a suggestion-only tool result into an installation claim.
3. For supported local coding agents, use the official Supabase distribution `supabase-community/supabase-plugin` through the `plugins` installer. Resolve the **current agent's** target id using installer help/`targets` and select it explicitly; auto-detection without a target can install into multiple agents. For example, when the active agent is Codex:

```bash
# Installer 1.3.4 supports --target, --scope and --yes; inspect help for other versions.
npx --yes plugins@1.3.4 add supabase-community/supabase-plugin --target codex --scope user --yes
```

The leading `--yes` permits npx's package download; the trailing flag confirms the already-authorized plugin installation. These flags do not authorize database writes or bypass a host's mandatory approval. Use the equivalent verified target for another supported agent. Install only into the active agent, and don't select project scope over user scope unless project configuration changes are intended. Reuse a working installer; no global npm install is required.
4. After success, verify the agent's installed/enabled plugin state, reload through its supported mechanism if needed, and verify that expected skills/tools are actually available. If reload requires a new session, report that state; do not repeatedly reinstall. Installer success alone does not prove that the current session has loaded tools.
5. Plugin installation is separate from account authentication. Do not launch OAuth just because a plugin was installed. Keep this skill's primary path on Management API/CLI + `SUPABASE_ACCESS_TOKEN`; a plugin used only for guidance does not need an MCP account connection. For actual MCP access follow the token-first rules below.

## Authentication: prefer the configured PAT

For a manually configurable remote MCP client, official Supabase MCP supports a PAT in the `Authorization` header. Reuse the intended `SUPABASE_ACCESS_TOKEN` through the client's supported environment/secret reference mechanism, never as a plaintext token in tracked configuration. The logical configuration is:

- Server: `https://mcp.supabase.com/mcp?project_ref=<chosen-project-ref>` for project-scoped work.
- Header: `Authorization: Bearer <value resolved from SUPABASE_ACCESS_TOKEN>`.
- Use `read_only=true` for read-only work, and a development/test project as recommended by Supabase. Project scoping disables account-level project-management tools; use the project Management API actions for those tasks.

The lines above describe the settings, not a universal interpolation syntax. Check the selected client's docs for custom headers and environment expansion; some managed connectors don't expose either. Validate a harmless read after connecting before reporting authentication success.

If the platform only exposes OAuth, explain that restriction and keep using the token-based CLI when it can complete the task. Run the platform's OAuth flow only when the user chooses that connection or the requested MCP-only capability requires it. Relay the exact authorization URL when supplied; respect platform confirmation requirements. Do not silently edit managed plugin settings to force PAT support or broaden permissions.

Source: [MCP manual/PAT authentication](https://supabase.com/docs/guides/ai-tools/mcp#manual-authentication).

If installation fails, stop retrying, report the concrete manager/network/permission error and continue any unaffected CLI path. Do not overwrite agent settings, enable policy-disabled plugins, or use a filesystem workaround to bypass a platform denial. If only a platform confirmation UI can complete installation, launch the supported flow and state what remains for the user.

Database extensions (`CREATE EXTENSION`) and language runtimes are not this agent plugin. Provision those only as required for the chosen workflow; never install local Docker as a plugin dependency, and use the Docker-free DB/resource paths instead; enabling a DB extension remains a scoped database change. Do not fabricate `supabase plugin install` commands.

Sources: [Supabase plugin installation](https://supabase.com/docs/guides/ai-tools/plugins), [official plugin repository](https://github.com/supabase-community/supabase-plugin), [installer commands and targets](https://github.com/vercel-labs/plugins).
