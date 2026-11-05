import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/search_google.sh"


class GoogleSearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="google-search-test-")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.log = self.work / "requests.jsonl"
        self.output = self.work / "result.json"
        self.raw = '{\n  "ai_overview": {"page_token": "opaque-token+/="}\n}\n'
        curl = self.work / "curl"
        curl.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
url = next(value for value in args if value.startswith('https://'))
assert url == 'https://mock.invalid/service/google-search'
body = json.loads(Path(args[args.index('--data') + 1][1:]).read_text())
with open(os.environ['MOCK_LOG'], 'a') as log:
    log.write(json.dumps(body) + '\\n')
Path(args[args.index('-o') + 1]).write_text(os.environ['MOCK_RESPONSE'])
print(os.environ['MOCK_HTTP'], end='')
''')
        curl.chmod(0o755)
        self.env = {
            **os.environ,
            "PATH": str(self.work) + os.pathsep + os.environ["PATH"],
            "FREVANA_TOKEN": "offline-test-token",
            "FREVANA_API_BASE_URL": "https://mock.invalid",
            "MOCK_LOG": str(self.log),
            "MOCK_RESPONSE": self.raw,
            "MOCK_HTTP": "200",
        }

    def run_script(self, *args):
        return subprocess.run(
            ["bash", str(SCRIPT), "--q", "heat pumps", "--output", str(self.output), *args],
            env=self.env, cwd=self.work, capture_output=True, text=True, timeout=15,
        )

    def requests(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_omitted_cache_control_preserves_default(self):
        self.env["GOOGLE_SEARCH_NO_CACHE"] = "true"
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.requests(), [{"q": "heat pumps"}])
        self.assertEqual(result.stdout, self.raw)
        self.assertEqual(self.output.read_text(), self.raw)

    def test_true_is_json_boolean_with_search_options_preserved(self):
        result = self.run_script("--no-cache", "true", "--gl", "us", "--hl", "en", "--start", "0", "--num", "10")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.requests(), [{"q": "heat pumps", "no_cache": True, "gl": "us", "hl": "en", "start": 0, "num": 10}])
        self.assertEqual(result.stdout, self.raw)

    def test_false_is_sent_explicitly(self):
        result = self.run_script("--no-cache", "false")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIs(self.requests()[0]["no_cache"], False)

    def test_invalid_or_missing_boolean_never_sends_request(self):
        for values in [[], [""], ["yes"], ["1"], ["TRUE"], ["--gl", "us"]]:
            with self.subTest(values=values):
                result = self.run_script("--no-cache", *values)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("expected true or false", result.stderr)
                self.assertEqual(self.requests(), [])

    def test_rejected_cache_option_is_not_silently_retried_without_it(self):
        self.env.update(MOCK_HTTP="400", MOCK_RESPONSE='{"error":"no_cache is unsupported"}')
        result = self.run_script("--no-cache", "true")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no_cache is unsupported", result.stderr)
        self.assertEqual(self.requests(), [{"q": "heat pumps", "no_cache": True}])
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
