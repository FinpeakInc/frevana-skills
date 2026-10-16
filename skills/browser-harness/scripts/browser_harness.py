#!/usr/bin/env python3
"""Local CLI bootstrap and registration. No provider calls or model runtime."""

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

PACKAGE = Path(__file__).resolve().parents[1]
INSTALL_GUIDE = "https://github.com/browser-use/browser-harness/blob/main/install.md"
CONSENT_PENDING = 3


def environment():
    env = os.environ.copy()
    env["BH_TELEMETRY"] = "0"
    env["UV_PRERELEASE"] = "disallow"
    # Empty blocks upstream .env setdefault while remaining falsy; "0" is truthy.
    env["BU_AUTOSPAWN"] = ""
    return env


def run(command, *, capture=False, code=None):
    return subprocess.run(
        command, env=environment(), text=True, encoding="utf-8", check=True,
        input=code, stdout=subprocess.PIPE if capture else None,
    )


def find_uv():
    found = shutil.which("uv")
    if found:
        return found
    candidate = Path.home() / ".local/bin/uv"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    raise RuntimeError("uv is missing. Install uv using https://docs.astral.sh/uv/getting-started/installation/ then retry.")


def find_harness():
    # uv's bin directory takes precedence over stale commands elsewhere on PATH.
    try:
        directory = run([find_uv(), "tool", "dir", "--bin"], capture=True).stdout.strip()
    except (RuntimeError, subprocess.CalledProcessError):
        directory = ""
    if directory:
        candidate = Path(directory) / ("browser-harness.exe" if os.name == "nt" else "browser-harness")
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    found = shutil.which("browser-harness")
    if found:
        return found
    raise RuntimeError("browser-harness is missing. Run setup with --skill-dir pointing to the active Agent's skill folder.")


def atomic_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".browser-harness-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def register(harness, destination):
    upstream = run([harness, "skill"], capture=True).stdout
    frontmatter = re.match(r"\A---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)", upstream)
    if not frontmatter or not re.search(r"^name:\s*browser-harness\s*$", frontmatter.group(1), re.M):
        raise RuntimeError("browser-harness skill did not return the expected skill frontmatter; registration left unchanged.")
    target = Path(destination).expanduser().resolve()
    if target.name != "browser-harness":
        raise RuntimeError("--skill-dir must name the browser-harness skill folder, not its parent.")
    version = run([harness, "--version"], capture=True).stdout.strip()
    directive = (
        "\n\n## Frevana CLI integration\n\n"
        "Before any command, read [references/integration.md](references/integration.md) "
        "and [references/browser-workflow.md](references/browser-workflow.md). "
        "Use `bash <skill-path>/scripts/browser_harness.sh run` for Python on stdin "
        "and `bash <skill-path>/scripts/browser_harness.sh cli <args>` for official "
        "CLI commands. Follow the setup and recording-consent workflow there. "
        "All official browser instructions below apply; use no MCP.\n\n"
    )
    entrypoint = upstream[:frontmatter.end()] + directive + upstream[frontmatter.end():]
    # Pre-read all sources and probe the version before touching the destination.
    files = {}
    if target != PACKAGE:
        for relative in ("agents/openai.yaml", "references/browser-workflow.md", "references/integration.md",
                         "scripts/browser_harness.sh", "scripts/setup_browser_harness.sh",
                         "scripts/browser_harness.py"):
            files[relative] = (PACKAGE / relative).read_text(encoding="utf-8")
    files["references/upstream-skill.md"] = upstream
    # Publish the discoverable entrypoint last, after its runtime and references.
    files["SKILL.md"] = entrypoint
    for relative, content in files.items():
        atomic_text(target / relative, content)
    print(f"Registered {target / 'SKILL.md'}; upstream instructions: {target / 'references/upstream-skill.md'}; {version}")


