"""Offline contract tests; curl is replaced before every helper invocation."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "create_response.sh"
MODEL = "meta/muse-wonder"
SLUG = "muse-wonder"
MAX_OUTPUT = 943718
EFFORTS = ['minimal', 'low', 'medium', 'high', 'xhigh', 'max']


class MuseWonderCreateResponseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.capture = self.root / "requests.jsonl"
        self.response = self.root / "response.json"
        self.response.write_text(json.dumps({
            "id": "resp_test_123", "object": "response", "status": "completed", "model": MODEL,
            "output": [{"id": "msg_test", "type": "message", "role": "assistant", "status": "completed", "phase": "final_answer", "content": [
                {"type": "output_text", "text": "Test response 中文"}
            ]}],
        }))
        fake_curl = self.root / "curl"
        fake_curl.write_text(f"#!{sys.executable}\n" + '''import json, os, sys
from pathlib import Path
args = sys.argv[1:]
headers = [args[i + 1] for i, arg in enumerate(args) if arg == '-H']
payload = json.loads(Path(args[args.index('--data') + 1][1:]).read_text())
assert payload.get('store') is False, 'Every request must disable upstream storage'
assert 'previous_response_id' not in payload, 'Gateway cannot resume stored responses'
request = {'payload': payload, 'headers': headers, 'url': args[args.index('-X') + 2], 'method': args[args.index('-X') + 1]}
with open(os.environ['MOCK_CAPTURE'], 'a') as f:
    f.write(json.dumps(request) + '\\n')
if os.environ.get('MOCK_SESSION_TARGET'):
    Path(os.environ['MOCK_SESSION_TARGET']).write_text(os.environ['MOCK_SESSION_CONTENT'])
Path(args[args.index('-o') + 1]).write_bytes(Path(os.environ['MOCK_RESPONSE']).read_bytes())
print(os.environ.get('MOCK_STATUS', '200'), end='')
''')
        fake_curl.chmod(0o755)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("FREVANA_", "X_FREVANA_", "MOCK_")) and k not in ("SESSION_ID", "CONVERSATION_ID")}
        self.env.update({
            "PATH": os.pathsep.join((str(self.root), str(Path(sys.executable).parent), self.env.get("PATH", ""))),
            "FREVANA_TOKEN": "test-token",
            "FREVANA_SESSION_DIR": str(self.root / "sessions"),
            "MOCK_CAPTURE": str(self.capture), "MOCK_RESPONSE": str(self.response),
        })

    def run_script(self, *args, stdin=None):
        return subprocess.run(["bash", str(SCRIPT), *args], input=stdin, text=True, capture_output=True, env=self.env, timeout=20, check=False)

    def requests(self):
        return [json.loads(row) for row in self.capture.read_text().splitlines()] if self.capture.exists() else []

    def write_json(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value, ensure_ascii=False))
        return str(path)

    def session(self, name="session.json", history=None, **extra):
        return self.write_json(name, {"schema_version": 1, "model": MODEL,
            "api_base_url": "https://ai-factory.frevana.com", "history": history or [], **extra})

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")

    def test_default_fixed_model_route_and_json_output(self):
        result = self.run_script("--input", "Hello 中文")
        self.assert_success(result)
        self.assertEqual(json.loads(result.stdout), json.loads(self.response.read_text()))
        request = self.requests()[0]
        self.assertEqual(request["method"], "POST")
        self.assertEqual(request["url"], "https://ai-factory.frevana.com/openrouter/v1/responses")
        self.assertEqual(request["payload"], {"model": MODEL, "input": "Hello 中文", "store": False})
        self.assertIn("Authorization: Bearer test-token", request["headers"])

    def test_input_options_tools_and_attribution(self):
        self.env["X_FREVANA_AGENT_APP_INSTANCE_ID"] = "fallback-instance"
        result = self.run_script("--prompt", "Plan a feature", "--instructions", "Explain tradeoffs", "--reasoning-effort", "high", "--max-output-tokens", "2048", "--service-tier", "default", "--tools", '[{"type":"web_search"}]', "--tool-choice", "auto")
        self.assert_success(result)
        request = self.requests()[0]
        self.assertEqual(request["payload"], {"model": MODEL, "input": "Plan a feature", "instructions": "Explain tradeoffs", "reasoning": {"effort": "high"}, "max_output_tokens": 2048, "service_tier": "default", "tools": [{"type": "web_search"}], "tool_choice": "auto", "store": False})
        self.assertIn("x-frevana-agent-app-instance-id: fallback-instance", request["headers"])

    def test_input_instruction_and_tool_files(self):
        messages = [{"role": "user", "content": [{"type": "input_text", "text": "Describe this"}, {"type": "input_image", "image_url": "https://example.com/image.png"}]}]
        input_path = self.write_json("input.json", messages)
        tools = [{"type": "function", "name": "lookup", "parameters": {"type": "object"}}]
        tools_path = self.write_json("tools.json", tools)
        instructions = self.root / "instructions.txt"
        instructions.write_text("Use concise language.")
        result = self.run_script("--input-file", input_path, "--instructions-file", str(instructions), "--tools-file", tools_path, "--tool-choice", '{"type":"function","name":"lookup"}')
        self.assert_success(result)
        payload = self.requests()[0]["payload"]
        self.assertEqual(payload["input"], messages)
        self.assertEqual(payload["instructions"], instructions.read_text())
        self.assertEqual(payload["tools"], tools)
        self.assertEqual(payload["tool_choice"], {"type": "function", "name": "lookup"})

    def test_explicit_auth_and_attribution_override_environment(self):
        self.env.update({"FREVANA_API_KEY": "env-key", "FREVANA_AGENT_APP_INSTANCE_ID": "env-instance", "X_FREVANA_AGENT_APP_INSTANCE_ID": "fallback"})
        result = self.run_script("--input", "Hello", "--api-key", "explicit-key", "--token", "explicit-token", "--agent-app-instance-id", "explicit-instance")
        self.assert_success(result)
        headers = self.requests()[0]["headers"]
        self.assertIn("X-API-Key: explicit-key", headers)
        self.assertIn("Authorization: Bearer explicit-token", headers)
        self.assertIn("x-frevana-agent-app-instance-id: explicit-instance", headers)
        self.assertNotIn("X-API-Key: env-key", headers)

    def test_api_key_without_token(self):
        self.env.pop("FREVANA_TOKEN")
        self.env["FREVANA_API_KEY"] = "key-only"
        result = self.run_script("--input", "Hello")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Authentication required", result.stderr)
        self.assertEqual(self.requests(), [])

    def test_missing_auth_fails_without_transport(self):
        self.env.pop("FREVANA_TOKEN")
        result = self.run_script("--input", "Hello", stdin="")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Authentication required", result.stderr)
        self.assertEqual(self.requests(), [])

    def test_missing_input_model_and_flag_values_fail_without_transport(self):
        for args in ((), ("--input", "hello", "--model", "gpt-6"), ("--input",), ("--input", "hello", "--reasoning-effort")):
            with self.subTest(args=args):
                self.assertNotEqual(self.run_script(*args).returncode, 0)
        self.assertEqual(self.requests(), [])

    def test_supported_reasoning_levels(self):
        for level in EFFORTS:
            with self.subTest(level=level):
                self.assert_success(self.run_script("--input", "Hello", "--reasoning-effort", level))
                self.assertEqual(self.requests()[-1]["payload"]["reasoning"], {"effort": level})

    def test_invalid_effort_and_sampling_fail_before_transport(self):
        cases = [("--reasoning-effort", "none"), ("--reasoning-effort", "extreme"), ("--temperature", "3"), ("--top-p", "-0.1")]
        if "max" not in EFFORTS:
            cases += [("--reasoning-effort", "max"), ("--reasoning-effort", "minimal")]
        for args in cases:
            with self.subTest(args=args):
                self.assertNotEqual(self.run_script("--input", "Hello", *args).returncode, 0)
        self.assertEqual(self.requests(), [])

    def test_sampling_can_accompany_required_reasoning(self):
        self.assert_success(self.run_script("--input", "Hello", "--reasoning-effort", "high", "--temperature", "0.7", "--top-p", "0.95"))
        payload = self.requests()[0]["payload"]
        self.assertEqual(payload["temperature"], 0.7)
        self.assertEqual(payload["top_p"], 0.95)
        self.assertEqual(payload["reasoning"], {"effort": "high"})

    def test_raw_payload_fixed_model_and_preserved_options(self):
        raw_path = self.write_json("raw.json", {"model": MODEL, "input": "Raw input", "reasoning": {"effort": "high", "summary": "auto"}, "metadata": {"source": "test"}, "store": False})
        self.assert_success(self.run_script("--raw-payload-file", raw_path, "--input", "CLI input"))
        payload = self.requests()[0]["payload"]
        self.assertEqual(payload["model"], MODEL)
        self.assertEqual(payload["input"], "CLI input")
        self.assertEqual(payload["reasoning"], {"effort": "high", "summary": "auto"})
        self.assertEqual(payload["metadata"], {"source": "test"})
        self.assertFalse(payload["store"])

    def test_raw_payload_cannot_bypass_model_parameter_validation(self):
        cases = [[], {}, {"input": ""}, {"input": []}, {"input": {}}, {"input": "Hello", "model": "another-model"},
                 {"input": "Hello", "reasoning": {"effort": "none"}}, {"input": "Hello", "reasoning": "high"},
                 {"input": "Hello", "reasoning": {"enabled": False}}, {"input": "Hello", "reasoning": {"max_tokens": 10}},
                 {"input": "Hello", "temperature": True}, {"input": "Hello", "temperature": 2.1}, {"input": "Hello", "top_p": -1},
                 {"input": "Hello", "max_output_tokens": MAX_OUTPUT + 1}, {"input": "Hello", "max_output_tokens": True},
                 {"input": "Hello", "service_tier": "priority"}, {"input": "Hello", "stream": True},
                 {"input": "Hello", "background": True}, {"input": "Hello", "speed": "fast"},
                 {"input": "Hello", "provider": {"only": ["xai/priority"]}}, {"input": "Hello", "provider": {"order": ["meta/fast"]}},
                 {"input": "Hello", "tools": {}}, {"input": "Hello", "tool_choice": "bogus"}]
        if "max" not in EFFORTS:
            cases.append({"input": "Hello", "reasoning": {"effort": "max"}})
        for case in cases:
            with self.subTest(case=case):
                raw_path = self.write_json("raw-invalid.json", case)
                self.assertNotEqual(self.run_script("--raw-payload-file", raw_path).returncode, 0)
        self.assertEqual(self.requests(), [])

    def test_output_limit_and_service_tier(self):
        for args in (("--max-output-tokens", "0"), ("--max-output-tokens", str(MAX_OUTPUT + 1)), ("--max-output-tokens", "2.5"),
                     ("--service-tier", "invalid"), ("--service-tier", "fast"), ("--service-tier", "priority")):
            with self.subTest(args=args):
                self.assertNotEqual(self.run_script("--input", "Hello", *args).returncode, 0)
        self.assertEqual(self.requests(), [])
        self.assert_success(self.run_script("--input", "Hello", "--max-output-tokens", str(MAX_OUTPUT), "--service-tier", "default"))
        self.assertEqual(self.requests()[0]["payload"]["max_output_tokens"], MAX_OUTPUT)

    def test_response_text_extraction_and_saved_full_json(self):
        output = self.root / "out" / "result.json"
        result = self.run_script("--input", "Hello", "--text-only", "--output", str(output))
        self.assert_success(result)
        self.assertEqual(result.stdout, "Test response 中文\n")
        self.assertEqual(json.loads(output.read_text()), json.loads(self.response.read_text()))
        self.response.write_text('{"output_text":"Direct text"}')
        result = self.run_script("--input", "Hello", "-t")
        self.assert_success(result)
        self.assertEqual(result.stdout, "Direct text\n")

    def test_session_replays_three_turns_without_response_ids(self):
        session = self.root / "session.json"
        output = json.loads(self.response.read_text())["output"]
        history = []
        for message in ("My project is a Go library", "What language?", "Explain its concurrency model"):
            self.assert_success(self.run_script("--input", message, "--session-file", str(session)))
            history += [{"role": "user", "content": message}]
            sent = self.requests()[-1]["payload"]
            self.assertEqual(sent["input"], history)
            self.assertFalse(sent["store"])
            self.assertNotIn("previous_response_id", sent)
            history += output
            saved = json.loads(session.read_text())
            self.assertEqual(saved["history"], history)
            self.assertEqual(saved["model"], MODEL)
        self.assertEqual(session.stat().st_mode & 0o777, 0o600)

    def test_no_session_leaves_explicit_session_untouched(self):
        session_path = self.session(history=[{"role": "user", "content": "Old turn"}], last_response_id="resp_old")
        before = Path(session_path).read_bytes()
        self.assert_success(self.run_script("--input", "Hello", "--session-file", session_path, "--no-session"))
        self.assertNotIn("previous_response_id", self.requests()[0]["payload"])
        self.assertEqual(Path(session_path).read_bytes(), before)

    def test_new_session_replaces_state_only_after_success(self):
        session_path = self.session(history=[{"role": "user", "content": "Old turn"}], last_response_id="resp_old")
        before = Path(session_path).read_bytes()
        self.env["MOCK_STATUS"] = "500"
        self.assertNotEqual(self.run_script("--input", "Hello", "--session-file", session_path, "--new-session").returncode, 0)
        self.assertEqual(Path(session_path).read_bytes(), before)
        self.assertNotIn("previous_response_id", self.requests()[0]["payload"])
        self.env["MOCK_STATUS"] = "200"
        self.assert_success(self.run_script("--input", "Hello", "--session-file", session_path, "--new"))
        self.assertEqual(self.requests()[-1]["payload"]["input"], [{"role": "user", "content": "Hello"}])
        saved = json.loads(Path(session_path).read_text())
        self.assertEqual(saved["last_response_id"], "resp_test_123")
        self.assertEqual(saved["history"], [{"role": "user", "content": "Hello"}] + json.loads(self.response.read_text())["output"])

    def test_automatic_session_uses_model_specific_filename(self):
        self.env["FREVANA_SESSION_ID"] = "test-conversation"
        self.assert_success(self.run_script("--input", "Hello"))
        path = self.root / "sessions" / f"test-conversation_{SLUG}.json"
        self.assertEqual(json.loads(path.read_text())["model"], MODEL)

    def test_http_and_protocol_errors_preserve_output_and_session(self):
        output = self.root / "output.json"
        output.write_text("existing output")
        session_path = self.session(history=[{"role": "user", "content": "Old turn"}], last_response_id="resp_old")
        before = Path(session_path).read_bytes()
        cases = [("429", '{"error":"rate limited"}'), ("200", "not JSON"), ("200", "[]"), ("200", "")]
        for status, body in cases:
            with self.subTest(status=status, body=body):
                self.env["MOCK_STATUS"] = status
                self.response.write_text(body)
                count = len(self.requests())
                result = self.run_script("--input", "Hello", "--output", str(output), "--session-file", session_path)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(len(self.requests()), count + 1)
                self.assertEqual(output.read_text(), "existing output")
                self.assertEqual(Path(session_path).read_bytes(), before)

    def test_api_origin_normalization(self):
        self.env["FREVANA_API_BASE_URL"] = "https://gateway.example///"
        self.assert_success(self.run_script("--input", "Hello"))
        self.assertEqual(self.requests()[0]["url"], "https://gateway.example/openrouter/v1/responses")
        self.env["FREVANA_API_BASE_URL"] = "https://bad.example?query=1"
        count = len(self.requests())
        self.assertNotEqual(self.run_script("--input", "Hello").returncode, 0)
        self.assertEqual(len(self.requests()), count)

    def test_interactive_chat_keeps_parameters_and_session(self):
        self.assert_success(self.run_script("--chat", "--reasoning-effort", "high", "--service-tier", "default", "--max-output-tokens", "100", "--tools", '[{"type":"web_search"}]', stdin="First turn\nSecond turn\nquit\n"))
        requests = self.requests()
        self.assertEqual(len(requests), 2)
        for request in requests:
            self.assertEqual(request["payload"]["reasoning"], {"effort": "high"})
            self.assertEqual(request["payload"]["service_tier"], "default")
            self.assertEqual(request["payload"]["max_output_tokens"], 100)
            self.assertEqual(request["payload"]["tools"], [{"type": "web_search"}])
        self.assertEqual(requests[1]["payload"]["input"], [{"role": "user", "content": "First turn"}] + json.loads(self.response.read_text())["output"] + [{"role": "user", "content": "Second turn"}])
        self.assertNotIn("previous_response_id", requests[1]["payload"])


    def test_full_reasoning_and_tool_items_round_trip_in_order(self):
        native_output = [
            {"id": "rs_1", "type": "reasoning", "summary": [], "encrypted_content": "opaque-ciphertext"},
            {"id": "ws_1", "type": "web_search_call", "status": "completed", "action": {"type": "search", "query": "example"}},
            {"id": "fc_1", "type": "function_call", "call_id": "call_1", "name": "lookup", "arguments": '{"key":"value"}', "status": "completed"},
        ]
        self.response.write_text(json.dumps({"id": "resp_tools", "status": "completed", "output": native_output}))
        session = self.root / "tools-session.json"
        self.assert_success(self.run_script("--input", "Research", "--session-file", str(session)))
        tool_result = {"type": "function_call_output", "call_id": "call_1", "output": "Tool result"}
        self.assert_success(self.run_script("--input", json.dumps([tool_result]), "--session-file", str(session)))
        self.assertEqual(self.requests()[-1]["payload"]["input"], [{"role": "user", "content": "Research"}] + native_output + [tool_result])

    def test_session_replays_multimodal_input_without_flattening(self):
        message = {"role": "user", "content": [{"type": "input_text", "text": "Describe"}, {"type": "input_image", "image_url": "data:image/png;base64,test"}]}
        session = self.root / "image-session.json"
        self.assert_success(self.run_script("--input", json.dumps([message]), "--session-file", str(session)))
        self.assert_success(self.run_script("--input", "More detail", "--session-file", str(session)))
        self.assertEqual(self.requests()[-1]["payload"]["input"][0], message)

    def test_instructions_persist_and_can_be_overridden(self):
        session = self.root / "instruction-session.json"
        self.assert_success(self.run_script("--input", "First", "--instructions", "Answer in Chinese", "--session-file", str(session)))
        self.assert_success(self.run_script("--input", "Second", "--session-file", str(session)))
        self.assertEqual(self.requests()[-1]["payload"]["instructions"], "Answer in Chinese")
        self.assert_success(self.run_script("--input", "Third", "--instructions", "Answer in English", "--session-file", str(session)))
        self.assertEqual(self.requests()[-1]["payload"]["instructions"], "Answer in English")

    def test_invalid_legacy_and_mismatched_sessions_stop_before_transport(self):
        cases = ["{broken", "[]", json.dumps({"model": MODEL, "last_response_id": "resp_legacy"}),
            json.dumps({"schema_version": 1, "model": "other-model", "api_base_url": "https://ai-factory.frevana.com", "history": []}),
            json.dumps({"schema_version": 1, "model": MODEL, "api_base_url": "https://other.example", "history": []}),
            json.dumps({"schema_version": 1, "model": MODEL, "api_base_url": "https://ai-factory.frevana.com", "history": ["invalid item"]})]
        for contents in cases:
            with self.subTest(contents=contents):
                session = self.root / "invalid-session.json"
                session.write_text(contents)
                result = self.run_script("--input", "Next turn", "--session-file", str(session))
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(session.read_text(), contents)
        self.assertEqual(self.requests(), [])

    def test_new_session_can_replace_legacy_state_after_success(self):
        session = self.write_json("legacy.json", {"model": MODEL, "last_response_id": "resp_legacy"})
        self.assert_success(self.run_script("--input", "Fresh start", "--session-file", session, "--new-session"))
        self.assertEqual(self.requests()[0]["payload"]["input"], [{"role": "user", "content": "Fresh start"}])
        self.assertEqual(json.loads(Path(session).read_text())["schema_version"], 1)

    def test_response_id_and_stored_conversation_are_rejected(self):
        result = self.run_script("--input", "Hello", "--previous-response-id", "resp_old")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("store:false", result.stderr)
        session = self.session(history=[{"role": "user", "content": "Original"}])
        before = Path(session).read_bytes()
        for extra in ({"previous_response_id": "resp_old"}, {"conversation": "conv_old"}):
            raw = self.write_json("stored.json", {"input": "Hello", **extra})
            for reset in ([], ["--new-session"]):
                self.assertNotEqual(self.run_script("--raw-payload-file", raw, "--session-file", session, *reset).returncode, 0)
                self.assertEqual(Path(session).read_bytes(), before)
        self.assertEqual(self.requests(), [])

    def test_raw_session_include_and_reasoning_settings_are_preserved(self):
        raw = self.write_json("raw-session.json", {"input": "Hello", "include": ["web_search_call.action.sources"], "reasoning": {"effort": "high", "summary": "auto"}, "store": True})
        session = self.root / "raw-session-history.json"
        self.assert_success(self.run_script("--raw-payload-file", raw, "--session-file", str(session), "--reasoning-effort", "high"))
        request = self.requests()[0]["payload"]
        self.assertFalse(request["store"])
        self.assertEqual(request["reasoning"], {"effort": "high", "summary": "auto"})
        self.assertEqual(request["include"], ["web_search_call.action.sources"])
        self.assertNotIn("test-token", session.read_text())

    def test_unwritable_session_path_fails_before_transport(self):
        directory = self.root / "is-directory"
        directory.mkdir()
        result = self.run_script("--input", "Hello", "--session-file", str(directory))
        self.assertNotEqual(result.returncode, 0)
        blocker = self.root / "not-a-directory"
        blocker.write_text("blocker")
        self.assertNotEqual(self.run_script("--input", "Hello", "--session-file", str(blocker / "session.json")).returncode, 0)
        self.assertEqual(self.requests(), [])

    def test_failed_response_does_not_replace_session_or_output(self):
        session = self.session(history=[{"role": "user", "content": "Original"}])
        before = Path(session).read_bytes()
        output = self.root / "output.json"
        output.write_text("Original output")
        responses = [
            {"id": "resp_failed", "status": "failed", "error": {"code": "server_error"}, "output": []},
            {"id": "resp_failed", "status": "failed", "error": None, "output": []},
            {"id": "resp_cancelled", "status": "cancelled", "error": None, "output": []},
            {"id": "resp_pending", "status": "in_progress", "output": []},
            {"error": {"message": "Failure"}}, {"id": "not-a-complete-response"},
        ]
        for response in responses:
            self.response.write_text(json.dumps(response))
            for reset in ([], ["--new-session"]):
                with self.subTest(response=response, reset=reset):
                    count = len(self.requests())
                    result = self.run_script("--input", "Next", "--session-file", session, "--output", str(output), *reset)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(len(self.requests()), count + 1)
                    self.assertEqual(Path(session).read_bytes(), before)
                    self.assertEqual(output.read_text(), "Original output")

    def test_save_failure_reports_recovery_and_preserves_prior_session(self):
        session = self.session(history=[{"role": "user", "content": "Original"}])
        before = Path(session).read_bytes()
        # The output parent is a regular file, so only post-response persistence fails.
        blocker = self.root / "block-output"
        blocker.write_text("blocker")
        result = self.run_script("--input", "Next", "--session-file", session, "--output", str(blocker / "result.json"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Persistence failed", result.stderr)
        self.assertEqual(Path(session).read_bytes(), before)
        recovery_path = Path(result.stderr.split("Response/history saved to ", 1)[1].split(";", 1)[0])
        self.addCleanup(recovery_path.unlink)
        recovery = json.loads(recovery_path.read_text())
        self.assertEqual(recovery["history"][-2], {"role": "user", "content": "Next"})
        self.assertEqual(recovery["recovery_response"], json.loads(self.response.read_text()))
        self.assertEqual(recovery_path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn("test-token", recovery_path.read_text())
        self.assert_success(self.run_script("--input", "Continue after recovery", "--session-file", str(recovery_path)))
        self.assertEqual(self.requests()[-1]["payload"]["input"], recovery["history"] + [{"role": "user", "content": "Continue after recovery"}])

    def test_atomic_session_write_failure_preserves_state_and_recovers_response(self):
        session = self.session(history=[{"role": "user", "content": "Original"}])
        before = Path(session).read_bytes()
        # Fail the actual session replacement, after the mocked API already responded.
        (self.root / "sitecustomize.py").write_text("""import os
