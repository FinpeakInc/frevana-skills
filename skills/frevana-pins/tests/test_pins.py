"""Offline behavioral tests. Run: python3 -m unittest discover -s tests -p 'test_*.py'."""

import copy
import http.client
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pins


def record(identifier):
    return {"id": identifier, "kind": "image", "sourceUrl": "",
            "mediaUrl": "assets/" + identifier + ".png", "savedAt": 1}


def collection(identifier, ids):
    return {"id": identifier, "title": identifier, "pinIds": ids,
            "createdAt": 1, "updatedAt": 1}


class FakeClient:
    def __init__(self):
        self.snapshot = {"version": 1, "updatedAt": 1,
                         "pins": [record("a"), record("b")],
                         "collections": [collection("one", ["a"]), collection("two", ["b"])]}
        self.writes = []
        self.requests = []
        self.uploads = 0
        self.fail_write = False

    def store(self):
        return copy.deepcopy(self.snapshot)

    def request(self, method, path="", payload=None, **kwargs):
        self.requests.append((method, path, payload))
        if method == "PUT":
            if self.fail_write:
                raise pins.PinsError("write failed")
            self.writes.append(copy.deepcopy(payload))
            self.snapshot.update(copy.deepcopy(payload))
            self.snapshot["collections"].sort(key=lambda c: -c["updatedAt"])
            self.snapshot["updatedAt"] += 1
            for pin in self.snapshot["pins"]:
                if not pin["mediaUrl"].startswith("https:"):
                    pin["mediaUrl"] = "https://s3.example/pins/user/" + pins.media_identity(pin["mediaUrl"]) + "?X-Amz-Signature=new"
            return self.store()
        if path.startswith("/assets?"):
            return b"downloaded"
        if path == "/present":
            return {"urls": {value: "https://signed.example/file" for value in payload["urls"]}}
        if path == "/assets/upload-url":
            return {"path": "user/assets/a.png", "signedUrl": "https://signed.example/upload", "token": ""}
        raise AssertionError((method, path))

    def upload(self, file):
        self.uploads += 1
        return {"path": "user/assets/upload.png", "url": "https://signed.example/file"}, "image/png"


