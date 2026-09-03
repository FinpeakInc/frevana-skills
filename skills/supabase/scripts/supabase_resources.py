#!/usr/bin/env python3
"""Cloud resource API groups; guarded CLI entry for file/deployment and additional resources."""
import sys
sys.dont_write_bytecode = True

from supabase_common import entrypoint, execute, parse_arguments, prepare
from supabase_api import (APIError, api_context, api_options, identifier, name_value,
                          read_json, result, summary, verify_after_write)

CONFIG = {
    'auth': ('/config/auth', 'PATCH'),
    'storage': ('/config/storage', 'PATCH'),
    'realtime': ('/config/realtime', 'PATCH'),
    'rest': ('/postgrest', 'PATCH'),
    'postgres': ('/config/database/postgres', 'PUT'),
}
GROUPS = {
    'functions': ('list', 'get', 'delete'),
    'secrets': ('list', 'set', 'unset'),
    'branches': ('list', 'create'),
    'storage': ('buckets',),
    'config': ('get', 'update'),
    'domains': ('get',),
    'network-restrictions': ('get',),
}
COMMANDS = tuple(GROUPS) + ('cli',)
SAFE_AUTH_FIELDS = {'site_url', 'disable_signup', 'jwt_exp', 'external_email_enabled',
                    'external_phone_enabled', 'mailer_autoconfirm', 'sms_autoconfirm',
                    'uri_allow_list', 'security_captcha_enabled'}


def configure(command, p):
    if command == 'cli':
        return
    p.add_argument('action', choices=GROUPS[command])
    api_options(p, mutation=True)
    if command == 'functions':
        p.add_argument('--slug', type=identifier, help='Required for get/delete')
    if command in ('secrets', 'branches', 'config'):
        p.add_argument('--body-file', help='Reviewed JSON request body; required for set/unset/create/update')
    if command == 'config':
        p.add_argument('--service', required=True, choices=CONFIG)


def secret_names(value):
    if not isinstance(value, list) or any(not isinstance(item, dict) or not isinstance(item.get('name'), str) for item in value):
        raise APIError('Expected secret metadata list; response was not logged.')
    return [{'name': item['name']} for item in value]


def safe_config(value, service):
    if not isinstance(value, dict):
        raise APIError('Expected config object; response was not logged.')
    if service == 'auth':
        return {'config': {key: val for key, val in value.items() if key in SAFE_AUTH_FIELDS},
                'other_fields': sorted(set(value) - SAFE_AUTH_FIELDS)}
    # Storage external providers and future settings may contain credentials.
    def redact(obj):
        if isinstance(obj, dict):
            return {key: '[redacted]' if any(word in key.lower() for word in ('secret', 'password', 'token', 'key', 'credential', 'external'))
                    else redact(val) for key, val in obj.items()}
        if isinstance(obj, list):
            return [redact(item) for item in obj]
        return obj
    return redact(value)


def contains(actual, requested):
    if isinstance(requested, dict):
        return isinstance(actual, dict) and all(key in actual and contains(actual[key], value) for key, value in requested.items())
    return actual == requested


