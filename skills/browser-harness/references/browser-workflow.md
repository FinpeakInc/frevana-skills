# Local browser workflow and recovery

## Connection

Run `bash <skill-path>/scripts/browser_harness.sh connect`. It executes
`print(page_info())`; successful page metadata is connection evidence.

On first setup, relay `chrome://inspect/#remote-debugging` and ask the user to
enable “Allow remote debugging for this browser instance”. This checkbox needs
manual action. If the command fails, make that change and run connect again.
If a command is still waiting for an Allow prompt, keep it alive and do not retry.

On macOS, while that exact command waits, use another Shell call:

```bash
bash <skill-path>/scripts/browser_harness.sh mac-approve
```

Preserve the same environment/`BU_NAME` for the waiting call and helper. If the
helper reports `accessibility-required`, tell the user which host app needs
System Settings > Privacy & Security > Accessibility access. Retry the helper
once after the user grants it, then resume/poll the original connection process.
On Windows/Linux ask the user to click Allow, then resume the original process.

For failures use `bash <skill-path>/scripts/browser_harness.sh doctor`, then the
current [upstream install guide](https://github.com/browser-use/browser-harness/blob/main/install.md).
Do not uninstall unrelated tools, delete skills, or reset recording preferences
to resolve a connection error. A connect failure after installation is partial
setup: retry `connect`, then `recordings`, without repeating an upgrade.

If a deep custom state path produces `AF_UNIX path too long` on macOS, set
`BH_RUNTIME_DIR` to a short, user-owned private directory and keep it identical
for every call to that daemon. Keep persistent state/screenshots in `BH_HOME`;
only the IPC directory needs shortening. Do not create a new runtime per command.

## Tasks and outputs

- Use the default local daemon. Avoid setting `BU_NAME`, `BU_CDP_URL`, or
  `BU_CDP_WS` for ordinary local setup. If inherited settings point to a remote
  browser, resolve them with the caller before claiming a local connection.
- One daemon has one mutable attached tab. The caller must serialize the full
  observe → switch → act → verify sequence across tasks. This wrapper does not
  provide a cross-task browser scheduler. Truly simultaneous tasks require
  separate remote browsers as described by the official skill; named local
  daemons are a last resort and still share one Chrome profile.
- Start with `new_tab(url)`, then reuse task tabs with `list_tabs()` and
  `switch_tab()`. Do not close unrelated user tabs or foreground Chrome unless
  requested. Close task-created tabs only when no longer needed and no unsaved work.
- Follow the generated upstream skill for AX-tree inspection, CDP input,
  screenshots, uploads and downloads. Verify the result after each consequential
  operation. Stop for passwords, MFA, consent, or ambiguous account selection.
- A local screenshot path must be read using the Agent's local image/vision tool.
  Text describing a path does not give the model visual access. If the host cannot
  read images, report the limitation for tasks requiring visual verification.
- Return concise results and useful absolute artifact paths. Verify downloaded
  files exist; do not claim success from a click alone.
- Respect user authorization for external actions. Browser connectivity does not
  authorize unrelated posting, messaging, purchases, or account changes.

## Recording

Setup uses upstream `recordings` status as the authority. It does not infer a
preference from directories or overwrite environment/config settings. To change
an existing preference after an explicit user request, invoke the installed CLI's
`recordings enable|disable`; `BH_RECORD` may still override that saved setting.
For task-specific requested recordings, use the upstream recording workflow and
retain the exact returned directory. Do not reenact a finished task as evidence.
Use `cli video init|review|export` for video production and follow the official
make-video interaction skill; exporting a video is separate from capturing traces.
