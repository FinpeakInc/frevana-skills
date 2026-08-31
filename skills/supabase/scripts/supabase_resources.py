#!/usr/bin/env python3
"""Native CLI entry for Storage, Functions, Secrets and other resource groups."""
import sys
sys.dont_write_bytecode = True

from supabase_common import entrypoint, execute, run

COMMANDS = ("cli",)


def handle(args, base, workdir, output, native):
    return execute(base + native, workdir, output)


def main(argv=None):
    return run(COMMANDS, __doc__, handle, argv)


if __name__ == "__main__":
    entrypoint(main)
