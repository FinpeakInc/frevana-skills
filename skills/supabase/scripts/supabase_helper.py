#!/usr/bin/env python3
"""Compatibility dispatcher; capability implementations live in separate scripts."""
import sys
sys.dont_write_bytecode = True

from supabase_common import entrypoint, run
import supabase_setup
import supabase_project
import supabase_db
import supabase_resources

HANDLERS = {
    "check": supabase_setup.handle,
    "init": supabase_project.handle,
    "link": supabase_project.handle,
    "gen-types": supabase_db.handle,
    "migration-new": supabase_db.handle,
    "db-lint": supabase_db.handle,
    "inspect": supabase_db.handle,
    "cli": supabase_resources.handle,
}


def handle(args, base, workdir, output, native):
    return HANDLERS[args.command](args, base, workdir, output, native)


def main(argv=None):
    return run(tuple(HANDLERS), __doc__, handle, argv)


if __name__ == "__main__":
    entrypoint(main)
