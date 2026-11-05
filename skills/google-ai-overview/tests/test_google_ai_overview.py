import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SKILL = Path(__file__).resolve().parents[1]
SCRIPT = SKILL / "scripts/get_google_ai_overview.sh"
SEARCH = SKILL.parent / "google-search/scripts/search_google.sh"


class GoogleAiOverviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="google-ai-overview-test-")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.log = self.work / "requests.jsonl"
        self.token = "opaque+/=._-%25-token"
        self.raw = '{\n  "ai_overview": {"text_blocks": [{"snippet": "mock answer"}]}\n}\n'
        curl = self.work / "curl"
        curl.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
url = next(value for value in args if value.startswith('https://'))
assert url in ['https://mock.invalid/service/google-search', 'https://mock.invalid/service/google-ai-overview']
body = json.loads(Path(args[args.index('--data') + 1][1:]).read_text())
with open(os.environ['MOCK_LOG'], 'a') as log:
    log.write(json.dumps({'url': url, 'body': body}) + '\\n')
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

    def run_script(self, *args, script=SCRIPT):
        return subprocess.run(
            ["bash", str(script), *args], env=self.env, cwd=self.work,
            capture_output=True, text=True, timeout=15,
        )

    def requests(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_missing_page_token_exits_nonzero_without_request(self):
        for args in [[], ["--output", str(self.work / "result.json")], ["--token", "override"], ["--no-cache", "true"]]:
            with self.subTest(args=args):
                result = self.run_script(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Missing required argument(s): --page-token", result.stderr)
                self.assertNotIn("unbound variable", result.stderr)
                self.assertEqual(self.requests(), [])

    def test_raw_token_and_response_are_preserved(self):
        output = self.work / "overview.json"
        result = self.run_script("--page-token", self.token, "--output", str(output))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.requests()[0]["body"], {"page_token": self.token})
        self.assertEqual(result.stdout, self.raw)
        self.assertEqual(output.read_text(), self.raw)

    def test_expired_token_is_not_retried(self):
        self.env.update(MOCK_HTTP="400", MOCK_RESPONSE='{"error":"expired page token"}')
        result = self.run_script("--page-token", self.token)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("expired page token", result.stderr)
        self.assertEqual(len(self.requests()), 1)

    def test_bundle_search_to_overview_handoff(self):
        search_output = self.work / "search.json"
        self.env["MOCK_RESPONSE"] = json.dumps({"ai_overview": {"page_token": self.token}})
        result = self.run_script("--q", "heat pumps", "--no-cache", "true", "--output", str(search_output), script=SEARCH)
        self.assertEqual(result.returncode, 0, result.stderr)
        token = json.loads(search_output.read_text())["ai_overview"]["page_token"]
        self.env["MOCK_RESPONSE"] = self.raw
        result = self.run_script("--page-token", token)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, self.raw)
        self.assertEqual(self.requests(), [
            {"url": "https://mock.invalid/service/google-search", "body": {"q": "heat pumps", "no_cache": True}},
            {"url": "https://mock.invalid/service/google-ai-overview", "body": {"page_token": self.token}},
        ])


if __name__ == "__main__":
    unittest.main()
