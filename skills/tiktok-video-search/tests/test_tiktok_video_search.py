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
SCRIPT = SKILL / 'scripts/tiktok_video_search.py'
TASK_ID = '7af283fe-13aa-431d-a7cf-b58675701884'
ROOT = '/service/tiktok-videos/tasks'
RESULT = b'[ {"id":"1878055429367345", "text":"test", "unknown": [1,2]} ]\n'
spec = importlib.util.spec_from_file_location('tiktok_video_search', SCRIPT)
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
    truncated = False

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
        self.send_header('Content-Length', str(len(body) + (10 if self.__class__.truncated else 0)))
        if code == 302:
            self.send_header('Location', '/redirected')
        self.end_headers()
        if self.__class__.truncated:
            self.close_connection = True
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


class TikTokVideoSearchTest(unittest.TestCase):
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
        Handler.truncated = False

    def run_script(self, *args, auth=('--token', 'test-token'), env=None):
        clean_env = os.environ.copy()
        clean_env.pop('FREVANA_TOKEN', None)
        clean_env.pop('FREVANA_API_KEY', None)
        if env:
            clean_env.update(env)
        return subprocess.run(['python3', str(SCRIPT), *args, '--api-base-url', self.base, *auth],
                              env=clean_env, input=b'', capture_output=True, timeout=10)


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
            res = self.run_script('run', '--keyword', 'q')
            self.assertNotEqual(res.returncode, 0)
            self.assertIn(status.encode(), res.stderr)
            self.assertEqual([r[0] for r in Handler.requests], ['POST', 'GET'])

    def test_zero_poll_interval_stops(self):
        Handler.delay = 0
        res = self.run_script('run', '--keyword', 'q')
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
        res = self.run_script('create', '--keyword', 'q', '--client-task-id', 'stable-retry')
        self.assertNotEqual(res.returncode, 0)
        self.assertIn(b'HTTP 302', res.stderr)
        self.assertIn(b'--client-task-id stable-retry', res.stderr)
        self.assertEqual(len(Handler.requests), 1)

    def test_create_uncertain_outcome_reports_stable_id(self):
        for code, body in ((500, None), (200, b'invalid json')):
            Handler.requests = []
            Handler.code, Handler.create_body = code, body
            res = self.run_script('create', '--keyword', 'q', '--client-task-id', 'stable-retry')
            self.assertNotEqual(res.returncode, 0)
            self.assertIn(b'--client-task-id stable-retry', res.stderr)
            self.assertEqual(len(Handler.requests), 1)


    def test_invalid_action_flags_and_credentials_no_requests(self):
        for args, auth in ((['status', '--task-id', '../escape'], ('--token', 'ok')),
                           (['status', '--task-id', TASK_ID, '--keyword', 'q'], ('--token', 'ok')),
                           (['result', '--task-id', TASK_ID, '--wait'], ('--token', 'ok')),
                           (['create', '--keyword', 'q', '--timeout', '1'], ('--token', 'ok')),
                           (['create', '--keyword', 'q'], ('--token', 'secret\nheader'))):
            res = self.run_script(*args, auth=auth)
            self.assertNotEqual(res.returncode, 0)
            self.assertEqual(Handler.requests, [])

    def test_create_wait_and_ready_creation_skip_poll(self):
        Handler.create_status = 'READY'
        with tempfile.TemporaryDirectory() as directory:
            res = self.run_script('create', '--wait', '--keyword', 'q', '--output', str(Path(directory) / 'r.json'))
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
                client.request('POST', payload={'keyword': 'q'})

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
                Handler.result = b'[{"id":"123"}]'
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


    def test_search_payload_and_raw_result(self):
        Handler.states = ['RUNNING', 'SETTLING', 'READY']
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'result.json'
            res = self.run_script('run', '--query', ' skincare ', '--query', 'beauty',
                                  '--query', 'beauty', '--video-search-sorting', 'LATEST',
                                  '--video-search-date-filter', 'PAST_WEEK', '--results-per-page', '100',
                                  '--scrape-related-search-words', 'true', '--max-total-charge-usd', '2.50',
                                  '--client-task-id', 'stable-id', '--output', str(output))
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertEqual(res.stdout, RESULT)
            self.assertEqual(output.read_bytes(), RESULT)
        self.assertEqual(json.loads(Handler.requests[0][3]), {
            'client_task_id': 'stable-id', 'search_queries': ['beauty', 'skincare'],
            'search_section': '/video', 'video_search_sorting': 'LATEST',
            'video_search_date_filter': 'PAST_WEEK', 'results_per_page': 100,
            'scrape_related_search_words': True, 'max_total_charge_usd': 2.5})
        self.assertEqual([(r[0], r[1]) for r in Handler.requests],
                         [('POST', ROOT)] + [('GET', f'{ROOT}/{TASK_ID}')] * 3 +
                         [('GET', f'{ROOT}/{TASK_ID}/result')])

    def test_minimal_payload_sends_twenty_results_per_query(self):
        res = self.run_script('create', '--query', 'coffee')
        self.assertEqual(res.returncode, 0, res.stderr)
        payload = json.loads(Handler.requests[0][3])
        self.assertEqual(set(payload), {'client_task_id', 'search_queries', 'search_section', 'results_per_page'})
        self.assertEqual(payload['results_per_page'], 20)
        self.assertEqual(payload['search_section'], '/video')
        self.assertIn(payload['client_task_id'].encode(), res.stderr)

    def test_invalid_search_inputs_make_no_requests(self):
        cases = [[], ['--query', ' '], ['--query', 'x' * 257],
                 ['--query', 'a'] * 6,
                 ['--query', 'x', '--results-per-page', '0'],
                 ['--query', 'x', '--results-per-page', '101'],
                 ['--query', 'x', '--video-search-sorting', 'popular'],
                 ['--query', 'x', '--video-search-date-filter', '7'],
                 ['--query', 'x', '--should-download-videos', 'yes'],
                 ['--query', 'x', '--proxy-country-code', 'CN'],
                 ['--query', 'x', '--video-search-date-filter', 'PAST_WEEK', '--least-diggs', '5'],
                 ['--query', 'x', '--least-diggs', '10', '--most-diggs', '10'],
                 ['--query', 'x', '--least-diggs', '0'],
                 ['--query', 'x', '--comments-per-post', '1001'],
                 ['--query', 'x', '--comments-per-post', '1', '--top-level-comments-per-post', '2'],
                 ['--query', 'x', '--max-replies-per-comment', '1'],
                 ['--query', 'x', '--client-task-id', '']]
        cases += [['--query', 'x', '--max-total-charge-usd', v]
                  for v in ('nan', 'inf', '0.49', '1000.01', '1.001', 'abc')]
        for flags in cases:
            with self.subTest(flags=flags):
                res = self.run_script('create', *flags)
                self.assertNotEqual(res.returncode, 0)
                self.assertEqual(Handler.requests, [])

    def test_enrichment_and_boundaries(self):
        res = self.run_script('create', '--query', 'x' * 256, '--results-per-page', '1',
                              '--least-diggs', '1', '--most-diggs', '9007199254740991',
                              '--comments-per-post', '1000', '--top-level-comments-per-post', '1000',
                              '--max-replies-per-comment', '100', '--proxy-country-code', 'US',
                              '--max-total-charge-usd', '0.50')
        self.assertEqual(res.returncode, 0, res.stderr)
        payload = json.loads(Handler.requests[0][3])
        self.assertEqual(payload['max_total_charge_usd'], 0.5)
        self.assertEqual(payload['most_diggs'], 9007199254740991)

    def test_auth_precedence_and_api_key_support(self):
        cases = [(('--api-key', 'explicit-key'), {'FREVANA_TOKEN': 'env-token'}, 'x-api-key', 'explicit-key'),
                 (('--token', 'explicit-token'), {'FREVANA_API_KEY': 'env-key'}, 'authorization', 'Bearer explicit-token'),
                 ((), {'FREVANA_TOKEN': 'env-token', 'FREVANA_API_KEY': 'env-key'}, 'authorization', 'Bearer env-token'),
                 ((), {'FREVANA_API_KEY': 'env-key'}, 'x-api-key', 'env-key')]
        for auth, env, header, expected in cases:
            res = self.run_script('create', '--query', 'x', auth=auth, env=env)
            self.assertEqual(res.returncode, 0, res.stderr)
            headers = {k.lower(): v for k, v in Handler.requests[-1][2].items()}
            self.assertEqual(headers[header], expected)
            self.assertNotIn(expected.encode(), res.stdout + res.stderr)
        Handler.requests = []
        res = self.run_script('create', '--query', 'x', auth=())
        self.assertNotEqual(res.returncode, 0)
        res = self.run_script('create', '--query', 'x', auth=('--token', 't', '--api-key', 'k'))
        self.assertNotEqual(res.returncode, 0)
        self.assertEqual(Handler.requests, [])

    def test_items_pagination_and_unchanged_bytes(self):
        page = b'{"task_id":"7af283fe-13aa-431d-a7cf-b58675701884", "offset":20,"limit":10,"count":1,"total":21,"items":[{"id":"123"}]}\n'
        original = Handler.do_GET
        def items(handler):
            if '/items?' in handler.path:
                handler.record()
                handler.respond(200, page)
            else:
                original(handler)
        with patch.object(Handler, 'do_GET', items):
            res = self.run_script('items', '--task-id', TASK_ID, '--offset', '20', '--limit', '10')
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout, page)
        self.assertEqual(Handler.requests[-1][1], f'{ROOT}/{TASK_ID}/items?offset=20&limit=10')
        Handler.requests = []
        for flags in (['items', '--task-id', TASK_ID, '--offset', '-1'],
                      ['items', '--task-id', TASK_ID, '--limit', '1001'],
                      ['status', '--task-id', TASK_ID, '--limit', '1']):
            self.assertNotEqual(self.run_script(*flags).returncode, 0)
        self.assertEqual(Handler.requests, [])


    def test_long_poll_interval_is_not_capped_by_http_timeout(self):
        with patch.object(module.time, 'monotonic', return_value=0), \
             patch.object(module.time, 'sleep', side_effect=RuntimeError('stop after sleep')) as sleep:
            with self.assertRaisesRegex(RuntimeError, 'stop after sleep'):
                module.wait_for_result(None, TASK_ID, 3600, None,
                                       initial=task('RUNNING', 1200000))
        sleep.assert_called_once_with(1200)

    def test_truncated_http_response_does_not_save_valid_looking_json(self):
        Handler.truncated = True
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'result.json'
            output.write_bytes(b'previous')
            res = self.run_script('result', '--task-id', TASK_ID, '--output', str(output))
            self.assertNotEqual(res.returncode, 0)
            self.assertIn(b'transport failed', res.stderr)
            self.assertEqual(res.stdout, b'')
            self.assertEqual(output.read_bytes(), b'previous')


    def test_removed_ai_parameters_rejected_before_request(self):
        for field in ('ai-video-description', 'ai-video-summary'):
            for value in ('true', 'false'):
                res = self.run_script('create', '--query', 'coffee', '--' + field, value)
                self.assertNotEqual(res.returncode, 0)
                self.assertIn(b'unrecognized arguments', res.stderr)
        self.assertEqual(Handler.requests, [])
        payload = module.create_payload(module.parser().parse_args(['create', '--query', 'coffee']))
        self.assertNotIn('ai_video_description', payload)
        self.assertNotIn('ai_video_summary', payload)


    def test_hashtag_and_username_sources_send_default_twenty(self):
        for flag, field, values in (('--hashtag', 'hashtags', ['skincare', 'beauty', 'beauty']),
                                    ('--username', 'profiles', ['tiktok', 'creator.name', 'tiktok'])):
            Handler.requests = []
            args = [arg for value in values for arg in (flag, value)]
            res = self.run_script('create', *args)
            self.assertEqual(res.returncode, 0, res.stderr)
            payload = json.loads(Handler.requests[0][3])
            self.assertEqual(set(payload), {'client_task_id', field, 'results_per_page'})
            self.assertEqual(payload[field], sorted(set(values)))
            self.assertEqual(payload['results_per_page'], 20)
            self.assertNotIn('search_section', payload)

    def test_source_modes_validate_before_network(self):
        cases = [ ['--query', 'coffee', '--hashtag', 'coffee'],
                  ['--username', 'tiktok', '--hashtag', 'coffee'],
                  ['--username', '@tiktok'], ['--username', 'https://www.tiktok.com/@tiktok'],
                  ['--username', 'bad name'], ['--username', 'x' * 129],
                  ['--hashtag', '#coffee'], ['--hashtag', 'two words'],
                  ['--hashtag', 'coffee/tea'], ['--hashtag', 'coffee?'], ['--hashtag', 'x' * 129],
                  ['--username', ' '], ['--hashtag', ' '],
                  ['--username', 'x'] * 6, ['--hashtag', 'x'] * 6,
                  ['--username', 'tiktok', '--video-search-sorting', 'LATEST'],
                  ['--hashtag', 'coffee', '--video-search-date-filter', 'PAST_WEEK'],
                  ['--username', 'tiktok', '--scrape-related-search-words', 'false'] ]
        for flags in cases:
            with self.subTest(flags=flags):
                res = self.run_script('create', *flags)
                self.assertNotEqual(res.returncode, 0)
                self.assertEqual(Handler.requests, [])
        for flags in (['status', '--task-id', TASK_ID, '--hashtag', 'coffee'],
                      ['items', '--task-id', TASK_ID, '--username', 'tiktok']):
            self.assertNotEqual(self.run_script(*flags).returncode, 0)
            self.assertEqual(Handler.requests, [])

    def test_non_keyword_run_and_explicit_result_limit(self):
        for flags, field, expected in ((['--hashtag', ' 咖啡 '], 'hashtags', ['咖啡']),
                                       (['--username', ' creator.name '], 'profiles', ['creator.name'])):
            Handler.requests = []
            with tempfile.TemporaryDirectory() as directory:
                res = self.run_script('run', *flags, '--results-per-page', '5',
                                      '--output', str(Path(directory) / 'result.json'))
                self.assertEqual(res.returncode, 0, res.stderr)
                self.assertEqual(res.stdout, RESULT)
            payload = json.loads(Handler.requests[0][3])
            self.assertEqual(payload[field], expected)
            self.assertEqual(payload['results_per_page'], 5)
            self.assertNotIn('search_queries', payload)
            self.assertNotIn('search_section', payload)


    def test_video_download_toggle_is_not_exposed_or_sent(self):
        for value in ('true', 'false'):
            res = self.run_script('create', '--query', 'coffee', '--should-download-videos', value)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn(b'unrecognized arguments', res.stderr)
        self.assertEqual(Handler.requests, [])
        for flag, value in (('--query', 'coffee'), ('--hashtag', 'coffee'), ('--username', 'tiktok')):
            payload = module.create_payload(module.parser().parse_args(['create', flag, value]))
            self.assertNotIn('should_download_videos', payload)


    def test_cover_download_toggle_is_not_exposed_or_sent(self):
        for value in ('true', 'false'):
            res = self.run_script('create', '--query', 'coffee', '--should-download-covers', value)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn(b'unrecognized arguments', res.stderr)
        self.assertEqual(Handler.requests, [])
        for flag, value in (('--query', 'coffee'), ('--hashtag', 'coffee'), ('--username', 'tiktok')):
            payload = module.create_payload(module.parser().parse_args(['create', flag, value]))
            self.assertNotIn('should_download_covers', payload)
            self.assertNotIn('should_download_videos', payload)


    def test_media_options_are_not_exposed_or_sent(self):
        removed = {
            '--should-download-slideshow-images': 'true',
            '--should-download-avatars': 'true',
            '--should-download-music-covers': 'true',
            '--download-subtitles-options': 'DOWNLOAD_SUBTITLES',
            '--video-kv-store-id-or-name': 'my-store',
        }
        for flag, value in removed.items():
            res = self.run_script('create', '--query', 'coffee', flag, value)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn(b'unrecognized arguments', res.stderr)
        self.assertEqual(Handler.requests, [])
        for flag, value in (('--query', 'coffee'), ('--hashtag', 'coffee'), ('--username', 'tiktok')):
            payload = module.create_payload(module.parser().parse_args(['create', flag, value]))
            self.assertFalse(any('download' in field or 'kv_store' in field for field in payload))


if __name__ == '__main__':
    unittest.main()
