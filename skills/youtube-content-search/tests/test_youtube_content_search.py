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

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'youtube_content_search.py'
spec = importlib.util.spec_from_file_location('youtube_content_search', SCRIPT)
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
        with patch.object(op, 'pause', wraps=op.pause) as pause:
            result = op.run()
        self.assertEqual(result['outcome'], 'completed')
        self.assertEqual([c[1] for c in client.calls], ['', '/' + TASK, '/' + TASK, '/' + TASK, '/' + TASK + '/result'])
        self.assertEqual(pause.call_count, 3)
        self.assertTrue(all(0 < call.args[0] <= .001 for call in pause.call_args_list))


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
        state, _ = self.state('--min-views', '0', '--async', '0', '--label-evidence', '1')
        payload = state['request_payload']
        self.assertEqual(payload['input'], {'query': 'workout routine', 'min_views': 0, 'async': 0, 'label_evidence': '1'})
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

    def test_all_33_fields_roundtrip_with_exact_native_camelcase_names(self):
        values = dict(query='javascript tutorial', fit='goal', goal='Find beginner lessons', seen='research-1',
                      type='videos', **{'async': '0'}, brand='Example', label='mention,intent,quality,ai_written',
                      offer='Developer tools', since='2026-01-01', until='2026-01-31', cursor='opaque+/=:000123',
                      region='JP', sortBy='popular', dry_run='1', exclude='engagement_bait,ai_written',
                      include='engagement,channel', duration='under_3_min', judgments='on', min_views=0,
                      relevance='filter', sort_rows='views', fit_tokens=800, uploadDate='this_year',
                      exact_dates='false', relevant_to='JavaScript beginner lessons', max_age_days=30,
                      includeExtras='true', label_evidence='1', brand_description='A software company',
                      relevance_threshold='0.70', ai_written_threshold='0.71')
        self.assertEqual(set(values) | {'continuationToken'}, set(m.INPUT_SCHEMA['properties']))
        for field, value in (('cursor', 'opaque+/=:000123'), ('continuationToken', 'native+/=:000123')):
            with self.subTest(field=field):
                self.path.unlink(missing_ok=True)
                current = {k: v for k, v in values.items() if k != 'cursor'}
                current[field] = value
                source = Path(self.temp.name) / 'input.json'
                source.write_text(json.dumps(current))
                args = self.args('--input-file', str(source), '--client-task-id', 'test-operation')
                state, _ = m.prepare(args, self.path)
                m.save(self.path, state)
                op, client = self.operation([(200, task('READY', 0, data={'estimate': {}}))], state, args)
                result = op.run()
                self.assertEqual(result['request_payload']['input'], current)
                self.assertEqual(result['endpoint_id'], 'youtube/search')
                self.assertEqual(len(client.calls), 1)

    def test_default_query_only_has_no_type_extras_channel_or_exact_date_override(self):
        op, client = self.operation([(200, task('READY', 0, data={'posts': []}, pagination={'next_cursor': 'next'}))])
        result = op.run()
        self.assertEqual(result['request_payload']['input'], {'query': 'workout routine'})
        self.assertEqual(result['pagination']['next_cursor'], 'next')
        self.assertEqual([c[0] for c in client.calls], ['POST'])

    def test_missing_query_never_generates_id_or_calls_network(self):
        for flags in ([], ['--type', 'shorts'], ['--include', 'channel'], ['--sort-by', 'popular']):
            with self.subTest(flags=flags), patch.object(m.Client, 'request') as network, patch.object(m.uuid, 'uuid4') as generate:
                code, result = self.invoke(*flags)
                self.assertEqual(code, 2)
                self.assertEqual(result['error_source'], 'client')
                generate.assert_not_called()
                network.assert_not_called()
                self.assertFalse(self.path.exists())

    def test_camelcase_cli_and_hyphen_aliases_emit_only_native_json_names(self):
        for flags in (['--sortBy', 'popular', '--uploadDate', 'this_year', '--includeExtras', 'true',
                       '--continuationToken', 'native-token'],
                      ['--sort-by', 'popular', '--upload-date', 'this_year', '--include-extras', 'true',
                       '--continuation-token', 'native-token']):
            with self.subTest(flags=flags):
                self.path.unlink(missing_ok=True)
                state, _ = self.state(*flags)
                self.assertEqual(state['request_payload']['input'],
                                 {'query': 'workout routine', 'sortBy': 'popular', 'uploadDate': 'this_year',
                                  'includeExtras': 'true', 'continuationToken': 'native-token'})
        for flags in (['--sortBy', 'popular', '--sort-by', 'relevance'],
                      ['--includeExtras', 'true', '--include-extras', 'false'],
                      ['--continuationToken', 'one', '--continuation-token', 'two']):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.args('--query', 'x', *flags)

    def test_universal_and_native_cursor_are_exact_strings(self):
        for field, flag in (('cursor', '--cursor'), ('continuationToken', '--continuation-token')):
            for value in ('0', '999999999999999999999999999', 'native+/=:000123'):
                with self.subTest(field=field, value=value):
                    self.path.unlink(missing_ok=True)
                    state, args = self.state(flag, value)
                    op, client = self.operation([(200, task('READY', 0, data=[]))], state, args)
                    result = op.run()
                    self.assertEqual(result['request_payload']['input'][field], value)
                    self.assertIs(type(result['request_payload']['input'][field]), str)
                    self.assertEqual(len(client.calls), 1)
            for value in (0, True, 1.5, None):
                with self.subTest(field=field, value=value), self.assertRaises(m.Invalid):
                    m.validate_input({'query': 'x', field: value})

    def test_conflicting_cursor_fields_never_submit_or_generate_id(self):
        with patch.object(m.Client, 'request') as network, patch.object(m.uuid, 'uuid4') as generate:
            code, _ = self.invoke('--query', 'x', '--cursor', 'universal', '--continuation-token', 'native')
        self.assertEqual(code, 2)
        network.assert_not_called()
        generate.assert_not_called()
        self.assertFalse(self.path.exists())

    def test_all_four_content_types_are_forwarded_without_assuming_video_shape(self):
        for kind in ('videos', 'shorts', 'channels', 'playlists'):
            with self.subTest(kind=kind):
                self.path.unlink(missing_ok=True)
                state, args = self.state('--type', kind)
                data = {'items': [{'kind': kind, 'future': {'keep': None}}]}
                op, client = self.operation([(200, task('READY', 0, data=data))], state, args)
                result = op.run()
                self.assertEqual(result['data'], data)
                self.assertEqual(result['request_payload']['input']['type'], kind)
                self.assertEqual(len(client.calls), 1)

    def test_channels_single_page_keeps_has_more_false_without_fabricating_cursor(self):
        state, args = self.state('--type', 'channels')
        data = {'channels': [{'id': 'channel', 'subscriber_count': None}]}
        op, client = self.operation([(200, task('READY', 0, data=data, pagination={'has_more': False}))], state, args)
        result = op.run()
        self.assertEqual(result['data'], data)
        self.assertEqual(result['pagination'], {'has_more': False})
        self.assertNotIn('next_cursor', result['pagination'])
        self.assertEqual(len(client.calls), 1)

    def test_short_popular_and_narrow_upload_date_conflicts_stop_before_submission(self):
        for flags in (['--sort-by', 'popular'], ['--sortBy', 'popular'], ['--upload-date', 'today'],
                      ['--uploadDate', 'this_week'], ['--upload-date', 'this_month']):
            with self.subTest(flags=flags), patch.object(m.Client, 'request') as network, patch.object(m.uuid, 'uuid4') as generate:
                code, result = self.invoke('--query', 'x', '--type', 'shorts', *flags)
                self.assertEqual(code, 2)
                self.assertEqual(result['error_source'], 'client')
                network.assert_not_called()
                generate.assert_not_called()
                self.assertFalse(self.path.exists())
        for extra in ({}, {'uploadDate': 'this_year'}, {'sortBy': 'relevance'}):
            value = {'query': 'x', 'type': 'shorts', **extra}
            self.assertEqual(m.validate_input(value), value)

    def test_popular_rank_is_not_locally_sorted_by_views(self):
        state, args = self.state('--sort-by', 'popular')
        data = {'posts': [{'id': 'a', 'engagement': {'views': 9500000}},
                          {'id': 'b', 'engagement': {'views': 502900000}},
                          {'id': 'c', 'engagement': {'views': 66000}}]}
        op, client = self.operation([(200, task('READY', 0, data=data))], state, args)
        result = op.run()
        self.assertEqual(result['data'], data)
        self.assertEqual(result['request_payload']['input']['sortBy'], 'popular')
        self.assertNotIn('sort_rows', result['request_payload']['input'])
        self.assertEqual(len(client.calls), 1)

    def test_explicit_sort_rows_is_distinct_and_native_order_is_unchanged(self):
        state, args = self.state('--sort-by', 'popular', '--sort-rows', 'views')
        data = {'posts': [{'id': 'top', 'engagement': {'views': 100}},
                          {'id': 'low', 'engagement': {'views': 1}}, {'id': 'unknown', 'engagement': {'views': None}}]}
        op, client = self.operation([(200, task('READY', 0, data=data))], state, args)
        result = op.run()
        self.assertEqual(result['data'], data)
        self.assertEqual(result['request_payload']['input']['sort_rows'], 'views')
        self.assertEqual(len(client.calls), 1)

    def test_short_year_date_repeats_are_preserved_without_automatic_dedup_or_refill(self):
        state, args = self.state('--type', 'shorts', '--upload-date', 'this_year')
        data = {'posts': [{'id': 'same'}, {'id': 'other'}, {'id': 'same'}]}
        op, client = self.operation([(200, task('READY', 0, data=data,
                                               pagination={'next_cursor': 'advancing-token'}))], state, args)
        result = op.run()
        self.assertEqual(result['data'], data)
        self.assertEqual(result['pagination']['next_cursor'], 'advancing-token')
        self.assertEqual(len(client.calls), 1)

    def test_duration_and_typed_upload_date_do_not_locally_enforce_unreliable_source_filters(self):
        state, args = self.state('--type', 'videos', '--upload-date', 'today', '--duration', 'under_3_min')
        data = {'posts': [{'id': 'long-old', 'content': {'duration_seconds': 4000}, 'published_at': '2018-01-01'},
                          {'id': 'mixed-kind', 'kind': 'channel', 'content': {'duration_seconds': None}}],
                '_warnings': ['source filter limitation']}
        op, client = self.operation([(200, task('READY', 0, data=data))], state, args)
        result = op.run()
        self.assertEqual(result['data'], data)
        self.assertEqual(result['request_payload']['input']['duration'], 'under_3_min')
        self.assertEqual(len(client.calls), 1)

    def test_default_short_identity_keeps_null_handle_avatar_without_auto_channel_join(self):
        state, args = self.state('--type', 'shorts')
        data = {'posts': [{'id': 'short', 'ext': {'channel_id': 'UC123'},
                           'author': {'display_name': 'Creator', 'username': None, 'avatar_url': None}}]}
        op, client = self.operation([(200, task('READY', 0, data=data))], state, args)
        result = op.run()
        self.assertEqual(result['data'], data)
        self.assertEqual(result['request_payload']['input'], {'query': 'workout routine', 'type': 'shorts'})
        self.assertEqual(len(client.calls), 1)

    def test_exact_dates_false_keeps_null_short_author_estimate_and_translated_title_markers(self):
        state, args = self.state('--type', 'shorts', '--exact-dates', 'false')
        data = {'posts': [{'id': 'short', 'author': None, 'title': 'Listing title',
                           'published_at': '2026-01-01T00:00:00Z',
                           'ext': {'published_precision': 'month', 'published_label': '4 months ago',
                                   'title_maybe_translated': True, 'channel_id': None},
                           'computed': {'language': 'en'}}]}
        op, client = self.operation([(200, task('READY', 0, data=data))], state, args)
        result = op.run()
        self.assertEqual(result['data'], data)
        self.assertEqual(result['request_payload']['input']['exact_dates'], 'false')
        self.assertEqual(len(client.calls), 1)

    def test_partial_exact_dates_keep_warnings_and_do_not_trigger_more_lookups(self):
        for warning in ('exact_dates_partial', 'exact_dates_unavailable'):
            with self.subTest(warning=warning):
                self.path.unlink(missing_ok=True)
                state, args = self.state('--exact-dates', 'true')
                data = {'posts': [{'id': 'unresolved', 'ext': {'published_precision': 'day',
                                   'published_label': 'yesterday', 'title_maybe_translated': True}}],
                        '_warnings': [warning]}
                op, client = self.operation([(200, task('READY', 0, data=data))], state, args)
                self.assertEqual(op.run()['data'], data)
                self.assertEqual(len(client.calls), 1)

    def test_exact_dates_and_include_extras_are_strings_not_booleans(self):
        state, _ = self.state('--exact-dates', 'false', '--include-extras', 'true')
        self.assertEqual(state['request_payload']['input'],
                         {'query': 'workout routine', 'exact_dates': 'false', 'includeExtras': 'true'})
        for field in ('exact_dates', 'includeExtras'):
            for value in (True, False, 0, None):
                with self.subTest(field=field, value=value), self.assertRaises(m.Invalid):
                    m.validate_input({'query': 'x', field: value})
        with self.assertRaises(m.Invalid):
            m.validate_input({'query': 'x', 'exact_dates': '1'})
        # includeExtras is a string without a schema enum; detailed values belong to the backend.
        self.assertEqual(m.validate_input({'query': 'x', 'includeExtras': 'false'})['includeExtras'], 'false')

    def test_include_extras_short_duration_does_not_create_channel_identity_or_subscribers(self):
        state, args = self.state('--type', 'shorts', '--include-extras', 'true')
        data = {'posts': [{'id': 'short', 'content': {'duration_seconds': 50},
                           'engagement': {'likes': 10, 'comments': 2},
                           'author': {'display_name': 'Creator', 'username': None, 'avatar_url': None},
                           'ext': {'channel_id': 'UC123', 'author_followers': None, 'description': 'Description'}}]}
        op, client = self.operation([(200, task('READY', 0, data=data))], state, args)
        result = op.run()
        self.assertEqual(result['data'], data)
        self.assertNotIn('include', result['request_payload']['input'])
        self.assertEqual(len(client.calls), 1)

    def test_explicit_combined_joins_preserve_hydration_country_rounding_and_unresolved_nulls(self):
        state, args = self.state('--type', 'shorts', '--include', 'engagement,channel')
        data = {'posts': [{'id': 'resolved', 'engagement': {'views': 10000, 'likes': 200, 'comments': 20},
                           'author': {'display_name': 'Creator', 'username': '@creator', 'avatar_url': 'https://media.invalid/a'},
                           'ext': {'channel_id': 'UC123', 'author_followers': 123000, 'author_country': 'JP'}},
                          {'id': 'unresolved', 'author': None, 'ext': {'author_followers': None, 'author_country': None}}],
                'hydration': {'rows': 2, 'lookups': 2, 'credits_held': 4, 'credits_kept': 2, 'elapsed_ms': 700}}
        op, client = self.operation([(200, task('READY', 0, data=data))], state, args)
        result = op.run()
        self.assertEqual(result['data'], data)
        self.assertEqual(result['request_payload']['input']['include'], 'engagement,channel')
        self.assertEqual(len(client.calls), 1)

    def test_video_join_skipped_channel_playlist_rows_do_not_trigger_extra_fetches(self):
        for kind in ('channels', 'playlists'):
            with self.subTest(kind=kind):
                self.path.unlink(missing_ok=True)
                state, args = self.state('--type', kind, '--include', 'engagement')
                data = {'rows': [{'kind': kind, 'engagement': {'views': None}}],
                        'hydration': {'lookups': 0, 'credits_kept': 0}}
                op, client = self.operation([(200, task('READY', 0, data=data))], state, args)
                self.assertEqual(op.run()['data'], data)
                self.assertEqual(len(client.calls), 1)

    def test_date_filters_empty_and_undated_rows_can_keep_continuation_without_stopping(self):
        for posts in ([], [{'id': 'old', 'published_at': '2018-01-01'}, {'id': 'undated', 'published_at': None}]):
            with self.subTest(posts=posts):
                self.path.unlink(missing_ok=True)
                state, args = self.state('--since', '2026-01-01', '--until', '2026-01-31', '--sort-by', 'popular')
                data = {'posts': posts, 'walk': {'discarded': {'since': 10}, 'request_ids': ['page-request']}}
                pagination = {'next_cursor': 'continue', 'stopped_at': None}
                op, client = self.operation([(200, task('READY', 0, data=data, pagination=pagination))], state, args)
                result = op.run()
                self.assertEqual(result['data'], data)
                self.assertEqual(result['pagination'], pagination)
                self.assertEqual(len(client.calls), 1)

    def test_date_aliases_emit_only_since_until_and_keep_age_integer(self):
        for left in ('--since', '--published-after', '--start-date', '--from-date'):
            for right in ('--until', '--published-before', '--end-date', '--to-date'):
                with self.subTest(left=left, right=right):
                    self.path.unlink(missing_ok=True)
                    state, _ = self.state(left, '2026-01-01', right, '2026-01-31', '--max-age-days', '30')
                    self.assertEqual(state['request_payload']['input'], {'query': 'workout routine',
                                     'since': '2026-01-01', 'until': '2026-01-31', 'max_age_days': 30})
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.args('--query', 'x', '--since', '2026-01-01', '--start-date', '2026-02-01')

    def test_numeric_bounds_and_filter_types_are_schema_exact(self):
        for extra in ({'min_views': 0}, {'min_views': 10**30}, {'max_age_days': 1}, {'max_age_days': 3650},
                      {'fit_tokens': -1}, {'fit_tokens': 0}):
            value = {'query': 'x', **extra}
            self.assertEqual(m.validate_input(value), value)
        for field, value in (('min_views', -1), ('min_views', True), ('min_views', '20'),
                             ('max_age_days', 0), ('max_age_days', 3651), ('max_age_days', 30.0),
                             ('fit_tokens', True), ('sort_rows', 'likes'), ('type', 'video')):
            with self.subTest(field=field, value=value), self.assertRaises(m.Invalid):
                m.validate_input({'query': 'x', field: value})

    def test_region_proxy_is_forwarded_without_country_filtering_or_normalization(self):
        state, args = self.state('--region', 'jp')
        data = {'posts': [{'id': 'a', 'ext': {'author_country': 'US'}}, {'id': 'b', 'ext': {'author_country': None}}]}
        op, client = self.operation([(200, task('READY', 0, data=data))], state, args)
        result = op.run()
        self.assertEqual(result['request_payload']['input']['region'], 'jp')
        self.assertEqual(result['data'], data)
        self.assertEqual(len(client.calls), 1)

    def test_seen_scope_is_not_client_identity_and_preview_never_triggers_paid_joins_or_recall(self):
        state, args = self.state('--seen', 'research-1', '--include', 'engagement,channel', '--fit', 'goal',
                                 '--goal', 'Find beginner lessons', '--relevance', 'filter', '--relevant-to', 'JavaScript lessons',
                                 '--label', 'mention,ai_written', '--brand', 'Example', '--exclude', 'ai_written', '--dry-run', '1')
        data = {'estimate': {'rows_expected': 20, 'base_credits': 1},
                'held_back': {'ids': ['held'], 'recall_id': 'keep-not-a-route'}, 'walk': {'repeats': 10},
                'labels': {'pending': ['p'], 'dropped_ids': ['d']}, 'relevance': {'pending': ['p'], 'dropped_ids': []},
                'posts': [{'id': 'p', 'computed': {'labels': None, 'relevance': None}}]}
        op, client = self.operation([(200, task('READY', 0, data=data))], state, args)
        result = op.run()
        self.assertEqual(result['data'], data)
        self.assertEqual(result['client_task_id'], 'test-operation')
        self.assertEqual(result['request_payload']['input']['seen'], 'research-1')
        self.assertEqual(result['request_payload']['input']['dry_run'], '1')
        self.assertEqual(len(client.calls), 1)

    def test_undeclared_legacy_fields_alias_json_keys_and_page_controls_are_rejected(self):
        for key, value in dict(search_query='x', sp='token', hl='en', gl='us', sort='popular', sort_by='popular',
                               upload_date='today', include_extras='true', continuation_token='token',
                               limit=20, max_items=100, page=2, trim=True, order='viewCount', country='US',
                               start_date='2026-01-01', end_date='2026-01-31', publish_time='yesterday', download=True).items():
            with self.subTest(key=key), self.assertRaises(m.Invalid):
                m.validate_input({'query': 'x', key: value})
        for field, value in (('include', True), ('includeExtras', True), ('dry_run', 1), ('label_evidence', True),
                             ('relevance_threshold', .7), ('ai_written_threshold', .71)):
            with self.subTest(field=field), self.assertRaises(m.Invalid):
                m.validate_input({'query': 'x', field: value})
        # include's description names CSV tokens, but schema leaves the string open for backend validation.
        self.assertEqual(m.validate_input({'query': 'x', 'include': 'engagement,channel'})['include'], 'engagement,channel')

    def test_retry_preserves_native_camelcase_token_date_and_join_payload_bytes(self):
        state, args = self.state('--continuation-token', 'native+/=:000123', '--type', 'videos', '--sort-by', 'popular',
                                 '--upload-date', 'this_year', '--include-extras', 'true', '--exact-dates', 'false',
                                 '--include', 'engagement,channel', '--max-age-days', '30')
        original = m.encode(state['request_payload'])
        op, client = self.operation([m.TransportError(), (503, {}), (200, task('READY', 0, data=[]))], state, args)
        with patch.object(op, 'pause'):
            result = op.run()
        self.assertEqual(result['outcome'], 'completed')
        self.assertEqual([call[2] for call in client.calls], [original] * 3)

    def test_saved_operation_rejects_changed_kind_token_rank_or_enrichment(self):
        self.state('--type', 'videos', '--cursor', 'original', '--sort-by', 'popular', '--exact-dates', 'false',
                   '--include-extras', 'true', '--include', 'engagement')
        before = self.path.read_bytes()
        for flags in (['--query', 'other'], ['--type', 'channels'], ['--cursor', 'next'], ['--continuation-token', 'native'],
                      ['--sort-by', 'relevance'], ['--exact-dates', 'true'], ['--include-extras', 'false'],
                      ['--include', 'engagement,channel'], ['--upload-date', 'today']):
            with self.subTest(flags=flags), patch.object(m.Client, 'request') as network:
                code, result = self.invoke(*flags)
                self.assertEqual(code, 5)
                self.assertEqual(result['error_source'], 'state')
                self.assertEqual(self.path.read_bytes(), before)
                network.assert_not_called()

    def test_explicit_playlist_next_page_uses_new_identity_exact_cursor_and_same_options(self):
        state, args = self.state('--type', 'playlists', '--region', 'JP', '--seen', 'scope')
        op, first = self.operation([(200, task('READY', 0, data=[], pagination={'next_cursor': 'opaque000123'}))], state, args)
        previous = op.run()
        original_path, original_bytes = self.path, self.path.read_bytes()
        self.path = Path(self.temp.name) / 'page2.json'
        args = self.args('--query', 'workout routine', '--type', 'playlists', '--region', 'JP', '--seen', 'scope',
                         '--cursor', previous['pagination']['next_cursor'])
        state, _ = m.prepare(args, self.path)
        m.save(self.path, state)
        body = task('READY', 0, data=[])
        body['client_task_id'] = state['client_task_id']
        op, second = self.operation([(200, body)], state, args)
        result = op.run()
        self.assertNotEqual(result['client_task_id'], previous['client_task_id'])
        self.assertEqual(result['request_payload']['input'], {**previous['request_payload']['input'], 'cursor': 'opaque000123'})
        self.assertEqual(original_path.read_bytes(), original_bytes)
        self.assertEqual(len(first.calls), 1)
        self.assertEqual(len(second.calls), 1)


if __name__ == '__main__':
    unittest.main()
