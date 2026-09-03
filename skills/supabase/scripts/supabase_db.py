#!/usr/bin/env python3
"""Remote database migrations, lint, diagnostics, types and native DB operations."""
import sys
sys.dont_write_bytecode = True

from supabase_common import entrypoint, execute, parse_arguments, prepare
from supabase_api import (APIError, api_context, api_options, confirm_target, read_file,
                          read_json, result, summary, verify_after_write)

LEGACY = ("gen-types", "migration-new", "db-lint", "inspect", "cli")
API_COMMANDS = ("query", "tables", "types", "migrations", "migration-apply", "backups", "restore-pitr")
COMMANDS = API_COMMANDS + LEGACY
NATIVE_GROUPS = ("db", "migration", "migrations", "inspect", "gen", "test", "seed")


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


def configure(command, p):
    if command in LEGACY:
        return
    api_options(p, mutation=command in ('query', 'migration-apply', 'restore-pitr'),
                destructive=command == 'restore-pitr')
    if command in ('query', 'migration-apply'):
        p.add_argument('--file', required=True, help='Reviewed UTF-8 SQL file; not SQL in argv')
    if command == 'query':
        p.add_argument('--write', action='store_true', help='Permit the already-authorized SQL write; default sends read_only=true')
        p.add_argument('--parameters-file', help='JSON array of bound SQL parameter values')
    if command == 'migration-apply':
        p.add_argument('--name', required=True)
        p.add_argument('--rollback-file', help='Optional reviewed rollback SQL, not automatic undo')
        p.add_argument('--partner-api-access', action='store_true',
                       help='Confirm this caller has Supabase selected-partner migration API access')
    if command in ('tables', 'types'):
        p.add_argument('--schema', default='public')
    if command == 'restore-pitr':
        p.add_argument('--timestamp', required=True, type=int, help='Authorized recovery target in Unix seconds')


def api_handle(args, workdir):
    command = args.command
    body = None
    if command in ('query', 'migration-apply'):
        sql = read_file(args.file, workdir)
        if not sql.strip():
            raise ValueError('SQL file must not be empty.')
        body = {'query': sql}
        if command == 'query':
            body['read_only'] = not args.write
            if args.parameters_file:
                parameters = read_json(args.parameters_file, workdir)
                if not isinstance(parameters, list):
                    raise ValueError('SQL parameters must be a JSON array.')
                body['parameters'] = parameters
        else:
            if any((workdir / 'supabase/migrations').glob('*.sql')):
                raise ValueError('Existing repository migrations detected; deploy through the CLI migration workflow, not a second API history.')
            if not args.dry_run and not args.partner_api_access:
                raise ValueError('The migration API is restricted to selected partner OAuth apps. '
                                 'Use query --write for ordinary PAT-based standalone SQL, or pass '
                                 '--partner-api-access only for a confirmed eligible integration.')
            from supabase_api import name_value
            body['name'] = name_value(args.name)
            if args.rollback_file:
                body['rollback'] = read_file(args.rollback_file, workdir)
    if command == 'restore-pitr':
        import time
        if not 0 < args.timestamp <= int(time.time()):
            raise ValueError('Recovery timestamp must be in the past, in Unix seconds (not milliseconds).')
        confirm_target(args)
        body = {'recovery_time_target_unix': args.timestamp}
    client, output = api_context(args, workdir)
    path = '/v1/projects/' + args.project_ref
    if getattr(args, 'dry_run', False):
        # Do not run arbitrary SQL under a pretend dry-run/rollback transaction.
        value = summary(command, args.project_ref, status='preview',
                        note='Local plan only; SQL/restore not executed and not validated by the server.')
    elif command == 'query':
        call = client.write if args.write else client.request
        value = call('POST', path + '/database/query', body)
        # The provider result is returned unchanged. The agent must interpret rows/RETURNING.
    elif command == 'tables':
        value = client.request('POST', path + '/database/query', {
            'query': 'select table_schema, table_name, table_type from information_schema.tables where table_schema = $1 order by table_name',
            'parameters': [args.schema], 'read_only': True})
    elif command == 'types':
        value = client.request('GET', path + '/types/typescript', query={'included_schemas': args.schema})
        if not isinstance(value, dict) or not isinstance(value.get('types'), str):
            raise APIError('API returned no TypeScript source; existing output was preserved.')
        result(value['types'], output, text=True)
        return 0
    elif command == 'migration-apply':
        client.write('POST', path + '/database/migrations', body)
        history = verify_after_write(lambda: client.request('GET', path + '/database/migrations'))
        value = summary(command, args.project_ref, verified=False,
                        note='Migration accepted; inspect returned history and verify schema/behavior before declaring completion.', history=history)
    elif command in ('migrations', 'backups'):
        value = client.request('GET', path + '/database/' + command)
    elif command == 'restore-pitr':
        client.project(args.project_ref)
        client.write('POST', path + '/database/backups/restore-pitr', body)
        observed = verify_after_write(lambda: client.project(args.project_ref))
        value = summary(command, args.project_ref, verified=False, observed_status=observed.get('status'),
                        note='Restore accepted, not verified complete. Do not resubmit; monitor project and restored data.')
    result(value, output)
    return 0


def main(argv=None):
    args, native, workdir = parse_arguments(COMMANDS, __doc__, argv, NATIVE_GROUPS, configure)
    if args.command in API_COMMANDS:
        return api_handle(args, workdir)
    base, output = prepare(args, workdir)
    return handle(args, base, workdir, output, native)


if __name__ == "__main__":
    entrypoint(main)