class MissingIndexClient(FakeClient):
    """The server returns Date.now() until the first index has been written."""
    def __init__(self):
        super().__init__()
        self.snapshot.update(pins=[], collections=[])

    def store(self):
        if not self.writes:
            self.snapshot["updatedAt"] += 1
        return super().store()


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = Path(self.tmp.name) / "photo.png"
        self.file.write_bytes(b"image")

    def run_command(self, *args):
        args = tuple(str(self.file) if value == "photo.png" else value for value in args)
        return pins.execute(self.client, pins.parser().parse_args(args))

    def test_move_removes_previous_membership_preserves_other_pins(self):
        self.run_command("collection", "move", "two", "--pin-ids", "a")
        self.assertEqual(pins.find(self.client.snapshot["collections"], "one", "Collection")["pinIds"], [])
        self.assertEqual(pins.find(self.client.snapshot["collections"], "two", "Collection")["pinIds"], ["b", "a"])
        self.assertEqual(set(self.client.writes[0]), {"collections"})

    def test_delete_collection_preserves_pins(self):
        self.run_command("collection", "delete", "one")
        self.assertEqual([p["id"] for p in self.client.snapshot["pins"]], ["a", "b"])
        self.assertEqual([c["id"] for c in self.client.snapshot["collections"]], ["two"])

    def test_remove_cleans_membership(self):
        self.run_command("remove", "a")
        self.assertEqual([p["id"] for p in self.client.snapshot["pins"]], ["b"])
        self.assertEqual(self.client.snapshot["collections"][0]["pinIds"], [])

    def test_upload_creates_pin_and_keeps_existing_records(self):
        result = self.run_command("upload", "photo.png", "--collection-id", "two")
        self.assertEqual(result["asset_path"], "user/assets/upload.png")
        self.assertEqual(len(self.client.snapshot["pins"]), 3)
        self.assertEqual(result["data"]["title"], "photo.png")
        self.assertIn(result["pin_id"], pins.find(self.client.snapshot["collections"], "two", "Collection")["pinIds"])

    def test_asset_only_does_not_write_library(self):
        self.run_command("upload", "photo.png", "--asset-only")
        self.assertEqual(self.client.writes, [])

    def test_limits_and_unknown_collection_prevent_upload(self):
        with self.assertRaises(pins.PinsError):
            self.run_command("upload", "photo.png", "--collection-id", "missing")
        self.client.snapshot["pins"] = [record(str(i)) for i in range(100)]
        with self.assertRaises(pins.PinsError):
            self.run_command("upload", "photo.png")
        self.assertEqual(self.client.uploads, 0)
        self.client.snapshot["collections"] = [collection(str(i), []) for i in range(40)]
        with self.assertRaises(pins.PinsError):
            self.run_command("collection", "create", "New")
        self.assertEqual(self.client.writes, [])

    def test_uploaded_path_survives_failed_save(self):
        self.client.fail_write = True
        with self.assertRaises(pins.PinsError) as caught:
            self.run_command("upload", "photo.png")
        self.assertEqual(caught.exception.details["asset_path"], "user/assets/upload.png")
        self.assertIn("pin_id", caught.exception.details)
        self.assertEqual(sum(r[0] == "PUT" for r in self.client.requests), 1)

    def test_concurrent_edit_stops_before_put(self):
        original = self.client.store()
        desired = copy.deepcopy(original)
        desired["pins"][0]["title"] = "My edit"
        self.client.snapshot["pins"][0]["title"] = "Another editor"
        with self.assertRaises(pins.PinsError):
            pins.save(self.client, original, desired, ["pins"])
        self.assertEqual(self.client.writes, [])

    def test_first_add_upload_and_collection_accept_fresh_empty_timestamps(self):
        for command in (("add", "--kind", "image", "--media-url", "https://example.com/a.png"),
                        ("upload", "photo.png"), ("collection", "create", "First")):
            with self.subTest(command=command[0]):
                self.client = MissingIndexClient()
                self.run_command(*command)
                self.assertEqual(len(self.client.writes), 1)
                field = "collections" if command[0] == "collection" else "pins"
                self.assertEqual(len(self.client.snapshot[field]), 1)

    def test_nonempty_timestamp_change_still_blocks_save(self):
        original = self.client.store()
        desired = copy.deepcopy(original)
        desired["pins"][0]["title"] = "My edit"
        self.client.snapshot["updatedAt"] += 1
        with self.assertRaises(pins.PinsError):
            pins.save(self.client, original, desired, ["pins"])
        self.assertEqual(self.client.writes, [])

    def test_empty_library_content_change_still_blocks_save(self):
        self.client = MissingIndexClient()
        original = self.client.store()
        desired = copy.deepcopy(original)
        desired["pins"] = [record("new")]
        self.client.snapshot["collections"] = [collection("concurrent", [])]
        with self.assertRaises(pins.PinsError):
            pins.save(self.client, original, desired, ["pins"])
        self.assertEqual(self.client.writes, [])

    def test_owned_url_conversion_passes_verification_for_media_and_poster(self):
        urls = (
            "https://s3.example/pins/user/assets/new.png",
            "https://s3.example/pins-dev/user/assets/new.png",
            "https://legacy.example/storage/v1/object/sign/pins/user/assets/new.png?token=old",
            "https://legacy.example/storage/v1/object/authenticated/pins/user/assets/new.png",
            "https://legacy.example/storage/v1/object/public/pins/user/assets/new.png",
        )
        for url in urls:
            with self.subTest(url=url):
                self.client = FakeClient()
                original_request = self.client.request
                def normalize(method, **kwargs):
                    response = original_request(method, **kwargs)
                    if method == "PUT":
                        self.client.snapshot["pins"][0].update(
                            mediaUrl="https://s3.example/pins/user/assets/new.png?X-Amz-Signature=new",
                            posterUrl="https://s3.example/pins/user/assets/poster.png?X-Amz-Signature=new")
                    return response
                self.client.request = normalize
                result = self.run_command("add", "--kind", "image", "--media-url", url,
                                          "--poster-url", url.replace("new.png", "poster.png"))
                self.assertEqual(result["pin_id"], self.client.snapshot["pins"][0]["id"])
                self.assertEqual(len(self.client.writes), 1)

    def test_external_assets_urls_are_not_treated_as_owned_refs(self):
        for url in ("https://external.example/assets/a.png",
                    "https://external.example/assets/a.png?X-Amz-Signature=external"):
            self.assertEqual(pins.media_identity(url), url)
            self.assertNotEqual(pins.media_identity(url), pins.media_identity(
                "https://s3.example/pins/user/assets/a.png?X-Amz-Signature=owned"))

    def test_verification_detects_media_replacement(self):
        original = self.client.store()
        original_request = self.client.request
        def corrupt(*args, **kwargs):
            result = original_request(*args, **kwargs)
            self.client.snapshot["pins"][0]["mediaUrl"] = "assets/wrong.png"
            return result
        self.client.request = corrupt
        with self.assertRaises(pins.PinsError):
            desired = copy.deepcopy(original)
            desired["pins"][0]["title"] = "My edit"
            pins.save(self.client, original, desired, ["pins"])

    def test_signed_url_refresh_does_not_report_conflict(self):
        self.client.snapshot["pins"][0]["mediaUrl"] = "https://s3.example/pins/user/assets/a.png?X-Amz-Signature=old"
        original = self.client.store()
        self.client.snapshot["pins"][0]["mediaUrl"] = "https://s3.example/pins/user/assets/a.png?X-Amz-Signature=new"
        desired = copy.deepcopy(original)
        desired["pins"][0]["title"] = "My edit"
        pins.save(self.client, original, desired, ["pins"])

    def test_download_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "a.png"
            result = self.run_command("download", "a", "--output", str(output))
            self.assertEqual(output.read_bytes(), b"downloaded")
            self.assertEqual(result["bytes_written"], 10)
            with self.assertRaises(pins.PinsError):
                self.run_command("download", "a", "--output", str(output))

    def test_add_present_and_upload_url(self):
        self.run_command("add", "--kind", "video", "--media-url", "https://example.com/v.mp4")
        self.assertEqual(self.client.snapshot["pins"][0]["kind"], "video")
        self.run_command("present", "assets/a.png")
        self.assertEqual(self.client.requests[-1][2], {"urls": ["assets/a.png"]})
        result = self.run_command("upload-url", "a.png", "--content-type", "image/png")
        self.assertIn("signedUrl", result["data"])

    def test_noop_does_not_write(self):
        self.run_command("collection", "ungroup", "--pin-ids", "a")
        writes = len(self.client.writes)
        self.run_command("collection", "ungroup", "--pin-ids", "a")
        self.assertEqual(len(self.client.writes), writes)

    def test_post_write_read_failure_is_unverified(self):
        original = self.client.store()
        desired = copy.deepcopy(original)
        desired["pins"][0]["title"] = "My edit"
        with patch.object(self.client, "store", side_effect=[copy.deepcopy(original), copy.deepcopy(original), pins.PinsError("read failed")]):
            with self.assertRaises(pins.PinsError) as caught:
                pins.save(self.client, original, desired, ["pins"])
        self.assertEqual(caught.exception.details["save_status"], "submitted_unverified")
        self.assertEqual(len(self.client.writes), 1)