def recording_preference(harness, choice):
    status = run([harness, "recordings"], capture=True).stdout
    print(status, end="" if status.endswith("\n") else "\n")
    match = re.search(r"^auto-recording:\s*(on|off)\s*\((default|config|BH_RECORD)\)\s*$", status, re.M)
    if not match:
        raise RuntimeError("Unrecognized recording status; preference was not modified.")
    source = match.group(2)
    if source != "default":
        print(f"Preserved existing recording preference ({source}).")
        return 0
    if choice == "ask":
        print("Recording consent required: Enable local browser recordings? This saves screenshots and action traces on this machine, which may include sensitive page content. Videos are never generated automatically. [y/N]", file=sys.stderr)
        print("Ask the user, then run recordings --choice yes|no. No response is not consent; leave this pending. An explicit default selection is no.", file=sys.stderr)
        return CONSENT_PENDING
    run([harness, "recordings", "enable" if choice == "yes" else "disable"])
    return 0


def connect(harness):
    # Inherit stderr so Chrome's pending permission hint is visible while this
    # exact process remains alive. The caller can yield and approve separately.
    run([harness], code="print(page_info())\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    setup = sub.add_parser("setup", help="Install/upgrade stable release with uv + Python 3.12, register and connect")
    setup.add_argument("--skill-dir", required=True, help="Exact active Agent skill folder ending in browser-harness")
    setup.add_argument("--recordings", choices=("ask", "yes", "no"), default="ask",
                       help="For an unset preference only; yes requires user opt-in, no requires an explicit answer/default selection")
    registration = sub.add_parser("register", help="Refresh registration without installing or connecting")
    registration.add_argument("--skill-dir", required=True)
    for command in ("check", "connect", "doctor", "mac-approve"):
        sub.add_parser(command)
    recordings = sub.add_parser("recordings", help="Inspect/preserve preference, or resolve first-install consent")
    recordings.add_argument("--choice", choices=("ask", "yes", "no"), default="ask")
    execute = sub.add_parser("run", help="Execute trusted Agent Python from stdin or a file; never installs/upgrades")
    execute.add_argument("--file", type=Path)
    cli = sub.add_parser("cli", help="Pass official CLI arguments through unchanged (auth, video, recordings, diagnostics, etc.)")
    cli.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if args.command in ("setup", "register"):
            if Path(args.skill_dir).expanduser().name != "browser-harness":
                raise RuntimeError("--skill-dir must end in browser-harness.")
        if args.command == "setup":
            run([find_uv(), "tool", "install", "--python", "3.12", "--upgrade", "--force", "browser-harness"])
        harness = find_harness()
        if args.command in ("setup", "register"):
            register(harness, args.skill_dir)
        if args.command == "setup":
            connect(harness)
            result = recording_preference(harness, args.recordings)
            if result == 0:
                print("Setup complete: installed, registered, browser connected, recording preference resolved.")
            return result
        if args.command == "check":
            run([harness, "--version"])
        elif args.command == "connect":
            connect(harness)
        elif args.command == "doctor":
            run([harness, "--doctor"])
        elif args.command == "mac-approve":
            if sys.platform != "darwin":
                raise RuntimeError("mac-approve is macOS-only. Keep the original connection command running and click Allow in Chrome.")
            run([harness, "mac-approve"])
        elif args.command == "recordings":
            return recording_preference(harness, args.choice)
        elif args.command == "run":
            if args.file:
                code = args.file.read_text(encoding="utf-8")
            elif sys.stdin.isatty():
                raise RuntimeError("Supply --file PATH or Python code on stdin.")
            else:
                code = sys.stdin.read()
            if not code.strip():
                raise RuntimeError("Python input is empty.")
            run([harness], code=code)
        elif args.command == "cli":
            cli_args = args.args[1:] if args.args[:1] == ["--"] else args.args
            if not cli_args:
                raise RuntimeError("Supply official CLI arguments, e.g. cli -- --help.")
            run([harness, *cli_args])
        return 0
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print(f"Error: {error}\nSetup/connection recovery: {INSTALL_GUIDE}", file=sys.stderr)
        return error.returncode if isinstance(error, subprocess.CalledProcessError) and error.returncode > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
