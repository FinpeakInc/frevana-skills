import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

SCRIPT = Path(__file__).parents[1] / 'scripts/generate_image.sh'
MODEL = 'gemini-nano-banana-2.1'


class NanoBananaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.log = self.root / 'calls.jsonl'
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(('FREVANA_', 'X_FREVANA_'))}
        self.env.update(PATH=f'{self.root}:{Path(sys.executable).parent}:{self.env["PATH"]}',
                        FREVANA_TOKEN='test-token', CAPTURE_LOG=str(self.log))
        fake = self.root / 'curl'
        fake.write_text(f'#!{sys.executable}\n' + '''import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ['CAPTURE_LOG'], 'a') as f:
    f.write(json.dumps(args) + '\\n')
out = Path(args[args.index('-o') + 1])
if '-X' not in args:
    Path(args[args.index('-D') + 1]).write_text('Content-Type: image/png\\n')
    out.write_bytes(b'\\x89PNG\\r\\n\\x1a\\n' + b'1234')
else:
    out.write_text(os.environ.get('MOCK_RESPONSE', '{"data":[{"image_url":"https://static.frevana.com/test.png"}],"credits_consumed":1}'))
    print(os.environ.get('MOCK_HTTP', '200'), end='')
''')
        fake.chmod(0o755)

    def run_script(self, *args):
        return subprocess.run(['bash', str(SCRIPT), *args], env=self.env, text=True,
                              capture_output=True, stdin=subprocess.DEVNULL)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_generation_contract_and_output(self):
        output = self.root / 'out/result.json'
        r = self.run_script('--contents', '咖啡杯', '--thinking-level', 'high', '--aspect-ratio', '16:9',
                            '--image-size', '2k', '--n', '1', '--seed', '42',
                            '--system-instruction', 'Detailed', '--output', str(output))
        self.assertEqual(r.returncode, 0, r.stderr)
        args = self.calls()[0]
        fields = dict(args[i + 1].split('=', 1) for i, a in enumerate(args) if a == '--form-string')
        self.assertEqual(fields, dict(prompt='咖啡杯', model=MODEL, thinking_level='high',
                                     aspect_ratio='16:9', image_size='2K', candidate_count='1',
                                     seed='42', system_instruction='Detailed'))
        self.assertIn('https://ai-factory.frevana.com/gemini/image/generate', args)
        self.assertEqual(json.loads(output.read_text()), json.loads(r.stdout))

    def test_defaults_and_thinking_levels(self):
        for level in (None, 'minimal', 'medium', 'high'):
            with self.subTest(level=level):
                r = self.run_script('--prompt', 'cup', *(['--thinking-level', level] if level else []))
                self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn('image_size=1K', self.calls()[0])
        self.assertNotIn('thinking_level=medium', self.calls()[0])

    def test_rejects_invalid_options_before_network(self):
        for args in [(), ('--prompt',), ('--prompt', ''), ('--prompt', 'cup', '--image', ''),
                     ('--prompt', 'cup', '--thinking-level', 'low'),
                     ('--prompt', 'cup', '--n', '2'), ('--prompt', 'cup', '--image-size', '8K'),
                     ('--prompt', 'cup', '--aspect-ratio', '16:10'),
                     ('--prompt', 'cup', '--model', MODEL), ('--prompt', 'cup', '--provider', 'gemini')]:
            with self.subTest(args=args):
                self.assertNotEqual(self.run_script(*args).returncode, 0)
        self.assertFalse(self.log.exists())

    def test_rejects_unsupported_sampling_and_legacy_config(self):
        for option in ('--temperature', '--top-p', '--top-k', '--max-output-tokens', '--response-modality'):
            with self.subTest(option=option):
                self.assertNotEqual(self.run_script('--prompt', 'cup', option, '1').returncode, 0)
        self.assertFalse(self.log.exists())

    def test_local_directory_and_remote_references(self):
        directory = self.root / 'refs'
        directory.mkdir()
        local = directory / 'b.png'
        local.write_bytes(b'\x89PNG\r\n\x1a\n1234')
        self.env.update(FREVANA_API_KEY='test-key', FREVANA_AGENT_APP_INSTANCE_ID='instance')
        r = self.run_script('--prompt', 'edit', '--image-dir', str(directory), '--image-url', 'https://example.com/ref.png')
        self.assertEqual(r.returncode, 0, r.stderr)
        download, post = self.calls()
        self.assertNotIn('-H', download)
        self.assertEqual(post.count('-F'), 2)
        self.assertFalse(any(a.startswith('X-API-Key:') for a in post))
        self.assertIn('Authorization: Bearer test-token', post)
        self.assertIn('x-frevana-agent-app-instance-id: instance', post)

    def test_reference_limits_and_format(self):
        img = self.root / 'ref.png'
        img.write_bytes(b'\x89PNG\r\n\x1a\n1234')
        r = self.run_script('--prompt', 'edit', *(['--image', str(img)] * 15))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('At most 14', r.stderr)
        img.write_bytes(b'not an image')
        self.assertNotEqual(self.run_script('--prompt', 'edit', '--image', str(img)).returncode, 0)
        self.assertFalse(self.log.exists())

    def test_auth_overrides_and_optional_attribution(self):
        self.env.pop('FREVANA_TOKEN')
        self.env['FREVANA_API_KEY'] = 'ignored-key'
        self.assertNotEqual(self.run_script('--prompt', 'cup').returncode, 0)
        self.assertFalse(self.log.exists())
        r = self.run_script('--prompt', 'cup', '--token', 'override', '--agent-app-instance-id', 'explicit')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('Authorization: Bearer override', self.calls()[0])
        self.assertFalse(any(a.startswith('X-API-Key:') for a in self.calls()[0]))
        self.assertIn('x-frevana-agent-app-instance-id: explicit', self.calls()[0])
        self.env['FREVANA_TOKEN'] = 'env-token'
        r = self.run_script('--prompt', 'cup', '--token', 'override-token')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('Authorization: Bearer override-token', self.calls()[1])
        self.assertNotIn('Authorization: Bearer env-token', self.calls()[1])
        self.assertFalse(any(a.startswith(('x-frevana-agent-app-instance-id:', 'X-API-Key:')) for a in self.calls()[1]))
        self.assertNotEqual(self.run_script('--prompt', 'cup', '--api-key', 'unsupported').returncode, 0)

    def test_async_acknowledgment(self):
        job = '11111111-1111-4111-8111-111111111111'
        response = {'id': job, 'status': 'running', 'created_at': 1}
        self.env['MOCK_RESPONSE'] = json.dumps(response)
        r = self.run_script('--prompt', 'cup', '--job-id', job)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), response)
        self.assertIn(f'https://ai-factory.frevana.com/gemini/image/generate?job_id={job}', self.calls()[0])

    def test_rejects_empty_or_invalid_job_id_before_network(self):
        for job in ('', ' ', 'not-a-uuid', '11111111-1111-9111-8111-111111111111',
                    '11111111-1111-4111-1111-111111111111'):
            with self.subTest(job=job):
                r = self.run_script('--prompt', 'cup', '--job-id', job,
                                    '--image-url', 'https://example.com/ref.png')
                self.assertNotEqual(r.returncode, 0)
                self.assertIn('Invalid --job-id', r.stderr)
        self.assertFalse(self.log.exists())

    def test_special_filenames_with_real_curl(self):
        captured = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                captured.append(self.rfile.read(int(self.headers['Content-Length'])))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"data":[{"image_url":"https://static.frevana.com/test.png"}]}')

            def log_message(self, *args):
                pass

        server = HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            # Use real curl: the mock does not parse curl's multipart syntax.
            (self.root / 'curl').unlink()
            self.env['FREVANA_API_BASE_URL'] = f'http://127.0.0.1:{server.server_port}'
            self.env['NO_PROXY'] = '127.0.0.1'
            names = ['ref,1.png', 'ref;1.png', 'ref"1.png', 'ref\\1.png', '产品 1.png']
            args, contents = [], []
            for index, name in enumerate(names):
                path = self.root / name
                content = b'\x89PNG\r\n\x1a\n' + f'image-{index}'.encode()
                path.write_bytes(content)
                contents.append(content)
                args.extend(['--image', str(path)])
            r = self.run_script('--prompt', 'edit', *args)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(len(captured), 1)
            self.assertEqual(captured[0].count(b'name="image";'), len(names))
            for content in contents:
                self.assertIn(content, captured[0])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_response_failures_do_not_save_output(self):
        for body, http in [('{}', '400'), ('', '200'), ('not json', '200'),
                           ('{"data":[]}', '200'), ('{"data":[{}]}', '200'),
                           ('{"status":"running"}', '200')]:
            with self.subTest(body=body, http=http):
                self.env.update(MOCK_RESPONSE=body, MOCK_HTTP=http)
                output = self.root / 'failed.json'
                r = self.run_script('--prompt', 'cup', '--output', str(output))
                self.assertNotEqual(r.returncode, 0)
                self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
