import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "create_response.sh"


class ClaudeOpus5CreateResponseTests(unittest.TestCase):
    def run_script(self, *args: str, env=None, input=None):
        run_env = os.environ.copy() if env is None else env.copy()
        python_bin_dir = str(Path(sys.executable).parent)
        run_env["PATH"] = f"{python_bin_dir}{os.pathsep}{run_env.get('PATH', '')}"
        return subprocess.run(
            ["bash", str(SCRIPT), *args],
            input=input,
            text=True,
            capture_output=True,
            env=run_env,
            check=False,
        )

    def test_rejects_missing_input(self):
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing required argument", result.stderr)

    def test_rejects_invalid_model(self):
        result = self.run_script("--input", "hello", "--model", "gpt-4.1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid model", result.stderr)

    def test_accepts_model_aliases(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            fake_curl = temp_path / "curl"
            fake_curl.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
response=''
data_file=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o) response="$2"; shift 2 ;;
    --data) data_file="${2#@}"; shift 2 ;;
    *) shift ;;
  esac
done
python3 - "$response" "$data_file" <<'PY'
import json, sys
with open(sys.argv[2], encoding="utf-8") as f:
    req = json.load(f)
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump({"id": "resp_test", "model": req.get("model"), "output_text": "ok"}, f)
PY
printf '200'
""",
                encoding="utf-8",
            )
            fake_curl.chmod(0o755)
            env = os.environ.copy()
            python_bin_dir = str(Path(sys.executable).parent)
            env.update({
                "PATH": f"{temp}{os.pathsep}{python_bin_dir}{os.pathsep}{env['PATH']}",
                "FREVANA_TOKEN": "test-token",
            })

            # alias 1: claude-opus-5
            res1 = self.run_script("--input", "hi", "--model", "claude-opus-5", env=env)
            self.assertEqual(res1.returncode, 0, res1.stderr)
            self.assertEqual(json.loads(res1.stdout)["model"], "anthropic/claude-opus-5")

            # alias 2: claude-ops-5
            res2 = self.run_script("--input", "hi", "--model", "claude-ops-5", env=env)
            self.assertEqual(res2.returncode, 0, res2.stderr)
            self.assertEqual(json.loads(res2.stdout)["model"], "anthropic/claude-opus-5")

    def test_rejects_invalid_reasoning_effort(self):
        result = self.run_script("--input", "hello", "--reasoning-effort", "extreme")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid --reasoning-effort", result.stderr)

    def test_rejects_invalid_temperature(self):
        result = self.run_script("--input", "hello", "--temperature", "3.0")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid --temperature", result.stderr)

    def test_rejects_invalid_top_p(self):
        result = self.run_script("--input", "hello", "--top-p", "1.5")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid --top-p", result.stderr)

    def test_rejects_invalid_service_tier(self):
        result = self.run_script("--input", "hello", "--service-tier", "hyperspeed")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid --service-tier", result.stderr)

    def test_payload_and_headers_reach_backend(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            fake_curl = temp_path / "curl"
            fake_curl.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
response=''
headers=()
data_file=''
target_url=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o) response="$2"; shift 2 ;;
    -H) headers+=("$2"); shift 2 ;;
    --data) data_file="${2#@}"; shift 2 ;;
    -X) shift 2 ;;
    http*|/*) target_url="$1"; shift ;;
    *) shift ;;
  esac
done

python3 - "$response" "$data_file" "$target_url" "${headers[@]}" <<'PY'
import json, sys
response_file = sys.argv[1]
data_file = sys.argv[2]
target_url = sys.argv[3]
headers = sys.argv[4:]

with open(data_file, encoding="utf-8") as f:
    req = json.load(f)

with open(response_file, "w", encoding="utf-8") as f:
    json.dump({
        "id": "resp_test123",
        "object": "response",
        "model": req.get("model"),
        "output_text": "Processed answer from claude opus 5",
        "output": [{
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Processed answer from claude opus 5"}]
        }],
        "captured_payload": req,
        "captured_headers": headers,
        "captured_url": target_url,
    }, f)
PY
printf '200'
""",
                encoding="utf-8",
            )
            fake_curl.chmod(0o755)

            env = os.environ.copy()
            python_bin_dir = str(Path(sys.executable).parent)
            env.update(
                {
                    "PATH": f"{temp}{os.pathsep}{python_bin_dir}{os.pathsep}{env['PATH']}",
                    "FREVANA_TOKEN": "opus-token",
                    "FREVANA_API_KEY": "opus-api-key",
                    "FREVANA_AGENT_APP_INSTANCE_ID": "instance-opus-1",
                }
            )

            result = self.run_script(
                "--input", "Explain category theory in functional programming",
                "--instructions", "Be rigorous and provide Haskell examples.",
                "--reasoning-effort", "high",
                "--temperature", "0.7",
                "--top-p", "0.95",
                "--max-output-tokens", "4096",
                "--service-tier", "ultrafast",
                "--previous-response-id", "resp_prev001",
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            req = payload["captured_payload"]
            self.assertEqual(req["model"], "anthropic/claude-opus-5")
            self.assertEqual(req["input"], "Explain category theory in functional programming")
            self.assertEqual(req["instructions"], "Be rigorous and provide Haskell examples.")
            self.assertEqual(req["reasoning"], {"effort": "high"})
            self.assertEqual(req["temperature"], 0.7)
            self.assertEqual(req["top_p"], 0.95)
            self.assertEqual(req["max_output_tokens"], 4096)
            self.assertEqual(req["service_tier"], "ultrafast")
            self.assertEqual(req["previous_response_id"], "resp_prev001")

            headers = payload["captured_headers"]
            self.assertIn("Authorization: Bearer opus-token", headers)
            self.assertIn("X-API-Key: opus-api-key", headers)
            self.assertIn("x-frevana-agent-app-instance-id: instance-opus-1", headers)

    def test_text_only_mode(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            fake_curl = temp_path / "curl"
            fake_curl.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
response=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o) response="$2"; shift 2 ;;
    *) shift ;;
  esac
