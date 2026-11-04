#!/usr/bin/env python3
"""Three-route AgentWeb client. No automatic POST retries; stdlib only."""
import argparse
import contextlib
from dataclasses import dataclass
import fcntl
import http.client
import json
import math
import os
from pathlib import Path
import queue
import re
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = '/service/agentweb'
DEFAULT_API_BASE = 'https://ai-factory.frevana.com'
STATES = {'STARTED', 'READY', 'DEBITING', 'BILLED', 'REJECTED', 'REVIEW'}
PENDING = {'STARTED', 'READY', 'DEBITING'}
KEY = re.compile(r'[A-Za-z0-9_.-]{1,128}\Z')
REQUEST_ID = re.compile(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\Z')


class ClientError(Exception):
    def __init__(self, message, response=None):
        super().__init__(message)
        self.response = response


def positive(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError('expected a finite positive number') from None
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError('expected a finite positive number')
    return result


def decode(raw):
    def constant(_value):
        raise ValueError('non-finite number')

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, parse_constant=constant, object_pairs_hook=unique)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')


def json_arg(value):
    try:
        return decode(Path(value[1:]).read_bytes() if value.startswith('@') else value)
    except (OSError, ValueError, UnicodeError):
        raise ClientError('Invalid JSON or unreadable @file') from None


def text_field(value, field, maximum):
    try:
        valid = (isinstance(value, str) and bool(value.strip())
                 and len(value.encode('utf-16-le')) // 2 <= maximum)
    except UnicodeError:
        valid = False
    if not valid:
        raise ClientError(f'{field} must be a nonblank string of at most {maximum} UTF-16 units')


def valid_key(value):
    if not isinstance(value, str) or not KEY.fullmatch(value):
        raise ClientError('Idempotency key must be 1–128 ASCII letters/digits/._-')
    return value


def valid_id(value):
    # Server IDs are hash-derived UUID-shaped values, not necessarily UUID v4.
    if not isinstance(value, str) or not REQUEST_ID.fullmatch(value):
        raise ClientError('request_id must be a UUID-shaped Frevana request ID')
    return value


def finite_number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def validate_body(body, operation):
    allowed = {'domain'} if operation == 'discover' else {'domain', 'action', 'params', 'idempotency_key'}
    if not isinstance(body, dict) or set(body) - allowed:
        raise ClientError('Unknown request fields; allowed: ' + ', '.join(sorted(allowed)))
    text_field(body.get('domain'), 'domain', 2048)
    if operation == 'execute':
        text_field(body.get('action'), 'action', 160)
        if 'params' in body:
            params = body['params']
            if not isinstance(params, dict) or any(
                not isinstance(key, str) or not (
                    isinstance(value, (str, bool)) or
                    finite_number(value)
                ) for key, value in params.items()
            ):
                raise ClientError('params must be a flat object of strings, finite numbers or booleans')
        if 'idempotency_key' in body:
            valid_key(body['idempotency_key'])
    return body


def api_base(value):
    try:
        parts = urllib.parse.urlsplit(value)
        _ = parts.port
        valid = (parts.hostname and parts.username is None and parts.password is None
                 and not parts.query and not parts.fragment
                 and parts.path.rstrip('/') in ('', ROOT)
                 and not any(c.isspace() for c in value)
                 and (parts.scheme == 'https' or parts.scheme == 'http'
                      and parts.hostname in ('localhost', '127.0.0.1', '::1')))
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise ClientError('API base must be an HTTPS origin or /service/agentweb base; HTTP only on localhost')
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, ROOT, '', ''))


def atomic_write(path, raw):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_state(path, state):
    try:
        atomic_write(path, encoded(state) + b'\n')
    except (OSError, ValueError, UnicodeError):
        raise ClientError('State save failed; retain the original key/request ID; do not create a replacement') from None


@contextlib.contextmanager
def locked(path):
    if path is None:
        yield
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(path) + '.lock', os.O_CREAT | os.O_RDWR, 0o600)
    except OSError:
        raise ClientError('Cannot access state lock') from None
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ClientError('State is in use; serialize this operation') from None
        yield
    finally:
        os.close(fd)


