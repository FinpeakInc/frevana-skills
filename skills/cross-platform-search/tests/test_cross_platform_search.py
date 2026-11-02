"""Offline contract tests. Mocked transport throughout; no network access."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'cross_platform_search.py'
spec = importlib.util.spec_from_file_location('cross_platform_search', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
TOKEN = 'offline-test-credential'
TASK = '11111111-1111-4111-8111-111111111111'


def task(status='PENDING', delay=1, **extra):
    return dict(task_id=TASK, client_task_id='test-operation', endpoint_id=m.ENDPOINT,
                status=status, next_poll_after_ms=delay, error_code=None, **extra)


class FakeClient:
    def __init__(self, replies, state_path):
        self.replies = iter(replies)
        self.calls = []
        self.state_path = state_path

    def request(self, method, suffix, payload, timeout):
        saved = json.loads(self.state_path.read_text())
        if method == 'POST':
            assert saved['request_payload'] == payload  # durable before submission
        self.calls.append((method, suffix, m.encode(payload)))
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return reply


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'state.json'


    def args(self, *extra):
        return m.parser().parse_args(['run', '--state-file', str(self.path), *extra])


    def state(self, *extra):
        args = self.args('--query', 'workout routine', '--client-task-id', 'test-operation', *extra)
        state, _ = m.prepare(args, self.path)
        m.save(self.path, state)
        return state, args


    def operation(self, replies, state=None, args=None):
        if state is None:
            state, args = self.state()
        client = FakeClient(replies, self.path)
        operation = m.Operation(state, self.path, client, args)
        return operation, client


    def test_sync_inline_has_no_poll_or_result_get(self):
        data = {'author': {'query': 'workout routine'}, 'unknown_field': ['preserved']}
        op, client = self.operation([(200, task('READY', 0, data=data, pagination={'next': 'retain-only'}))])
        result = op.run()
        self.assertEqual(result['outcome'], 'completed')
        self.assertEqual(result['data'], data)
        self.assertEqual(result['pagination'], {'next': 'retain-only'})
        self.assertEqual([c[0] for c in client.calls], ['POST'])
        self.assertFalse(result['resumable'])


    def test_sync_empty_or_null_data_is_a_result(self):
        for value in (None, {}, []):
            with self.subTest(value=value):
                self.path.unlink(missing_ok=True)
                op, client = self.operation([(200, task('READY', 0, data=value))])
                self.assertEqual(op.run()['data'], value)
                self.assertEqual(len(client.calls), 1)


    def test_async_polls_then_fetches_only_after_ready(self):
        op, client = self.operation([
            (202, task()), (200, task('RUNNING')), (200, task('SETTLING')),
            (200, task('READY', 0)), (200, {'task_id': TASK, 'data': {'author': {}}, 'pagination': None})])
        # Freeze scheduling time so filesystem latency cannot consume the 1ms hint.
        with patch.object(m.time, 'time', return_value=1000), patch.object(op, 'pause') as pause:
            result = op.run()
        self.assertEqual(result['outcome'], 'completed')
        self.assertEqual([c[1] for c in client.calls], ['', '/' + TASK, '/' + TASK, '/' + TASK, '/' + TASK + '/result'])
        self.assertEqual(pause.call_count, 3)
        for call in pause.call_args_list:
            self.assertAlmostEqual(call.args[0], .001)


    def test_retry_uses_identical_payload_and_persisted_client_id(self):
        op, client = self.operation([m.TransportError(), (503, {'message': 'temporary'}), (200, task('READY', 0, data=[]))])
        with patch.object(op, 'pause'):
            result = op.run()
        self.assertEqual(result['outcome'], 'completed')
        self.assertEqual(len(client.calls), 3)
        self.assertEqual(len({call[2] for call in client.calls}), 1)
        self.assertEqual(json.loads(self.path.read_text())['request_payload']['client_task_id'], result['client_task_id'])


    def test_request_timeout_then_resume_replays_original_post(self):
        op, client = self.operation([m.TimedOut()])
        first = op.run()
        self.assertEqual(first['outcome'], 'timeout')
        self.assertTrue(first['resumable'])
        self.assertEqual(len(client.calls), 1)
        args = m.parser().parse_args(['resume', '--state-file', str(self.path)])
        state, _ = m.prepare(args, self.path)
        resumed, retry = self.operation([(200, task('READY', 0, data=[]))], state, args)
        self.assertEqual(resumed.run()['outcome'], 'completed')
        self.assertEqual(client.calls[0][2], retry.calls[0][2])


    def test_poll_timeout_returns_task_and_resume_never_posts(self):
        state, args = self.state()
        args.timeout = .02
        op, client = self.operation([(202, task(delay=5000))], state, args)
        result = op.run()
        self.assertEqual(result['outcome'], 'timeout')
        self.assertEqual(result['task_id'], TASK)
        self.assertEqual(len(client.calls), 1)
        saved = json.loads(self.path.read_text())
        # The saved scheduling survives restart and can itself exhaust the new budget.
        again, second = self.operation([], saved, args)
        self.assertEqual(again.run()['outcome'], 'timeout')
        self.assertEqual(second.calls, [])
        args.timeout = 120
        again, second = self.operation([(200, task('READY', 0)), (200, {'task_id': TASK, 'data': []})], saved, args)
        with patch.object(again, 'pause'):
            self.assertEqual(again.run()['outcome'], 'completed')
        self.assertTrue(all(call[0] == 'GET' for call in second.calls))


    def test_known_task_without_local_state(self):
        args = self.args('--task-id', TASK)
        state, _ = m.prepare(args, self.path)
        m.save(self.path, state)
        op, client = self.operation([(200, task('READY', 0)), (200, {'task_id': TASK, 'data': []})], state, args)
        result = op.run()
        self.assertEqual(result['outcome'], 'completed')
        self.assertEqual(result['client_task_id'], 'test-operation')
        self.assertTrue(all(call[0] == 'GET' for call in client.calls))


    def test_generated_id_is_persisted_once(self):
        args = self.args('--query', 'workout routine')
        first, _ = m.prepare(args, self.path)
        self.assertEqual(str(m.uuid.UUID(first['client_task_id'])), first['client_task_id'])
        m.save(self.path, first)
        with patch.object(m.uuid, 'uuid4', side_effect=AssertionError('must reuse saved ID')):
            resumed, _ = m.prepare(self.args(), self.path)
        self.assertEqual(first['request_payload'], resumed['request_payload'])


    def test_transient_http_with_task_id_is_persisted_without_another_post(self):
        op, client = self.operation([(503, task())])
        result = op.run()
        self.assertEqual(result['task_id'], TASK)
        self.assertEqual(result['outcome'], 'http_error')
        self.assertEqual(len(client.calls), 1)


    def test_missing_identity_or_result_returns_protocol_error(self):
        for replies, error in (
            ([(202, {'status': 'PENDING'})], 'MISSING_TASK_ID'),
            ([(200, {'status': 'READY'})], 'MISSING_TASK_ID'),
            ([(200, task('READY', 0)), (200, {'task_id': TASK})], 'MISSING_RESULT_DATA'),
        ):
            self.path.unlink(missing_ok=True)
            op, _ = self.operation(replies)
            self.assertEqual(op.run()['error_code'], error)


    def test_request_timeout_bounds_slow_response(self):
        release = threading.Event()
        entered = threading.Event()
        class Response:
            code = 200
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self):
                entered.set()
                release.wait(2)
                return b'{}'
        client = m.Client('https://api.frevana.com', TOKEN)
        with patch.object(client.opener, 'open', return_value=Response()):
            try:
                with self.assertRaises(m.TimedOut):
                    client.request('POST', '', {'input': {}}, .02)
                self.assertTrue(entered.is_set())
            finally:
                release.set()


    def test_http_error_json_body_is_parsed_by_transport(self):
        client = m.Client('https://api.frevana.com', TOKEN)
        error = m.urllib.error.HTTPError(client.base + m.ROOT, 409, 'Conflict', {},
                                        io.BytesIO(b'{"message":"CLIENT_TASK_ID_CONFLICT"}'))
        with patch.object(client.opener, 'open', side_effect=error):
            status, body = client.request('POST', '', {}, 1)
        self.assertEqual(status, 409)
        self.assertEqual(m.error_code(body), 'CLIENT_TASK_ID_CONFLICT')


    def test_malformed_http_body_is_reported_without_echoing_it(self):
        client = m.Client('https://api.frevana.com', TOKEN)
        error = m.urllib.error.HTTPError(client.base + m.ROOT, 502, 'Bad Gateway', {},
                                        io.BytesIO(('not-json-' + TOKEN).encode()))
        with patch.object(client.opener, 'open', side_effect=error):
            status, body = client.request('POST', '', {}, 1)
        self.assertEqual(status, 502)
        self.assertEqual(body, {'error_code': 'INVALID_JSON_RESPONSE'})


    def test_redirect_handler_refuses_following(self):
        self.assertIsNone(m.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.example'))


    def test_terminal_states_stop_for_200_and_409(self):
        for status in ('FAILED', 'REVIEW_REQUIRED'):
            for http in (200, 409):
                with self.subTest(status=status, http=http):
                    self.path.unlink(missing_ok=True)
                    body = task(status, 0)
                    body['error_code'] = 'UPSTREAM_UNCERTAIN'
                    op, client = self.operation([(http, body)])
                    result = op.run()
                    self.assertEqual(result['outcome'], 'failed')
                    self.assertEqual(result['error_code'], 'UPSTREAM_UNCERTAIN')
                    self.assertEqual(result['task_id'], TASK)
                    self.assertFalse(result['resumable'])
                    self.assertEqual(len(client.calls), 1)
                    cached, calls = self.operation([], json.loads(self.path.read_text()), op.args)
                    self.assertEqual(cached.run()['outcome'], 'failed')
                    self.assertEqual(calls.calls, [])


    def test_conflict_parses_nest_message_without_retry(self):
        op, client = self.operation([(409, {'statusCode': 409, 'message': 'CLIENT_TASK_ID_CONFLICT', 'error': 'Conflict'})])
        result = op.run()
        self.assertEqual(result['outcome'], 'conflict')
        self.assertEqual(result['error_code'], 'CLIENT_TASK_ID_CONFLICT')
        self.assertEqual(len(client.calls), 1)
        resumed, calls = self.operation([], json.loads(self.path.read_text()), op.args)
        self.assertEqual(resumed.run()['outcome'], 'conflict')
        self.assertEqual(calls.calls, [])


    def test_result_409_preserves_task_without_recreating(self):
        op, client = self.operation([(202, task('READY', 0)), (409, {'error': {'code': 'RESULT_NOT_READY'}})])
        result = op.run()
        self.assertEqual(result['error_code'], 'RESULT_NOT_READY')
        self.assertEqual(result['task_id'], TASK)
        self.assertEqual([c[0] for c in client.calls], ['POST', 'GET'])


    def test_zero_or_missing_poll_hint_returns_pending(self):
        for delay in (0, None, -1, '5000'):
            self.path.unlink(missing_ok=True)
            op, client = self.operation([(202, task(delay=delay))])
            self.assertEqual(op.run()['outcome'], 'pending')
            self.assertEqual(len(client.calls), 1)


    def test_cached_ready_does_not_make_requests(self):
        op, client = self.operation([(200, task('READY', 0, data=[]))])
        op.run()
        cached, calls = self.operation([], json.loads(self.path.read_text()), op.args)
        self.assertEqual(cached.run()['outcome'], 'completed')
        self.assertEqual(calls.calls, [])


    def test_bad_input_fields_or_types_rejected(self):
        invalid = ({}, {'query': 'x', 'max_items': 1}, {'query': 'x', 'count': 1},
                   {'query': 'x', 'published_before': '2026-01-01'}, {'query': 'x', 'fit': 'other'},
                   {'query': 'x', 'trim': 1}, {'query': 'x', 'contact_email': 1},
                   {'query': 'x', 'async': 1.0}, {'query': 'x', 'async': 'yes'},
                   {'query': '   '}, {'query': None})
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(m.Invalid):
                m.validate_input(value)


    def test_all_async_schema_values_preserve_types(self):
        for value in (True, False, 1, 0, 'true', 'false', '1', '0'):
            result = m.validate_input({'query': 'x', 'async': value})
            self.assertIs(type(result['async']), type(value))


    def test_exact_payload_no_undeclared_defaults(self):
        state, _ = self.state('--lookback-days', '30', '--async', '0', '--include-transcripts', 'false')
        payload = state['request_payload']
        self.assertEqual(payload['input'], {'query': 'workout routine', 'lookback_days': 30, 'async': 0, 'include_transcripts': False})
        self.assertEqual(set(payload), {'endpoint_id', 'client_task_id', 'input', 'response_mode'})
        self.assertEqual(payload['response_mode'], 'json')


    def test_changed_input_or_client_id_or_origin_rejected(self):
        self.state()
        for flags in (('--query', 'other'), ('--client-task-id', 'other'), ('--api-base-url', 'https://other.example')):
            with self.subTest(flags=flags), self.assertRaises(m.Invalid):
                m.prepare(self.args(*flags), self.path)


    def test_no_new_operation_on_resume_without_state(self):
        args = m.parser().parse_args(['resume', '--state-file', str(self.path)])
        with self.assertRaises(m.Invalid):
            m.prepare(args, self.path)


    def test_input_file_rejects_extras_and_flag_mix(self):
        input_path = Path(self.temp.name) / 'input.json'
        input_path.write_text(json.dumps({'query': 'x', 'max_items': 10}))
        with self.assertRaises(m.Invalid):
            m.prepare(self.args('--input-file', str(input_path)), self.path)
        input_path.write_text(json.dumps({'query': 'x'}))
        with self.assertRaises(m.Invalid):
            m.prepare(self.args('--input-file', str(input_path), '--query', 'x'), self.path)


    def test_exhausted_retries_returns_same_identity(self):
        op, client = self.operation([m.TransportError()] * 3)
        with patch.object(op, 'pause'):
            result = op.run()
        self.assertEqual(result['outcome'], 'transport_error')
        self.assertTrue(result['resumable'])
        self.assertEqual(len({c[2] for c in client.calls}), 1)


    def test_auth_and_secret_redaction_with_mock_http_response(self):
        observed = []
        class Response:
            code = 200
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self):
                return json.dumps(task('READY', 0, data={'value': TOKEN, 'field': 'native'})).encode()
        def open_request(opener, request, timeout):
            observed.append((request.full_url, request.get_header('Authorization'), json.loads(request.data)))
            return Response()
        self.state()
        env = {'FREVANA_TOKEN': TOKEN, 'FREVANA_API_BASE_URL': 'https://api.frevana.com'}
        output = io.StringIO()
        with patch.dict(os.environ, env), patch.object(m.urllib.request.OpenerDirector, 'open', open_request), contextlib.redirect_stdout(output):
            code = m.main(['run', '--state-file', str(self.path)])
        self.assertEqual(code, 0, output.getvalue())
        self.assertEqual(observed[0][0], 'https://api.frevana.com/socialcrawl/tasks')
        self.assertEqual(observed[0][1], 'Bearer ' + TOKEN)
        self.assertEqual(observed[0][2]['input'], {'query': 'workout routine'})
        for text in (output.getvalue(), self.path.read_text()):
            self.assertNotIn(TOKEN, text)
        self.assertEqual(json.loads(output.getvalue())['data']['value'], '[REDACTED]')
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)


    def test_runnable_bash_entrypoint_help(self):
        run = subprocess.run(['bash', str(SCRIPT.with_suffix('.sh')), '--help'], capture_output=True, text=True, timeout=10)
        self.assertEqual(run.returncode, 0)
        self.assertIn('resume', run.stdout)


    def test_missing_auth_and_unknown_cli_field_make_no_network_calls(self):
        with patch.dict(os.environ, {'FREVANA_TOKEN': ''}), patch.object(m.Client, 'request') as network:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(m.main(['run', '--query', 'x', '--state-file', str(self.path)]), 2)
            network.assert_not_called()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            m.parser().parse_args(['run', '--state-file', str(self.path), '--max-items', '10'])


    def test_lock_rejects_concurrent_writer(self):
        with m.locked(self.path), self.assertRaises(m.Invalid):
            with m.locked(self.path):
                pass


    def invoke(self, *flags):
        stdout = io.StringIO()
        with patch.dict(os.environ, {'FREVANA_TOKEN': TOKEN, 'FREVANA_API_BASE_URL': 'https://api.frevana.com'}), contextlib.redirect_stdout(stdout):
            code = m.main(['run', '--state-file', str(self.path), *flags])
        return code, json.loads(stdout.getvalue())


    def test_invalid_existing_state_never_creates_or_overwrites(self):
        for content in ('null', '', '{broken', '[]', '{}', '{"version":2}'):
            with self.subTest(content=content):
                self.path.write_text(content)
                with patch.object(m.Client, 'request') as network, patch.object(m.uuid, 'uuid4') as generate:
                    code, result = self.invoke('--query', 'workout routine')
                self.assertEqual(code, 5)
                self.assertEqual(result['outcome'], 'state_error')
                network.assert_not_called()
                generate.assert_not_called()
                self.assertEqual(self.path.read_text(), content)


    def test_missing_state_identity_fields_never_get_replaced(self):
        original, _ = self.state()
        for key in ('task_id', 'client_task_id', 'request_payload'):
            with self.subTest(key=key):
                damaged = dict(original)
                del damaged[key]
                m.save(self.path, damaged)
                before = self.path.read_bytes()
                with patch.object(m.Client, 'request') as network:
                    code, _ = self.invoke()
                self.assertEqual(code, 5)
                network.assert_not_called()
                self.assertEqual(self.path.read_bytes(), before)


    def test_output_failure_keeps_completed_data_and_task_metadata(self):
        self.state()
        with patch.object(m.Client, 'request', return_value=(200, task('READY', 0, data={'profile': 'kept'}))) as network:
            code, result = self.invoke('--output', self.temp.name)  # existing directory
        self.assertEqual(code, 5)
        self.assertEqual(result['outcome'], 'completed')
        self.assertEqual(result['task_id'], TASK)
        self.assertEqual(result['client_task_id'], 'test-operation')
        self.assertEqual(result['data'], {'profile': 'kept'})
        self.assertEqual(result['client_errors'][0]['code'], 'OUTPUT_SAVE_FAILED')
        self.assertEqual(json.loads(self.path.read_text())['outcome'], 'completed')
        self.assertEqual(network.call_count, 1)
        with patch.object(m.Client, 'request') as retry:
            code, result = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(result['data'], {'profile': 'kept'})
        retry.assert_not_called()


    def test_output_failure_keeps_timeout_recovery_metadata(self):
        self.state()
        with patch.object(m.Client, 'request', return_value=(202, task(delay=5000))):
            code, result = self.invoke('--timeout', '.01', '--output', self.temp.name)
        self.assertEqual(code, 5)
        self.assertEqual(result['outcome'], 'timeout')
        self.assertEqual(result['error_code'], 'CLIENT_TIMEOUT')
        self.assertEqual(result['task_id'], TASK)
        self.assertEqual(result['state_file'], str(self.path.resolve()))
        self.assertTrue(result['resumable'])
        self.assertEqual(result['client_errors'][0]['code'], 'OUTPUT_SAVE_FAILED')


    def test_output_failure_does_not_replace_server_error(self):
        self.state()
        body = task('REVIEW_REQUIRED', 0)
        body['error_code'] = 'BILLING_REQUIRES_REVIEW'
        with patch.object(m.Client, 'request', return_value=(409, body)):
            code, result = self.invoke('--output', self.temp.name)
        self.assertEqual(code, 5)
        self.assertEqual(result['outcome'], 'failed')
        self.assertEqual(result['error_code'], 'BILLING_REQUIRES_REVIEW')
        self.assertEqual(result['http_status'], 409)


    def test_initial_state_save_failure_never_posts(self):
        with patch.object(m, 'save', side_effect=OSError('disk full')), patch.object(m.Client, 'request') as network:
            code, _ = self.invoke('--query', 'workout routine')
        self.assertEqual(code, 5)
        network.assert_not_called()


    def test_state_save_failure_after_response_returns_identity_and_stops(self):
        self.state()
        original = self.path.read_bytes()
        real_save = m.save
        def fail_after_initial(path, value):
            if value.get('task_id'):
                raise OSError('disk full')
            return real_save(path, value)
        with patch.object(m, 'save', side_effect=fail_after_initial), patch.object(m.Client, 'request', return_value=(202, task())) as network:
            code, result = self.invoke()
        self.assertEqual(code, 5)
        self.assertEqual(result['task_id'], TASK)
        self.assertEqual(result['request_payload'], json.loads(original)['request_payload'])
        self.assertTrue(result['resumable'])
        self.assertEqual(result['client_errors'][0]['code'], 'STATE_SAVE_FAILED')
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(network.call_count, 1)


    def test_invalid_task_id_is_rejected_before_any_network_request(self):
        for value in ('..', '', 'not-a-uuid', '11111111-1111-1111-8111-111111111111'):
            with self.subTest(value=value), patch.object(m.Client, 'request') as network:
                code, _ = self.invoke('--task-id', value)
                self.assertEqual(code, 2)
                network.assert_not_called()
                self.assertFalse(self.path.exists())


    def test_state_save_failure_after_completion_preserves_success(self):
        self.state()
        real_save = m.save
        def fail_on_completion(path, value):
            if value.get('outcome') == 'completed':
                raise OSError('disk full')
            return real_save(path, value)
        with patch.object(m, 'save', side_effect=fail_on_completion), patch.object(m.Client, 'request', return_value=(200, task('READY', 0, data=[]))) as network:
            code, result = self.invoke()
        self.assertEqual(code, 5)
        self.assertEqual(result['outcome'], 'completed')
        self.assertEqual(result['data'], [])
        self.assertEqual(result['task_id'], TASK)
        self.assertEqual(result['client_errors'][0]['code'], 'STATE_SAVE_FAILED')
        self.assertEqual(network.call_count, 1)


    def test_known_task_with_fresh_state_recovers_without_post(self):
        with patch.object(m.Client, 'request', side_effect=[(200, task('READY', 0)), (200, {'task_id': TASK, 'data': []})]) as network:
            code, result = self.invoke('--task-id', TASK)
        self.assertEqual(code, 0)
        self.assertEqual(result['outcome'], 'completed')
        self.assertEqual([call.args[0] for call in network.call_args_list], ['GET', 'GET'])


    def test_checkpoint_failure_preserves_conflict_without_a_replacement(self):
        self.state()
        real_save = m.save
        def fail_on_conflict(path, value):
            if value.get('http_status') == 409:
                raise OSError('disk full')
            return real_save(path, value)
        with patch.object(m, 'save', side_effect=fail_on_conflict), patch.object(m.Client, 'request', return_value=(409, {'message': 'CLIENT_TASK_ID_CONFLICT'})) as network:
            code, result = self.invoke()
        self.assertEqual(code, 5)
        self.assertEqual(result['outcome'], 'conflict')
        self.assertEqual(result['error_code'], 'CLIENT_TASK_ID_CONFLICT')
        self.assertEqual(result['client_task_id'], 'test-operation')
        self.assertFalse(result['resumable'])
        self.assertEqual(result['client_errors'][0]['code'], 'STATE_SAVE_FAILED')
        self.assertEqual(network.call_count, 1)


    def test_uppercase_task_id_is_the_same_task(self):
        task_id = 'abcdefab-cdef-4abc-8def-abcdefabcdef'
        state, args = self.state()
        state['task_id'] = task_id
        m.save(self.path, state)
        body = task('READY', 0, data=[])
        body['task_id'] = task_id.upper()
        op, client = self.operation([(200, body), (200, {'task_id': task_id, 'data': []})], state, args)
        result = op.run()
        self.assertEqual(result['outcome'], 'completed')
        self.assertEqual(result['task_id'], task_id)
        self.assertEqual([call[0] for call in client.calls], ['GET', 'GET'])


    def test_invalid_persisted_task_id_is_not_overwritten(self):
        state, _ = self.state()
        state['task_id'] = '..'
        m.save(self.path, state)
        before = self.path.read_bytes()
        with patch.object(m.Client, 'request') as network:
            code, _ = self.invoke('--task-id', TASK)
        self.assertEqual(code, 5)
        network.assert_not_called()
        self.assertEqual(self.path.read_bytes(), before)


    def test_success_response_requires_valid_task_id_even_inline(self):
        for value in (None, '', '..', 123, '11111111-1111-1111-8111-111111111111'):
            with self.subTest(value=value):
                self.path.unlink(missing_ok=True)
                self.state()
                body = task('READY', 0, data={'profile': 'unverified'})
                if value is None:
                    del body['task_id']
                else:
                    body['task_id'] = value
                with patch.object(m.Client, 'request', return_value=(200, body)) as network:
                    code, result = self.invoke()
                self.assertEqual(code, 4)
                self.assertEqual(result['outcome'], 'protocol_error')
                self.assertEqual(result['error_code'], 'MISSING_TASK_ID' if value is None else 'INVALID_TASK_ID')
                self.assertNotIn('data', result)
                self.assertIsNone(result['task_id'])
                self.assertEqual(network.call_count, 1)


    def test_resumed_task_mismatch_preserves_original_identity(self):
        state, _ = self.state()
        state['task_id'] = TASK
        m.save(self.path, state)
        body = task('READY', 0, data=[])
        body['task_id'] = '22222222-2222-4222-8222-222222222222'
        with patch.object(m.Client, 'request', return_value=(200, body)) as network:
            code, result = self.invoke()
        self.assertEqual(code, 4)
        self.assertEqual(result['outcome'], 'protocol_error')
        self.assertEqual(result['error_code'], 'TASK_ID_MISMATCH')
        self.assertEqual(result['task_id'], TASK)
        self.assertNotIn('data', result)
        self.assertEqual([call.args[0] for call in network.call_args_list], ['GET'])


    def test_result_response_also_requires_matching_task_id(self):
        for body in ({'data': []}, {'task_id': '..', 'data': []}):
            with self.subTest(body=body):
                self.path.unlink(missing_ok=True)
                self.state()
                with patch.object(m.Client, 'request', side_effect=[(200, task('READY', 0)), (200, body)]) as network:
                    code, result = self.invoke()
                self.assertEqual(code, 4)
                self.assertEqual(result['outcome'], 'protocol_error')
                self.assertEqual(result['task_id'], TASK)
                self.assertEqual([call.args[0] for call in network.call_args_list], ['POST', 'GET'])


    def test_origin_does_not_allow_auth_or_plain_remote_http(self):
        for value in ('https://u:p@example.com', 'http://example.com', 'https://example.com/path', 'https://example.com?token=x'):
            with self.subTest(value=value), self.assertRaises(m.Invalid):
                m.origin(value)


    def test_status_data_is_never_used_as_final_result(self):
        state, args = self.state()
        state['task_id'] = TASK
        m.save(self.path, state)
        status = task('READY', 0, data={'items': ['status-only-data']})
        final = {'task_id': TASK, 'data': {'items': ['final-result']}, 'pagination': None}
        op, client = self.operation([(200, status), (200, final)], state, args)
        result = op.run()
        self.assertEqual(result['data'], final['data'])
        self.assertEqual([call[0] for call in client.calls], ['GET', 'GET'])
        self.assertEqual([call[1] for call in client.calls], ['/' + TASK, '/' + TASK + '/result'])


    def test_202_ready_with_data_still_fetches_result(self):
        op, client = self.operation([(202, task('READY', 0, data={'preview': True})),
                                     (200, {'task_id': TASK, 'data': {'items': []}})])
        result = op.run()
        self.assertEqual(result['data'], {'items': []})
        self.assertEqual([call[1] for call in client.calls], ['', '/' + TASK + '/result'])


    def test_active_failed_and_review_tasks_do_not_fetch_result(self):
        for status in ('PENDING', 'RUNNING', 'POLLING', 'SETTLING', 'FAILED', 'REVIEW_REQUIRED'):
            for known in (False, True):
                with self.subTest(status=status, known=known):
                    self.path.unlink(missing_ok=True)
                    state, args = self.state()
                    if known:
                        state['task_id'] = TASK
                        m.save(self.path, state)
                    op, client = self.operation([(200 if known else 202, task(status, 0))], state, args)
                    result = op.run()
                    self.assertEqual(result['outcome'], 'failed' if status in m.STOP else 'pending')
                    self.assertEqual([call[0] for call in client.calls], ['GET' if known else 'POST'])
                    self.assertFalse(any(call[1].endswith('/result') for call in client.calls))


    def test_nonready_result_body_cannot_be_reported_as_completed(self):
        op, client = self.operation([(200, task('READY', 0)), (200, task('RUNNING', 0, data=[]))])
        result = op.run()
        self.assertEqual(result['outcome'], 'protocol_error')
        self.assertEqual(result['error_code'], 'RESULT_NOT_READY')
        self.assertEqual(result['task_id'], TASK)
        self.assertNotIn('data', result)


    def test_identity_mismatch_without_verified_task_never_replays_post(self):
        self.state()
        body = task('READY', 0, data={'items': []})
        body['client_task_id'] = 'different-operation'
        with patch.object(m.Client, 'request', return_value=(200, body)) as network:
            code, result = self.invoke()
        self.assertEqual(code, 4)
        self.assertEqual(result['error_code'], 'CLIENT_TASK_ID_MISMATCH')
        self.assertIsNone(result['task_id'])
        self.assertEqual(network.call_count, 1)
        with patch.object(m.Client, 'request') as retry:
            code, result = self.invoke()
        self.assertEqual(code, 4)
        self.assertEqual(result['error_code'], 'CLIENT_TASK_ID_MISMATCH')
        retry.assert_not_called()


    def test_missing_client_identity_recovers_existing_task_with_zero_posts(self):
        self.state()
        body = task('PENDING', 0)
        del body['client_task_id']
        with patch.object(m.Client, 'request', return_value=(202, body)):
            code, first = self.invoke()
        self.assertEqual(code, 4)
        self.assertEqual(first['task_id'], TASK)
        with patch.object(m.Client, 'request', side_effect=[
            (200, task('READY', 0, data={'status_only': True})),
            (200, {'task_id': TASK, 'data': {'items': []}}),
        ]) as network:
            code, result = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(result['data'], {'items': []})
        self.assertEqual([call.args[0] for call in network.call_args_list], ['GET', 'GET'])


    def test_missing_client_identity_stops_without_replacement(self):
        self.state()
        body = task('READY', 0, data=[])
        del body['client_task_id']
        with patch.object(m.Client, 'request', return_value=(200, body)) as network:
            code, result = self.invoke()
        self.assertEqual(code, 4)
        self.assertEqual(result['error_source'], 'protocol')
        self.assertEqual(result['error_code'], 'MISSING_CLIENT_TASK_ID')
        self.assertEqual(result['task_id'], TASK)
        self.assertEqual(result['client_task_id'], 'test-operation')
        self.assertEqual(network.call_count, 1)


    def test_state_lock_permission_error_is_a_state_error(self):
        with patch.object(m.os, 'open', side_effect=PermissionError('denied')), patch.object(m.Client, 'request') as network:
            code, result = self.invoke('--query', 'workout routine')
        self.assertEqual(code, 5)
        self.assertEqual(result['outcome'], 'state_error')
        self.assertEqual(result['error_code'], 'STATE_ACCESS_FAILED')
        self.assertEqual(result['error_source'], 'state')
        network.assert_not_called()


    def test_malformed_or_mismatched_client_identity_preserves_operation(self):
        for invalid in ('different-operation', '', None, 1, 'bad/id'):
            with self.subTest(invalid=invalid):
                self.path.unlink(missing_ok=True)
                state, _ = self.state()
                state['task_id'] = TASK
                m.save(self.path, state)
                body = task('READY', 0, data=[])
                body['client_task_id'] = invalid
                with patch.object(m.Client, 'request', return_value=(200, body)) as network:
                    code, result = self.invoke()
                self.assertEqual(code, 4)
                self.assertEqual(result['task_id'], TASK)
                self.assertEqual(result['client_task_id'], 'test-operation')
                self.assertEqual(result['error_code'], 'CLIENT_TASK_ID_MISMATCH' if invalid == 'different-operation' else 'INVALID_CLIENT_TASK_ID')
                self.assertEqual([call.args[0] for call in network.call_args_list], ['GET'])


    def test_persisted_client_identity_mismatch_keeps_recovery_metadata(self):
        state, _ = self.state()
        state['task_id'] = TASK
        state['client_task_id'] = 'changed'
        m.save(self.path, state)
        before = self.path.read_bytes()
        with patch.object(m.Client, 'request') as network:
            code, result = self.invoke()
        self.assertEqual(code, 5)
        self.assertEqual(result['outcome'], 'state_error')
        self.assertEqual(result['error_source'], 'state')
        self.assertEqual(result['error_code'], 'CLIENT_TASK_ID_MISMATCH')
        self.assertEqual(result['task_id'], TASK)
        self.assertEqual(result['request_payload']['client_task_id'], 'test-operation')
        self.assertTrue(result['requires_state_repair'])
        self.assertEqual(self.path.read_bytes(), before)
        network.assert_not_called()


    def test_state_bound_to_endpoint_and_version(self):
        original, _ = self.state()
        for changes in ({'endpoint_id': 'instagram/profile'}, {'version': 2}, {'version': True},
                        {'request_payload': None}, {'next_poll_at': 'tomorrow'}, {'status': []}):
            with self.subTest(changes=changes):
                m.save(self.path, {**original, **changes})
                before = self.path.read_bytes()
                with patch.object(m.Client, 'request') as network:
                    code, result = self.invoke()
                self.assertEqual(code, 5)
                self.assertEqual(result['outcome'], 'state_error')
                self.assertEqual(self.path.read_bytes(), before)
                network.assert_not_called()


    def test_server_code_survives_client_timeout_separately(self):
        state, args = self.state()
        args.timeout = .01
        body = task('SETTLING', 5000)
        body['error_code'] = 'SETTLEMENT_PENDING'
        op, client = self.operation([(202, body)], state, args)
        result = op.run()
        self.assertEqual(result['outcome'], 'timeout')
        self.assertEqual(result['error_source'], 'client')
        self.assertEqual(result['error_code'], 'CLIENT_TIMEOUT')
        self.assertEqual(result['server_error_code'], 'SETTLEMENT_PENDING')
        self.assertEqual(result['task_id'], TASK)
        self.assertEqual(len(client.calls), 1)


    def test_server_error_source_is_not_a_configuration_error(self):
        self.state()
        with patch.object(m.Client, 'request', return_value=(401, {'message': 'UNAUTHORIZED'})):
            code, result = self.invoke()
        self.assertEqual(code, 4)
        self.assertEqual(result['outcome'], 'http_error')
        self.assertEqual(result['error_source'], 'server')
        self.assertEqual(result['server_error_code'], 'UNAUTHORIZED')


    def test_nonfinite_state_is_rejected_without_mutation(self):
        self.path.write_text('{"version":NaN}')
        with patch.object(m.Client, 'request') as network:
            code, result = self.invoke('--query', 'workout routine')
        self.assertEqual(code, 5)
        self.assertEqual(result['outcome'], 'state_error')
        self.assertEqual(self.path.read_text(), '{"version":NaN}')
        network.assert_not_called()


    def test_invalid_returned_status_does_not_become_a_runtime_crash(self):
        state, args = self.state()
        body = task()
        body['status'] = ['RUNNING']
        op, client = self.operation([(202, body)], state, args)
        result = op.run()
        self.assertEqual(result['error_source'], 'protocol')
        self.assertEqual(result['error_code'], 'INVALID_TASK_STATUS')
        self.assertEqual(result['task_id'], TASK)
        self.assertEqual(len(client.calls), 1)

    def test_all_16_fields_roundtrip_in_allowlist_and_blocklist_modes(self):
        values = dict(query='AI coding assistants', **{'async': '0'}, limit=100, since='2026-01-02T12:00:00Z',
                      until='2026-01-30T12:00:00Z', include='facebook,stance', sources='reddit,youtube,github',
                      to_date='2026-01-31', from_date='2026-01-01', judgments='on', platforms='reddit,x',
                      relevance='filter', switch_from='Example', lookback_days=120, include_transcripts=True)
        self.assertEqual(set(values) | {'exclude'}, set(m.INPUT_SCHEMA['properties']))
        for mode in ({'sources': 'reddit,youtube,github', 'platforms': 'reddit,x'}, {'exclude': 'youtube,instagram'}):
            with self.subTest(mode=mode):
                self.path.unlink(missing_ok=True)
                current = {k: v for k, v in values.items() if k not in ('sources', 'platforms')}
                current.update(mode)
                source = Path(self.temp.name) / 'input.json'
                source.write_text(json.dumps(current))
                args = self.args('--input-file', str(source), '--client-task-id', 'test-operation')
                state, _ = m.prepare(args, self.path)
                m.save(self.path, state)
                op, client = self.operation([(200, task('READY', 0, data={'items': []}))], state, args)
                result = op.run()
                self.assertEqual(result['request_payload']['input'], current)
                self.assertEqual(result['endpoint_id'], 'search/everywhere')
                self.assertEqual(len(client.calls), 1)

    def test_query_only_default_does_not_select_sources_transcripts_limit_or_other_lanes(self):
        data = {'items': [], 'items_by_source': {'reddit': []}, 'accounting': {'credits': 20}}
        op, client = self.operation([(200, task('READY', 0, data=data))])
        result = op.run()
        self.assertEqual(result['request_payload']['input'], {'query': 'workout routine'})
        self.assertEqual(result['data'], data)
        self.assertEqual([c[0] for c in client.calls], ['POST'])

    def test_query_length_and_nonblank_validation_happen_before_uuid_or_network(self):
        for query in ('', ' ', 'a' * 513):
            with self.subTest(query=query), patch.object(m.Client, 'request') as network, patch.object(m.uuid, 'uuid4') as generate:
                code, _ = self.invoke('--query', query)
                self.assertEqual(code, 2)
                network.assert_not_called()
                generate.assert_not_called()
                self.assertFalse(self.path.exists())
        for query in ('x', '月' * 512):
            self.assertEqual(m.validate_input({'query': query})['query'], query)
        with patch.object(m.Client, 'request') as network, patch.object(m.uuid, 'uuid4') as generate:
            code, _ = self.invoke('--sources', 'reddit')
        self.assertEqual(code, 2)
        network.assert_not_called()
        generate.assert_not_called()

    def test_allowlist_or_platforms_cannot_combine_with_exclude(self):
        for flags in (['--sources', 'reddit', '--exclude', 'youtube'],
                      ['--platforms', 'reddit', '--exclude', 'youtube'],
                      ['--sources', 'reddit', '--platforms', 'x', '--exclude', 'youtube']):
            with self.subTest(flags=flags), patch.object(m.Client, 'request') as network, patch.object(m.uuid, 'uuid4') as generate:
                code, result = self.invoke('--query', 'x', *flags)
                self.assertEqual(code, 2)
                self.assertIn('mutually exclusive', result['message'])
                network.assert_not_called()
                generate.assert_not_called()
                self.assertFalse(self.path.exists())

    def test_sources_platforms_precedence_and_shorthands_are_not_rewritten_locally(self):
        state, args = self.state('--sources', 'youtube,x,instagram,tiktok', '--platforms', 'reddit')
        data = {'items': [], '_warnings': ['sources overrides differing platforms'],
                'items_by_source': {'youtube': [], 'youtube-hashtag': [], 'twitter': []}}
        op, client = self.operation([(200, task('READY', 0, data=data))], state, args)
        result = op.run()
        self.assertEqual(result['request_payload']['input'],
                         {'query': 'workout routine', 'sources': 'youtube,x,instagram,tiktok', 'platforms': 'reddit'})
        self.assertEqual(result['data'], data)
        self.assertEqual(len(client.calls), 1)
        self.path.unlink()
        state, _ = self.state('--exclude', 'youtube,instagram,tiktok')
        self.assertEqual(state['request_payload']['input'], {'query': 'workout routine', 'exclude': 'youtube,instagram,tiktok'})

    def test_facebook_include_and_allowlist_are_distinct_explicit_requests(self):
        for flag in ('--include', '--sources', '--platforms'):
            with self.subTest(flag=flag):
                self.path.unlink(missing_ok=True)
                state, args = self.state(flag, 'facebook')
                op, client = self.operation([(200, task('READY', 0, data={'items': []}))], state, args)
                result = op.run()
                self.assertEqual(result['request_payload']['input'], {'query': 'workout routine', flag[2:]: 'facebook'})
                self.assertEqual(len(client.calls), 1)

    def test_hangul_query_is_not_translated_or_given_a_local_source_override(self):
        query = '인공지능 개발 도구'
        args = self.args('--query', query, '--client-task-id', 'test-operation')
        state, _ = m.prepare(args, self.path)
        m.save(self.path, state)
        data = {'items': [], 'items_by_source': {'naver': []}}
        op, client = self.operation([(200, task('READY', 0, data=data))], state, args)
        result = op.run()
        self.assertEqual(result['request_payload']['input'], {'query': query})
        self.assertEqual(result['data'], data)
        self.assertEqual(len(client.calls), 1)

    def test_unknown_source_server_error_never_falls_back_or_replaces_task(self):
        state, args = self.state('--sources', 'not-a-source')
        op, client = self.operation([(400, {'error_code': 'UNKNOWN_SOURCE'})], state, args)
        result = op.run()
        self.assertEqual(result['error_code'], 'UNKNOWN_SOURCE')
        self.assertEqual(result['request_payload']['input']['sources'], 'not-a-source')
        self.assertEqual(result['client_task_id'], 'test-operation')
        self.assertEqual(len(client.calls), 1)

    def test_limit_over_40_is_preserved_and_native_clamp_warning_and_source_results_survive(self):
        for limit in (1, 40, 41, 1000, 10**30):
            self.assertEqual(m.validate_input({'query': 'x', 'limit': limit})['limit'], limit)
        state, args = self.state('--limit', '1000')
        data = {'items': [{'id': str(i)} for i in range(40)], 'items_by_source': {'reddit': [{'id': 'source-only'}]},
                '_warnings': ['limit clamped to 40'], 'accounting': {'credits': 20}}
        op, client = self.operation([(200, task('READY', 0, data=data))], state, args)
        result = op.run()
        self.assertEqual(result['request_payload']['input']['limit'], 1000)
        self.assertEqual(result['data'], data)
        self.assertEqual(len(client.calls), 1)
        for value in (0, -1, True, '10', 10.0):
            with self.subTest(value=value), self.assertRaises(m.Invalid):
                m.validate_input({'query': 'x', 'limit': value})

    def test_changed_limit_cannot_mutate_saved_operation_despite_shared_backend_cache(self):
        self.state('--limit', '10')
        with patch.object(m.Client, 'request') as network:
            code, result = self.invoke('--limit', '20')
        self.assertEqual(code, 5)
        self.assertEqual(result['error_source'], 'state')
        self.assertEqual(json.loads(self.path.read_text())['request_payload']['input']['limit'], 10)
        network.assert_not_called()

    def test_lookback_is_preserved_without_hard_date_filter_or_90_day_cap(self):
        for value in (1, 30, 91, 10**30):
            self.assertEqual(m.validate_input({'query': 'x', 'lookback_days': value})['lookback_days'], value)
        for value in (0, -1, True, '30', 30.0):
            with self.subTest(value=value), self.assertRaises(m.Invalid):
                m.validate_input({'query': 'x', 'lookback_days': value})
        state, args = self.state('--lookback-days', '120')
        data = {'items': [{'id': 'old', 'published_at': '2018-01-01', 'date_confidence': 'low', 'date_source': 'estimate'},
                          {'id': 'undated', 'published_at': None}]}
        op, client = self.operation([(200, task('READY', 0, data=data))], state, args)
        result = op.run()
        self.assertEqual(result['request_payload']['input'], {'query': 'workout routine', 'lookback_days': 120})
        self.assertEqual(result['data'], data)
        self.assertEqual(len(client.calls), 1)

    def test_native_from_to_dates_remain_distinct_from_since_until_with_backend_precedence(self):
        state, args = self.state('--from-date', '2026-01-01', '--to-date', '2026-01-31',
                                 '--since', '2026-01-02T12:00:00Z', '--until', '2026-01-30T12:00:00Z', '--lookback-days', '120')
        data = {'items': [{'id': 'undated', 'published_at': None}],
                'since': {'since': '2026-01-02T12:00:00Z', 'until': '2026-01-30T12:00:00Z', 'dropped': 5, 'kept_undated': 1},
                '_warnings': ['later lower bound used', 'earlier upper bound used']}
        op, client = self.operation([(200, task('READY', 0, data=data))], state, args)
        result = op.run()
        self.assertEqual(result['request_payload']['input'],
                         {'query': 'workout routine', 'from_date': '2026-01-01', 'to_date': '2026-01-31',
                          'since': '2026-01-02T12:00:00Z', 'until': '2026-01-30T12:00:00Z', 'lookback_days': 120})
        self.assertEqual(result['data'], data)
        self.assertEqual(len(client.calls), 1)

    def test_from_date_only_does_not_inject_today_or_other_date_fields(self):
        state, _ = self.state('--from-date', '2026-01-01')
        self.assertEqual(state['request_payload']['input'], {'query': 'workout routine', 'from_date': '2026-01-01'})

    def test_static_nonnative_aliases_map_to_since_until_without_colliding_with_from_to(self):
        for left in ('--since', '--published-after', '--start-date'):
            for right in ('--until', '--published-before', '--end-date'):
                with self.subTest(left=left, right=right):
                    self.path.unlink(missing_ok=True)
                    state, _ = self.state(left, '2026-01-02', right, '2026-01-30',
                                          '--from-date', '2026-01-01', '--to-date', '2026-01-31')
                    self.assertEqual(state['request_payload']['input'],
                                     {'query': 'workout routine', 'since': '2026-01-02', 'until': '2026-01-30',
                                      'from_date': '2026-01-01', 'to_date': '2026-01-31'})
        for flags in (['--since', '2026-01-01', '--start-date', '2026-01-02'],
                      ['--from-date', '2026-01-01', '--from-date', '2026-01-02']):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.args('--query', 'x', *flags)

    def test_relevance_filters_ranked_items_but_source_results_and_stance_totals_are_preserved(self):
        state, args = self.state('--relevance', 'filter', '--include', 'stance')
        data = {'items': [{'id': 'uncertain', 'computed': {'stance': None, 'relevance': None}}],
                'items_by_source': {'reddit': [{'id': 'off-topic'}, {'id': 'uncertain'}]},
                'relevance': {'dropped_ids': ['off-topic'], 'off_topic': 1},
                'stance_split': {'overall': {'positive': 1, 'uncertain': 1}, 'ids': {'positive': ['off-topic']}},
                '_warnings': ['stance_unavailable']}
        op, client = self.operation([(200, task('READY', 0, data=data))], state, args)
        result = op.run()
        self.assertEqual(result['data'], data)
        self.assertEqual(result['request_payload']['input']['relevance'], 'filter')
        self.assertEqual(len(client.calls), 1)

    def test_unavailable_or_disabled_judgments_never_trigger_refill_or_local_reclassification(self):
        for flags, data in ((['--relevance', 'filter'], {'items': [{'id': 'unknown', 'computed': {'stance': None, 'relevance': None}}],
                                                       '_warnings': ['relevance_unavailable', 'stance_skipped']}),
                            (['--judgments', 'off'], {'items': [{'id': 'native', 'future_field': None}]})):
            with self.subTest(flags=flags):
                self.path.unlink(missing_ok=True)
                state, args = self.state(*flags)
                op, client = self.operation([(200, task('READY', 0, data=data))], state, args)
                self.assertEqual(op.run()['data'], data)
                self.assertEqual(len(client.calls), 1)

    def test_switch_receipts_do_not_filter_other_items_or_create_a_percentage(self):
        state, args = self.state('--switch-from', 'Example')
        data = {'items': [{'id': 'switch'}, {'id': 'non-switch'}],
                'switch_receipts': [{'id': 'switch', 'quote': 'I left Example for Other because of speed',
                                     'reason': 'speed', 'destination': 'Other', 'link': 'https://example.invalid/post'}]}
        op, client = self.operation([(200, task('READY', 0, data=data))], state, args)
        result = op.run()
        self.assertEqual(result['data'], data)
        self.assertEqual(result['request_payload']['input']['query'], 'workout routine')
        self.assertNotIn('percentage', result['data']['switch_receipts'][0])
        self.assertEqual(len(client.calls), 1)

    def test_transcripts_explicit_boolean_keeps_segmented_and_plain_native_text_without_video_calls(self):
        state, args = self.state('--include-transcripts', 'true')
        data = {'items': [{'id': 'video1', 'source_items': [{'metadata': {'transcript': [{'start': 1.5, 'text': 'Narration'}]}}]},
                          {'id': 'video2', 'source_items': [{'metadata': {'transcript': 'Plain narration'}}]},
                          {'id': 'video3', 'source_items': [{'metadata': {'transcript': None}}]}]}
        op, client = self.operation([(200, task('READY', 0, data=data))], state, args)
        result = op.run()
        self.assertEqual(result['request_payload']['input'], {'query': 'workout routine', 'include_transcripts': True})
        self.assertEqual(result['data'], data)
        self.assertEqual(len(client.calls), 1)
        for value in (1, 'true', 'false', None):
            with self.subTest(value=value), self.assertRaises(m.Invalid):
                m.validate_input({'query': 'x', 'include_transcripts': value})

    def test_invalid_date_server_error_never_rewrites_bounds_or_creates_fallback_search(self):
        state, args = self.state('--to-date', 'invalid-date')
        op, client = self.operation([(400, {'error_code': 'INVALID_DATE'})], state, args)
        result = op.run()
        self.assertEqual(result['error_code'], 'INVALID_DATE')
        self.assertEqual(result['request_payload']['input']['to_date'], 'invalid-date')
        self.assertEqual(result['client_task_id'], 'test-operation')
        self.assertEqual(len(client.calls), 1)

    def test_undeclared_paging_labels_previews_and_source_specific_controls_are_rejected(self):
        for key, value in dict(cursor='next', page=2, max_items=100, max_age_days=30, label='quality', fit='goal',
                               dry_run='1', relevant_to='topic', sort='latest', region='US', includeExtras='true',
                               from_member='ACoAAExample', start_date='2026-01-01', published_before='2026-01-31',
                               download=True).items():
            with self.subTest(key=key), self.assertRaises(m.Invalid):
                m.validate_input({'query': 'x', key: value})
        for field, value in (('relevance', 'score'), ('judgments', 'none'), ('include', True), ('sources', ['reddit'])):
            with self.subTest(field=field), self.assertRaises(m.Invalid):
                m.validate_input({'query': 'x', field: value})

    def test_retry_keeps_source_precedence_dates_limit_and_transcript_payload_bytes(self):
        state, args = self.state('--sources', 'youtube,x,github', '--platforms', 'reddit', '--limit', '1000',
                                 '--from-date', '2026-01-01', '--to-date', '2026-01-31', '--since', '2026-01-02',
                                 '--until', '2026-01-30', '--lookback-days', '120', '--include-transcripts', 'true')
        original = m.encode(state['request_payload'])
        op, client = self.operation([m.TransportError(), (503, {}), (200, task('READY', 0, data={'items': []}))], state, args)
        with patch.object(op, 'pause'):
            result = op.run()
        self.assertEqual(result['outcome'], 'completed')
        self.assertEqual([call[2] for call in client.calls], [original] * 3)

    def test_saved_operation_rejects_changed_query_scope_bounds_display_limit_and_processing(self):
        self.state('--sources', 'reddit,youtube', '--platforms', 'reddit', '--limit', '10', '--lookback-days', '30',
                   '--from-date', '2026-01-01', '--to-date', '2026-01-31', '--include-transcripts', 'false')
        before = self.path.read_bytes()
        for flags in (['--query', 'other'], ['--sources', 'github'], ['--platforms', 'x'], ['--limit', '20'],
                      ['--lookback-days', '120'], ['--from-date', '2026-01-02'], ['--to-date', '2026-01-30'],
                      ['--since', '2026-01-02'], ['--until', '2026-01-30'], ['--include-transcripts', 'true'],
                      ['--include', 'facebook'], ['--judgments', 'off'], ['--switch-from', 'Example']):
            with self.subTest(flags=flags), patch.object(m.Client, 'request') as network:
                code, result = self.invoke(*flags)
                self.assertEqual(code, 5)
                self.assertEqual(result['error_source'], 'state')
                self.assertEqual(self.path.read_bytes(), before)
                network.assert_not_called()


    def test_x_posts_and_optional_synthesis_remain_separate_without_followup_calls(self):
        for flags in ([], ['--sources', 'x,web', '--include', 'synthesis']):
            with self.subTest(flags=flags):
                self.path.unlink(missing_ok=True)
                state, args = self.state(*flags)
                data = {'items': [{'id': 'post-1', 'source': 'twitter'}],
                        'synthesis': {'web': {'text': 'Web answer with citations'}},
                        'sources_failed': []}
                if flags:
                    data['synthesis']['x'] = {'text': 'X summary with citations'}
                else:
                    data['sources_failed'] = [{'source': 'github', 'reason': 'unavailable'}]
                op, client = self.operation([(200, task('READY', 0, data=data))], state, args)
                result = op.run()
                self.assertEqual(result['data'], data)
                self.assertEqual(result['data']['items'], [{'id': 'post-1', 'source': 'twitter'}])
                self.assertEqual(len(client.calls), 1)
                expected = {'query': 'workout routine'}
                if flags:
                    expected.update(sources='x,web', include='synthesis')
                self.assertEqual(json.loads(client.calls[0][2])['input'], expected)

    def test_unready_x_summary_warning_does_not_trigger_replacement_task(self):
        state, args = self.state('--include', 'synthesis')
        data = {'items': [], 'synthesis': {}, 'sources_failed': [
            {'source': 'twitter-ai-search', 'reason': 'not ready when the rest of the answer was'}]}
        op, client = self.operation([(200, task('READY', 0, data=data))], state, args)
        self.assertEqual(op.run()['data'], data)
        self.assertEqual(len(client.calls), 1)


if __name__ == '__main__':
    unittest.main()
