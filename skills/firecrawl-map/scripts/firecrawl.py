#!/usr/bin/env python3
"""Standalone Frevana Firecrawl client; standard library only, no paid retries."""
import argparse
import http.client
import json
import math
import os
from pathlib import Path
import re
import sys
import subprocess
import tempfile
import time
from urllib.parse import urlsplit
import uuid

KIND = 'map'


class ClientError(Exception):
    pass


def positive(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError('must be a finite positive number')
    return number


def url(value):
    try:
        parts = urlsplit(value)
        valid = (parts.scheme in ('http', 'https') and parts.hostname
                 and not parts.username and not parts.password and not parts.fragment)
        _ = parts.port
    except (ValueError, TypeError):
        valid = False
    if not valid or any(c.isspace() for c in value):
        raise ClientError('Expected an HTTP/HTTPS URL without credentials or fragment')
    return value


def load_json(value):
    try:
        text = Path(value[1:]).read_text() if value.startswith('@') else value
        result = json.loads(text, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    except (ValueError, OSError):
        raise ClientError('Invalid JSON or unreadable @file') from None
    if not isinstance(result, dict):
        raise ClientError('Request must be a JSON object')
    return result


def validate(body, route):
    """Check execution constraints; Server owns detailed option validation."""
    if route in ('start-scrape', 'start-crawl'):
        excluded = {'timeout'} | ({'pollInterval'} if route == 'start-crawl' else set())
        if excluded.intersection(body):
            raise ClientError('Async start does not accept ' + ', '.join(sorted(excluded.intersection(body))))
    if route.startswith(('get-', 'cancel-')):
        allowed = {'jobId'}
        if route.startswith('get-'):
            allowed |= {'autoPaginate', 'maxPages', 'maxResults', 'maxWaitTime'}
        if set(body) - allowed:
            raise ClientError('Job operations accept only job ID and pagination options')
        if 'autoPaginate' in body and not isinstance(body['autoPaginate'], bool):
            raise ClientError('autoPaginate must be a boolean')
        for field in ('maxPages', 'maxResults', 'maxWaitTime'):
            if field not in body:
                continue
            value = body[field]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ClientError(field + ' must be a finite nonnegative number')
            if field != 'maxWaitTime' and value != int(value):
                raise ClientError(field + ' must be an integer')
    if route == 'search':
        if body.get('includeDomains') is not None and body.get('excludeDomains') is not None:
            raise ClientError('includeDomains and excludeDomains are mutually exclusive')
        categories = body.get('categories', [])
        if isinstance(categories, list):
            names = [x if isinstance(x, str) else x.get('type') if isinstance(x, dict) else None for x in categories]
            if len(names) > 1 and any(x in ('developer', 'gov') for x in names):
                raise ClientError('developer and gov categories must be used alone')


def choose(args, body):
    if args.action in ('status', 'wait', 'cancel'):
        if not args.job_id or not re.fullmatch(r'[A-Za-z0-9._:-]{1,255}', args.job_id) or args.job_id in ('.', '..'):
            raise ClientError('A valid --job-id is required')
        body = dict(body)
        if 'jobId' in body and body['jobId'] != args.job_id:
            raise ClientError('Conflicting jobId and --job-id')
        body['jobId'] = args.job_id
        route = ('cancel-' if args.action == 'cancel' else 'get-') + KIND + ('' if args.action == 'cancel' else '-status')
        validate(body, route)
        return route, body
    if args.job_id:
        raise ClientError('--job-id is only for status, wait and cancel')
    body = dict(body)
    if args.url:
        if 'url' in body or 'urls' in body:
            raise ClientError('Use either --url or URL fields in --json')
        body['urls' if KIND == 'scrape' and len(args.url) > 1 else 'url'] = args.url if len(args.url) > 1 else args.url[0]
    if args.query is not None:
        if 'query' in body:
            raise ClientError('Use either --query or query in --json')
        body['query'] = args.query
    if KIND == 'scrape':
        if 'url' in body and 'urls' in body:
            raise ClientError('url and urls are mutually exclusive')
        urls = body.get('urls', [body['url']] if 'url' in body else [])
        if not isinstance(urls, list) or not urls:
            raise ClientError('Provide --url or nonempty urls in --json')
        for item in urls:
            url(item)
        heavy_formats = {'screenshot', 'audio', 'video', 'json', 'question', 'query'}
        formats = body.get('formats', [])
        if not isinstance(formats, list):
            raise ClientError('formats must be an array')
        heavy = (bool(body.get('actions')) or bool(body.get('parsers')) or bool(body.get('waitFor'))
                 or any((x if isinstance(x, str) else x.get('type') if isinstance(x, dict) else None)
                        in heavy_formats for x in formats))
        asynchronous = args.action == 'start' or args.mode == 'async' or (args.mode == 'auto' and (len(urls) > 1 or heavy))
        if args.mode == 'sync' and len(urls) > 1:
            raise ClientError('Synchronous scrape accepts exactly one URL')
        body.pop('url', None)
        body.pop('urls', None)
        body['urls' if asynchronous else 'url'] = urls if asynchronous else urls[0]
        route = 'start-scrape' if asynchronous else 'scrape'
    else:
        route = 'start-crawl' if KIND == 'crawl' and (args.action == 'start' or args.mode != 'sync') else KIND
        if KIND == 'search':
            if not isinstance(body.get('query'), str) or not body['query'].strip():
                raise ClientError('A nonempty --query or query in --json is required')
        else:
            url(body.get('url'))
    validate(body, route)
    return route, body


def post(base, route, body, token, key, deadline, http_timeout):
    # Isolate blocking DNS/connect/send/header reads so one absolute deadline
    # can terminate the entire HTTP operation on every supported platform.
    request_deadline = min(deadline, time.monotonic() + http_timeout)
    payload = dict(base=base, route=route, body=body, token=token, key=key,
                   deadline=request_deadline, http_timeout=http_timeout)
    remaining = request_deadline - time.monotonic()
    if remaining <= 0:
        raise ClientError('Client deadline reached; retain the existing job and key')
    try:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), '--_http-worker'],
            input=json.dumps(payload).encode(), capture_output=True, timeout=remaining,
        )
    except subprocess.TimeoutExpired:
        raise ClientError('HTTP deadline reached; outcome uncertain. Retain route, body and key; do not resubmit a new task') from None
    if result.returncode:
        raise ClientError(result.stderr.decode('utf-8', errors='replace').strip() or 'HTTP worker failed')
    return result.stdout, json.loads(result.stdout)


