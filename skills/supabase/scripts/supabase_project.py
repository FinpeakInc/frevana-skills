#!/usr/bin/env python3
"""Cloud project Management API operations; CLI only for local init/link/config files."""
import os
import sys
sys.dont_write_bytecode = True

from supabase_common import emit, entrypoint, execute, parse_arguments, prepare
from supabase_api import (APIError, api_context, api_options, confirm_target, identifier,
                          name_value, read_json, result, summary, verify_after_write)

LEGACY = ("init", "link", "cli")
COMMANDS = ("list", "get", "create", "rename", "delete", "pause", "restore", "restart", "organizations") + LEGACY
NATIVE_GROUPS = ("projects", "orgs", "config", "init", "link", "unlink")


def configure(command, p):
    if command in LEGACY:
        return
    if command == "rename":
        p.add_argument("--output", help="Private atomic result file")
        return
    api_options(p, target=command not in ("list", "organizations", "create"),
                mutation=command in ("create", "delete", "pause", "restore", "restart"),
                destructive=command == "delete")
    if command == "create":
        p.add_argument("--name", required=True, type=name_value)
        p.add_argument("--organization-slug", required=True, type=identifier)
        p.add_argument("--config-file", required=True,
                       help="Reviewed JSON with region_selection (or legacy region), optional desired_instance_size/high_availability")
        p.add_argument("--db-password-env", default="SUPABASE_DB_PASSWORD", help="Environment variable name; never the password")


def rename_project(args, workdir):
    identifier(args.project_ref)
    name_value(args.name)
    client, output = api_context(args, workdir)
    previous = client.project(args.project_ref)['name']
    if args.expect_name is not None and previous != args.expect_name:
        raise ValueError("Current project name differs from --expect-name; nothing was changed.")
    value = summary('rename', args.project_ref, old_name=previous, new_name=args.name)
    if args.dry_run or previous == args.name:
        value['status'] = 'preview' if args.dry_run else 'already_named'
    else:
        client.write('PATCH', '/v1/projects/' + args.project_ref, {'name': args.name})
        observed = verify_after_write(lambda: client.project(args.project_ref))
        if observed['name'] != args.name:
            raise APIError('Rename may have applied; readback name differs. Inspect current state before retrying.')
        value.update(status='renamed', verified=True)
    result(value, output)
    return 0


def api_handle(args, workdir):
    command = args.command
    if command == 'rename':
        return rename_project(args, workdir)
    body = None
    if command == 'create':
        config = read_json(args.config_file, workdir)
        allowed = {'region_selection', 'region', 'desired_instance_size', 'high_availability'}
        if not isinstance(config, dict) or not config or set(config) - allowed:
            raise ValueError('Project config supports only region_selection/region, desired_instance_size and high_availability.')
        if ('region' in config) == ('region_selection' in config):
            raise ValueError('Select exactly one explicit region or region_selection in the config file.')
        body = dict(config, name=args.name, organization_slug=args.organization_slug)
        password = os.environ.get(args.db_password_env, '')
        if not args.dry_run and not password:
            raise ValueError('Configure the project database password in the selected environment variable; do not paste it into chat.')
        body['db_pass'] = password
    if command == 'delete':
        confirm_target(args)
    client, output = api_context(args, workdir)
    ref = getattr(args, 'project_ref', None)
    path = '/v1/projects/' + ref if ref else '/v1/projects'
    if command in ('list', 'organizations'):
        value = client.request('GET', '/v1/organizations' if command == 'organizations' else path)
        if not isinstance(value, list):
            raise APIError('Expected a resource list; response was not logged.')
    elif command == 'get':
        value = client.project(ref)
    elif command == 'create':
        if args.dry_run:
            value = summary(command, status='preview', name=args.name,
                            organization_slug=args.organization_slug, configuration=config)
        else:
            created = client.write('POST', path, body)
            if not isinstance(created, dict) or not created.get('ref', created.get('id')):
                raise APIError('Creation may have applied; no project ref returned. List projects before retrying.')
            new_ref = identifier(created.get('ref', created.get('id')))
            observed = verify_after_write(lambda: client.project(new_ref))
            value = summary(command, new_ref, status='accepted', observed_status=observed.get('status'),
                            name=observed['name'], verified=False)
    else:
        before = client.project(ref)
        if args.dry_run:
            value = summary(command, ref, status='preview', name=before['name'])
        else:
            client.write('DELETE' if command == 'delete' else 'POST',
                         path if command == 'delete' else path + '/' + command)
            if command == 'delete':
                # Only explicit 404 proves absence; 403/network errors do not.
                try:
                    observed = client.project(ref)
                except APIError as error:
                    if error.status != 404:
                        raise APIError('Deletion accepted but readback failed; inspect state before retrying.') from None
                    value = summary(command, ref, status='deleted', verified=True)
                else:
                    value = summary(command, ref, observed_status=observed.get('status'), verified=False)
            else:
                observed = verify_after_write(lambda: client.project(ref))
                value = summary(command, ref, observed_status=observed.get('status'), verified=False)
    result(value, output)
    return 0


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
    args, native, workdir = parse_arguments(COMMANDS, __doc__, argv, NATIVE_GROUPS, configure)
    if args.command not in LEGACY:
        return api_handle(args, workdir)
    base, output = prepare(args, workdir)
    return handle(args, base, workdir, output, native)


if __name__ == "__main__":
    entrypoint(main)
