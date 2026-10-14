import importlib.util
import http.client
import json
import os
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[1]
SCRIPT = SKILL / 'scripts/tiktok_ads_search.py'
TASK_ID = '7af283fe-13aa-431d-a7cf-b58675701884'
ROOT = '/service/tiktok-ads/tasks'
RESULT = b'[ {"adId":"1878055429367345", "adTitle":"test", "unknown": [1,2]} ]\n'
spec = importlib.util.spec_from_file_location('tiktok_ads_search', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def task(status='READY', delay=1):
    return {'task_id': TASK_ID, 'status': status, 'result_available': status == 'READY',
            'result_count': 1, 'error_code': None, 'error_message': None,
            'next_poll_after_ms': delay if status in ('PENDING', 'RUNNING', 'SETTLING') else 0}


class Handler(BaseHTTPRequestHandler):
    requests = []
    states = []
    create_status = 'PENDING'
    code = 200
    result = RESULT
    create_body = None
    delay = 1
    slow_response = None

    def record(self):
        body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        self.__class__.requests.append((self.command, self.path, dict(self.headers), body))
        return body

    def respond(self, code, body):
        if self.__class__.slow_response == 'headers' and self.path.endswith('/result'):
            self.wfile.write(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n')
            self.wfile.flush()
            for _ in range(12):
                self.wfile.write(b'X-Slow: yes\r\n')
                self.wfile.flush()
                time.sleep(0.2)
            self.wfile.write(f'Content-Length: {len(body)}\r\n\r\n'.encode() + body)
            return
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        if code == 302:
            self.send_header('Location', '/redirected')
        self.end_headers()
        if self.__class__.slow_response == 'body' and self.path.endswith('/result'):
            for byte in body:
                self.wfile.write(bytes([byte]))
                self.wfile.flush()
                time.sleep(0.2)
        else:
            self.wfile.write(body)

    def do_POST(self):
        payload = json.loads(self.record())
        body = self.__class__.create_body
        if body is None:
            body = json.dumps({**task(self.__class__.create_status, self.__class__.delay),
                               'client_task_id': payload['client_task_id']}).encode()
        code = self.__class__.code
        self.respond(202 if code == 200 else code, body)

    def do_GET(self):
        self.record()
        if self.path.endswith('/result'):
            try:
                self.respond(self.__class__.code, self.__class__.result)
            except (BrokenPipeError, ConnectionResetError):
                pass  # Expected when the timeout closes the client connection.
        else:
            status = self.__class__.states.pop(0) if self.__class__.states else 'READY'
            self.respond(self.__class__.code, json.dumps(task(status, self.__class__.delay)).encode())

    def log_message(self, *args):
        pass


class TikTokAdsSearchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(5)

    def setUp(self):
        Handler.requests = []
        Handler.states = []
        Handler.create_status = 'PENDING'
        Handler.code = 200
        Handler.result = RESULT
        Handler.create_body = None
        Handler.delay = 1
        Handler.slow_response = None

    def run_script(self, *args, auth=('--token', 'test-token'), env=None):
        clean_env = os.environ.copy()
        clean_env.pop('FREVANA_TOKEN', None)
        clean_env.pop('FREVANA_API_KEY', None)
        if env:
            clean_env.update(env)
        return subprocess.run(['python3', str(SCRIPT), *args, '--api-base-url', self.base, *auth],
                              env=clean_env, input=b'', capture_output=True, timeout=10)

    def test_run_all_three_endpoints_and_raw_bytes(self):
        Handler.states = ['RUNNING', 'SETTLING', 'READY']
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'sub folder/result.json'
            res = self.run_script('run', '--query', ' pikoya ', '--country', 'ES',
                                  '--client-task-id', 'stable-id', '--max-pages', '2',
                                  '--advertiser-name', 'Nike', '--start-date', '2026-10-01',
                                  '--end-date', '2026-10-13', '--timezone', 'UTC',
                                  '--sort-by', 'impression,desc', '--quick-search', 'true',
                                  '--output', str(output))
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertEqual(res.stdout, RESULT)
            self.assertEqual(output.read_bytes(), RESULT)
        self.assertEqual([(r[0], r[1]) for r in Handler.requests],
                         [('POST', ROOT)] + [('GET', f'{ROOT}/{TASK_ID}')] * 3 +
                         [('GET', f'{ROOT}/{TASK_ID}/result')])
        self.assertTrue(all(r[2].get('Authorization') == 'Bearer test-token' for r in Handler.requests))
        payload = json.loads(Handler.requests[0][3])
        self.assertEqual(payload, {'client_task_id': 'stable-id', 'query': 'pikoya',
                                 'country': 'ES', 'max_pages': 2, 'advertiser_name': 'Nike',
                                 'start_date': '2026-10-01', 'end_date': '2026-10-13',
                                 'timezone': 'UTC', 'sort_by': 'impression,desc', 'quick_search': True})

    def test_ad_ids_have_no_search_defaults(self):
        res = self.run_script('create', '--ad-id', '00123', '--ad-id', '9')
        self.assertEqual(res.returncode, 0, res.stderr)
        payload = json.loads(Handler.requests[0][3])
        self.assertEqual(set(payload), {'client_task_id', 'ad_ids'})
        self.assertEqual(payload['ad_ids'], ['00123', '9'])
        self.assertIn(payload['client_task_id'].encode(), res.stderr)

    def test_search_defaults_left_to_server_and_country_only(self):
        res = self.run_script('create', '--country', 'GB')
        self.assertEqual(res.returncode, 0, res.stderr)
        payload = json.loads(Handler.requests[0][3])
        self.assertEqual(set(payload), {'client_task_id', 'country'})

    def test_invalid_inputs_no_requests(self):
        options = [[], ['--country', 'all'], ['--country', 'US'], ['--query', '  '],
                   ['--query', 'x' * 257], ['--query', 'q', '--max-pages', '0'],
                   ['--query', 'q', '--max-pages', '26'], ['--query', 'q', '--start-date', '2026-02-30'],
                   ['--query', 'q', '--start-date', '2026-10-13', '--end-date', '2026-10-01'],
                   ['--query', 'q', '--timezone', 'Mars/Olympus'],
                   ['--query', 'q', '--quick-search', 'yes'], ['--ad-id', '123', '--query', 'q'],
                   ['--ad-id', '123', '--max-pages', '1'], ['--ad-id', '123', '--quick-search', 'false'],
                   ['--ad-id', '12', '--ad-id', '12'], ['--ad-id', '-1'], ['--ad-id', '1' * 33],
                   ['--query', 'q', '--client-task-id', ''], ['--query', 'q', '--client-task-id', 'x' * 129],
                   [arg for i in range(101) for arg in ('--ad-id', str(i))]]
        for flags in options:
            with self.subTest(flags=flags):
                res = self.run_script('create', *flags)
                self.assertNotEqual(res.returncode, 0)
                self.assertEqual(Handler.requests, [])

    def test_valid_boundaries(self):
        for flags in (['--query', 'x' * 256, '--max-pages', '25', '--timezone', 'Asia/Shanghai'],
                      [arg for i in range(100) for arg in ('--ad-id', str(i))]):
            res = self.run_script('create', *flags)
            self.assertEqual(res.returncode, 0, res.stderr)

    def test_status_and_direct_result(self):
        res = self.run_script('status', '--task-id', TASK_ID)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(json.loads(res.stdout)['status'], 'READY')
        res = self.run_script('result', '--task-id', TASK_ID)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout, RESULT)

    def test_terminal_states_stop_without_result_or_new_task(self):
        for status in ('FAILED', 'REVIEW_REQUIRED', 'RESULT_EXPIRED'):
            Handler.requests = []
            Handler.states = [status]
            res = self.run_script('run', '--query', 'q')
            self.assertNotEqual(res.returncode, 0)
            self.assertIn(status.encode(), res.stderr)
            self.assertEqual([r[0] for r in Handler.requests], ['POST', 'GET'])

    def test_zero_poll_interval_stops(self):
        Handler.delay = 0
        res = self.run_script('run', '--query', 'q')
        self.assertNotEqual(res.returncode, 0)
        self.assertIn(b'polling must stop', res.stderr)
        self.assertEqual(len(Handler.requests), 1)

    def test_result_errors_preserve_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'result.json'
            output.write_bytes(b'previous')
            for code, body in ((409, b'{"message":"unavailable"}'), (410, b'expired'),
                               (200, b'{"status":"RUNNING"}'), (200, b'[bad json]')):
                Handler.code, Handler.result = code, body
                res = self.run_script('result', '--task-id', TASK_ID, '--output', str(output))
                self.assertNotEqual(res.returncode, 0)
                self.assertEqual(res.stdout, b'')
                self.assertEqual(output.read_bytes(), b'previous')

    def test_redirect_never_forwards_credentials(self):
        Handler.code = 302
        res = self.run_script('create', '--query', 'q', '--client-task-id', 'stable-retry')
        self.assertNotEqual(res.returncode, 0)
        self.assertIn(b'HTTP 302', res.stderr)
        self.assertIn(b'--client-task-id stable-retry', res.stderr)
        self.assertEqual(len(Handler.requests), 1)

    def test_create_uncertain_outcome_reports_stable_id(self):
        for code, body in ((500, None), (200, b'invalid json')):
            Handler.requests = []
            Handler.code, Handler.create_body = code, body
            res = self.run_script('create', '--query', 'q', '--client-task-id', 'stable-retry')
            self.assertNotEqual(res.returncode, 0)
            self.assertIn(b'--client-task-id stable-retry', res.stderr)
            self.assertEqual(len(Handler.requests), 1)

    def test_token_override_and_environment_auth(self):
        for auth, env, expected in ((('--token', 'explicit-token'), {'FREVANA_TOKEN': 'env-token'}, 'explicit-token'),
                                    ((), {'FREVANA_TOKEN': 'env-token'}, 'env-token'),
                                    ((), {'FREVANA_TOKEN': 'env-token', 'FREVANA_API_KEY': 'env-key'}, 'env-token')):
            res = self.run_script('create', '--query', 'q', auth=auth, env=env)
            self.assertEqual(res.returncode, 0, res.stderr)
            headers = {k.lower(): v for k, v in Handler.requests[-1][2].items()}
            self.assertEqual(headers.get('authorization'), f'Bearer {expected}')
            self.assertNotIn('x-api-key', headers)
            for secret in ('explicit-token', 'env-token', 'env-key'):
                self.assertNotIn(secret.encode(), res.stdout + res.stderr)

        # FREVANA_API_KEY alone is not sufficient; FREVANA_TOKEN is required
        res = self.run_script('create', '--query', 'q', auth=(), env={'FREVANA_API_KEY': 'env-key'})
        self.assertNotEqual(res.returncode, 0)
        self.assertIn(b'FREVANA_TOKEN is not set', res.stderr)

        # --api-key is no longer supported
        res = self.run_script('create', '--query', 'q', auth=('--api-key', 'key'), env={'FREVANA_TOKEN': 'env-token'})
        self.assertNotEqual(res.returncode, 0)
        self.assertIn(b'unrecognized arguments: --api-key', res.stderr)

    def test_invalid_action_flags_and_credentials_no_requests(self):
        for args, auth in ((['status', '--task-id', '../escape'], ('--token', 'ok')),
                           (['status', '--task-id', TASK_ID, '--query', 'q'], ('--token', 'ok')),
                           (['result', '--task-id', TASK_ID, '--wait'], ('--token', 'ok')),
                           (['create', '--query', 'q', '--timeout', '1'], ('--token', 'ok')),
                           (['create', '--query', 'q'], ('--token', 'secret\nheader'))):
            res = self.run_script(*args, auth=auth)
            self.assertNotEqual(res.returncode, 0)
            self.assertEqual(Handler.requests, [])

    def test_create_wait_and_ready_creation_skip_poll(self):
        Handler.create_status = 'READY'
        with tempfile.TemporaryDirectory() as directory:
            res = self.run_script('create', '--wait', '--query', 'q', '--output', str(Path(directory) / 'r.json'))
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertEqual(res.stdout, RESULT)
        self.assertEqual([r[1] for r in Handler.requests], [ROOT, f'{ROOT}/{TASK_ID}/result'])

    def test_wait_deadline_and_server_interval(self):
        class FakeClient:
            def request(self, *args, **kwargs):
                return json.dumps(task('SETTLING', 5000)).encode()
        sleeps = []
        # Deadline at t=1; response at t=0; sleep only remaining 1 second, then stop.
        with patch.object(module.time, 'monotonic', side_effect=[0, 0, 0, 1]), \
             patch.object(module.time, 'sleep', side_effect=sleeps.append):
            with self.assertRaisesRegex(module.CliError, 'Timed out'):
                module.wait_for_result(FakeClient(), TASK_ID, 1, None)
        self.assertEqual(sleeps, [1])

    def test_base_url_rejects_credentials(self):
        for url in ('https://user:pass@example.com', 'file:///tmp/task',
                    'https://example.com?q=1', 'https://example.com/#fragment'):
            with self.assertRaises(module.CliError):
                module.validate_base_url(url)

    def test_incomplete_response_is_reported_as_transport_failure(self):
        client = module.Client(self.base, {'Authorization': 'Bearer test-token'})
        with patch.object(client.opener, 'open', side_effect=http.client.IncompleteRead(b'partial')):
            with self.assertRaisesRegex(module.CliError, 'transport failed'):
                client.request('POST', payload={'query': 'q'})

    def test_unlimited_wait_follows_server_interval_and_empty_array(self):
        Handler.result = b'[]\n'
        with tempfile.TemporaryDirectory() as directory, patch.object(module.time, 'sleep') as sleep:
            client = module.Client(self.base, {'Authorization': 'Bearer test-token'})
            with patch.object(module, 'emit') as emit:
                module.wait_for_result(client, TASK_ID, 0, str(Path(directory) / 'r.json'),
                                       initial=task('SETTLING', 5000))
                emit.assert_called_once_with(b'[]\n', str(Path(directory) / 'r.json'))
            sleep.assert_called_once_with(5)

    def test_uppercase_uuid_wait_and_status_use_canonical_id(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'result.json'
            res = self.run_script('wait', '--task-id', TASK_ID.upper(), '--output', str(output))
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertEqual(output.read_bytes(), RESULT)
        self.assertEqual([r[1] for r in Handler.requests],
                         [f'{ROOT}/{TASK_ID}', f'{ROOT}/{TASK_ID}/result'])
        res = self.run_script('status', '--task-id', TASK_ID.upper())
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(Handler.requests[-1][1], f'{ROOT}/{TASK_ID}')

    def test_slow_headers_and_body_cannot_exceed_wait_budget_and_save(self):
        for slow in ('body', 'headers'):
            with self.subTest(slow=slow), tempfile.TemporaryDirectory() as directory:
                Handler.slow_response = slow
                Handler.result = b'[{"adId":"123"}]'
                output = Path(directory) / 'result.json'
                output.write_bytes(b'previous result')
                started = time.monotonic()
                res = self.run_script('wait', '--task-id', TASK_ID, '--timeout', '1',
                                      '--output', str(output))
                elapsed = time.monotonic() - started
                self.assertNotEqual(res.returncode, 0)
                self.assertIn(b'timed out', res.stderr.lower())
                self.assertEqual(res.stdout, b'')
                self.assertEqual(output.read_bytes(), b'previous result')
                # Allow interpreter startup/scheduling, but not a >2s response.
                self.assertLess(elapsed, 1.8)

    def test_uuid_identity_still_rejects_different_task(self):
        other = task()
        other['task_id'] = '8af283fe-13aa-431d-a7cf-b58675701884'
        with self.assertRaisesRegex(module.CliError, 'different task_id'):
            module.wait_for_result(None, TASK_ID.upper(), 1, None, initial=other)


if __name__ == '__main__':
    unittest.main()
