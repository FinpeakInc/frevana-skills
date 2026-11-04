"""Offline protocol and recovery tests. No real HTTP/provider calls."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'agentweb.py'
SPEC = importlib.util.spec_from_file_location('agentweb_client', SCRIPT)
api = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = api
SPEC.loader.exec_module(api)
BASE = 'https://ai-factory.frevana.com/service/agentweb'
RID = '01234567-89ab-cdef-0123-456789abcdef'
OTHER = '11234567-89ab-cdef-0123-456789abcdef'


def response(body, status=200):
    return api.Response(status, api.encoded(body), body)


def envelope(status='BILLED', **extra):
    return dict(request_id=RID, status=status, execution_http_status=200,
                data={'domain': 'example.com/us', 'action': 'lookup',
                      'data': {'kind': 'json', 'value': {'billing': 'business field'}},
                      'outcome': 'partial'},
                billing={'status': status, 'credits': 0.6 if status == 'BILLED' else None}, **extra)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'operation.json'
        self.client = Mock()
        self.args = ['execute', '--domain', 'example.com/us', '--action', 'lookup',
                     '--params', '{"productId":"001","available":false,"offset":0}',
                     '--state-file', str(self.path)]
        self.client.request.return_value = response(envelope())

    def run_command(self, args=None):
        parsed = api.parser().parse_args(args or self.args)
        with contextlib.redirect_stderr(io.StringIO()):
            return api.operate(parsed, self.client, BASE, self.path if parsed.command != 'discover' else None)

    def saved(self):
        return api.decode(self.path.read_bytes())

    def test_discover_one_post_preserves_regional_key(self):
        self.client.request.return_value = response({'data': {'domain': 'example.com/us', 'actions': []}})
        result, code = self.run_command(['discover', '--domain', 'example.com/us'])
        self.assertEqual(code, 0)
        self.client.request.assert_called_once_with('POST', '/discover', {'domain': 'example.com/us'}, timeout=None)
        self.assertFalse(self.path.exists())
        self.assertEqual(result.body['data']['actions'], [])

    def test_execute_saves_identity_before_network_and_preserves_parameters(self):
        def send(*args, **kwargs):
            saved = self.saved()
            self.assertEqual(saved['phase'], 'submitted')
            self.assertEqual(args[3], saved['idempotency_key'])
            self.assertEqual(args[2], saved['body'])
            self.assertEqual(args[2]['params'], {'productId': '001', 'available': False, 'offset': 0})
            return response(envelope())
        self.client.request.side_effect = send
        result, code = self.run_command()
        self.assertEqual(code, 0)
        self.assertEqual(self.saved()['request_id'], RID)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(result.body['data']['data']['value']['billing'], 'business field')
        self.assertEqual(result.body['data']['outcome'], 'partial')

    def test_existing_execute_and_recover_use_get_only(self):
        self.run_command()
        key = self.saved()['idempotency_key']
        self.client.reset_mock()
        self.run_command()
        self.client.request.assert_called_once_with('GET', '/requests/' + RID, timeout=None)
        self.client.reset_mock()
        self.run_command(['recover', '--state-file', str(self.path)])
        self.client.request.assert_called_once_with('GET', '/requests/' + RID, timeout=None)
        self.assertEqual(self.saved()['idempotency_key'], key)

    def test_changed_arguments_do_not_mutate_state_or_call_http(self):
        self.run_command()
        original = self.path.read_bytes()
        self.client.reset_mock()
        for args in (self.args + ['--idempotency-key', 'different'],
                     [value if value != 'lookup' else 'changed' for value in self.args],
                     [value.replace('false', '0') for value in self.args]):
            with self.assertRaises(api.ClientError):
                self.run_command(args)
        self.assertEqual(self.path.read_bytes(), original)
        self.client.request.assert_not_called()

    def test_server_argument_conflict_does_not_relabel_another_operation(self):
        conflict = {'request_id': RID, 'message': 'Idempotency-Key was used for different arguments'}
        self.client.request.return_value = response(conflict, 409)
        with self.assertRaises(api.ClientError) as caught:
            self.run_command()
        self.assertEqual(caught.exception.response.body, conflict)
        self.assertTrue(self.saved()['protocol_error'])
        self.client.reset_mock()
        with self.assertRaises(api.ClientError):
            self.run_command()
        self.client.request.assert_not_called()

    def test_timeout_no_automatic_post_and_explicit_recover_keeps_key_body(self):
        self.client.request.side_effect = api.ClientError('timeout')
        with self.assertRaises(api.ClientError):
            self.run_command()
        first = self.saved()
        self.assertEqual(first['phase'], 'submitted')
        self.assertIsNone(first['request_id'])
        with self.assertRaises(api.ClientError):
            self.run_command()
        self.assertEqual(self.client.request.call_count, 1)
        self.client.request.side_effect = None
        self.run_command(['recover', '--state-file', str(self.path)])
        call = self.client.request.call_args.args
        self.assertEqual(call[:4], ('POST', '/execute', first['body'], first['idempotency_key']))
        self.assertEqual(self.saved()['request_id'], RID)

    def test_conflict_id_is_preserved_then_queried_without_replay(self):
        self.client.request.return_value = response({'request_id': RID, 'message': 'in progress'}, 409)
        _, code = self.run_command()
        self.assertEqual(code, 2)
        self.assertEqual(self.saved()['request_id'], RID)
        self.client.request.return_value = response(envelope())
        _, code = self.run_command()
        self.assertEqual(code, 0)
        self.assertEqual(self.client.request.call_args.args, ('GET', '/requests/' + RID))

    def test_identity_mismatch_retains_original_and_blocks_state_recovery(self):
        self.run_command()
        bad = envelope()
        bad['request_id'] = OTHER
        self.client.request.return_value = response(bad)
        with self.assertRaises(api.ClientError):
            self.run_command()
        self.assertEqual(self.saved()['request_id'], RID)
        self.assertTrue(self.saved()['protocol_error'])
        self.client.reset_mock()
        with self.assertRaises(api.ClientError):
            self.run_command(['recover', '--state-file', str(self.path)])
        self.client.request.assert_not_called()

    def test_invalid_or_different_origin_state_is_not_replaced(self):
        for raw in (b'{broken', b'{}', api.encoded({'version': 1, 'api_base': 'https://other.example'})):
            self.path.write_bytes(raw)
            with self.assertRaises(api.ClientError):
                self.run_command()
            self.assertEqual(self.path.read_bytes(), raw)
        self.client.request.assert_not_called()

    def test_header_key_wins_body_key_and_is_not_part_of_business_body(self):
        self.run_command(['execute', '--json', '{"domain":"example.com","action":"search","idempotency_key":"body"}',
                          '--idempotency-key', 'header', '--state-file', str(self.path)])
        self.assertEqual(self.saved()['idempotency_key'], 'header')
        self.assertNotIn('idempotency_key', self.saved()['body'])

    def test_wait_uses_get_until_settlement_and_stops_on_review(self):
        self.run_command()
        for terminal, expected in (('BILLED', 0), ('REVIEW', 4), ('REJECTED', 4)):
            self.client.reset_mock()
            pending = envelope('READY')
            pending['data'] = None
            self.client.request.side_effect = [response(pending), response(envelope(terminal))]
            with patch.object(api.time, 'sleep'):
                _, code = self.run_command(['wait', '--state-file', str(self.path)])
            self.assertEqual(code, expected)
            self.assertEqual(self.client.request.call_count, 2)
            self.assertTrue(all(call.args[0] == 'GET' for call in self.client.request.call_args_list))

    def test_wait_deadline_preserves_pending_record(self):
        self.run_command()
        self.client.request.return_value = response(envelope('DEBITING'))
        with patch.object(api.time, 'monotonic', side_effect=[100, 100, 102, 102]), patch.object(api.time, 'sleep'):
            _, code = self.run_command(['wait', '--state-file', str(self.path), '--wait-timeout', '1'])
        self.assertEqual(code, 3)
        self.assertEqual(self.saved()['request_id'], RID)
        self.assertEqual(self.saved()['last_response']['status'], 'DEBITING')

    def test_wait_stops_on_saved_auth_failure_without_post_or_more_polls(self):
        self.run_command()
        auth = envelope(error={'code': 'AUTH_REQUIRED', 'auth': {
            'provider': 'site_account', 'connect_url': 'https://www.agentweb.us/connect/site_account?state=sample'}})
        auth.update(execution_http_status=403, data=None)
        self.client.reset_mock()
        self.client.request.return_value = response(auth)
        _, code = self.run_command(['wait', '--state-file', str(self.path)])
        self.assertEqual(code, 4)
        self.assertEqual(self.client.request.call_count, 1)
        self.assertEqual(self.client.request.call_args.args, ('GET', '/requests/' + RID))
        self.assertEqual(self.saved()['request_id'], RID)

    def test_save_failure_after_submission_retains_original_identity(self):
        real_save = api.save_state
        count = 0

        def fail_last(path, state):
            nonlocal count
            count += 1
            if count == 3:
                raise api.ClientError('disk full')
            real_save(path, state)
        parsed = api.parser().parse_args(self.args)
        log = io.StringIO()
        with patch.object(api, 'save_state', side_effect=fail_last), contextlib.redirect_stderr(log):
            with self.assertRaises(api.ClientError):
                api.operate(parsed, self.client, BASE, self.path)
        self.assertIn(RID, log.getvalue())
        self.assertEqual(self.saved()['phase'], 'submitted')
        self.assertEqual(self.client.request.call_count, 1)


class ContractTests(unittest.TestCase):
    def test_authorization_notice_requires_explicit_target_auth_requirement(self):
        for body, status in (({'error': {'code': 'ACTION_NOT_PUBLIC'}}, 403),
                             ({'error': {'code': 'BILLING_ACCOUNT_RESTRICTED'}}, 403),
                             ({'error': {'code': 'AUTH_REQUIRED'}}, 401),
                             (envelope(), 200)):
            log = io.StringIO()
            with contextlib.redirect_stderr(log):
                api.authorization_note(response(body, status))
            self.assertEqual(log.getvalue(), '')

    def test_discovery_connection_requirement_does_not_invent_url(self):
        for metadata in ({'requires_login': True}, {'connect_providers': ['ikea_de_account']}):
            log = io.StringIO()
            body = {'data': {'domain': 'ikea.com/de/de', **metadata}}
            with contextlib.redirect_stderr(log):
                api.authorization_note(response(body), discovery=True)
            self.assertIn('Site authorization required', log.getvalue())
            self.assertIn('no usable connect_url', log.getvalue())
            self.assertNotIn('https://', log.getvalue())

    def test_auth_notice_does_not_offer_unsafe_or_credentialed_urls(self):
        for link in ('javascript:alert(1)', 'http://example.com/connect',
                     'https://name:secret@example.com/connect', 'https://example.com/\nconnect'):
            log = io.StringIO()
            body = {'error': {'code': 'AUTH_REQUIRED', 'auth': {'connect_url': link}}}
            with contextlib.redirect_stderr(log):
                api.authorization_note(response(body, 403))
            self.assertIn('no usable connect_url', log.getvalue())
            self.assertNotIn(link, log.getvalue())

    def test_cli_shows_exact_authorization_url_and_keeps_response_without_retries(self):
        with tempfile.TemporaryDirectory() as directory:
            path, out = Path(directory) / 'state.json', Path(directory) / 'result.json'
            link = 'https://www.agentweb.us/connect/site_account?state=ab%2FCD&region=de'
            body = {'error': {'code': 'AUTH_REQUIRED', 'message': 'Connect site account',
                              'auth': {'provider': 'site_account', 'connect_url': link}}}
            reply = response(body, 403)
            stdout, log = io.TextIOWrapper(io.BytesIO(), encoding='utf-8'), io.StringIO()
            with patch.dict(api.os.environ, {'FREVANA_TOKEN': 'private'}, clear=True), \
                    patch.object(api.Client, 'request', return_value=reply) as send, \
                    contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(log):
                code = api.main(['execute', '--domain', 'example.com', '--action', 'lookup',
                                 '--state-file', str(path), '--output', str(out)])
            self.assertEqual(code, 2)
            self.assertEqual(send.call_count, 1)
            self.assertEqual(send.call_args.args[0], 'POST')
            self.assertIn(link, log.getvalue())
            self.assertIn('Wait for the user', log.getvalue())
            self.assertEqual(out.read_bytes(), reply.raw)
            self.assertEqual(api.decode(path.read_bytes())['last_response'], body)

    def test_invalid_inputs_are_rejected(self):
        invalid = [[], {}, {'domain': ' '}, {'domain': 'x', 'action': ' '},
                   {'domain': 'x', 'action': 'a', 'auth_id': 'fake'},
                   {'domain': 'x', 'action': 'a', 'params': None},
                   {'domain': 'x', 'action': 'a', 'params': []},
                   {'domain': 'x', 'action': 'a', 'params': {'x': None}},
                   {'domain': 'x', 'action': 'a', 'params': {'x': []}},
                   {'domain': 'x', 'action': 'a', 'params': {'x': {'nested': 1}}},
                   {'domain': 'x', 'action': 'a', 'params': {'x': float('inf')}},
                   {'domain': 'x', 'action': 'a', 'params': {'x': 10 ** 1000}},
                   {'domain': 'x', 'action': 'a', 'idempotency_key': 'bad/key'},
                   {'domain': 'x', 'action': 'a' * 161},
                   {'domain': 'x', 'action': '😀' * 81}]
        for body in invalid:
            with self.subTest(body=str(body)[:100]), self.assertRaises(api.ClientError):
                api.validate_body(body, 'execute')

    def test_bad_json_and_bases(self):
        for value in ('{"x":NaN}', '{"x":1,"x":2}', '{broken'):
            with self.assertRaises(api.ClientError):
                api.json_arg(value)
        for base in ('http://example.com', 'https://user:pass@example.com',
                     'https://example.com?key=x', 'https://example.com/other',
                     'https://example.com/#fragment'):
            with self.assertRaises(api.ClientError):
                api.api_base(base)
        self.assertEqual(api.api_base('https://ai-factory.frevana.com'), BASE)
        self.assertEqual(api.api_base(BASE + '/'), BASE)
        self.assertEqual(api.api_base('http://localhost:8000'), 'http://localhost:8000' + api.ROOT)

    def test_billed_business_error_is_not_success(self):
        failed = envelope(error={'code': 'PARAM_UNRESOLVED', 'resolve': {'candidates': ['a', 'b']}})
        failed.update(execution_http_status=422, data=None)
        self.assertEqual(api.outcome(response(failed)), 4)
        self.assertEqual(api.outcome(response(failed, 422)), 4)
        self.assertEqual(failed['billing']['credits'], 0.6)

    def test_pending_zero_cost_and_malformed_envelopes(self):
        for status in api.PENDING:
            self.assertEqual(api.outcome(response(envelope(status))), 3)
        zero = envelope()
        zero['billing']['credits'] = 0
        self.assertEqual(api.outcome(response(zero)), 0)
        for bad in (None, [], {}, dict(envelope(), status='UNKNOWN'),
                    dict(envelope(), billing={'status': 'READY', 'credits': None})):
            with self.assertRaises(api.ClientError):
                api.outcome(response(bad))
        self.assertEqual(api.outcome(response({'message': 'unavailable'}, 503)), 2)

    def test_auth_transport_routes_and_redirect_refusal(self):
        client = api.Client(BASE, 'private')
        received = Mock()
        received.code = 200
        received.read.return_value = b'{"data":{"domain":"example.com"}}'
        received.__enter__ = Mock(return_value=received)
        received.__exit__ = Mock(return_value=None)
        client.opener = Mock()
        client.opener.open.return_value = received
        raw = client.request('POST', '/discover', {'domain': 'example.com'}, 'key')
        request = client.opener.open.call_args.args[0]
        self.assertEqual(request.full_url, BASE + '/discover')
        self.assertEqual(request.get_header('Authorization'), 'Bearer private')
        self.assertIsNone(request.get_header('X-api-key'))
        self.assertEqual(request.get_header('Idempotency-key'), 'key')
        self.assertEqual(raw.raw, received.read.return_value)
        self.assertIsNone(api.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.example'))

    def test_missing_token_stops_without_using_other_credentials(self):
        with patch.dict(api.os.environ, {'FREVANA_API_KEY': 'unused'}, clear=True), \
                patch.object(api.Client, 'request') as send, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(api.main(['discover', '--domain', 'example.com']), 2)
        send.assert_not_called()

    def test_cli_keeps_http_error_bytes_and_private_state_without_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            out = Path(directory) / 'result.json'
            native = b'{ "request_id": "' + RID.encode() + b'", "error": {"code":"RATE_LIMITED"} }\n'
            reply = api.Response(429, native, api.decode(native))
            stdout = io.TextIOWrapper(io.BytesIO(), encoding='utf-8')
            with patch.dict(api.os.environ, {'FREVANA_TOKEN': 'super-private'}, clear=True), \
                    patch.object(api.Client, 'request', return_value=reply), \
                    contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
                code = api.main(['execute', '--domain', 'example.com', '--action', 'lookup',
                                 '--state-file', str(path), '--output', str(out)])
            self.assertEqual(code, 2)
            self.assertEqual(out.read_bytes(), native)
            self.assertNotIn('super-private', path.read_text())
            self.assertEqual(api.decode(path.read_bytes())['request_id'], RID)

    def test_cli_keeps_received_bytes_when_state_persistence_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path, out = Path(directory) / 'state.json', Path(directory) / 'result.json'
            real_save = api.save_state
            count = 0

            def save(path, state):
                nonlocal count
                count += 1
                if count == 3:
                    raise api.ClientError('disk full')
                real_save(path, state)
            reply = response(envelope())
            stdout = io.TextIOWrapper(io.BytesIO(), encoding='utf-8')
            with patch.dict(api.os.environ, {'FREVANA_TOKEN': 'private'}, clear=True), \
                    patch.object(api.Client, 'request', return_value=reply), \
                    patch.object(api, 'save_state', side_effect=save), \
                    contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
                code = api.main(['execute', '--domain', 'example.com', '--action', 'lookup',
                                 '--state-file', str(path), '--output', str(out)])
            self.assertEqual(code, 2)
            self.assertEqual(out.read_bytes(), reply.raw)
            self.assertEqual(api.decode(path.read_bytes())['phase'], 'submitted')


if __name__ == '__main__':
    unittest.main()
