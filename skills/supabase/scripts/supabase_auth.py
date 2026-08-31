#!/usr/bin/env python3
"""Check PAT presence or verify its access without login/OAuth or token persistence."""
import os
import sys
sys.dont_write_bytecode = True

from supabase_common import emit, entrypoint, execute, parse_arguments, prepare

COMMANDS = ("status", "verify")


def main(argv=None):
    args, native, workdir = parse_arguments(COMMANDS, __doc__, argv)
    configured = bool(os.environ.get("SUPABASE_ACCESS_TOKEN", "").strip())
    if args.command == "status":
        # Presence only; no CLI installation, network access, or secret output.
        emit({"configured": configured, "variable": "SUPABASE_ACCESS_TOKEN"})
        return 0
    if not configured:
        print("ERROR: Configure SUPABASE_ACCESS_TOKEN from "
              "https://supabase.com/dashboard/account/tokens in the process environment. "
              "Do not paste it into chat. No login or OAuth was started.", file=sys.stderr)
        return 1
    base, output = prepare(args, workdir)
    # The token is inherited in the environment, never passed in argv.
    return execute(base + ["projects", "list"], workdir)


if __name__ == "__main__":
    entrypoint(main)