class TransportTests(unittest.TestCase):
    def test_output_failure_preserves_completed_operation_and_recovery_ids(self):
        result = {"pin_id": "saved-pin", "asset_path": "user/assets/a.png", "data": {"id": "saved-pin"}}
        for failed_step in ("write", "flush", "close"):
            with self.subTest(failed_step=failed_step), tempfile.TemporaryDirectory() as tmp:
                class FailedFile(io.StringIO):
                    def write(self, text):
                        if failed_step == "write":
                            raise OSError("disk full")
                        return super().write(text)
                    def flush(self):
                        if failed_step == "flush":
                            raise OSError("disk full")
                        return super().flush()
                    def close(self):
                        was_closed = self.closed
                        super().close()
                        if failed_step == "close" and not was_closed:
                            raise OSError("disk full")
                stdout, stderr = io.StringIO(), io.StringIO()
                with patch.dict(os.environ, {"FREVANA_TOKEN": "test-token"}), \
                        patch.object(sys, "argv", ["pins.py", "upload", "photo.png", "--output-json", str(Path(tmp) / "result.json")]), \
                        patch.object(pins.Path, "open", return_value=FailedFile()), patch.object(pins.os, "chmod"), \
                        patch.object(pins, "execute", return_value=result) as execute, \
                        patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                    self.assertEqual(pins.main(), 1)
                execute.assert_called_once()
                self.assertEqual(json.loads(stdout.getvalue())["data"], result["data"])
                error = json.loads(stderr.getvalue())
                self.assertEqual(error["operation_status"], "completed")
                self.assertEqual(error["output_json_status"], "failed")
                self.assertEqual(error["pin_id"], "saved-pin")
                self.assertEqual(error["asset_path"], "user/assets/a.png")

    def test_truncated_response_is_structured_without_retry_or_token_leak(self):
        class TruncatedResponse(io.BytesIO):
            def read(self, *args):
                raise http.client.IncompleteRead(b"secret-token", 10)
        for method in ("GET", "PUT"):
            with self.subTest(method=method):
                client = pins.Client("https://api.example", "secret-token")
                with patch.object(client.opener, "open", return_value=TruncatedResponse()) as opened:
                    with self.assertRaises(pins.PinsError) as caught:
                        client.request(method, payload={"pins": []} if method == "PUT" else None)
                self.assertNotIn("secret-token", str(caught.exception))
                self.assertEqual(opened.call_count, 1)
                if method == "PUT":
                    self.assertEqual(caught.exception.details["save_status"], "outcome_unknown")
                else:
                    self.assertNotIn("save_status", caught.exception.details)

    def test_common_options_before_and_after_subcommand(self):
        args = pins.parser().parse_args(["--token", "override", "collection", "list", "--timeout", "12", "--api-base-url", "https://api.example"])
        self.assertEqual(args.token, "override")
        self.assertEqual(args.timeout, 12)
        self.assertEqual(args.api_base_url, "https://api.example")

    def test_main_override_and_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "result.json"
            stdout = io.StringIO()
            with patch.dict(os.environ, {"FREVANA_TOKEN": "env-token"}), patch.object(sys, "argv", ["pins.py", "list", "--token", "override", "--api-base-url", "https://api.example", "--output-json", str(output)]), patch.object(pins, "execute", return_value={"data": []}) as execute, patch("sys.stdout", stdout):
                self.assertEqual(pins.main(), 0)
            self.assertEqual(execute.call_args.args[0].token, "override")
            self.assertEqual(output.read_text(), stdout.getvalue())
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)

    def test_existing_json_output_blocks_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "result.json"
            output.write_text("keep")
            with patch.dict(os.environ, {"FREVANA_TOKEN": "env-token"}), patch.object(sys, "argv", ["pins.py", "list", "--output-json", str(output)]), patch.object(pins, "execute") as execute, patch("sys.stderr", io.StringIO()):
                self.assertEqual(pins.main(), 1)
            execute.assert_not_called()
            self.assertEqual(output.read_text(), "keep")

    def test_invalid_upload_stops_before_library_read(self):
        client = FakeClient()
        with patch.object(client, "store") as store:
            with self.assertRaises(pins.PinsError):
                pins.execute(client, pins.parser().parse_args(["upload", "/missing/file.png"]))
        store.assert_not_called()

    def test_invalid_library_is_explicit_error(self):
        client = pins.Client("https://api.example", "token")
        with patch.object(client, "request", return_value={"version": 1, "pins": [{"bad": 1}], "collections": []}):
            with self.assertRaises(pins.PinsError):
                client.store()

    def test_read_timeout_does_not_claim_unknown_write(self):
        client = pins.Client("https://api.example", "token", timeout=7)
        with patch.object(client.opener, "open", side_effect=TimeoutError) as opened:
            with self.assertRaises(pins.PinsError) as caught:
                client.request("GET")
        self.assertNotIn("write outcome", str(caught.exception))
        self.assertEqual(opened.call_args.kwargs["timeout"], 7)

    def test_multipart_and_auth(self):
        client = pins.Client("https://api.example/api", "test-token")
        response = io.BytesIO(json.dumps({"path": "user/assets/a.png", "url": "signed"}).encode())
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "a.png"
            file.write_bytes(b"image-bytes")
            with patch.object(client.opener, "open", return_value=response) as opened:
                client.upload(file)
            request = opened.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.example/api/user-pins/assets")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-token")
        self.assertIn(b'name="file"', request.data)
        self.assertIn(b"image-bytes", request.data)

    def test_http_error_does_not_expose_token_or_retry(self):
        client = pins.Client("https://api.example", "secret-token")
        failure = urllib.error.HTTPError("https://api.example", 401, "secret-token", {}, None)
        with patch.object(client.opener, "open", side_effect=failure) as opened:
            with self.assertRaises(pins.PinsError) as caught:
                client.request("PUT", payload={"pins": []})
        self.assertNotIn("secret-token", str(caught.exception))
        self.assertEqual(caught.exception.details["http_status"], 401)
        self.assertEqual(opened.call_count, 1)

    def test_redirects_are_rejected(self):
        handler = pins.NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 302, "", {}, "https://other.example"))

    def test_empty_and_unsupported_files_are_rejected(self):
        client = pins.Client("https://api.example", "test-token")
        with tempfile.TemporaryDirectory() as tmp:
            for filename in ("a.png", "a.txt"):
                file = Path(tmp) / filename
                file.write_bytes(b"")
                with self.assertRaises(pins.PinsError):
                    client.upload(file)


if __name__ == "__main__":
    unittest.main()