def api_handle(args, workdir):
    group, action = args.command, args.action
    mutation = action in ('delete', 'set', 'unset', 'create', 'update')
    if args.dry_run and not mutation:
        raise ValueError('--dry-run applies only to a write operation.')
    body = None
    if group == 'functions' and action in ('get', 'delete') and not args.slug:
        raise ValueError('--slug is required for function get/delete.')
    if mutation and group in ('secrets', 'branches', 'config'):
        if not args.body_file:
            raise ValueError('--body-file is required for this operation.')
        body = read_json(args.body_file, workdir)
        if group == 'secrets':
            if not isinstance(body, list) or not body:
                raise ValueError('Secrets body must be a nonempty JSON array.')
            if action == 'set':
                if any(not isinstance(item, dict) or set(item) != {'name', 'value'} or
                       not isinstance(item['name'], str) or not isinstance(item['value'], str) for item in body):
                    raise ValueError('Secret set expects objects containing only string name/value fields.')
                for item in body:
                    name_value(item['name'])
            elif any(not isinstance(item, str) or not item.strip() for item in body):
                raise ValueError('Secret unset expects an array of names.')
        elif not isinstance(body, dict) or not body:
            raise ValueError('Request body must be a nonempty JSON object.')
        elif group == 'branches':
            allowed = {'branch_name', 'git_branch', 'persistent', 'region', 'desired_instance_size', 'with_data'}
            if set(body) - allowed or not isinstance(body.get('branch_name'), str):
                raise ValueError('Branch create requires branch_name; only documented scoped branch options are supported.')
            name_value(body['branch_name'])
    elif getattr(args, 'body_file', None):
        raise ValueError('--body-file is not accepted for a read operation.')
    client, output = api_context(args, workdir)
    prefix = '/v1/projects/' + args.project_ref
    suffix = {'functions': '/functions', 'secrets': '/secrets', 'branches': '/branches',
              'storage': '/storage/buckets', 'domains': '/custom-hostname',
              'network-restrictions': '/network-restrictions'}.get(group)
    if group == 'config':
        suffix = CONFIG[args.service][0]
    if group == 'functions' and action in ('get', 'delete'):
        suffix += '/' + args.slug
    path = prefix + suffix
    # Read the actual affected resource, not unrelated account metadata.
    before = client.request('GET', path)
    if not mutation:
        value = secret_names(before) if group == 'secrets' else safe_config(before, args.service) if group == 'config' else before
    elif args.dry_run:
        value = summary(group + ' ' + action, args.project_ref, status='preview',
                        note='Read/preflight only; request values omitted to protect secrets.')
    else:
        method = 'DELETE' if action in ('delete', 'unset') else CONFIG[args.service][1] if group == 'config' else 'POST'
        response = client.write(method, path, body)
        if group == 'functions':
            listing = verify_after_write(lambda: client.request('GET', prefix + '/functions'))
            if not isinstance(listing, list) or any(not isinstance(item, dict) or 'slug' not in item for item in listing):
                raise APIError('Function deletion accepted but listing could not be verified; do not repeat automatically.')
            absent = all(item['slug'] != args.slug for item in listing)
            value = summary('functions delete', args.project_ref, status='deleted' if absent else 'accepted', verified=absent)
        elif group == 'secrets':
            names = verify_after_write(lambda: secret_names(client.request('GET', path)))
            observed = {item['name'] for item in names}
            requested = {item['name'] for item in body} if action == 'set' else set(body)
            matches = requested <= observed if action == 'set' else not requested & observed
            value = summary('secrets ' + action, args.project_ref, names=sorted(requested),
                            status='accepted', names_verified=matches, verified=matches if action == 'unset' else False,
                            note='Set checks name presence only, not the stored secret value.')
        elif group == 'config':
            observed = verify_after_write(lambda: client.request('GET', path))
            value = summary('config update', args.project_ref, service=args.service,
                            fields=sorted(body), verified=contains(observed, body))
        else:
            listing = verify_after_write(lambda: client.request('GET', path))
            value = summary('branches create', args.project_ref, verified=False,
                            note='Creation accepted; check branch readiness without repeating creation.',
                            branch_ref=response.get('project_ref') if isinstance(response, dict) else None)
    result(value, output)
    return 0


def handle(args, base, workdir, output, native):
    return execute(base + native, workdir, output)


def main(argv=None):
    args, native, workdir = parse_arguments(COMMANDS, __doc__, argv, configure=configure)
    if args.command != 'cli':
        return api_handle(args, workdir)
    base, output = prepare(args, workdir)
    return handle(args, base, workdir, output, native)


if __name__ == '__main__':
    entrypoint(main)
