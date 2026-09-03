#!/usr/bin/env python3
"""Offline contract tests: mocked HTTP only, no cloud requests or credential files."""
import contextlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import supabase_api as api
import supabase_auth as auth
import supabase_project as project
import supabase_db as db
import supabase_resources as resources
from supabase_cli_policy import validate_cli


class APIContracts(unittest.TestCase):
    ref = 'abcdefghijklmnopqrst'
    token = 'fake-test-pat'

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='supabase-api-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.opener = Mock()
        self.addCleanup(patch.stopall)
        self.factory = patch.object(api, 'build_opener', return_value=self.opener).start()
        patch.dict(os.environ, {'SUPABASE_ACCESS_TOKEN': self.token,
                                'SUPABASE_API_URL': 'https://untrusted.example',
                                'SUPABASE_DB_PASSWORD': 'fake-db-secret'}).start()
        for module in (project, db, resources):
            patch.object(module, 'prepare', side_effect=AssertionError('API must not install/invoke CLI')).start()
        self.stdout = io.StringIO()

    def response(self, body, status=200):
        stream = io.BytesIO(json.dumps(body).encode())
        stream.status = status
        return stream

    def queue(self, *bodies):
        self.opener.open.side_effect = [body if isinstance(body, Exception) else self.response(body) for body in bodies]

    def file(self, name, body):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body if isinstance(body, str) else json.dumps(body))
        return str(path)

    def run_script(self, module, *args):
        self.stdout = io.StringIO()
        with contextlib.redirect_stdout(self.stdout):
            code = module.main([args[0], '--workdir', str(self.root), *args[1:]])
        return code

    def requests(self):
        return [(call.args[0].get_method(), call.args[0].full_url,
                 json.loads(call.args[0].data) if call.args[0].data else None)
                for call in self.opener.open.call_args_list]

    def output(self):
        return json.loads(self.stdout.getvalue())

    def target(self, name='demo', **fields):
        return dict(ref=self.ref, name=name, status='ACTIVE_HEALTHY', **fields)

    def test_auth_direct_ref_does_not_require_project_enumeration(self):
        self.queue(self.target())
        self.assertEqual(self.run_script(auth, 'verify', '--project-ref', self.ref), 0)
        self.assertEqual(len(self.requests()), 1)
        self.assertTrue(self.requests()[0][1].endswith('/projects/' + self.ref))
        request = self.opener.open.call_args.args[0]
        self.assertEqual(request.get_header('User-agent'), api.USER_AGENT)
        self.assertEqual(self.output()['scope'], 'project-read')
        self.assertNotIn(self.token, self.stdout.getvalue())

    def test_auth_list_and_error_never_login_or_retry(self):
        self.queue([])
        self.run_script(auth, 'verify')
        self.assertEqual(self.output()['status'], 'verified')
        self.opener.reset_mock()
        self.queue(HTTPError('https://example/' + self.token, 403, self.token, {}, io.BytesIO(b'provider-secret')))
        with self.assertRaises(api.APIError) as error:
            self.run_script(auth, 'verify')
        self.assertNotIn(self.token, str(error.exception))
        self.assertEqual(len(self.requests()), 1)

    def test_query_default_enforces_read_only_and_preserves_parameters(self):
        sql = self.file('query.sql', 'select * from public.items where id = $1')
        params = self.file('params.json', ["x'; delete from items; --"])
        rows = [{'id': 'x', 'name': '商品'}]
        self.queue(rows)
        self.run_script(db, 'query', '--project-ref', self.ref, '--file', sql, '--parameters-file', params)
        method, url, body = self.requests()[0]
        self.assertEqual(method, 'POST')
        self.assertEqual(url, 'https://api.supabase.com/v1/projects/' + self.ref + '/database/query')
        self.assertTrue(body['read_only'])
        self.assertEqual(body['parameters'], ["x'; delete from items; --"])
        self.assertEqual(self.output(), rows)
        self.assertEqual(len(self.requests()), 1)

    def test_query_write_has_no_automatic_api_or_cli_replay(self):
        sql = self.file('write.sql', 'update public.items set name = $1 returning id')
        self.queue(URLError('credential-bearing provider text'))
        with self.assertRaisesRegex(api.APIError, 'Write may have applied'):
            self.run_script(db, 'query', '--project-ref', self.ref, '--file', sql, '--write')
        self.assertFalse(self.requests()[0][2]['read_only'])
        self.assertEqual(len(self.requests()), 1)
        self.assertEqual(self.stdout.getvalue(), '')

    def test_query_dry_run_never_submits_sql(self):
        sql = self.file('danger.sql', 'drop table public.items;')
        self.run_script(db, 'query', '--project-ref', self.ref, '--file', sql, '--write', '--dry-run')
        self.opener.open.assert_not_called()
        self.assertEqual(self.output()['status'], 'preview')
        self.assertNotIn('drop table', self.stdout.getvalue())

    def test_invalid_sql_inputs_and_target_fail_before_connection(self):
        sql = self.file('empty.sql', '')
        params = self.file('params.json', {'not': 'an array'})
        for extra in [('--file', sql), ('--file', self.file('ok.sql', 'select 1'), '--parameters-file', params),
                      ('--file', self.file('ok.sql', 'select 1'), '--profile', 'another-account')]:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.run_script(db, 'query', '--project-ref', self.ref, *extra)
        self.opener.open.assert_not_called()

    def test_tables_binds_schema_and_avoids_deprecated_metadata(self):
        self.queue([])
        self.run_script(db, 'tables', '--project-ref', self.ref, '--schema', 'strange"schema')
        body = self.requests()[0][2]
        self.assertEqual(body['parameters'], ['strange"schema'])
        self.assertNotIn('strange', body['query'])
        self.assertTrue(body['read_only'])

    def test_types_writes_private_source_and_keeps_old_file_on_bad_response(self):
        target = self.file('types/db.ts', 'old source')
        self.queue({'types': 'export type Database = {}\n'})
        self.run_script(db, 'types', '--project-ref', self.ref, '--schema', 'public,custom', '--output', target)
        self.assertEqual(Path(target).read_text(), 'export type Database = {}\n')
        self.assertEqual(stat.S_IMODE(Path(target).stat().st_mode), 0o600)
        self.assertIn('included_schemas=public%2Ccustom', self.requests()[0][1])
        self.queue({'unexpected': 'response'})
        with self.assertRaises(api.APIError):
            self.run_script(db, 'types', '--project-ref', self.ref, '--output', target)
        self.assertEqual(Path(target).read_text(), 'export type Database = {}\n')
        self.assertEqual(list(Path(target).parent.glob('.supabase-*')), [])

    def test_output_symlink_fails_before_any_http(self):
        target = Path(self.file('keep.json', 'keep'))
        link = self.root / 'link.json'
        link.symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.run_script(project, 'list', '--output', str(link))
        self.opener.open.assert_not_called()
        self.assertEqual(target.read_text(), 'keep')

    def test_create_uses_password_environment_and_returns_pending(self):
        config = self.file('create.json', {'region': 'us-east-1'})
        self.queue({'ref': self.ref}, self.target())
        self.run_script(project, 'create', '--name', 'new', '--organization-slug', 'org', '--config-file', config)
        self.assertEqual(self.requests()[0][2], {'name': 'new', 'organization_slug': 'org',
                                               'region': 'us-east-1', 'db_pass': 'fake-db-secret'})
        self.assertEqual(self.output()['status'], 'accepted')
        self.assertFalse(self.output()['verified'])
        self.assertNotIn('fake-db-secret', self.stdout.getvalue())
        self.assertEqual([r[0] for r in self.requests()], ['POST', 'GET'])

    def test_create_preview_and_unsupported_config_cannot_provision(self):
        config = self.file('create.json', {'region': 'us-east-1'})
        with patch.dict(os.environ, {'SUPABASE_DB_PASSWORD': ''}):
            self.run_script(project, 'create', '--name', 'new', '--organization-slug', 'org', '--config-file', config, '--dry-run')
        self.opener.open.assert_not_called()
        config = self.file('bad.json', {'region': 'us-east-1', 'template_url': 'https://example.invalid'})
        with self.assertRaises(ValueError):
            self.run_script(project, 'create', '--name', 'new', '--organization-slug', 'org', '--config-file', config)
        self.opener.open.assert_not_called()

    def test_delete_requires_exact_confirmation_and_only_404_proves_absence(self):
        with self.assertRaises(ValueError):
            self.run_script(project, 'delete', '--project-ref', self.ref, '--confirm-project-ref', 'wrong')
        self.opener.open.assert_not_called()
        self.queue(self.target(), {}, HTTPError('https://example', 404, 'gone', {}, None))
        self.run_script(project, 'delete', '--project-ref', self.ref, '--confirm-project-ref', self.ref)
        self.assertEqual(self.output()['status'], 'deleted')
        self.assertTrue(self.output()['verified'])

    def test_delete_readback_forbidden_is_not_absence(self):
        self.queue(self.target(), {}, HTTPError('https://example', 403, 'forbidden', {}, None))
        with self.assertRaisesRegex(api.APIError, 'readback failed'):
            self.run_script(project, 'delete', '--project-ref', self.ref, '--confirm-project-ref', self.ref)
        self.assertEqual([r[0] for r in self.requests()], ['GET', 'DELETE', 'GET'])
        self.assertEqual(self.stdout.getvalue(), '')

    def test_project_lifecycle_reports_observation_not_completion(self):
        for action in ('pause', 'restore', 'restart'):
            with self.subTest(action=action):
                self.opener.reset_mock()
                self.queue(self.target(), {}, self.target())
                self.run_script(project, action, '--project-ref', self.ref)
                self.assertEqual(self.output()['status'], 'accepted')
                self.assertFalse(self.output()['verified'])
                self.assertTrue(self.requests()[1][1].endswith('/' + action))

    def test_standalone_migration_does_not_duplicate_repository_workflow(self):
        sql = self.file('schema.sql', 'create table items (id int)')
        self.file('supabase/migrations/001.sql', 'select 1')
        with self.assertRaisesRegex(ValueError, 'repository migrations'):
            self.run_script(db, 'migration-apply', '--project-ref', self.ref, '--name', 'items', '--file', sql)
        self.opener.open.assert_not_called()

    def test_migration_submits_once_and_reads_history_without_claiming_schema_verified(self):
        sql = self.file('schema.sql', 'create table items (id int)')
        undo = self.file('undo.sql', 'drop table items')
        self.queue({}, [{'version': '123', 'name': 'items'}])
        self.run_script(db, 'migration-apply', '--project-ref', self.ref, '--name', 'items',
                        '--file', sql, '--rollback-file', undo, '--partner-api-access')
        self.assertEqual([r[0] for r in self.requests()], ['POST', 'GET'])
        self.assertEqual(self.requests()[0][2]['rollback'], 'drop table items')
        self.assertFalse(self.output()['verified'])

    def test_migration_requires_confirmed_partner_access_before_connection(self):
        sql = self.file('schema.sql', 'create table items (id int)')
        with self.assertRaisesRegex(ValueError, 'selected partner OAuth apps'):
            self.run_script(db, 'migration-apply', '--project-ref', self.ref,
                            '--name', 'items', '--file', sql)
        self.factory.assert_not_called()

    def test_pitr_rejects_milliseconds_and_requires_exact_target(self):
        for extra in [('--timestamp', '1700000000000', '--confirm-project-ref', self.ref),
                      ('--timestamp', '1700000000')]:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.run_script(db, 'restore-pitr', '--project-ref', self.ref, *extra)
        self.opener.open.assert_not_called()
        self.queue(self.target(), {}, self.target())
        self.run_script(db, 'restore-pitr', '--project-ref', self.ref, '--timestamp', '1700000000', '--confirm-project-ref', self.ref)
        self.assertEqual(self.requests()[1][2], {'recovery_time_target_unix': 1700000000})
        self.assertEqual(self.output()['status'], 'accepted')
        self.assertFalse(self.output()['verified'])

    def test_function_delete_verifies_slug_absence(self):
        self.queue({'slug': 'hello'}, {}, [{'slug': 'other'}])
        self.run_script(resources, 'functions', 'delete', '--project-ref', self.ref, '--slug', 'hello')
        self.assertEqual(self.output()['status'], 'deleted')
        self.assertTrue(self.output()['verified'])
        self.assertTrue(self.requests()[1][1].endswith('/functions/hello'))

    def test_secret_list_never_emits_values_even_if_provider_returns_them(self):
        self.queue([{'name': 'SECRET', 'value': 'do-not-print'}])
        self.run_script(resources, 'secrets', 'list', '--project-ref', self.ref)
        self.assertEqual(self.output(), [{'name': 'SECRET'}])
        self.assertNotIn('do-not-print', self.stdout.getvalue())

    def test_secret_set_only_claims_name_verification(self):
        body = self.file('secrets.json', [{'name': 'SECRET', 'value': 'do-not-print'}])
        self.queue([], {}, [{'name': 'SECRET', 'value': 'masked'}])
        self.run_script(resources, 'secrets', 'set', '--project-ref', self.ref, '--body-file', body)
        self.assertTrue(self.output()['names_verified'])
        self.assertFalse(self.output()['verified'])
        self.assertNotIn('do-not-print', self.stdout.getvalue())
        self.assertEqual(self.requests()[1][2], [{'name': 'SECRET', 'value': 'do-not-print'}])

    def test_secret_unset_uses_array_and_checks_absence(self):
        body = self.file('names.json', ['SECRET'])
        self.queue([{'name': 'SECRET'}], {}, [])
        self.run_script(resources, 'secrets', 'unset', '--project-ref', self.ref, '--body-file', body)
        self.assertTrue(self.output()['verified'])
        self.assertEqual(self.requests()[1][0], 'DELETE')
        self.assertEqual(self.requests()[1][2], ['SECRET'])

    def test_config_preview_never_writes_and_hides_secret_values(self):
        body = self.file('config.json', {'smtp_pass': 'do-not-print'})
        self.queue({'smtp_pass': 'also-secret'})
        self.run_script(resources, 'config', 'update', '--service', 'auth', '--project-ref', self.ref, '--body-file', body, '--dry-run')
        self.assertEqual([r[0] for r in self.requests()], ['GET'])
        self.assertNotIn('secret', self.stdout.getvalue().replace('secrets', ''))
        self.assertNotIn('do-not-print', self.stdout.getvalue())

    def test_config_read_redacts_unknown_auth_fields(self):
        self.queue({'site_url': 'https://app.example', 'smtp_pass': 'secret', 'future_credential_field': 'secret'})
        self.run_script(resources, 'config', 'get', '--service', 'auth', '--project-ref', self.ref)
        self.assertEqual(self.output()['config'], {'site_url': 'https://app.example'})
        self.assertNotIn('"secret"', self.stdout.getvalue())

    def test_config_update_matches_only_requested_fields(self):
        body = self.file('config.json', {'disable_signup': True})
        self.queue({'disable_signup': False}, {}, {'disable_signup': True, 'other': 123})
        self.run_script(resources, 'config', 'update', '--service', 'auth', '--project-ref', self.ref, '--body-file', body)
        self.assertTrue(self.output()['verified'])
        self.assertEqual(self.requests()[1][0], 'PATCH')

    def test_branch_creation_is_not_ready_and_unknown_scope_fields_rejected(self):
        body = self.file('branch.json', {'branch_name': 'feature'})
        self.queue([], {'project_ref': 'child'}, [])
        self.run_script(resources, 'branches', 'create', '--project-ref', self.ref, '--body-file', body)
        self.assertFalse(self.output()['verified'])
        self.assertEqual(self.output()['branch_ref'], 'child')
        self.opener.reset_mock()
        body = self.file('bad.json', {'branch_name': 'feature', 'notify_url': 'https://untrusted.example'})
        with self.assertRaises(ValueError):
            self.run_script(resources, 'branches', 'create', '--project-ref', self.ref, '--body-file', body)
        self.opener.open.assert_not_called()

    def test_empty_body_and_http_204_are_supported(self):
        empty = io.BytesIO(b'')
        empty.status = 204
        self.opener.open.side_effect = [empty]
        self.assertIsNone(api.Client().request('DELETE', '/v1/projects/' + self.ref))

    def test_http_failures_do_not_echo_body_or_follow_redirects(self):
        for code in (302, 401, 403, 429, 500):
            self.opener.reset_mock()
            self.queue(HTTPError('https://example/' + self.token, code, self.token, {}, io.BytesIO(b'raw-secret')))
            with self.subTest(code=code), self.assertRaises(api.APIError) as caught:
                api.Client().request('GET', '/v1/projects')
            self.assertNotIn(self.token, str(caught.exception))
            self.assertNotIn('raw-secret', str(caught.exception))
            self.assertEqual(len(self.requests()), 1)
        handler = self.factory.call_args.args[0]
        self.assertIsInstance(handler, api.NoRedirect)
        self.assertIsNone(handler.redirect_request(None, None, 302, '', {}, 'https://evil.example'))

    def test_bad_json_and_untrusted_request_paths_never_report_success(self):
        response = io.BytesIO(b'{invalid-json-with-secret')
        response.status = 200
        self.opener.open.side_effect = [response]
        with self.assertRaisesRegex(api.APIError, 'invalid JSON'):
            api.Client().request('GET', '/v1/projects')
        self.opener.reset_mock()
        for path in ('https://evil.example', '//evil.example', '/v1/projects/../secrets', '/v1/projects?key=x'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                api.Client().request('GET', path)
        self.opener.open.assert_not_called()

    def test_api_help_works_without_credentials_and_lists_routes(self):
        with patch.dict(os.environ, {'SUPABASE_ACCESS_TOKEN': ''}):
            for module, args in ((project, ('create', '--help')), (db, ('query', '--help')),
                                 (resources, ('functions', '--help')), (auth, ('verify', '--help'))):
                with self.subTest(module=module.__name__), self.assertRaises(SystemExit) as caught:
                    self.run_script(module, *args)
                self.assertEqual(caught.exception.code, 0)
        self.factory.assert_not_called()


class CLIPolicyContracts(unittest.TestCase):
    def test_known_container_modes_and_unknown_commands_are_blocked(self):
        blocked = [ ['start'], ['db', 'start'], ['db', 'dump', '--linked'],
                    ['db', 'diff', '--linked'], ['db', 'pull', '--linked'],
                    ['db', 'schema', 'declarative', 'sync', '--no-apply'],
                    ['test', 'db', '--linked'], ['functions', 'serve'],
                    ['functions', 'deploy', 'hello'], ['functions', 'deploy', '--use-api=false'],
                    ['migration', 'squash', '--linked'], ['future-resource', 'run'],
                    ['db', 'query', '--local=false'], ['db', 'query', '--db-url=postgres://host'],
                    ['gen', 'types', 'typescript'], ['gen', 'types', '--lang=go', '--linked'],
                    ['gen', 'types', 'python', '--linked'], ['db', 'push'],
                    ['storage', 'rm', 'ss:///bucket/file', '--project-ref', 'ref', '--experimental'],
                    ['--profile', '--help', 'start'], ['login', '--token', 'secret'],
                    ['link', '--password=secret'], ['db', 'push', '--linked', '-p', 'secret'],
                    ['login', '--token=secret', '--help'],
                    ['--help', '--token', 'secret'], ['db', 'push', '--linked', '-p=secret'],
                    ['db', 'dump', '--help', '--db-url=postgres://secret@host/db'] ]
        for args in blocked:
            with self.subTest(args=args), self.assertRaises(ValueError):
                validate_cli(args)

    def test_help_and_known_remote_file_workflows_remain_available(self):
        allowed = [['start', '--help'], ['db', 'dump', '-h'], ['--help'],
                   ['--experimental', 'storage', 'ls', '--linked'],
                   ['db', 'push', '--linked', '--dry-run'],
                   ['db', 'dump', '--help', '--linked'],
                   ['functions', 'deploy', 'hello', '--use-api', '--project-ref', 'ref'],
                   ['storage', 'rm', 'ss:///bucket/file', '--project-ref', 'ref', '--experimental', '--yes'],
                   ['--yes', 'storage', 'rm', 'ss:///bucket/file', '--project-ref', 'ref', '--experimental'],
                   ['gen', 'types', 'typescript', '--project-id=ref'],
                   ['--profile', 'staging', 'projects', 'list']]
        for args in allowed:
            with self.subTest(args=args):
                validate_cli(args)


if __name__ == '__main__':
    unittest.main(verbosity=2)