done
printf '{"id":"resp_abc","output_text":"Only this text should be visible."}' > "$response"
printf '200'
""",
                encoding="utf-8",
            )
            fake_curl.chmod(0o755)
            env = os.environ.copy()
            python_bin_dir = str(Path(sys.executable).parent)
            env.update(
                {
                    "PATH": f"{temp}{os.pathsep}{python_bin_dir}{os.pathsep}{env['PATH']}",
                    "FREVANA_TOKEN": "test-token",
                }
            )

            result = self.run_script("--input", "hi", "--text-only", env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "Only this text should be visible.")

    def test_agent_app_instance_id_env_and_flag(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            fake_curl = temp_path / "curl"
            fake_curl.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
response=''
headers=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o) response="$2"; shift 2 ;;
    -H) headers+=("$2"); shift 2 ;;
    *) shift ;;
  esac
done
python3 - "$response" "${headers[@]}" <<'PY'
import json, sys
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump({
        "id": "resp_test",
        "output_text": "ok",
        "captured_headers": sys.argv[2:],
    }, f)
PY
printf '200'
""",
                encoding="utf-8",
            )
            fake_curl.chmod(0o755)

            # Test 1: FREVANA_AGENT_APP_INSTANCE_ID
            env1 = os.environ.copy()
            python_bin_dir = str(Path(sys.executable).parent)
            env1.update(
                {
                    "PATH": f"{temp}{os.pathsep}{python_bin_dir}{os.pathsep}{env1['PATH']}",
                    "FREVANA_TOKEN": "token-1",
                    "FREVANA_AGENT_APP_INSTANCE_ID": "instance-env-1",
                }
            )
            res1 = self.run_script("--input", "test", env=env1)
            self.assertEqual(res1.returncode, 0, res1.stderr)
            headers1 = json.loads(res1.stdout)["captured_headers"]
            self.assertIn("x-frevana-agent-app-instance-id: instance-env-1", headers1)

            # Test 2: CLI flag --agent-app-instance-id overrides env
            env2 = os.environ.copy()
            env2.update(
                {
                    "PATH": f"{temp}{os.pathsep}{python_bin_dir}{os.pathsep}{env2['PATH']}",
                    "FREVANA_TOKEN": "token-2",
                    "FREVANA_AGENT_APP_INSTANCE_ID": "instance-env-old",
                }
            )
            res2 = self.run_script("--input", "test", "--agent-app-instance-id", "instance-flag-override", env=env2)
            self.assertEqual(res2.returncode, 0, res2.stderr)
            headers2 = json.loads(res2.stdout)["captured_headers"]
            self.assertIn("x-frevana-agent-app-instance-id: instance-flag-override", headers2)

    def test_session_file_preserves_and_chains_context(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            fake_curl = temp_path / "curl"
            fake_curl.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
response=''
data_file=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o) response="$2"; shift 2 ;;
    --data) data_file="${2#@}"; shift 2 ;;
    *) shift ;;
  esac