def _post(base, route, body, token, key, deadline, http_timeout):
    parts = urlsplit(base)
    connection_class = http.client.HTTPSConnection if parts.scheme == 'https' else http.client.HTTPConnection
    request_deadline = min(deadline, time.monotonic() + http_timeout)
    remaining = request_deadline - time.monotonic()
    if remaining <= 0:
        raise ClientError('Client deadline reached; do not submit a replacement')
    connection = connection_class(parts.hostname, parts.port, timeout=remaining)
    headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json', 'Accept': 'application/json'}
    if key:
        headers['Idempotency-Key'] = key
    try:
        prefix = parts.path.rstrip('/')
        if not prefix.endswith('/service/web'):
            prefix += '/service/web'
        connection.request('POST', prefix + '/' + route,
                           json.dumps(body, separators=(',', ':'), ensure_ascii=False).encode(), headers)
        sock = connection.sock
        response = connection.getresponse()
        chunks = []
        while True:
            remaining = request_deadline - time.monotonic()
            if remaining <= 0:
                raise ClientError('Client deadline reached; retain the existing job and key')
            if sock:
                sock.settimeout(remaining)
            chunk = response.read1(65536)
            if not chunk:
                break
            chunks.append(chunk)
            if response.isclosed():
                break
        raw = b''.join(chunks)
        if response.status < 200 or response.status >= 300:
            request_id = None
            try:
                candidate = json.loads(raw).get('request_id')
                if isinstance(candidate, str) and re.fullmatch(r'[A-Za-z0-9._:-]{1,255}', candidate):
                    request_id = candidate
            except (ValueError, AttributeError):
                pass
            raise ClientError('HTTP ' + str(response.status) + ((' request_id=' + request_id) if request_id else '')
                              + '; no automatic retry or redirect; recover using the same route, body and key')
        try:
            result = json.loads(raw)
        except ValueError:
            raise ClientError('Server returned invalid JSON') from None
        if not isinstance(result, dict) or 'data' not in result or not isinstance(result.get('billing'), dict):
            raise ClientError('Unexpected Frevana response envelope')
        return raw, result
    except (OSError, http.client.HTTPException):
        raise ClientError('Transport failed or timed out; outcome uncertain. Retain route, body and key; do not resubmit a new task') from None
    finally:
        connection.close()


def outcome(result, job):
    billing = result['billing'].get('status')
    data = result.get('data')
    if billing in ('REVIEW', 'REJECTED'):
        return 4
    if isinstance(data, dict) and (data.get('success') is False or data.get('status') in ('failed', 'cancelled')):
        return 4
    if billing != 'BILLED' or data is None:
        return 3
    if job:
        if not isinstance(data, dict) or data.get('status') != 'completed' or data.get('next'):
            return 3
        documents = data.get('data')
        completed, total = data.get('completed'), data.get('total')
        counts = (completed, total)
        if (not isinstance(documents, list)
                or any(isinstance(n, bool) or not isinstance(n, int) or n < 0 for n in counts)
                or completed != total or len(documents) < completed):
            # SDK 4.46.0 clears next even when auto-pagination stops early.
            # Missing counters cannot establish complete coverage either.
            return 3
    return 0


def emit(raw, output):
    if output:
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        name = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
                name = handle.name
                handle.write(raw)
            os.replace(name, target)
        finally:
            if name and os.path.exists(name):
                os.unlink(name)
    sys.stdout.buffer.write(raw)
    if not raw.endswith(b'\n'):
        sys.stdout.buffer.write(b'\n')


