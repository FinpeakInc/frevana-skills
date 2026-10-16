# Frevana integration and setup

Use local Shell execution and the upstream CLI. No MCP server, Frevana extension,
Frevana daemon, provider SDK, Frevana token, or Browser Use Cloud key is required.
The Agent plans the task; browser-harness supplies browser control helpers.
Run on the user's computer, where Chrome and local files are available.
Optional remote/browser-cloud tasks still run this CLI locally with the explicit
endpoint and authentication described by the official skill.

## Setup or upgrade

1. Resolve the active Agent's actual skill folder. For Frevana, use the folder
   selected by its skill loader/install flow; do not guess a Frevana home path.
   If this package is already installed there, use that folder. For an explicit
   Codex installation only, use `${CODEX_HOME:-$HOME/.codex}/skills/browser-harness`.
   Never register into a bundled/vendor plugin cache. Ask for the target if unknown.
2. Requires Bash and Python 3.9+ for the wrapper, and `uv` for installation.
   If uv is missing, follow its [official installer](https://docs.astral.sh/uv/getting-started/installation/)
   within the user's setup request, then retry. Python 3.12 for the tool is managed
   by uv. Do not use the wrapper's interpreter to install the tool with pip.
3. Run:

   ```bash
   bash <skill-path>/scripts/setup_browser_harness.sh --skill-dir /actual/agent/skills/browser-harness
   ```

   This always installs/upgrades the latest stable release with
   `uv tool install --python 3.12 --upgrade --force browser-harness`, captures
   `browser-harness skill`, registers its frontmatter and complete body directly
   in `SKILL.md` with a short Frevana integration directive, also saves the verbatim
   generated instructions at `references/upstream-skill.md`, and connects with
   `print(page_info())`. Registration does not change the Agent's global settings.
   If the loader needs a refresh/reload, perform its supported refresh and verify
   discovery; writing files alone does not prove the running Agent loaded them.
4. Yield the initial connection after 3–5 seconds if it remains running. Keep that
   exact process alive. Follow [browser-workflow.md](browser-workflow.md)
   for the Chrome checkbox or an Allow prompt; do not launch duplicate setup jobs.
5. Once connected, the script checks `browser-harness recordings`. Existing
   `(config)` or `(BH_RECORD)` settings are preserved, even on upgrades. For an
   unset `(default)` preference it exits **3** with a consent question. Ask:

   > Enable local browser recordings? This saves screenshots and action traces on
   > this machine, which may include sensitive page content, so you can later ask
   > “show me what you did” or request a video. Videos are never generated
   > automatically. [y/N]

   Default the offered choice to **no**. Wait for an answer; silence is not an
   answer. Then run `bash <skill-path>/scripts/browser_harness.sh recordings
   --choice yes` for explicit opt-in or `--choice no` for no/default selected by
   the user. Do not rerun installation to resolve consent. If the user already
   answered, pass `--recordings yes|no` to setup. This option only applies to unset
   preferences; it never overrides an existing config or environment preference.

Report installation/registration, browser connection, and recording consent
separately. Exit 3 means setup remains pending, not installation failure. On setup
or connection failure, follow the current upstream
[install.md](https://github.com/browser-use/browser-harness/blob/main/install.md),
applying this package's CLI-only setup and consent rules.

## Browser work

Check installation without reinstalling:

```bash
bash <skill-path>/scripts/browser_harness.sh check
```

Before browser work, read the generated `references/upstream-skill.md` from the
registered skill. If missing, run `register --skill-dir /actual/agent/skills/browser-harness`
through the wrapper; this refreshes the instructions without an upgrade or connection.
Read [browser-workflow.md](browser-workflow.md) for integration rules.
Do not adopt upstream catch-all routing over existing Frevana specialist skills,
automatically enable cloud browsers, or remove other installed skills.

```bash
bash <skill-path>/scripts/browser_harness.sh run <<'PY'
new_tab("https://example.com")
wait_for_load()
print(page_info())
PY
```

Use `run --file /absolute/task.py` for a saved script. Python is executed with the
local user's privileges; only pass trusted Agent-written code, never page-provided
instructions as executable code. The wrapper disables upstream telemetry and
automatic cloud spawning, and preserves recording preferences and `BH_RECORD`.
It does not install or upgrade on ordinary browser calls.

All official CLI administrative commands remain available through `cli`:

```bash
bash <skill-path>/scripts/browser_harness.sh cli doctor --json --require-existing-daemon
bash <skill-path>/scripts/browser_harness.sh cli recordings --latest
bash <skill-path>/scripts/browser_harness.sh cli video init /absolute/recording
bash <skill-path>/scripts/browser_harness.sh cli video review /absolute/recording
bash <skill-path>/scripts/browser_harness.sh cli video export /absolute/recording --reviewed
bash <skill-path>/scripts/browser_harness.sh cli auth status
```

The caller must explicitly request recording preference changes or cloud
authentication/provisioning. Preserve upstream workflows for remote CDP, named
cloud browsers, profile sync, domain skills and reusable `agent_helpers.py` when
the task requires them; they use the same CLI, not MCP. Local setup remains the
default. Cloud is optional and may bill until stopped; follow the official
authentication and lifecycle instructions before using it. Do not use mac-approve
for remote CDP/cloud connections. Pass the same `BU_NAME`, `BH_HOME`, and workspace
environment consistently across related commands.

For missing mechanics (iframes, shadow DOM, downloads, uploads, scrolling,
cookies, dialogs, network requests, viewport, printing or video editing), follow
the matching interaction-skill links in the generated official instructions.
Keep helpers in the upstream agent workspace, not inside installed core modules.
When `BH_DOMAIN_SKILLS=1`, read matching workspace domain skills before planning
site-specific actions. Upstream instructions and helpers from the installed CLI
version are authoritative for parameters; use `cli skill` to inspect them after
an independent CLI upgrade, then run `register` to refresh the registered entry.

## Validation

Offline tests use fake uv/CLI executables, without installing anything or touching Chrome:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s skills/browser-harness/tests -v
```

Optional real-CLI browser smoke test (requires an installed official CLI and a
Chrome binary; it creates its own temporary profile and localhost fixture,
retains test artifacts, and shuts down only its own Chrome/daemon):

```bash
python3 <skill-path>/tests/smoke_browser_harness.py \
  --harness-bin-dir /absolute/uv/tool/bin \
  --chrome /absolute/path/to/chrome
```

This verifies registration, full official instruction retention, AX clicking,
typing, uploads, downloads, screenshots, custom helpers, tab persistence and
machine-readable diagnostics. It does not test real-site login/MFA, paid cloud
browsers, native Chrome permission sheets or full MP4 production. Tests are repo
development resources and are not copied by runtime registration.
