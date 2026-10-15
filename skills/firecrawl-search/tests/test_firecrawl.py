from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest

SKILL = Path(__file__).resolve().parents[1]
KIND = SKILL.name.removeprefix('firecrawl-')
SCRIPT = SKILL / 'scripts/firecrawl.sh'


def envelope(data=None, billing='BILLED'):
    if isinstance(data, dict) and data.get('status') == 'completed':
        data = dict(data)
        data.setdefault('data', [])
        data.setdefault('completed', len(data['data']))
        data.setdefault('total', data['completed'])
    return {'request_id': 'audit-1', 'data': data if data is not None else {'value': 1},
            'billing': {'status': billing, 'credits': 1}}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.calls.append((self.path, dict(self.headers), body))
        response = self.server.responses.pop(0) if self.server.responses else (200, envelope())
        status, payload = response[:2]
        raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        if len(response) > 2 and response[2] == 'slow-headers':
            try:
                headers = b'HTTP/1.0 200 OK\r\nX-Slow: ' + b'x' * 160 + b'\r\nContent-Length: ' + str(len(raw)).encode() + b'\r\n\r\n'
                for byte in headers:
                    self.wfile.write(bytes([byte]))
                    self.wfile.flush()
                    time.sleep(.01)
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        self.send_response(status)
        self.send_header('Content-Length', str(len(raw)))
        if status == 302:
            self.send_header('Location', self.server.base + '/leak')
        self.end_headers()
        try:
            if len(response) > 2:
                for byte in raw:
                    self.wfile.write(bytes([byte]))
                    self.wfile.flush()
                    time.sleep(response[2])
            else:
                self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError):
            pass


class FirecrawlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.server.base = 'http://127.0.0.1:' + str(cls.server.server_port)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.server.calls = []
        self.server.responses = []

    def cli(self, *args, token=True):
        env = {**os.environ, 'FREVANA_TOKEN': 'test-jwt' if token else '', 'FREVANA_API_KEY': 'must-not-use'}
        return subprocess.run(['bash', str(SCRIPT), *args, '--api-base-url', self.server.base],
                              env=env, capture_output=True, timeout=5)

    def input_args(self):
        return ['--query', 'example'] if KIND == 'search' else ['--url', 'https://example.com']

    def sync_args(self):
        return ['--mode', 'sync'] if KIND in ('scrape', 'crawl') else []

    def test_bearer_auth_and_exact_raw_file(self):
        raw = b'{ "request_id":"a", "data":{"status":"completed","id":"job-1","completed":0,"total":0,"data":[]}, "billing":{"status":"BILLED"} }'
        self.server.responses = [(200, raw)]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'out.json'
            result = self.cli('run', *self.input_args(), *self.sync_args(), '--output', str(output), '--idempotency-key', 'stable-1')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output.read_bytes(), raw)
        path, headers, body = self.server.calls[0]
        self.assertEqual(headers['Authorization'], 'Bearer test-jwt')
        self.assertNotIn('X-API-Key', headers)
        self.assertEqual(headers['Idempotency-Key'], 'stable-1')
        self.assertNotIn(b'test-jwt', result.stderr + result.stdout)
        self.assertNotIn('output', body)
        self.assertEqual(path, '/service/web/' + KIND)

    def test_service_web_base_prefix_is_not_duplicated(self):
        self.server.responses = [(200, envelope({'id': 'job-1', 'status': 'completed'}))]
        env = {**os.environ, 'FREVANA_TOKEN': 'test-jwt'}
        result = subprocess.run(['bash', str(SCRIPT), 'run', *self.input_args(), *self.sync_args(),
                                 '--api-base-url', self.server.base + '/service/web/'],
                                env=env, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.server.calls[0][0], '/service/web/' + KIND)

    def test_missing_token_never_uses_api_key(self):
        result = self.cli('run', *self.input_args(), token=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn(b'FREVANA_TOKEN', result.stderr)
        self.assertFalse(self.server.calls)

    def test_advanced_options_forwarded_for_server_validation(self):
        self.server.responses = [(200, envelope({'id': 'job-1', 'status': 'completed'}))]
        result = self.cli('run', *self.input_args(), *self.sync_args(), '--json', '{"futureField":true}')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.server.calls[0][2]['futureField'])

    def test_required_inputs_still_checked_locally(self):
        result = self.cli('run')
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.server.calls)

    def test_invalid_input_before_network(self):
        cases = [['--json', '[]'], ['--json', '{"limit":NaN}'], ['--wait-timeout', 'nan']]
        for args in cases:
            with self.subTest(args=args):
                self.assertEqual(self.cli('run', *self.input_args(), *args).returncode, 2)
        self.assertFalse(self.server.calls)

    def test_no_redirect_or_http_retry_and_preserve_file(self):
        for status in (302, 409, 429, 502):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                self.server.calls = []
                self.server.responses = [(status, {'request_id': 'audit-error'})]
                output = Path(directory) / 'out.json'
                output.write_text('keep')
                result = self.cli('run', *self.input_args(), *self.sync_args(), '--output', str(output))
                self.assertEqual(result.returncode, 2)
                self.assertEqual(len(self.server.calls), 1)
                self.assertEqual(output.read_text(), 'keep')
                self.assertIn(b'idempotency_key=', result.stderr)

    def test_malformed_response(self):
        for payload in (b'not json', b'[]', b'{"data":{}}'):
            self.server.responses = [(200, payload)]
            result = self.cli('run', *self.input_args(), *self.sync_args())
            self.assertEqual(result.returncode, 2)

    def test_review_stops_without_resubmission(self):
        self.server.responses = [(200, {'request_id': 'a', 'data': None, 'billing': {'status': 'REVIEW'}})]
        result = self.cli('run', *self.input_args())
        self.assertEqual(result.returncode, 4)
        self.assertEqual(len(self.server.calls), 1)
        self.assertEqual(json.loads(result.stdout)['billing']['status'], 'REVIEW')

    def test_whole_response_deadline(self):
        self.server.responses = [(200, envelope(), .02)]
        before = time.monotonic()
        result = self.cli('run', *self.input_args(), '--wait-timeout', '.5')
        self.assertEqual(result.returncode, 2)
        self.assertLess(time.monotonic() - before, 1.5)
        self.assertEqual(len(self.server.calls), 1)

    def test_slow_headers_obey_invocation_and_http_deadlines(self):
        for deadline_flag in ('--wait-timeout', '--http-timeout'):
            with self.subTest(deadline_flag=deadline_flag):
                self.server.calls = []
                self.server.responses = [(200, envelope(), 'slow-headers')]
                before = time.monotonic()
                result = self.cli('run', *self.input_args(), *self.sync_args(), deadline_flag, '.35')
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertLess(time.monotonic() - before, 1.2)
                self.assertEqual(len(self.server.calls), 1)
                self.assertIn(b'idempotency_key=', result.stderr)
                self.assertNotIn(b'test-jwt', result.stderr)

    def test_settled_partial_without_next_never_succeeds(self):
        if KIND not in ('scrape', 'crawl'):
            self.skipTest('jobs only')
        partial = envelope({'id': 'job-1', 'status': 'completed', 'completed': 3,
                            'total': 3, 'next': None, 'data': [{'markdown': 'page1'}]})
        for action in ('status', 'wait'):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as directory:
                self.server.calls = []
                self.server.responses = [(200, partial)]
                output = Path(directory) / 'partial.json'
                result = self.cli(action, '--job-id', 'job-1', '--output', str(output))
                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertEqual(len(self.server.calls), 1)
                self.assertEqual(json.loads(output.read_bytes()), partial)
                self.assertEqual(json.loads(result.stdout), partial)

    def test_job_coverage_requires_counters_and_complete_documents(self):
        if KIND not in ('scrape', 'crawl'):
            self.skipTest('jobs only')
        cases = [
            ({'id': 'job-1', 'status': 'completed', 'data': []}, 3),
            ({'id': 'job-1', 'status': 'completed', 'completed': 1, 'total': 2, 'data': [{}]}, 3),
            ({'id': 'job-1', 'status': 'completed', 'completed': 2, 'total': 2, 'data': [{}, {}]}, 0),
            ({'id': 'job-1', 'status': 'completed', 'completed': 0, 'total': 0, 'data': []}, 0),
        ]
        for data, code in cases:
            with self.subTest(data=data):
                self.server.responses = [(200, {'request_id': 'a', 'data': data, 'billing': {'status': 'BILLED'}})]
                result = self.cli('status', '--job-id', 'job-1')
                self.assertEqual(result.returncode, code, result.stderr)

    def test_nested_validation_delegated_and_dynamic_schema_preserved(self):
        if KIND == 'map':
            bad = {'location': {'future': True}}
        elif KIND == 'search':
            bad = {'scrapeOptions': {'future': True}}
        else:
            bad = {'formats': [{'type': 'json', 'future': True}]} if KIND == 'scrape' else {'scrapeOptions': {'formats': [{'type': 'invalid'}]}}
        self.server.responses = [(400, {'message': 'Invalid option'})]
        result = self.cli('run', *self.input_args(), '--json', json.dumps(bad))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(len(self.server.calls), 1)
        for field, value in bad.items():
            self.assertEqual(self.server.calls[0][2][field], value)
        self.server.calls = []
        if KIND == 'scrape':
            schema = {'type': 'object', 'properties': {'brand_new_key': {'type': 'string'}}}
            options = {'formats': [{'type': 'json', 'schema': schema}], 'headers': {'X-Custom': 'target-secret'}}
            result = self.cli('run', *self.input_args(), '--mode', 'sync', '--json', json.dumps(options))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.server.calls[0][2]['formats'][0]['schema'], schema)
            self.assertNotIn(b'target-secret', result.stderr)

    def test_scrape_mode_selection_and_batch(self):
        if KIND != 'scrape':
            self.skipTest('scrape only')
        self.server.responses = [(200, envelope({'id': 'batch-1'}, 'PENDING')),
                                 (200, envelope({'id': 'batch-1', 'status': 'completed', 'data': [{'markdown': 'ok'}]}))]
        result = self.cli('run', '--url', 'https://example.com/a', '--url', 'https://example.com/b', '--poll-interval', '.01')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([x[0] for x in self.server.calls], ['/service/web/start-scrape', '/service/web/get-scrape-status'])
        self.assertEqual(len(self.server.calls[0][2]['urls']), 2)
        self.assertNotIn('url', self.server.calls[0][2])
        self.assertNotIn('Idempotency-Key', self.server.calls[1][1])
        self.assertEqual(self.server.calls[1][2]['jobId'], 'batch-1')

    def test_simple_scrape_defaults_to_sync_and_cannot_sync_batch(self):
        if KIND != 'scrape':
            self.skipTest('scrape only')
        self.assertEqual(self.cli('run', '--url', 'https://example.com').returncode, 0)
        self.assertEqual(self.server.calls[0][0], '/service/web/scrape')
        self.server.calls = []
        result = self.cli('run', '--url', 'https://example.com/a', '--url', 'https://example.com/b', '--mode', 'sync')
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.server.calls)

    def test_async_heavy_and_explicit_sync_override(self):
        if KIND != 'scrape':
            self.skipTest('scrape only')
        self.server.responses = [(200, envelope({'id': 'job-1'}, 'PENDING'))]
        result = self.cli('start', '--url', 'https://example.com', '--json', '{"actions":[{"type":"wait","milliseconds":0}]}')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.server.calls[0][0], '/service/web/start-scrape')
        self.assertEqual(self.server.calls[0][2]['urls'], ['https://example.com'])
        self.server.calls = []
        result = self.cli('run', '--url', 'https://example.com', '--json', '{"formats":["screenshot"],"timeout":5000}')
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.server.calls)
        self.server.responses = [(200, envelope())]
        result = self.cli('run', '--url', 'https://example.com', '--mode', 'sync', '--json', '{"formats":["screenshot"],"timeout":5000}')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.server.calls[0][0], '/service/web/scrape')

    def test_default_crawl_async_and_sync_contract(self):
        if KIND != 'crawl':
            self.skipTest('crawl only')
        self.server.responses = [(200, envelope({'id': 'crawl-1'}, 'PENDING')),
                                 (200, envelope({'id': 'crawl-1', 'status': 'completed'}))]
        result = self.cli('run', *self.input_args(), '--poll-interval', '.01', '--json', '{"sitemap":"only","limit":2}')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.server.calls[0][0], '/service/web/start-crawl')
        self.server.calls = []
        result = self.cli('start', *self.input_args(), '--json', '{"timeout":30}')
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.server.calls)

    def test_job_status_cancel_and_task_id_validation(self):
        if KIND not in ('scrape', 'crawl'):
            self.skipTest('jobs only')
        self.server.responses = [(200, envelope({'id': 'job-1', 'status': 'completed'}))]
        result = self.cli('status', '--job-id', 'job-1')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.server.calls[0][0], '/service/web/get-' + KIND + '-status')
        self.server.responses = [(200, envelope(True, 'PENDING'))]
        result = self.cli('cancel', '--job-id', 'job-1')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.server.calls[-1][0], '/service/web/cancel-' + KIND)
        self.assertEqual(self.cli('status', '--job-id', '../../x').returncode, 2)

    def test_wait_settlement_and_partial_result(self):
        if KIND not in ('scrape', 'crawl'):
            self.skipTest('jobs only')
        self.server.responses = [(200, {'data': None, 'billing': {'status': 'READY'}}),
                                 (200, envelope({'id': 'job-1', 'status': 'completed', 'data': []}))]
        result = self.cli('wait', '--job-id', 'job-1', '--poll-interval', '.01')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(self.server.calls), 2)
        self.server.responses = [(200, envelope({'id': 'job-1', 'status': 'completed', 'next': 'https://provider.example/next'}))]
        result = self.cli('status', '--job-id', 'job-1')
        self.assertEqual(result.returncode, 3)
        self.assertIn('next', json.loads(result.stdout)['data'])

    def test_wait_deadline_and_terminal_failure(self):
        if KIND not in ('scrape', 'crawl'):
            self.skipTest('jobs only')
        self.server.responses = [(200, envelope({'id': 'job-1', 'status': 'scraping'}, 'PENDING'))]
        result = self.cli('wait', '--job-id', 'job-1', '--wait-timeout', '.5')
        self.assertEqual(result.returncode, 3)
        self.assertIn(b'job-1', result.stderr)
        self.assertEqual(len(self.server.calls), 1)
        self.server.responses = [(200, envelope({'id': 'job-1', 'status': 'failed'}))]
        self.assertEqual(self.cli('wait', '--job-id', 'job-1').returncode, 4)

    def test_search_filters_and_known_url_modes(self):
        if KIND == 'search':
            for body in ({'includeDomains': ['x'], 'excludeDomains': ['y']}, {'categories': ['developer', 'pdf']}):
                self.assertEqual(self.cli('run', *self.input_args(), '--json', json.dumps(body)).returncode, 2)
            self.assertFalse(self.server.calls)
            self.assertEqual(self.cli('run', *self.input_args(), '--json', '{"sources":["news"],"scrapeOptions":{"formats":["markdown"]}}').returncode, 0)
        elif KIND == 'map':
            self.assertEqual(self.cli('run', *self.input_args(), '--json', '{"sitemap":"only","limit":2,"search":"docs"}').returncode, 0)
            self.assertEqual(self.server.calls[0][2]['sitemap'], 'only')


if __name__ == '__main__':
    unittest.main()