def main():
    parser = argparse.ArgumentParser(description='Frevana Firecrawl ' + KIND)
    actions = ['run', 'start', 'status', 'wait', 'cancel'] if KIND in ('scrape', 'crawl') else ['run']
    parser.add_argument('action', choices=actions, nargs='?', default='run')
    parser.add_argument('--json', default='{}', help='request JSON object or @file; server camelCase names')
    if KIND != 'search':
        parser.add_argument('--url', action='append', help='HTTP(S) URL; repeat only for scrape')
    else:
        parser.add_argument('--query')
    parser.add_argument('--job-id')
    parser.add_argument('--mode', choices=['auto', 'sync', 'async'] if KIND in ('scrape', 'crawl') else ['auto'], default='auto')
    parser.add_argument('--idempotency-key')
    parser.add_argument('--wait-timeout', type=positive, default=180, help='whole invocation deadline in seconds')
    parser.add_argument('--http-timeout', type=positive, default=60, help='per HTTP operation limit in seconds')
    parser.add_argument('--poll-interval', type=positive, default=3)
    parser.add_argument('--output', help='save exact final response JSON, including pending/review results')
    parser.add_argument('--api-base-url', default=os.environ.get('FREVANA_API_BASE_URL', 'https://ai-factory.frevana.com'))
    args = parser.parse_args()
    args.url = getattr(args, 'url', None)
    args.query = getattr(args, 'query', None)
    try:
        base = url(args.api_base_url).rstrip('/')
        if urlsplit(base).query:
            raise ClientError('API base URL must not contain a query')
        if KIND != 'scrape' and args.url and len(args.url) != 1:
            raise ClientError('This skill accepts exactly one URL')
        if args.action == 'start' and args.mode == 'sync':
            raise ClientError('start conflicts with --mode sync')
        if args.action in ('status', 'wait', 'cancel') and (args.url or args.query or args.mode != 'auto'):
            raise ClientError('Job operations do not accept URL/query/mode')
        route, body = choose(args, load_json(args.json))
        token = os.environ.get('FREVANA_TOKEN', '').strip()
        if not token or any(c.isspace() for c in token):
            raise ClientError('Set FREVANA_TOKEN to a Frevana JWT; no API-key fallback')
        key = args.idempotency_key
        paid = args.action in ('run', 'start')
        if paid:
            key = key or str(uuid.uuid4())
            if not re.fullmatch(r'[A-Za-z0-9._-]{1,128}', key):
                raise ClientError('Invalid --idempotency-key (1..128 letters/digits/dot/underscore/hyphen)')
            print('route=' + route + ' idempotency_key=' + key, file=sys.stderr)
        elif key:
            raise ClientError('--idempotency-key is only for paid run/start operations')
        deadline = time.monotonic() + args.wait_timeout
        raw, result = post(base, route, body, token, key, deadline, args.http_timeout)
        job = route in ('crawl', 'start-crawl', 'start-scrape') or args.action in ('status', 'wait')
        job_id = args.job_id or (result['data'].get('id') if isinstance(result.get('data'), dict) else None)
        if job_id is not None and (not isinstance(job_id, str) or not re.fullmatch(r'[A-Za-z0-9._:-]{1,255}', job_id)):
            raise ClientError('Server returned an invalid job ID')
        if job_id:
            print('job_id=' + job_id, file=sys.stderr)
        should_wait = args.action == 'wait' or (args.action == 'run' and job)
        code = (0 if result['data'] is True else 4) if args.action == 'cancel' else outcome(result, job)
        if args.action == 'start' and code != 4 and job_id:
            code = 0  # submitted; this does not mean completed
        while should_wait and code == 3 and job_id:
            if (result['billing'].get('status') == 'BILLED'
                    and isinstance(result.get('data'), dict)
                    and result['data'].get('status') == 'completed'):
                break  # settled but incomplete: return the native partial snapshot
            remaining = deadline - time.monotonic()
            if remaining <= args.poll_interval:
                break
            time.sleep(args.poll_interval)
            pagination = body if args.action == 'wait' else {}
            polling = {**pagination, 'jobId': job_id}
            polling.setdefault('autoPaginate', True)
            polling['maxWaitTime'] = min(polling.get('maxWaitTime', 10), max(0, deadline - time.monotonic() - 1))
            raw, result = post(base, 'get-' + KIND + '-status', polling, token, None, deadline, args.http_timeout)
            code = outcome(result, True)
        emit(raw, args.output)
        if code == 3:
            print('Pending, unsettled or paginated result; resume wait/status with existing job ID. Never create a replacement.', file=sys.stderr)
        elif code == 4:
            print('Failed, cancelled, rejected or billing REVIEW; stop automatic work and inspect the response.', file=sys.stderr)
        return code
    except (ClientError, OSError, ValueError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    if sys.argv[1:] == ['--_http-worker']:
        try:
            raw, _ = _post(**json.load(sys.stdin))
            sys.stdout.buffer.write(raw)
        except (ClientError, OSError, ValueError, TypeError) as error:
            print(str(error), file=sys.stderr)
            sys.exit(2)
    else:
        sys.exit(main())