def load_state(path, base):
    try:
        state = decode(path.read_bytes())
        if (not isinstance(state, dict) or type(state.get('version')) is not int or state.get('version') != 1
                or state.get('api_base') != base or state.get('operation') != 'execute'
                or state.get('phase') not in ('prepared', 'submitted', 'received')
                or not isinstance(state.get('protocol_error', False), bool)):
            raise ValueError()
        validate_body(state.get('body'), 'execute')
        if 'idempotency_key' in state['body']:
            raise ValueError()
        valid_key(state.get('idempotency_key'))
        if state.get('request_id') is not None:
            valid_id(state['request_id'])
        response = state.get('last_response')
        if response is not None and not isinstance(response, dict):
            raise ValueError()
    except (OSError, ValueError, UnicodeError, ClientError):
        raise ClientError('Invalid/unreadable state or API origin mismatch; state was not replaced') from None
    return state


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass
class Response:
    status: int
    raw: bytes
    body: object


class Client:
    def __init__(self, base, token):
        self.base = base
        self.headers = {'Accept': 'application/json', 'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + token}
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method, suffix, body=None, key=None, timeout=None):
        def perform():
            headers = dict(self.headers)
            if key is not None:
                headers['Idempotency-Key'] = key
            req = urllib.request.Request(self.base + suffix, method=method,
                                         data=encoded(body) if body is not None else None,
                                         headers=headers)
            try:
                response = self.opener.open(req, timeout=timeout)
            except urllib.error.HTTPError as exc:
                response = exc
            with response:
                status, raw = response.code, response.read()
            try:
                result = decode(raw)
            except (ValueError, UnicodeError):
                result = None
            return Response(status, raw, result)

        # An optional local deadline also bounds DNS and slow/trickling reads.
        # The thread is never followed by a retry; server work may continue.
        if timeout is None:
            try:
                return perform()
            except (OSError, ValueError, urllib.error.URLError, http.client.HTTPException):
                raise ClientError('HTTP transport failed; outcome uncertain, retain state and query/recover deliberately') from None
        done = queue.Queue(maxsize=1)

        def worker():
            try:
                done.put((perform(), None))
            except Exception:
                done.put((None, True))
        threading.Thread(target=worker, daemon=True).start()
        try:
            result, failed = done.get(timeout=timeout)
        except queue.Empty:
            raise ClientError('Local HTTP deadline reached; server work may continue; retain state') from None
        if failed:
            raise ClientError('HTTP transport failed; outcome uncertain, retain state and query/recover deliberately')
        return result


def outcome(response, discovery=False):
    body = response.body
    if not isinstance(body, dict):
        raise ClientError('Server returned malformed/non-object JSON; retain the original operation')
    http_error = response.status < 200 or response.status >= 300
    if http_error and (discovery or body.get('status') not in STATES):
        return 2
    if discovery:
        if not isinstance(body.get('data'), dict) or not isinstance(body['data'].get('domain'), str):
            raise ClientError('Invalid discovery envelope')
        return 0
    valid_id(body.get('request_id'))
    status, billing = body.get('status'), body.get('billing')
    if status not in STATES or not isinstance(billing, dict) or billing.get('status') != status:
        raise ClientError('Invalid/inconsistent request or billing status')
    if status in {'REVIEW', 'REJECTED'}:
        return 4
    if status in PENDING:
        return 2 if http_error else 3
    credits, execution = billing.get('credits'), body.get('execution_http_status')
    if (not finite_number(credits) or credits < 0
            or type(execution) is not int or not 100 <= execution <= 599):
        raise ClientError('Invalid settled billing/execution envelope')
    return 4 if http_error or body.get('error') or not 200 <= execution < 300 or body.get('data') is None else 0


def identity_note(state):
    if state:
        print('AgentWeb recovery: ' + json.dumps({
            'idempotency_key': state['idempotency_key'],
            'request_id': state.get('request_id'),
        }), file=sys.stderr)


