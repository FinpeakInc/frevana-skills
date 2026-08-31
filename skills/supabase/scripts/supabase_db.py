#!/usr/bin/env python3
"""Database migrations, lint, reset, diagnostics, types and native DB operations."""
import sys
sys.dont_write_bytecode = True

from supabase_common import entrypoint, execute, run

COMMANDS = ("gen-types", "migration-new", "db-lint", "inspect", "cli")
NATIVE_GROUPS = ("db", "migration", "inspect", "gen", "test", "seed")


def handle(args, base, workdir, output, native):
    command = args.command
    if command == "cli":
        tail = native
    elif command == "gen-types":
        tail = ["gen", "types", "typescript", "--" + args.target, "--schema", args.schema]
    elif command == "migration-new":
        tail = ["migration", "new", args.value]
    elif command == "db-lint":
        tail = ["db", "lint", "--" + args.target, "--schema", args.schema, "--fail-on", args.fail_on]
    elif command == "inspect":
        tail = ["inspect", "db", args.value, "--" + args.target]
    else:
        raise ValueError("Unsupported database command")
    return execute(base + tail, workdir, output)


def main(argv=None):
    return run(COMMANDS, __doc__, handle, argv, NATIVE_GROUPS)


if __name__ == "__main__":
    entrypoint(main)
