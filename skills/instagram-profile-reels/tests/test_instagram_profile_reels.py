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

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'instagram_profile_reels.py'
spec = importlib.util.spec_from_file_location('instagram_profile_reels', SCRIPT)
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
        args = self.args('--handle', 'instagram', '--client-task-id', 'test-operation', *extra)
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
        data = {'author': {'handle': 'instagram'}, 'unknown_field': ['preserved']}
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
        args = self.args('--handle', 'instagram')
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
        invalid = ({}, {'handle': 'instagram', 'limit': 1}, {'handle': 'instagram', 'count': 1},
                   {'handle': 'instagram', 'published_before': '2026-01-01'}, {'handle': 'instagram', 'fit': 'other'},
                   {'handle': 'instagram', 'trim': 1}, {'handle': 'instagram', 'contact_email': 1},
                   {'handle': 'instagram', 'async': 1.0}, {'handle': 'instagram', 'async': 'yes'},
                   {'handle': '   '}, {'handle': None})
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(m.Invalid):
                m.validate_input(value)

    def test_all_async_schema_values_preserve_types(self):
        for value in (True, False, 1, 0, 'true', 'false', '1', '0'):
            result = m.validate_input({'handle': 'instagram', 'async': value})
            self.assertIs(type(result['async']), type(value))

    def test_exact_payload_no_undeclared_defaults(self):
        state, _ = self.state('--trim', 'false', '--async', '0', '--label-evidence', '1')
        payload = state['request_payload']
        self.assertEqual(payload['input'], {'handle': 'instagram', 'trim': False, 'async': 0, 'label_evidence': '1'})
        self.assertEqual(set(payload), {'endpoint_id', 'client_task_id', 'input', 'response_mode'})
        self.assertEqual(payload['response_mode'], 'json')

    def test_changed_input_or_client_id_or_origin_rejected(self):
        self.state()
        for flags in (('--handle', 'other'), ('--client-task-id', 'other'), ('--api-base-url', 'https://other.example')):
            with self.subTest(flags=flags), self.assertRaises(m.Invalid):
                m.prepare(self.args(*flags), self.path)

    def test_no_new_operation_on_resume_without_state(self):
        args = m.parser().parse_args(['resume', '--state-file', str(self.path)])
        with self.assertRaises(m.Invalid):
            m.prepare(args, self.path)

    def test_input_file_rejects_extras_and_flag_mix(self):
        input_path = Path(self.temp.name) / 'input.json'
        input_path.write_text(json.dumps({'handle': 'instagram', 'limit': 10}))
        with self.assertRaises(m.Invalid):
            m.prepare(self.args('--input-file', str(input_path)), self.path)
        input_path.write_text(json.dumps({'handle': 'instagram'}))
        with self.assertRaises(m.Invalid):
            m.prepare(self.args('--input-file', str(input_path), '--handle', 'instagram'), self.path)

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
        self.assertEqual(observed[0][2]['input'], {'handle': 'instagram'})
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
                self.assertEqual(m.main(['run', '--handle', 'instagram', '--state-file', str(self.path)]), 2)
            network.assert_not_called()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            m.parser().parse_args(['run', '--state-file', str(self.path), '--limit', '10'])

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
                    code, result = self.invoke('--handle', 'instagram')
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
            code, _ = self.invoke('--handle', 'instagram')
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






    def test_schema_composition_accepts_handle_user_id_or_both(self):
        for identity in ({'handle': 'mrbeast'}, {'user_id': '00012345678901234567890'},
                         {'handle': 'mrbeast', 'user_id': '00012345678901234567890'}):
            with self.subTest(identity=identity):
                self.assertEqual(m.validate_input(identity), identity)
                self.assertTrue(m.required_fields_match(identity, m.INPUT_SCHEMA))
        self.assertFalse(m.required_fields_match({}, m.INPUT_SCHEMA))
        self.assertEqual(m.INPUT_SCHEMA['required'], [])
        self.assertIn('allOf', m.INPUT_SCHEMA)

    def test_missing_identifiers_stops_before_id_creation_and_network(self):
        for flags in ([], ['--trim', 'true'], ['--sort', 'most_viewed'], ['--dry-run', '1']):
            with self.subTest(flags=flags), patch.object(m.Client, 'request') as network, patch.object(m.uuid, 'uuid4') as generate:
                code, result = self.invoke(*flags)
                self.assertEqual(code, 2)
                self.assertEqual(result['error_source'], 'client')
                self.assertFalse(self.path.exists())
                network.assert_not_called()
                generate.assert_not_called()

    def test_user_id_only_does_not_resolve_or_add_handle(self):
        user_id = '00012345678901234567890'
        with patch.object(m.Client, 'request', return_value=(200, task('READY', 0, data={'items': []}))) as network:
            code, result = self.invoke('--user-id', user_id, '--client-task-id', 'test-operation')
        self.assertEqual(code, 0)
        self.assertEqual(result['request_payload']['input'], {'user_id': user_id})
        self.assertIs(type(result['request_payload']['input']['user_id']), str)
        self.assertEqual(network.call_count, 1)
        self.assertEqual(network.call_args.args[0], 'POST')

    def test_invalid_identifier_values_are_not_ignored(self):
        invalid = ({'handle': ''}, {'handle': '   '}, {'handle': '@mrbeast'}, {'handle': 123},
                   {'user_id': ''}, {'user_id': '  '}, {'user_id': 12345678901234567890},
                   {'handle': 'mrbeast', 'user_id': None}, {'user_id': '123', 'handle': ''})
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(m.Invalid):
                m.validate_input(values)

    def test_all_25_schema_fields_supported_without_extra_defaults(self):
        values = {'handle': 'mrbeast', 'user_id': '00012345678901234567890', 'fit': 'goal',
                  'goal': 'Find useful beginner examples', 'trim': False, 'async': '1',
                  'brand': 'Example product', 'label': 'mention,intent,quality,ai_style,ai_written,injection',
                  'offer': 'A learning guide.', 'since': '2026-09-01', 'until': '2026-10-31T12:00:00Z',
                  'cursor': 'opaque+/%2F=', 'dry_run': '1', 'exclude': 'engagement_bait,ai_style',
                  'include': 'audio,stats', 'judgments': 'on', 'fit_tokens': 1000, 'stop_at_id': 'known-reel',
                  'recent_days': 7, 'exclude_pinned': True, 'label_evidence': '1',
                  'brand_description': 'A fictional product.', 'ai_written_threshold': '0.71'}
        input_path = Path(self.temp.name) / 'input.json'
        input_path.write_text(json.dumps(values))
        state, _ = m.prepare(self.args('--input-file', str(input_path)), self.path)
        self.assertEqual(state['request_payload']['input'], values)
        self.assertEqual(state['request_payload']['endpoint_id'], 'instagram/profile/reels')
        self.assertEqual(set(values) | {'sort', 'max_id'}, set(m.INPUT_SCHEMA['properties']))
        self.assertEqual(len(m.INPUT_SCHEMA['properties']), 25)
        self.assertEqual(m.validate_input({'user_id': '123', 'max_id': 'native'})['max_id'], 'native')
        self.assertEqual(m.validate_input({'handle': 'mrbeast', 'sort': 'most_viewed'})['sort'], 'most_viewed')

    def test_default_request_is_one_page_without_modes_or_enrichment(self):
        state, args = self.state()
        data = {'items': [{'post': {'id': 'reel-1'}}], '_warnings': ['keep warning'],
                'labels': {'status': 'partial', 'pending': ['reel-1']}}
        pagination = {'next_cursor': 'opaque+', 'stopped_at': None}
        op, client = self.operation([(200, task('READY', 0, data=data, pagination=pagination))], state, args)
        result = op.run()
        self.assertEqual(result['data'], data)
        self.assertEqual(result['pagination'], pagination)
        self.assertEqual(json.loads(client.calls[0][2])['input'], {'handle': 'instagram'})
        self.assertEqual([call[0] for call in client.calls], ['POST'])

    def test_popular_sort_rejects_exact_documented_incompatible_fields(self):
        invalid = ({'include': 'stats'}, {'include': 'audio'}, {'include': ''},
                   {'trim': True}, {'trim': False}, {'recent_days': 7},
                   {'since': '2026-09-01'}, {'stop_at_id': 'known-reel'})
        for options in invalid:
            with self.subTest(options=options), self.assertRaises(m.Invalid):
                m.validate_input({'handle': 'mrbeast', 'sort': 'most_viewed', **options})
        # until and exclude_pinned are not in the documented incompatibility list.
        allowed = {'user_id': '123', 'sort': 'most_viewed', 'until': '2026-10-31', 'exclude_pinned': True}
        self.assertEqual(m.validate_input(allowed), allowed)

    def test_incompatible_popular_sort_never_submits(self):
        with patch.object(m.Client, 'request') as network, patch.object(m.uuid, 'uuid4') as generate:
            code, _ = self.invoke('--handle', 'mrbeast', '--sort', 'most_viewed', '--trim', 'false')
        self.assertEqual(code, 2)
        network.assert_not_called()
        generate.assert_not_called()
        self.assertFalse(self.path.exists())

    def test_cursor_and_native_max_id_are_mutually_exclusive(self):
        with self.assertRaises(m.Invalid):
            m.validate_input({'handle': 'mrbeast', 'cursor': 'opaque', 'max_id': 'native'})
        with self.assertRaises(m.Invalid):
            m.validate_input({'handle': 'mrbeast', 'max_id': 123})

    def test_next_page_preserves_popular_sort_and_opaque_cursor(self):
        state, _ = self.state('--sort', 'most_viewed')
        before = self.path.read_bytes()
        cursor = 'popular+/%2F=[]'
        with self.assertRaises(m.StateError):
            m.prepare(self.args('--cursor', cursor), self.path)
        self.assertEqual(self.path.read_bytes(), before)
        next_path = Path(self.temp.name) / 'page2.task.json'
        args = m.parser().parse_args(['run', '--state-file', str(next_path), '--handle', 'instagram',
                                      '--sort', 'most_viewed', '--cursor', cursor])
        next_state, _ = m.prepare(args, next_path)
        self.assertNotEqual(next_state['client_task_id'], state['client_task_id'])
        self.assertEqual(next_state['request_payload']['input'],
                         {'handle': 'instagram', 'sort': 'most_viewed', 'cursor': cursor})

    def test_new_page_preserves_explicit_stats_audio_mode(self):
        cursor = 'stats+cursor/=[]'
        next_path = Path(self.temp.name) / 'stats-page2.task.json'
        args = m.parser().parse_args(['run', '--state-file', str(next_path), '--user-id', '000123',
                                      '--include', 'audio,stats', '--cursor', cursor])
        state, _ = m.prepare(args, next_path)
        self.assertEqual(state['request_payload']['input'],
                         {'user_id': '000123', 'include': 'audio,stats', 'cursor': cursor})

    def test_stats_or_sort_cannot_be_changed_on_a_persisted_operation(self):
        state, _ = self.state('--include', 'stats', '--cursor', 'stats-cursor')
        before = self.path.read_bytes()
        for flags in (('--include', 'audio,stats'), ('--include', ''), ('--sort', 'most_viewed')):
            with self.subTest(flags=flags), self.assertRaises(m.StateError):
                m.prepare(self.args(*flags), self.path)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(state['request_payload']['input']['include'], 'stats')

    def test_explicit_stats_and_audio_preserve_native_fields_without_media_fetch(self):
        for include in ('stats', 'audio', 'audio,stats'):
            with self.subTest(include=include):
                self.path.unlink(missing_ok=True)
                state, args = self.state('--include', include)
                data = {'items': [{'post': {'engagement': {'shares': 3, 'saves': 4},
                                           'ext': {'repost_count': 2, 'music_id': 'music-1',
                                                   'audio_cluster_id': 'cluster-1', 'music': {'name': 'sound'}}}}]}
                op, client = self.operation([(200, task('READY', 0, data=data))], state, args)
                self.assertEqual(op.run()['data'], data)
                self.assertEqual(json.loads(client.calls[0][2])['input'], {'handle': 'instagram', 'include': include})
                self.assertEqual(len(client.calls), 1)

    def test_trimmed_unknown_pin_rows_and_omissions_are_preserved(self):
        state, args = self.state('--trim', 'true', '--exclude-pinned', 'true')
        data = {'items': [{'post': {'id': 'reel-1', 'content': {'caption': 'native text',
                       'thumbnail_url': 'https://images.example/cover.jpg'}, 'engagement': {'views': 10}}}],
                '_warnings': ['TEST_UNKNOWN_PIN_STATE']}
        op, client = self.operation([(200, task('READY', 0, data=data))], state, args)
        result = op.run()
        self.assertEqual(result['data'], data)
        post = result['data']['items'][0]['post']
        self.assertNotIn('media_urls', post['content'])
        self.assertNotIn('duration_seconds', post['content'])
        self.assertNotIn('flags', post)
        self.assertEqual(len(client.calls), 1)

    def test_stopping_metadata_and_absent_cursor_do_not_trigger_more_pages(self):
        for reason in ('since', 'known_id', 'end'):
            with self.subTest(reason=reason):
                self.path.unlink(missing_ok=True)
                state, args = self.state()
                pagination = {'stopped_at': reason}
                op, client = self.operation([(200, task('READY', 0, data={'items': []}, pagination=pagination))], state, args)
                result = op.run()
                self.assertEqual(result['pagination'], pagination)
                self.assertEqual(result['data'], {'items': []})
                self.assertEqual(len(client.calls), 1)

    def test_until_aliases_normalize_before_request_persistence(self):
        for option in ('--until', '--published-before', '--end-date', '--to-date'):
            with self.subTest(option=option):
                state, _ = m.prepare(self.args('--user-id', '000123', option, '2026-10-31'), self.path)
                self.assertEqual(state['request_payload']['input'], {'user_id': '000123', 'until': '2026-10-31'})
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.args('--handle', 'mrbeast', '--until', '2026-10-31', '--end-date', '2026-10-30')
        self.assertFalse(self.path.exists())

    def test_reel_specific_types_bounds_enums_and_unknown_fields(self):
        invalid = ({'recent_days': 0}, {'recent_days': 3651}, {'recent_days': True}, {'fit_tokens': False},
                   {'trim': 1}, {'exclude_pinned': 1}, {'sort': 'latest'}, {'judgments': 'auto'},
                   {'fit': 'all'}, {'dry_run': 1}, {'label_evidence': 1}, {'ai_written_threshold': .95},
                   {'limit': 10}, {'page': 1}, {'next_max_id': 'wrong'}, {'query': 'fitness'},
                   {'region': 'US'}, {'min_views': 1000}, {'download_media': True})
        for options in invalid:
            with self.subTest(options=options), self.assertRaises(m.Invalid):
                m.validate_input({'handle': 'mrbeast', **options})
        for days in (1, 3650):
            self.assertEqual(m.validate_input({'user_id': '123', 'recent_days': days})['recent_days'], days)

    def test_retry_retains_identifier_cursor_modes_and_relative_date(self):
        state, args = self.state('--recent-days', '7', '--include', 'audio,stats', '--cursor', 'stats-cursor')
        op, client = self.operation([m.TransportError(), (200, task('READY', 0, data={'items': []}))], state, args)
        with patch.object(op, 'pause'):
            self.assertEqual(op.run()['outcome'], 'completed')
        self.assertEqual(client.calls[0][2], client.calls[1][2])
        self.assertEqual(json.loads(client.calls[1][2])['input'],
                         {'handle': 'instagram', 'recent_days': 7, 'include': 'audio,stats', 'cursor': 'stats-cursor'})
        self.assertNotIn('since', json.loads(client.calls[1][2])['input'])

    def test_preview_and_goal_fitting_do_not_trigger_paid_followup_or_recall(self):
        state, args = self.state('--fit', 'goal', '--goal', 'Find useful examples', '--fit-tokens', '1000',
                                 '--dry-run', '1', '--label', 'quality')
        data = {'estimate': {'rows_expected': 25}, 'held_back': {'ids': ['one'], 'recall_id': 'keep'}}
        op, client = self.operation([(200, task('READY', 0, data=data))], state, args)
        self.assertEqual(op.run()['data'], data)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(json.loads(client.calls[0][2])['input'], state['request_payload']['input'])

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
            code, result = self.invoke('--handle', 'instagram')
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
            code, result = self.invoke('--handle', 'instagram')
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




if __name__ == '__main__':
    unittest.main()