done

python3 - "$response" "$data_file" <<'PY'
import json, sys
response_file, data_file = sys.argv[1], sys.argv[2]
with open(data_file, encoding="utf-8") as f:
    req = json.load(f)

turn = 2 if "previous_response_id" in req else 1
with open(response_file, "w", encoding="utf-8") as f:
    json.dump({
        "id": f"resp_turn_{turn}",
        "object": "response",
        "model": req.get("model"),
        "output_text": f"Response for turn {turn}",
        "captured_payload": req,
    }, f)
PY
printf '200'
""",
                encoding="utf-8",
            )
            fake_curl.chmod(0o755)

            session_file = temp_path / "session.json"
            python_bin_dir = str(Path(sys.executable).parent)
            env = os.environ.copy()
            env.update({
                "PATH": f"{temp}{os.pathsep}{python_bin_dir}{os.pathsep}{env['PATH']}",
                "FREVANA_TOKEN": "test-token",
            })

            # Turn 1
            res1 = self.run_script("--session-file", str(session_file), "--input", "Hello turn 1", env=env)
            self.assertEqual(res1.returncode, 0, res1.stderr)
            data1 = json.loads(res1.stdout)
            self.assertEqual(data1["id"], "resp_turn_1")
            self.assertNotIn("previous_response_id", data1["captured_payload"])

            # Verify session file was created and contains resp_turn_1
            self.assertTrue(session_file.exists())
            with open(session_file, encoding="utf-8") as f:
                saved_session = json.load(f)
            self.assertEqual(saved_session["last_response_id"], "resp_turn_1")

            # Turn 2: run with the same session file
            res2 = self.run_script("--session-file", str(session_file), "--input", "Hello turn 2", env=env)
            self.assertEqual(res2.returncode, 0, res2.stderr)
            data2 = json.loads(res2.stdout)
            self.assertEqual(data2["id"], "resp_turn_2")
            self.assertEqual(data2["captured_payload"]["previous_response_id"], "resp_turn_1")

            # Verify session file now points to resp_turn_2
            with open(session_file, encoding="utf-8") as f:
                saved_session2 = json.load(f)
            self.assertEqual(saved_session2["last_response_id"], "resp_turn_2")

    def test_auto_session_via_env_conversation_id(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            fake_curl = temp_path / "curl"
            fake_curl.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
response=''
data_file=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o) response="$2"; shift 2 ;;
    --data) data_file="${2#@}"; shift 2 ;;
    *) shift ;;
  esac
done

python3 - "$response" "$data_file" <<'PY'
import json, sys
response_file, data_file = sys.argv[1], sys.argv[2]
with open(data_file, encoding="utf-8") as f:
    req = json.load(f)

turn = 2 if "previous_response_id" in req else 1
with open(response_file, "w", encoding="utf-8") as f:
    json.dump({
        "id": f"resp_auto_{turn}",
        "object": "response",
        "model": req.get("model"),
        "output_text": f"Auto turn {turn}",
        "captured_payload": req,
    }, f)
PY
printf '200'
""",
                encoding="utf-8",
            )
            fake_curl.chmod(0o755)

            python_bin_dir = str(Path(sys.executable).parent)
            session_dir = temp_path / "sessions"
            env = os.environ.copy()
            env.update({
                "PATH": f"{temp}{os.pathsep}{python_bin_dir}{os.pathsep}{env['PATH']}",
                "FREVANA_TOKEN": "test-token",
                "CONVERSATION_ID": "chat-thread-opus-999",
                "FREVANA_SESSION_DIR": str(session_dir),
            })

            # Turn 1: without passing any session flags!
            res1 = self.run_script("--input", "My research area is topological data analysis", env=env)
            self.assertEqual(res1.returncode, 0, res1.stderr)
            data1 = json.loads(res1.stdout)
            self.assertEqual(data1["id"], "resp_auto_1")
            self.assertNotIn("previous_response_id", data1["captured_payload"])

            # Turn 2: without passing any session flags!
            res2 = self.run_script("--input", "What was my research area?", env=env)
            self.assertEqual(res2.returncode, 0, res2.stderr)
            data2 = json.loads(res2.stdout)
            self.assertEqual(data2["id"], "resp_auto_2")
            # Automatically chained previous response ID!
            self.assertEqual(data2["captured_payload"]["previous_response_id"], "resp_auto_1")


    def run_sequence(self, responses, *args, http_codes=None, raw_fields=None):
        # Mock complete request/response rounds, including the continuation payload.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "responses.json").write_text(json.dumps(responses))
            (root / "codes.json").write_text(json.dumps(http_codes or [200] * len(responses)))
            (root / "calls.json").write_text("[]")
            session = root / "session.json"
            session.write_text(json.dumps({"model": f"anthropic/{SCRIPT.parents[1].name}", "last_response_id": "old"}))
            original_session = session.read_text()
            fake = root / "curl"
            fake.write_text("#!/usr/bin/env python3\n" + '''import json, os, sys
from pathlib import Path
root = Path(os.environ["MOCK_ROOT"])
args = sys.argv[1:]
request_path = args[args.index("--data") + 1][1:]
calls = json.loads((root / "calls.json").read_text())
index = len(calls)
calls.append({"payload": json.loads(Path(request_path).read_text()), "args": args})
(root / "calls.json").write_text(json.dumps(calls))
responses = json.loads((root / "responses.json").read_text())
Path(args[args.index("-o") + 1]).write_text(json.dumps(responses[index]))
print(json.loads((root / "codes.json").read_text())[index], end="")
''')
            fake.chmod(0o755)
            env = os.environ.copy()
            env.update({"PATH": f"{temp}{os.pathsep}{env['PATH']}", "MOCK_ROOT": temp,
                        "FREVANA_TOKEN": "test-token", "FREVANA_AGENT_APP_INSTANCE_ID": "test-app"})
            raw = root / "raw.json"
            raw.write_text(json.dumps({"input": [{"role": "user", "content": "original"}],
                                       "temperature": 0.4, "metadata": {"test": "raw"},
                                       **({"previous_response_id": "raw_old", "store": True} if "STATEFUL_RAW_FILE" in args else {}),
                                       **(raw_fields or {})}))
            replaced_args = [str(raw) if a in ("RAW_FILE", "STATEFUL_RAW_FILE") else a for a in args]
            result = self.run_script("--input", "original", "--session-file", str(session),
                                     "--output", str(root / "result.json"), *replaced_args, env=env,
                                     input="original\nexit\n" if "--chat" in args else None)
            saved = root / "result.json"
            return (result, json.loads((root / "calls.json").read_text()),
                    json.loads(saved.read_text()) if saved.exists() else None,
                    session.read_text(), original_session)

    def truncated(self, text="abc", **updates):
        response = {"id": "first", "status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"},
                    "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}],
                    "usage": {"input_tokens": 10, "output_tokens": 3, "total_tokens": 13,
                              "output_tokens_details": {"reasoning_tokens": 1}}}
        response.update(updates)
        return response

    def test_continuation_stitches_text_json_and_usage(self):
        first = self.truncated("{\"name\":\"hel")
        second = self.truncated("lo", id="second", output_text="lo")
        last = {"id": "last", "status": "completed", "output_text": '\"}',
                "usage": {"input_tokens": 20, "output_tokens": 2, "total_tokens": 22}}
        result, calls, saved, session, _ = self.run_sequence(
            [first, second, last], "--new-session", "--max-output-tokens", "10",
            "--instructions", "strict JSON", "--reasoning-effort", "high", "--text-only")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '{"name":"hello"}\n')
        self.assertEqual(saved["output_text"], '{"name":"hello"}')
        self.assertEqual(saved["output"][0]["content"][0]["text"], saved["output_text"])
        self.assertEqual(saved["continuation"]["responses"], [first, second, last])
        self.assertEqual(saved["usage"]["input_tokens"], 40)
        self.assertEqual(saved["usage"]["output_tokens_details"]["reasoning_tokens"], 2)
        self.assertEqual(json.loads(session)["last_response_id"], "last")
        self.assertEqual(len(calls), 3)
        for call in calls[1:]:
            request = call["payload"]
            self.assertNotIn("previous_response_id", request)
            self.assertEqual(request["max_output_tokens"], 10)
            self.assertEqual(request["instructions"], "strict JSON")
            self.assertEqual(request["reasoning"], {"effort": "high"})
            self.assertIn("Authorization: Bearer test-token", call["args"])
            self.assertIn("x-frevana-agent-app-instance-id: test-app", call["args"])
        self.assertEqual(calls[1]["payload"]["input"][0]["content"], "original")
        self.assertEqual(calls[2]["payload"]["input"][-4]["content"], '{"name":"hel')
        self.assertEqual(calls[2]["payload"]["input"][-2]["content"], "lo")

    def test_continuation_works_without_session_and_with_raw_payload(self):
        result, calls, saved, session, original = self.run_sequence(
            [self.truncated(), {"id": "last", "status": "completed", "output_text": "def"}],
            "--no-session", "--raw-payload-file", "RAW_FILE")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["output_text"], "abcdef")
        self.assertEqual(calls[1]["payload"]["metadata"], {"test": "raw"})
        self.assertEqual(calls[1]["payload"]["temperature"], 0.4)
        self.assertEqual(session, original)

    def test_continuation_limit_preserves_partial_output_and_session(self):
        result, calls, saved, session, original = self.run_sequence(
            [self.truncated(), self.truncated("def", id="second")],
            "--new-session", "--max-continuations", "1", "--text-only")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result.stdout, "abcdef\n")
        self.assertEqual(saved["status"], "incomplete")
        self.assertEqual(session, original)

    def test_continuation_error_preserves_partial_output(self):
        for response, code in [({"error": {"message": "quota"}}, 429),
                               ({"status": "failed", "error": {"message": "failed"}}, 200)]:
            with self.subTest(code=code):
                result, calls, saved, session, original = self.run_sequence(
                    [self.truncated(), response], "--new-session", "--text-only", http_codes=[200, code])
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "abc\n")
                self.assertEqual(saved["output_text"], "abc")
                self.assertEqual(session, original)

    def test_does_not_retry_other_incomplete_reasons_empty_text_or_tools(self):
        cases = [self.truncated(incomplete_details={"reason": "content_filter"}),
                 self.truncated(""),
                 self.truncated(output=[{"type": "function_call", "arguments": "{", "call_id": "c1"}])]
        for response in cases:
            with self.subTest(response=response):
                result, calls, saved, session, original = self.run_sequence([response], "--new-session")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(len(calls), 1)
                self.assertEqual(saved["continuation"]["responses"], [response])
                self.assertEqual(session, original)

    def test_zero_continuations_and_invalid_limit(self):
        result, calls, saved, _, _ = self.run_sequence([self.truncated()], "--no-session", "--max-continuations", "0")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(saved["output_text"], "abc")
        for value in ("-1", "33", "abc", ""):
            invalid = self.run_script("--input", "hi", "--max-continuations", value)
            self.assertNotEqual(invalid.returncode, 0)

    def test_chat_continuation_preserves_options(self):
        result, calls, _, session, _ = self.run_sequence(
            [self.truncated(), {"id": "last", "status": "completed", "output_text": "def"}],
            "--chat", "--new-session", "--max-continuations", "1", "--max-output-tokens", "10",
            "--instructions", "keep format")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("abcdef", result.stdout)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1]["payload"]["instructions"], "keep format")
        self.assertEqual(calls[1]["payload"]["max_output_tokens"], 10)
        self.assertEqual(json.loads(session)["last_response_id"], "last")

    def test_final_tool_call_is_preserved_after_continuation(self):
        tool = {"type": "function_call", "name": "lookup", "call_id": "call_1", "arguments": "{}"}
        last = {"id": "last", "status": "completed", "output": [tool]}
        result, calls, saved, _, _ = self.run_sequence([self.truncated(), last], "--new-session")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(tool, saved["output"])
        self.assertEqual(saved["output_text"], "abc")

    def test_continuation_preserves_prior_conversation_anchor(self):
        responses = [self.truncated(), self.truncated("def", id="second"),
                     {"id": "last", "status": "completed", "output_text": "ghi"}]
        for args, expected in [((), "old"),
                               (("--no-session", "--previous-response-id", "explicit_old"), "explicit_old"),
                               (("--no-session", "--raw-payload-file", "STATEFUL_RAW_FILE"), "raw_old")]:
            with self.subTest(args=args):
                result, calls, saved, session, original = self.run_sequence(responses, *args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(saved["output_text"], "abcdefghi")
                self.assertEqual(len(calls), 3)
                for call in calls:
                    self.assertEqual(call["payload"]["previous_response_id"], expected)
                    if expected == "raw_old":
                        self.assertTrue(call["payload"]["store"])
                self.assertEqual(calls[1]["payload"]["input"][0]["content"], "original")
                self.assertEqual(calls[2]["payload"]["input"][-2]["content"], "def")
                if "--no-session" not in args:
                    self.assertEqual(json.loads(session)["last_response_id"], "last")
                else:
                    self.assertEqual(session, original)

    def test_completed_hosted_tools_are_replayed_and_pending_tools_stop(self):
        tool = {"type": "web_search_call", "id": "search_1", "status": "completed",
                "action": {"type": "search", "query": "example"}}
        first = self.truncated()
        first["output"].insert(0, tool)
        result, calls, saved, _, _ = self.run_sequence(
            [first, {"id": "last", "status": "completed", "output_text": "def"}], "--new-session")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(saved["output_text"], "abcdef")
        self.assertIn(tool, calls[1]["payload"]["input"])
        self.assertIn(tool, saved["output"])
        for pending in [{**tool, "status": "in_progress"},
                        {"type": "function_call", "status": "completed", "name": "write",
                         "call_id": "c1", "arguments": "{}"}]:
            first = self.truncated()
            first["output"].insert(0, pending)
            result, calls, saved, session, original = self.run_sequence([first], "--new-session")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(len(calls), 1)
            self.assertEqual(saved["output_text"], "abc")
            self.assertEqual(session, original)

    def test_structured_json_continuation_uses_unconstrained_suffix(self):
        schema = {"type": "json_schema", "name": "answer", "strict": True,
                  "schema": {"type": "object", "properties": {"name": {"type": "string"}},
                             "required": ["name"], "additionalProperties": False}}
        for fields in [{"text": {"format": schema, "verbosity": "low"}},
                       {"response_format": {"type": "json_object"}}]:
            with self.subTest(fields=fields):
                result, calls, saved, _, _ = self.run_sequence(
                    [self.truncated('{"name":"hel'),
                     {"id": "last", "status": "completed", "output_text": 'lo"}'}],
                    "--new-session", "--raw-payload-file", "RAW_FILE", raw_fields=fields)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(saved["output_text"]), {"name": "hello"})
                for key, value in fields.items():
                    self.assertEqual(calls[0]["payload"][key], value)
                continued = calls[1]["payload"]
                if "text" in fields:
                    self.assertEqual(continued["text"], {"format": {"type": "text"}, "verbosity": "low"})
                    self.assertIn('"required": ["name"]', continued["input"][-1]["content"])
                else:
                    self.assertNotIn("response_format", continued)

    def test_invalid_stitched_structured_json_preserves_partial_and_session(self):
        result, calls, saved, session, original = self.run_sequence(
            [self.truncated('{"name":"hel'),
             {"id": "last", "status": "completed", "output_text": '{"name":"hello"}'}],
            "--new-session", "--raw-payload-file", "RAW_FILE",
            raw_fields={"text": {"format": {"type": "json_object"}}})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not valid JSON", result.stderr)
        self.assertEqual(saved["status"], "incomplete")
        self.assertEqual(session, original)
        self.assertEqual(len(calls), 2)

    def test_single_response_is_unchanged(self):
        response = {"id": "last", "status": "completed", "output_text": "done", "usage": {"output_tokens": 1}}
        result, calls, saved, _, _ = self.run_sequence([response], "--new-session")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), response)
        self.assertEqual(saved, response)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
