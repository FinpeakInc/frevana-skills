#!/usr/bin/env python3
"""Check PAT presence or verify Management API access without installing a CLI."""
import os
import sys
sys.dont_write_bytecode = True

from supabase_common import emit, entrypoint, parse_arguments
from supabase_api import APIError, Client, identifier

COMMANDS = ('status', 'verify')


def configure(command, p):
    if command == 'verify':
        p.add_argument('--project-ref', type=identifier, help='Verify this project directly without enumerating all projects')


def main(argv=None):
    args, _, _ = parse_arguments(COMMANDS, __doc__, argv, configure=configure)
    if args.command == 'status':
        emit({'configured': bool(os.environ.get('SUPABASE_ACCESS_TOKEN', '').strip()),
              'variable': 'SUPABASE_ACCESS_TOKEN'})
        return 0
    if args.profile:
        raise ValueError('PAT verification uses SUPABASE_ACCESS_TOKEN; --profile is CLI-only.')
    client = Client()
    if args.project_ref:
        client.project(args.project_ref)
    else:
        projects = client.request('GET', '/v1/projects')
        if not isinstance(projects, list):
            raise APIError('Could not verify project-list response.')
    emit({'status': 'verified', 'transport': 'management-api', 'project_ref': args.project_ref,
          'scope': 'project-read' if args.project_ref else 'projects-list',
          'note': 'This verifies only the selected read permission, not every write permission.'})
    return 0


if __name__ == '__main__':
    entrypoint(main)