original_replace = os.replace

def fail_session_replace(source, destination, *args, **kwargs):
    if os.path.abspath(destination) == os.environ.get('MOCK_FAIL_SESSION_REPLACE'):
        raise OSError('Simulated session replacement failure')
    return original_replace(source, destination, *args, **kwargs)

os.replace = fail_session_replace
""")
        self.env["PYTHONPATH"] = str(self.root) + os.pathsep + self.env.get("PYTHONPATH", "")
        self.env["MOCK_FAIL_SESSION_REPLACE"] = str(Path(session).absolute())
        result = self.run_script("--input", "New turn", "--session-file", session)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("Simulated session replacement failure", result.stderr)
        self.assertEqual(Path(session).read_bytes(), before)
        self.assertEqual(len(self.requests()), 1)
        self.assertEqual(list(self.root.glob(".session.json.*")), [])
        recovery_path = Path(result.stderr.split("Response/history saved to ", 1)[1].split(";", 1)[0])
        self.addCleanup(recovery_path.unlink)
        recovery = json.loads(recovery_path.read_text())
        self.assertEqual(recovery["history"], [{"role": "user", "content": "Original"}, {"role": "user", "content": "New turn"}] + json.loads(self.response.read_text())["output"])
        self.assertEqual(recovery["recovery_response"], json.loads(self.response.read_text()))
        self.assert_success(self.run_script("--input", "Next turn", "--session-file", str(recovery_path)))
        self.assertEqual(self.requests()[-1]["payload"]["input"], recovery["history"] + [{"role": "user", "content": "Next turn"}])

    def test_failed_chat_turn_stops_without_consuming_more_api_calls(self):
        session = self.session(history=[{"role": "user", "content": "Original"}])
        before = Path(session).read_bytes()
        self.response.write_text(json.dumps({"id": "resp_failed", "status": "failed", "error": {"code": "server_error"}, "output": []}))
        result = self.run_script("--chat", "--session-file", session, stdin="First turn\nSecond turn\nquit\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.requests()), 1)
        self.assertEqual(Path(session).read_bytes(), before)

    def test_changed_session_is_preserved_and_new_turn_is_recoverable(self):
        session = self.session(history=[{"role": "user", "content": "Original"}])
        self.env["MOCK_SESSION_TARGET"] = session
        self.env["MOCK_SESSION_CONTENT"] = "Modified by another invocation"
        result = self.run_script("--input", "New turn", "--session-file", session)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(Path(session).read_text(), "Modified by another invocation")
        self.assertIn("Session changed during the request", result.stderr)
        recovery_path = Path(result.stderr.split("Response/history saved to ", 1)[1].split(";", 1)[0])
        self.addCleanup(recovery_path.unlink)
        recovery = json.loads(recovery_path.read_text())
        self.assertEqual(recovery["history"][1], {"role": "user", "content": "New turn"})
        self.assertEqual(recovery["recovery_response"], json.loads(self.response.read_text()))
        self.assertEqual(len(self.requests()), 1)

    def test_chat_without_persistence_keeps_history_for_current_run(self):
        session = self.session(history=[{"role": "user", "content": "Unrelated"}])
        before = Path(session).read_bytes()
        self.assert_success(self.run_script("--chat", "--no-session", "--session-file", session, stdin="First\nSecond\nquit\n"))
        self.assertEqual(len(self.requests()), 2)
        self.assertEqual(self.requests()[1]["payload"]["input"][0], {"role": "user", "content": "First"})
        self.assertEqual(Path(session).read_bytes(), before)

    def test_session_and_full_output_cannot_share_a_file(self):
        session = self.root / "same.json"
        self.assertNotEqual(self.run_script("--input", "Hello", "--session-file", str(session), "--output", str(session)).returncode, 0)
        self.assertEqual(self.requests(), [])



    def test_model_alias_and_raw_alias_are_normalized(self):
        self.assert_success(self.run_script("--input", "Hello", "--model", SLUG))
        raw = self.write_json("alias.json", {"model": SLUG, "input": "Hello"})
        self.assert_success(self.run_script("--raw-payload-file", raw))
        self.assertTrue(all(request["payload"]["model"] == MODEL for request in self.requests()))

    def test_web_search_flag_adds_server_tool_without_changing_model(self):
        self.assert_success(self.run_script("--input", "Find recent research", "--web-search"))
        payload = self.requests()[0]["payload"]
        self.assertEqual(payload["tools"], [{"type": "openrouter:web_search"}])
        self.assertEqual(payload["model"], MODEL)
        self.assertNotIn("plugins", payload)

    def test_native_search_and_explicit_auto_engine(self):
        self.assert_success(self.run_script("--input", "Latest news", "--web-search-engine", "native"))
        self.assertEqual(self.requests()[-1]["payload"]["tools"], [{"type": "openrouter:web_search", "parameters": {"engine": "native"}}])
        self.assert_success(self.run_script("--input", "Latest news", "--tools", '[{"type":"openrouter:web_search","parameters":{"engine":"native","max_results":3}}]', "--web-search-engine", "auto"))
        self.assertEqual(self.requests()[-1]["payload"]["tools"], [{"type": "openrouter:web_search", "parameters": {"engine": "auto", "max_results": 3}}])

    def test_web_search_merges_raw_config_and_preserves_provider_tools(self):
        provider = {"only": ["meta" if SLUG == "muse-wonder" else "xai"], "allow_fallbacks": False, "require_parameters": True}
        tools = [{"type": "function", "name": "lookup", "parameters": {"type": "object"}},
                 {"type": "openrouter:web_search", "parameters": {"engine": "native", "max_results": 3}}]
        plugins = [{"id": "response-healing"}]
        raw = self.write_json("search.json", {"input": "Latest news", "plugins": plugins, "provider": provider, "tools": tools})
        self.assert_success(self.run_script("--raw-payload-file", raw, "--web-search"))
        payload = self.requests()[0]["payload"]
        self.assertEqual(payload["plugins"], plugins)
        self.assertEqual(payload["provider"], provider)
        self.assertEqual(payload["tools"], tools)
        self.assertNotIn(":online", payload["model"])

    def test_plugin_file_and_inline_cli_override_raw_plugins(self):
        plugins = [{"id": "web", "engine": "native", "search_prompt": "Cite sources"}]
        path = self.write_json("plugins.json", plugins)
        raw = self.write_json("raw.json", {"input": "Latest news", "plugins": [{"id": "response-healing"}]})
        self.assert_success(self.run_script("--raw-payload-file", raw, "--plugins-file", path))
        self.assertEqual(self.requests()[-1]["payload"]["plugins"], plugins)
        self.assert_success(self.run_script("--raw-payload-file", raw, "--plugins", json.dumps(plugins)))
        self.assertEqual(self.requests()[-1]["payload"]["plugins"], plugins)

    def test_invalid_search_configuration_fails_without_transport(self):
        for plugins in ({}, [None], [{}], [{"id": 1}], [{"id": "web"}, {"id": "web"}]):
            with self.subTest(plugins=plugins):
                self.assertNotEqual(self.run_script("--input", "Hi", "--plugins", json.dumps(plugins), "--web-search").returncode, 0)
                raw = self.write_json("bad-search.json", {"input": "Hi", "plugins": plugins})
                self.assertNotEqual(self.run_script("--raw-payload-file", raw).returncode, 0)
        for args in (("--web-search-engine", "bogus"), ("--plugins-file", str(self.root / "missing.json")),
                     ("--plugins", "[]", "--plugins-file", "missing.json"),
                     ("--web-search", "--plugins", '[{"id":"web","enabled":false}]')):
            self.assertNotEqual(self.run_script("--input", "Hi", *args).returncode, 0)
        for flag in ("--web-search-engine", "--plugins", "--plugins-file"):
            self.assertNotEqual(self.run_script("--input", "Hi", flag).returncode, 0)
        self.assertEqual(self.requests(), [])

    def test_chat_preserves_web_search_every_turn(self):
        self.assert_success(self.run_script("--chat", "--web-search-engine", "native", "--tools", '[{"type":"openrouter:web_search","parameters":{"max_results":3}}]', stdin="First\nSecond\nquit\n"))
        self.assertEqual(len(self.requests()), 2)
        for request in self.requests():
            self.assertEqual(request["payload"]["tools"], [{"type": "openrouter:web_search", "parameters": {"engine": "native", "max_results": 3}}])

    def test_search_annotations_and_usage_survive_output_and_history(self):
        response = json.loads(self.response.read_text())
        annotation = {"type": "url_citation", "url": "https://example.com/research", "title": "Research", "start_index": 0, "end_index": 4}
        response["output"][0]["content"][0]["annotations"] = [annotation]
        response["usage"] = {"input_tokens": 100, "output_tokens": 30, "cost": 0.15, "server_tool_use_details": {"web_search_requests": 1}}
        self.response.write_text(json.dumps(response))
        session = self.root / "search-session.json"
        output = self.root / "search-output.json"
        result = self.run_script("--input", "Latest research", "--web-search", "--session-file", str(session), "--output", str(output))
        self.assert_success(result)
        self.assertEqual(json.loads(result.stdout), response)
        self.assertEqual(json.loads(output.read_text()), response)
        self.assertEqual(json.loads(session.read_text())["history"][-1], response["output"][0])

    def test_incomplete_response_is_preserved_without_automatic_continuation(self):
        response = json.loads(self.response.read_text())
        response.update(status="incomplete", incomplete_details={"reason": "max_output_tokens"})
        self.response.write_text(json.dumps(response))
        result = self.run_script("--input", "Hello", "--web-search")
        self.assert_success(result)
        self.assertEqual(json.loads(result.stdout), response)
        self.assertEqual(len(self.requests()), 1)


    def test_search_flag_appends_to_function_tools_and_preserves_other_plugins(self):
        tools = [{"type": "function", "name": "lookup", "parameters": {"type": "object"}}]
        self.assert_success(self.run_script("--input", "Research", "--tools", json.dumps(tools), "--plugins", '[{"id":"response-healing"}]', "--web-search"))
        payload = self.requests()[0]["payload"]
        self.assertEqual(payload["tools"], tools + [{"type": "openrouter:web_search"}])
        self.assertEqual(payload["plugins"], [{"id": "response-healing"}])

    def test_invalid_server_tool_configuration_and_legacy_conflicts_stop_before_transport(self):
        for tools in ([{"type": "openrouter:web_search", "parameters": []}],
                      [{"type": "openrouter:web_search"}, {"type": "openrouter:web_search"}]):
            self.assertNotEqual(self.run_script("--input", "Hi", "--tools", json.dumps(tools), "--web-search").returncode, 0)
        for flags in (("--web-search",), ("--web-search-engine", "native")):
            self.assertNotEqual(self.run_script("--input", "Hi", "--plugins", '[{"id":"web"}]', *flags).returncode, 0)
        self.assertEqual(self.requests(), [])

if __name__ == "__main__":
    unittest.main()
