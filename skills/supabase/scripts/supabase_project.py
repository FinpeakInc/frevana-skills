#!/usr/bin/env python3
"""Project initialization, linking and native projects/orgs/config operations."""
import sys
sys.dont_write_bytecode = True

from supabase_common import emit, entrypoint, execute, run

COMMANDS = ("init", "link", "cli")
NATIVE_GROUPS = ("projects", "orgs", "config", "unlink")


def handle(args, base, workdir, output, native):
    command = args.command
    if command == "init":
        config = workdir / "supabase/config.toml"
        if config.is_file():
            emit({"status": "already_initialized", "path": str(config)})
            return 0
        code = execute(base + ["init"], workdir)
        if not code:
            if not config.is_file():
                raise ValueError("CLI returned success but supabase/config.toml was not created")
            emit({"status": "initialized", "path": str(config)})
        return code
    tail = native if command == "cli" else ["link", "--project-ref", args.value]
    return execute(base + tail, workdir, output)


def main(argv=None):
    return run(COMMANDS, __doc__, handle, argv, NATIVE_GROUPS)


if __name__ == "__main__":
    entrypoint(main)
