#!/usr/bin/env python3
"""Internal Management API transport. Fixed host, PAT only, no redirects or retries."""
import json
import os
import re
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from supabase_common import emit, output_path, write_output

BASE_URL = 'https://api.supabase.com'
# The API contract authenticates with Authorization. An explicit client
# identifier also avoids provider edge filtering of urllib's default UA.
USER_AGENT = 'frevana-supabase-skill/1.0'


class APIError(ValueError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def token_from_env():
    token = os.environ.get('SUPABASE_ACCESS_TOKEN', '').strip()
    if not token or not token.isascii() or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in token):
        raise ValueError('Configure a valid SUPABASE_ACCESS_TOKEN in the process environment; do not paste it into chat.')
    return token


def identifier(value):
    if not value or not re.fullmatch(r'[A-Za-z0-9_-]+', value):
        raise ValueError('Use an exact resource ref/identifier, not a URL or path.')
    return value


def name_value(value):
    if not value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError('Name must be nonempty and contain no control characters.')
    return value


def read_file(value, workdir):
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = workdir / path
    try:
        return path.read_text(encoding='utf-8')
    except (OSError, UnicodeError):
        raise ValueError('Could not read the input file as UTF-8.') from None


def read_json(value, workdir):
    try:
        return json.loads(read_file(value, workdir))
    except json.JSONDecodeError:
        raise ValueError('Input file must contain valid JSON; content was not logged.') from None


def api_options(p, target=True, mutation=False, destructive=False):
    if target:
        p.add_argument('--project-ref', required=True, type=identifier)
    p.add_argument('--output', help='Private atomic result file, relative to --workdir')
    if mutation:
        p.add_argument('--dry-run', action='store_true', help='Read/preflight and preview only; never sends the write')
    if destructive:
        p.add_argument('--confirm-project-ref', help='Repeat the authorized destructive target ref (not a substitute for user authorization)')


def api_context(args, workdir):
    if args.profile:
        raise ValueError('Management API operations use SUPABASE_ACCESS_TOKEN; --profile is CLI-only.')
    output = output_path(workdir, args.output) if getattr(args, 'output', None) else None
    return Client(), output


def confirm_target(args):
    if not args.dry_run and getattr(args, 'confirm_project_ref', None) != args.project_ref:
        raise ValueError('Destructive operation requires --confirm-project-ref matching the authorized --project-ref.')


def result(value, output=None, text=False):
    if output:
        content = value if text else json.dumps(value, ensure_ascii=False, indent=2) + '\n'
        write_output(output, content)
        emit({'status': 'saved', 'output': str(output)})
    elif text:
        print(value, end='' if value.endswith('\n') else '\n')
    else:
        emit(value)


def summary(operation, ref=None, status='accepted', **fields):
    return dict(transport='management-api', operation=operation, project_ref=ref,
                status=status, **fields)


class Client:
    def __init__(self):
        self.token = token_from_env()
        self.opener = build_opener(NoRedirect())

    def request(self, method, path, body=None, query=None):
        # Only registered operation code supplies paths. Do not accept caller URLs.
        if not re.fullmatch(r'/v1/[A-Za-z0-9_/-]+', path) or method not in ('GET', 'POST', 'PATCH', 'PUT', 'DELETE'):
            raise ValueError('Unsupported Management API request.')
        url = BASE_URL + path + ('?' + urlencode(query) if query else '')
        data = json.dumps(body, allow_nan=False).encode('utf-8') if body is not None else None
        request = Request(url, data=data, method=method, headers={
            'Authorization': 'Bearer ' + self.token, 'Accept': 'application/json',
            'Content-Type': 'application/json', 'User-Agent': USER_AGENT})
        try:
            with self.opener.open(request, timeout=30) as response:
                if not 200 <= response.status < 300:
                    raise APIError('Management API returned a non-success response.', response.status)
                raw = response.read()
                return json.loads(raw) if raw else None
        except HTTPError as error:
            status = error.code
            error.close()
            hint = {401: 'check PAT validity', 403: 'check permissions',
                    429: 'rate limited; wait before a read retry'}.get(status, 'inspect current state')
            raise APIError(f'Management API {method} failed (HTTP {status}); {hint}; no automatic retry.', status) from None
        except (URLError, OSError, HTTPException):
            raise APIError(f'Management API {method} failed (network/timeout); no automatic retry.') from None
        except (json.JSONDecodeError, UnicodeError):
            raise APIError('Management API returned an invalid JSON response; no automatic retry.') from None

    def project(self, ref):
        value = self.request('GET', '/v1/projects/' + identifier(ref))
        if not isinstance(value, dict) or value.get('ref', value.get('id')) != ref or not isinstance(value.get('name'), str):
            raise APIError('Could not verify the project ref/name from the API response.')
        return value

    def write(self, method, path, body=None):
        try:
            return self.request(method, path, body)
        except APIError as error:
            raise APIError(str(error) + ' Write may have applied; read current state before retrying.', error.status) from None


def verify_after_write(read):
    try:
        return read()
    except (ValueError, OSError):
        raise APIError('Write was accepted but readback failed; inspect current state before retrying. No automatic retry.') from None