def record(response, state, path, expected_id=None):
    body = response.body
    returned = body.get('request_id') if isinstance(body, dict) else None
    problem = None
    if returned is not None:
        try:
            valid_id(returned)
            if expected_id is not None and returned != expected_id:
                raise ClientError('Request identity mismatch; original ID retained')
        except ClientError as exc:
            problem = str(exc)
    if (response.status == 409 and isinstance(body, dict)
            and body.get('message') == 'Idempotency-Key was used for different arguments'):
        problem = 'Idempotency key conflicts with different server arguments; investigate the original record'
    if state is not None:
        state.update(phase='received', last_http_status=response.status, last_response=body if isinstance(body, dict) else None)
        if returned is not None and not problem:
            state['request_id'] = returned
        if problem:
            state['protocol_error'] = True
        identity_note(state)  # Retain recovery metadata even if the save fails.
        save_state(path, state)
    if problem:
        raise ClientError(problem)


def assess(response, state=None, path=None, expected_id=None, discovery=False):
    try:
        if not discovery:
            record(response, state, path, expected_id)
        return response, outcome(response, discovery)
    except ClientError as exc:
        # Keep the actual response reviewable even after a state/protocol failure.
        exc.response = response
        raise


def build_body(args):
    body = json_arg(args.json) if args.json is not None else {}
    if not isinstance(body, dict):
        raise ClientError('Request body must be a JSON object')
    for field, value in (('domain', args.domain), ('action', getattr(args, 'action', None)),
                         ('params', json_arg(args.params) if getattr(args, 'params', None) is not None else None)):
        if value is not None:
            if field in body:
                raise ClientError('Provide ' + field + ' once, via flags or --json')
            body[field] = value
    return validate_body(body, args.command)


def operate(args, client, base, path=None):
    if args.command == 'discover':
        response = client.request('POST', '/discover', build_body(args), timeout=args.http_timeout)
        return assess(response, discovery=True)

    state = load_state(path, base) if path is not None and path.exists() else None
    if args.command in ('recover', 'execute'):
        if args.command == 'execute':
            body = build_body(args)
            body_key = body.pop('idempotency_key', None)
            key = valid_key(args.idempotency_key) if args.idempotency_key is not None else body_key
            if state is not None:
                if (json.dumps(state['body'], sort_keys=True) != json.dumps(body, sort_keys=True)
                        or key is not None and key != state['idempotency_key']):
                    raise ClientError('Existing state has different arguments/key; preserve the original operation')
            else:
                state = dict(version=1, operation='execute', api_base=base, body=body,
                             idempotency_key=key or str(uuid.uuid4()), request_id=None,
                             phase='prepared', last_response=None)
                save_state(path, state)
        if state is None:
            raise ClientError('Existing state is required for recovery')
        identity_note(state)
        if state.get('protocol_error'):
            raise ClientError('State records a protocol/identity error; investigate before recovery')
        if state.get('request_id'):
            response = client.request('GET', '/requests/' + state['request_id'], timeout=args.http_timeout)
        else:
            if args.command == 'execute' and state['phase'] != 'prepared':
                raise ClientError('Submission has no verified ID; use explicit recover with the original state')
            state['phase'] = 'submitted'
            save_state(path, state)
            response = client.request('POST', '/execute', state['body'], state['idempotency_key'], args.http_timeout)
        return assess(response, state, path, state.get('request_id'))

    supplied_id = valid_id(args.request_id) if args.request_id is not None else None
    if path is not None and state is None:
        raise ClientError('State file does not exist')
    if state is not None:
        if state.get('protocol_error'):
            raise ClientError('State records a protocol/identity error; query the original ID explicitly for investigation')
        if supplied_id and supplied_id != state.get('request_id'):
            raise ClientError('Supplied request ID does not match state')
        supplied_id = state.get('request_id')
    if supplied_id is None:
        raise ClientError('Provide --request-id or state with a verified ID; no-ID state needs explicit recover')
    deadline = time.monotonic() + args.wait_timeout if args.command == 'wait' else None
    response = None
    while True:
        remaining = deadline - time.monotonic() if deadline is not None else None
        if remaining is not None and remaining <= 0:
            if response is None:
                raise ClientError('Local wait deadline reached before status retrieval')
            return response, 3
        timeout = args.http_timeout
        if remaining is not None:
            timeout = min(timeout, remaining) if timeout is not None else remaining
        response = client.request('GET', '/requests/' + supplied_id, timeout=timeout)
        response, code = assess(response, state, path, supplied_id)
        if args.command != 'wait' or code != 3:
            return response, code
        time.sleep(min(args.poll_interval, max(0, deadline - time.monotonic())))


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest='command', required=True)
    for command in ('discover', 'execute', 'status', 'wait', 'recover'):
        sub = commands.add_parser(command)
        sub.add_argument('--api-base-url')
        sub.add_argument('--http-timeout', type=positive)
        sub.add_argument('--output')
        if command in ('discover', 'execute'):
            sub.add_argument('--domain')
            sub.add_argument('--json', help='JSON object or @file')
        if command == 'execute':
            sub.add_argument('--action')
            sub.add_argument('--params', help='Flat JSON object or @file')
            sub.add_argument('--idempotency-key')
        if command != 'discover':
            sub.add_argument('--state-file', required=command in ('execute', 'recover'))
        if command in ('status', 'wait'):
            sub.add_argument('--request-id')
        if command == 'wait':
            sub.add_argument('--wait-timeout', type=positive, default=180)
            sub.add_argument('--poll-interval', type=positive, default=3)
    return root


