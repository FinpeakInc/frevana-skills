#!/usr/bin/env python3
"""Offline behavior tests; never invoke a real CLI, Docker, or cloud account."""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

HELPER = Path(__file__).resolve().parents[1] / "scripts/supabase_helper.py"
MOCK = '''#!{python}
import json, os, pathlib, sys
args = sys.argv[1:]
with open(os.environ['MOCK_LOG'], 'a') as stream:
    stream.write(json.dumps(dict(args=args, cwd=os.getcwd(), binary=sys.argv[0])) + '\\n')
if os.environ.get('MOCK_FAIL'):
    print('partial output')
    sys.exit(7)
if '--version' in args:
    print('2.99.0')
elif 'status' in args:
    print(json.dumps({{'API_URL': 'http://user:password@localhost:54321?key=secret',
                      'STUDIO_URL': 'http://localhost:54323', 'DB_URL': 'postgres://secret',
                      'SERVICE_ROLE_KEY': 'secret', 'ANON_KEY': 'anon', 'SECRET_KEY': 'secret'}}))
elif 'init' in args:
    pathlib.Path('supabase').mkdir(exist_ok=True)
    pathlib.Path('supabase/config.toml').write_text('project_id = "test"\\n')
else:
    print('raw output')
'''


class HelperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="supabase-helper-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / 'project with spaces'
        self.project.mkdir()
        self.caller = self.root / 'caller'
        self.caller.mkdir()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.log = self.root / 'calls.jsonl'
        self.install(self.bin / 'supabase')
        self.env = dict(os.environ, PATH=str(self.bin), MOCK_LOG=str(self.log))
        # Ignore ambient credentials and provider/workdir settings completely.
        for key in list(self.env):
            if key.startswith(('SUPABASE_', 'MOCK_FAIL')):
                self.env.pop(key)
        self.cache = self.root / "managed-cli"
        self.env["FREVANA_SUPABASE_CLI_DIR"] = str(self.cache)
        self.frevana_bin = self.root / "frevana-bin"
        self.env["FREVANA_BIN_DIR"] = str(self.frevana_bin)
        self.install_log = self.root / "installs.jsonl"

    def install(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(MOCK.format(python=sys.executable))
        path.chmod(0o755)

    def run_helper(self, *args, fail=False, script=None):
        env = dict(self.env)
        if fail:
            env['MOCK_FAIL'] = '1'
        script_path = HELPER.with_name(script) if script else HELPER
        return subprocess.run([sys.executable, str(script_path), args[0],
                               '--workdir', str(self.project), *args[1:]],
                              cwd=self.caller, env=env, capture_output=True, text=True)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_help_needs_no_cli(self):
        (self.bin / 'supabase').unlink()
        self.assertEqual(self.run_helper('cli', '--help').returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_missing_cli_without_manager_reports_prerequisite(self):
        (self.bin / 'supabase').unlink()
        result = self.run_helper('check')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('need npm with Node.js 20+, Scoop, Winget, or Homebrew', result.stderr)

    def installer(self, manager="npm", fail=False, empty=False, node_version="v22.0.0"):
        if manager == "npm":
            node = self.bin / 'node'
            node.write_text(f'#!{sys.executable}\nprint({node_version!r})\n')
            node.chmod(0o755)
        npm_prefix = self.root / 'global-npm'
        brew_prefix = self.root / 'brew-supabase'
        script = self.bin / manager
        script.write_text(f"""#!{sys.executable}
import json, pathlib, sys
args = sys.argv[1:]
if args == ['prefix', '-g']:
    print({str(npm_prefix)!r})
    sys.exit(0)
if args == ['--prefix', 'supabase']:
    print({str(brew_prefix)!r})
    sys.exit(0)
with open({str(self.install_log)!r}, 'a') as stream:
    stream.write(json.dumps(args) + '\\n')
if {fail!r}:
    sys.exit(9)
if {empty!r}:
    sys.exit(0)
if {manager!r} == 'npm':
    target = pathlib.Path({str(npm_prefix)!r}) / 'bin/supabase'
else:
    target = pathlib.Path({str(brew_prefix)!r}) / 'bin/supabase'
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text({MOCK.format(python=sys.executable)!r})
target.chmod(0o755)
print('installer progress')
""")
        script.chmod(0o755)

    def test_npm_install_runs_once_and_does_not_modify_app(self):
        (self.bin / 'supabase').unlink()
        self.installer()
        manifest = self.project / 'package.json'
        manifest.write_text('{"name":"unchanged"}')
        result = self.run_helper('check')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['path'], str(self.root / 'global-npm/bin/supabase'))
        self.assertTrue((self.frevana_bin / 'supabase').is_symlink())
        self.assertEqual((self.frevana_bin / 'supabase').resolve(), (self.root / 'global-npm/bin/supabase').resolve())
        self.assertIn('installer progress', result.stderr)
        self.assertEqual(self.run_helper('check').returncode, 0)
        installs = self.install_log.read_text().splitlines()
        self.assertEqual(len(installs), 1)
        self.assertEqual(json.loads(installs[0]), ['install', '-g', '--no-audit', '--no-fund', 'supabase@latest'])
        self.assertEqual(manifest.read_text(), '{"name":"unchanged"}')
        self.assertFalse((self.project / 'node_modules').exists())

    def test_install_then_continue_original_command(self):
        (self.bin / 'supabase').unlink()
        self.installer()
        result = self.run_helper('cli', '--', 'projects', 'list')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls()[0]['args'], ['--version'])
        self.assertEqual(self.calls()[1]['args'][-2:], ['projects', 'list'])
        self.assertEqual(result.stdout, 'raw output\n')

    def test_existing_cli_skips_installer(self):
        self.installer()
        self.assertEqual(self.run_helper('check').returncode, 0)
        self.assertFalse(self.install_log.exists())

    def test_no_install_and_help_never_invoke_installer(self):
        (self.bin / 'supabase').unlink()
        self.installer()
        self.assertNotEqual(self.run_helper('check', '--no-install').returncode, 0)
        self.assertEqual(self.run_helper('cli', '--help').returncode, 0)
        self.assertFalse(self.install_log.exists())

    def test_install_failure_prevents_pending_command(self):
        (self.bin / 'supabase').unlink()
        self.installer(fail=True)
        result = self.run_helper('cli', '--', 'db', 'push', '--linked')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('installation failed', result.stderr)
        self.assertEqual(self.calls(), [])
        self.assertEqual(len(self.install_log.read_text().splitlines()), 1)

    def test_install_success_without_binary_is_not_success(self):
        (self.bin / 'supabase').unlink()
        self.installer(empty=True)
        result = self.run_helper('check')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('without a usable Supabase binary', result.stderr)
        self.assertEqual(self.calls(), [])

    def test_postinstall_verification_failure_stops_operation(self):
        (self.bin / 'supabase').unlink()
        self.installer()
        result = self.run_helper('cli', '--', 'db', 'push', '--linked', fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(self.calls()[0]['args'], ['--version'])
        self.assertIn('version check failed', result.stderr)

    def test_brew_fallback_without_node(self):
        (self.bin / 'supabase').unlink()
        self.installer(manager='brew')
        result = self.run_helper('check')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.install_log.read_text()), ['install', 'supabase/tap/supabase'])
        self.assertEqual(json.loads(result.stdout)['path'], str(self.root / 'brew-supabase/bin/supabase'))

    def test_check_and_project_dependency_precedence(self):
        local = self.project / 'node_modules/.bin/supabase'
        self.install(local)
        result = self.run_helper('check')
        self.assertEqual(json.loads(result.stdout)['path'], str(local))
        self.assertEqual(self.calls()[0]['binary'], str(local))

    def test_ancestor_project_dependency(self):
        local = self.root / 'node_modules/.bin/supabase'
        self.install(local)
        result = self.run_helper('check')
        self.assertEqual(json.loads(result.stdout)['path'], str(local))

    def test_failed_version_never_reports_installed(self):
        result = self.run_helper('check', fail=True)
        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.stdout, '')

    def test_init_is_idempotent_in_target_workdir(self):
        self.assertEqual(self.run_helper('init').returncode, 0)
        result = self.run_helper('init')
        self.assertEqual(json.loads(result.stdout)['status'], 'already_initialized')
        self.assertEqual(len(self.calls()), 1)
        self.assertFalse((self.caller / 'supabase').exists())

    def test_shortcuts_reject_unknown_or_inapplicable_arguments(self):
        for args in [('db-lint', '--target', 'production'), ('gen-types', '--schema'),
                     ('inspect', 'locks', '--typo'), ('link',)]:
            with self.subTest(args=args):
                self.assertNotEqual(self.run_helper(*args).returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_relative_output_uses_workdir(self):
        result = self.run_helper('gen-types', '--output', 'types/db.ts')
        self.assertEqual(result.returncode, 0, result.stderr)
        out = self.project / 'types/db.ts'
        self.assertEqual(out.read_text(), 'raw output\n')
        self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o600)
        self.assertFalse((self.caller / 'types').exists())
        self.assertIn('--linked', self.calls()[0]['args'])

    def test_failure_preserves_file_and_removes_temporary_output(self):
        output = self.project / 'types.ts'
        output.write_text('existing types')
        result = self.run_helper('gen-types', '--output', 'types.ts', fail=True)
        self.assertEqual(result.returncode, 7)
        self.assertEqual(output.read_text(), 'existing types')
        self.assertEqual(list(self.project.glob('.supabase-*')), [])
        self.assertNotIn('success', result.stdout)

    def test_inspect_output_is_saved(self):
        out = self.root / 'locks.txt'
        result = self.run_helper('inspect', 'locks', '--output', str(out))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(out.read_text(), 'raw output\n')

    def test_unsafe_output_rejected_before_cli(self):
        victim = self.project / 'keep.txt'
        victim.write_text('unchanged')
        (self.project / 'link.txt').symlink_to(victim)
        for target in ('link.txt', '.'):
            self.assertNotEqual(self.run_helper('gen-types', '--output', target).returncode, 0)
        self.assertEqual(victim.read_text(), 'unchanged')
        self.assertEqual(self.calls(), [])

    def test_native_arguments_preserved_without_shell_interpretation(self):
        native = ['projects', 'create', 'name with spaces $(touch nope)', '--org-id', 'org',
                  '--region', 'us-east-1', '--output', 'json']
        result = self.run_helper('cli', '--profile', 'staging', '--', *native)
        self.assertEqual(result.returncode, 0)
        args = self.calls()[0]['args']
        self.assertEqual(args, ['--workdir', str(self.project), '--profile', 'staging', *native])
        self.assertFalse((self.project / 'nope').exists())

    def test_native_db_preview_is_preserved(self):
        result = self.run_helper('cli', '--', 'db', 'push', '--linked', '--dry-run')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.calls()[0]['args'][-4:], ['db', 'push', '--linked', '--dry-run'])

    def test_native_separator_required_and_workdir_cannot_diverge(self):
        for args in [('cli', 'projects', 'list'), ('cli', '--'),
                     ('cli', '--', 'projects', 'list', '--workdir=/other')]:
            self.assertNotEqual(self.run_helper(*args).returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_native_atomic_output_and_failure_code(self):
        self.assertEqual(self.run_helper('cli', '--output', 'projects.json', '--',
                                         'projects', 'list', '--output', 'json').returncode, 0)
        result = self.run_helper('cli', '--output', 'projects.json', '--', 'projects', 'list', fail=True)
        self.assertEqual(result.returncode, 7)
        self.assertEqual((self.project / 'projects.json').read_text(), 'raw output\n')

    def test_lint_fails_on_errors_and_uses_explicit_target(self):
        self.assertEqual(self.run_helper('db-lint').returncode, 0)
        self.assertEqual(self.calls()[0]['args'][-7:],
                         ['db', 'lint', '--linked', '--schema', 'public', '--fail-on', 'error'])

    def test_invalid_directory_fails_before_cli(self):
        self.assertNotEqual(self.run_helper('check', '--workdir', str(self.root / 'missing')).returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_capability_entries_match_legacy_behavior(self):
        cases = [
            ('supabase_setup.py', ('check',)),
            ('supabase_project.py', ('link', 'example-ref')),
            ('supabase_project.py', ('cli', '--', 'projects', 'list')),
            ('supabase_project.py', ('cli', '--', 'config', 'push', '--help')),
            ('supabase_db.py', ('gen-types',)),
            ('supabase_db.py', ('migration-new', 'add_table')),
            ('supabase_db.py', ('db-lint',)),
            ('supabase_db.py', ('inspect', 'locks')),
            ('supabase_db.py', ('cli', '--', 'db', 'push', '--linked', '--dry-run')),
            ('supabase_resources.py', ('cli', '--', 'storage', '--help')),
            ('supabase_resources.py', ('cli', '--', '--experimental', 'branches', 'list')),
        ]
        for script, args in cases:
            with self.subTest(script=script, args=args):
                old = self.run_helper(*args)
                old_call = self.calls()[-1]
                new = self.run_helper(*args, script=script)
                self.assertEqual(new.returncode, 0, new.stderr)
                self.assertEqual(new.stdout, old.stdout)
                self.assertEqual(self.calls()[-1], old_call)

    def test_project_entry_initializes_selected_directory(self):
        result = self.run_helper('init', script='supabase_project.py')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.project / 'supabase/config.toml').is_file())
        result = self.run_helper('init', script='supabase_project.py')
        self.assertEqual(json.loads(result.stdout)['status'], 'already_initialized')
        self.assertEqual(len(self.calls()), 1)

    def test_capability_group_validation_before_execution(self):
        for script, args in [
            ('supabase_project.py', ('cli', '--', 'db', 'push')),
            ('supabase_db.py', ('cli', '--', 'projects', 'delete', 'ref')),
        ]:
            with self.subTest(script=script):
                self.assertNotEqual(self.run_helper(*args, script=script).returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_capability_output_failure_preserves_file(self):
        output = self.project / 'types.ts'
        output.write_text('keep')
        result = self.run_helper('gen-types', '--output', 'types.ts', fail=True,
                                 script='supabase_db.py')
        self.assertEqual(result.returncode, 7)
        self.assertEqual(output.read_text(), 'keep')

    def test_capability_help_is_offline(self):
        (self.bin / 'supabase').unlink()
        for name in ('setup', 'auth', 'project', 'db', 'resources'):
            result = self.run_helper('--help', script=f'supabase_{name}.py')
            # --help exits before any workdir processing or installation.
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [])

    def test_auth_status_is_secret_free_and_offline(self):
        (self.bin / 'supabase').unlink()
        result = self.run_helper('status', script='supabase_auth.py')
        self.assertEqual(json.loads(result.stdout)['configured'], False)
        token = 'fake-token-for-offline-tests'
        self.env['SUPABASE_ACCESS_TOKEN'] = token
        result = self.run_helper('status', script='supabase_auth.py')
        self.assertEqual(json.loads(result.stdout)['configured'], True)
        self.assertNotIn(token, result.stdout + result.stderr)
        self.assertEqual(self.calls(), [])
        self.assertFalse(self.cache.exists())

    def test_auth_verify_requires_token_without_login_or_install(self):
        (self.bin / 'supabase').unlink()
        self.installer()
        result = self.run_helper('verify', script='supabase_auth.py')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Configure SUPABASE_ACCESS_TOKEN', result.stderr)
        self.assertEqual(self.calls(), [])
        self.assertFalse(self.install_log.exists())

    def test_auth_verify_uses_read_only_discovery_and_keeps_token_out_of_argv(self):
        token = 'fake-token-for-offline-tests'
        self.env['SUPABASE_ACCESS_TOKEN'] = token
        result = self.run_helper('verify', script='supabase_auth.py')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls()[0]['args'][-2:], ['projects', 'list'])
        self.assertNotIn(token, self.log.read_text() + result.stdout + result.stderr)
        self.assertEqual(len(self.calls()), 1)

    def test_auth_failure_does_not_fallback_to_login(self):
        self.env['SUPABASE_ACCESS_TOKEN'] = 'fake-token-for-offline-tests'
        result = self.run_helper('verify', script='supabase_auth.py', fail=True)
        self.assertEqual(result.returncode, 7)
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(self.calls()[0]['args'][-2:], ['projects', 'list'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
