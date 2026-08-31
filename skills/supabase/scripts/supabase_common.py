#!/usr/bin/env python3
"""Shared argument validation, CLI execution and atomic output handling."""
import argparse
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile


def parser(commands, description):
    root = argparse.ArgumentParser(description=description, allow_abbrev=False)
    sub = root.add_subparsers(dest="command", required=True)
    for name in commands:
        p = sub.add_parser(name, allow_abbrev=False)
        p.add_argument("--workdir", default=".", help="Existing project directory")
        p.add_argument("--profile", help="Supabase CLI authentication profile")
        p.add_argument("--no-install", action="store_true", help="Check/use existing CLI only (offline diagnostics)")
        if name in ("gen-types", "db-lint", "inspect"):
            p.add_argument("--target", choices=("linked",), default="linked")
        if name in ("gen-types", "db-lint"):
            p.add_argument("--schema", default="public")
        if name in ("gen-types", "inspect", "cli"):
            p.add_argument("--output", help="Save stdout atomically; relative to workdir")
        if name == "db-lint":
            p.add_argument("--fail-on", choices=("none", "warning", "error"), default="error")
        if name in ("migration-new", "inspect", "link"):
            p.add_argument("value", help="Migration name, metric, or project ref")
    return root


def emit(value):
    print(json.dumps(value, ensure_ascii=False))


def output_path(workdir, value):
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = workdir / path
    # Do not resolve the leaf: that would silently follow a symlink output target.
    path = path.parent.resolve() / path.name
    if path.is_symlink():
        raise ValueError("Output must not be a symlink")
    if path.exists():
        info = path.stat()
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("Output must be a regular file")
        if hasattr(os, "getuid") and info.st_uid != os.getuid():
            raise ValueError("Output must be a current-user-owned regular file")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def execute(argv, cwd, output=None):
    if output is None:
        return subprocess.run(argv, cwd=cwd).returncode
    # Stage in the destination directory so replacement is atomic on this filesystem.
    fd, temporary = tempfile.mkstemp(prefix=".supabase-", dir=output.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            result = subprocess.run(argv, cwd=cwd, stdout=stream)
        if result.returncode:
            return result.returncode
        os.replace(temporary, output)
        emit({"status": "success", "output": str(output)})
        return 0
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def parse_arguments(commands, description, argv=None, native_groups=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    native = None
    if arguments and arguments[0] == "cli" and "--" in arguments:
        split = arguments.index("--")
        arguments, native = arguments[:split], arguments[split + 1:]
    p = parser(commands, description)
    args = p.parse_args(arguments)
    if args.command == "cli" and not native:
        p.error("cli requires an explicit separator: cli [helper options] -- <CLI arguments>")
    # The wrapper owns workdir so CLI selection and relative output paths stay coherent.
    if native and any(a == "--workdir" or a.startswith("--workdir=") for a in native):
        p.error("put --workdir before the cli separator")
    if native and native_groups and native[0] not in native_groups:
        p.error("this entry accepts CLI groups: " + ", ".join(native_groups))
    workdir = Path(args.workdir).expanduser().resolve()
    if not workdir.is_dir():
        p.error("--workdir must be an existing directory")
    return args, native, workdir


def prepare(args, workdir):
    from supabase_setup import cli_path

    output = output_path(workdir, args.output) if getattr(args, "output", None) else None
    binary = cli_path(workdir, auto_install=not args.no_install)
    base = [binary, "--workdir", str(workdir)]
    if args.profile:
        base += ["--profile", args.profile]
    return base, output


def run(commands, description, handler, argv=None, native_groups=None):
    args, native, workdir = parse_arguments(commands, description, argv, native_groups)
    base, output = prepare(args, workdir)
    return handler(args, base, workdir, output, native)


def entrypoint(main):
    try:
        sys.exit(main())
    except (ValueError, OSError) as error:
        # Do not include a subprocess argv (which may contain credentials) in errors.
        print("ERROR: " + str(error), file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("ERROR: Supabase setup timed out; verify installation state before retrying.", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