def authorization_note(response, discovery=False):
    """Surface backend auth handoffs without fetching links or retrying execution."""
    body = response.body
    if not isinstance(body, dict):
        return
    error = body.get('error')
    error = error if isinstance(error, dict) else {}
    site = body.get('data') if discovery else None
    site = site if isinstance(site, dict) else {}
    providers = site.get('connect_providers')
    required = (discovery and (site.get('requires_login') is True
                              or isinstance(providers, list) and bool(providers)))
    required = required or (error.get('code') in {'AUTH_REQUIRED', 'TARGET_AUTH_UNSUPPORTED'}
                            and (response.status == 403 or body.get('execution_http_status') == 403))
    if not required:
        return
    auth = error.get('auth') if error else site.get('auth')
    link = auth.get('connect_url') if isinstance(auth, dict) else None
    try:
        parts = urllib.parse.urlsplit(link) if isinstance(link, str) else None
        valid_link = (parts is not None and parts.scheme == 'https' and parts.hostname
                      and parts.username is None and parts.password is None
                      and not any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in link))
        if parts is not None:
            _ = parts.port
    except ValueError:
        valid_link = False
    if valid_link:
        print('AgentWeb: Site authorization required. Ask the user to open this backend-returned link: '
              + link + '\nWait for the user to finish authorization and confirm before continuing. '
              'Do not retry execute automatically; retain the original request/billing state.', file=sys.stderr)
    else:
        print('AgentWeb: Site authorization required, but no usable connect_url was returned. '
              'Tell the user that a backend authorization entry point is needed to continue. '
              'Do not construct a link from connect_providers or retry execute automatically.', file=sys.stderr)


def emit(response, output, discovery=False):
    # Keep native bytes, including HTTP/protocol errors and unknown fields.
    sys.stdout.buffer.write(response.raw)
    sys.stdout.buffer.flush()
    authorization_note(response, discovery)
    if output:
        try:
            atomic_write(output, response.raw)
        except OSError:
            raise ClientError('Output save failed; response is on stdout and original operation state is retained') from None


def main(argv=None):
    args = parser().parse_args(argv)
    output = None
    try:
        base = api_base(args.api_base_url or os.environ.get('FREVANA_API_BASE_URL') or DEFAULT_API_BASE)
        token = os.environ.get('FREVANA_TOKEN', '').strip()
        if not token or any(c.isspace() for c in token):
            raise ClientError('FREVANA_TOKEN is not set or invalid; set the Frevana Bearer token before running')
        path = Path(args.state_file).resolve() if getattr(args, 'state_file', None) else None
        output = Path(args.output).resolve() if args.output else None
        if path and output in (path, Path(str(path) + '.lock')):
            raise ClientError('Output must not overwrite operation state or its lock')
        with locked(path):
            response, code = operate(args, Client(base, token), base, path)
            emit(response, output, discovery=args.command == 'discover')
            return code
    except (ClientError, OSError) as exc:
        if isinstance(exc, ClientError) and exc.response is not None:
            try:
                emit(exc.response, output, discovery=args.command == 'discover')
            except (ClientError, OSError):
                print('AgentWeb: Response output could not be fully saved', file=sys.stderr)
        print('AgentWeb: ' + (str(exc) if isinstance(exc, ClientError) else 'Local file access failed; preserve existing state'), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print('AgentWeb: Interrupted; retain original state/key/ID before recovery', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
