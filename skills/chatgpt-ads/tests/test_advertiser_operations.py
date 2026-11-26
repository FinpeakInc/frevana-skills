import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from ads_test_support import AdvertiserCase

# isort: split
from ads_api import AdsAPI, AdsError
from ads_operations import CATALOG, is_read


class AdvertiserOperationsTests(AdvertiserCase):
    def test_catalog_discovery_and_access_classification(self):
        table = self.cli("operations")
        routes = set()
        for name, op in CATALOG.items():
            with self.subTest(name=name):
                described = self.cli("describe", name)
                self.assertEqual(table[name], described["access"])
                routes.add((op["method"], op["path"]))
                if not is_read(op):
                    with self.assertRaises(AdsError):
                        self.cli("read", name)
        self.assertEqual(len(routes), len(CATALOG))
        self.assertTrue(
            {
                ("GET", "/ads/{ad_id}/landing_page_crawl"),
                ("GET", "/ad_account/hotel_insights"),
                ("POST", "/custom_audiences/merge"),
                ("GET", "/feeds/{feed_id}/products"),
            }
            <= routes
        )
        self.assertFalse(self.calls)

    def test_lead_list_and_get_preserve_account_and_opaque_subscription_id(self):
        rows = [{"subscription_id": "leadsync_x.g1", "object": "subscription", "status": "active"}]
        self.store["/lead_sync_subscriptions"]["data"] = rows
        self.store["/lead_sync_subscriptions/leadsync_x.g1"] = rows[0]
        self.assertEqual(
            self.cli(
                "read", "list-lead-sync-subscriptions", "--query", self.write({"ad_account_id": "acct"})
            )["data"],
            rows,
        )
        self.assertEqual(self.calls[-1][2], {"ad_account_id": ["acct"]})
        result = self.cli("read", "get-lead-sync-subscription", "--param", "subscription_id=leadsync_x.g1")
        self.assertEqual(result, rows[0])
        self.assertTrue(all(c[0] == "GET" for c in self.calls))

    def test_lead_create_recovers_with_same_key_and_keeps_secrets_private(self):
        signing_secret = "whsec_" + "A" * 43 + "="
        body = {
            "ad_account_id": "acct",
            "destination_url": "https://hooks.example/c/manual-token?key=private-query",
            "signing_secret": signing_secret,
        }
        native = {
            "subscription_id": "leadsync_acct_g1",
            "object": "subscription",
            "status": "active",
            "signing_secret": signing_secret,
        }
        dest = self.tmp / "new-secret.json"
        p = self.prepare("create-lead-sync-subscription", body=body, secret=dest)
        self.assertEqual(p[1]["proposal"]["private_summary"]["destination_origin"], "https://hooks.example")
        self.assertTrue(all(c[0] == "GET" for c in self.calls))
        with self.assertRaisesRegex(AdsError, "Confirmation"):
            self.cli("execute", "--state", p[0], "--confirm", "another-preview")
        self.responses["POST", "/lead_sync_subscriptions"] = [URLError("lost response"), native]
        with self.assertRaises(AdsError):
            self.apply(p)
        self.store["/lead_sync_subscriptions"]["data"] = [
            {k: v for k, v in native.items() if k != "signing_secret"}
        ]
        receipt = self.apply(p)
        self.assertEqual(receipt["response"]["subscription_id"], native["subscription_id"])
        self.assertEqual(self.apply(p), receipt)
        posts = [c for c in self.calls if c[0] == "POST"]
        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[0][3], body)
        self.assertEqual(posts[0][4]["Idempotency-key"], p[1]["operation_id"])
        self.assertEqual(posts[0][3:5], posts[1][3:5])
        self.assertEqual(json.loads(dest.read_bytes()), native)
        self.assertEqual(dest.stat().st_mode & 0o777, 0o600)
        for secret in (signing_secret, "manual-token", "private-query"):
            self.assertNotIn(secret, p[0].read_text())
            self.assertNotIn(secret, json.dumps(receipt))

    def test_lead_proposal_rejects_wrong_account_invalid_inputs_and_edits(self):
        dest = self.tmp / "key.json"
        body = {"ad_account_id": "acct", "destination_url": "https://crm.example/lead"}
        for change in (
            {"ad_account_id": "different"},
            {"signing_secret": "invalid"},
            {"destination_url": "http://crm.example"},
        ):
            with self.subTest(change=change), self.assertRaises(AdsError):
                self.prepare("create-lead-sync-subscription", body=dict(body, **change), secret=dest)
        p = self.prepare("create-lead-sync-subscription", body=body, secret=dest)
        Path(p[1]["proposal"]["request"]["private_body"]["path"]).write_text(
            json.dumps(dict(body, destination_url="https://other.example/"))
        )
        with self.assertRaisesRegex(AdsError, "changed"):
            self.apply(p)
        self.assertFalse(any(c[0] == "POST" for c in self.calls))

    def test_lead_delete_confirms_exact_account_and_current_subscription(self):
        row = {"subscription_id": "leadsync_acct_g1", "status": "active"}
        args = {"subscription_id": row["subscription_id"]}
        with self.assertRaisesRegex(AdsError, "absent"):
            self.prepare("delete-lead-sync-subscription", args)
        self.store["/lead_sync_subscriptions"]["data"] = [row]
        p = self.prepare("delete-lead-sync-subscription", args)
        row["status"] = "disabled"
        with self.assertRaisesRegex(AdsError, "changed"):
            self.apply(p)
        self.assertTrue(all(c[0] == "GET" for c in self.calls))
        row["status"] = "active"
        endpoint = "/lead_sync_subscriptions/leadsync_acct_g1"
        self.responses["DELETE", endpoint] = dict(row, deleted=True)
        result = self.apply(p)
        self.assertEqual(result["state"], "deleted")
        self.assertEqual(self.calls[-1][:4], ("DELETE", endpoint, {}, None))
        self.assertEqual(self.apply(p), result)
        self.assertEqual(sum(c[0] == "DELETE" for c in self.calls), 1)

    def test_lead_delete_after_lost_response_reconciles_without_repeat(self):
        row = {"subscription_id": "leadsync_acct_g1", "status": "active"}
        self.store["/lead_sync_subscriptions"]["data"] = [row]
        p = self.prepare("delete-lead-sync-subscription", {"subscription_id": row["subscription_id"]})
        self.responses["DELETE", "/lead_sync_subscriptions/leadsync_acct_g1"] = [URLError("lost response")]
        with self.assertRaises(AdsError):
            self.apply(p)
        with self.assertRaisesRegex(AdsError, "uncertain"):
            self.apply(p)
        self.store["/lead_sync_subscriptions"]["data"] = []
        self.assertEqual(self.apply(p)["state"], "absent_in_account")
        self.assertEqual(sum(c[0] == "DELETE" for c in self.calls), 1)

    def test_partner_upload_uses_api_key_only_and_returns_session_metadata(self):
        manifest = {
            "data_type": "identity_graph",
            "snapshot_date": "2026-11-01",
            "file_name": "snapshot.parquet",
            "file_size_bytes": 100,
            "sha256": "a" * 64,
        }
        upload_id = "pdu_" + "ab" * 16
        receipt_path = self.tmp / "instructions.json"
        native = dict(
            manifest,
            upload_id=upload_id,
            status="pending",
            upload_url="https://storage.example/upload?sig=private",
            upload_url_expires_at="2026-11-20T15:00:00Z",
            upload_method="PUT",
            upload_headers={"x-transfer-auth": "private-header"},
        )
        os.environ.update(
            OPENAI_ADS_OAUTH_TOKEN="oauth-token",
            OPENAI_ADS_PARTNER_KEY="partner-key",
            OPENAI_ADS_ACCOUNT_ID="selected",
        )
        self.api = AdsAPI()
        self.api.opener = self
        p = self.prepare("create-partner-data-upload", body=manifest, secret=receipt_path)
        self.assertFalse(self.calls)
        self.responses["POST", "/partner_data/uploads"] = native
        os.environ["OPENAI_ADS_PARTNER_KEY"] = "different-key"
        with self.assertRaises(AdsError):
            self.apply(p)
        self.assertFalse(self.calls)
        os.environ["OPENAI_ADS_PARTNER_KEY"] = "partner-key"
        self.assertEqual(self.apply(p)["response"]["upload_id"], upload_id)
        self.assertEqual(self.calls[-1][3], manifest)
        self.assertNotIn("Idempotency-key", self.calls[-1][4])
        self.assertEqual(json.loads(receipt_path.read_bytes()), native)
        self.assertEqual(receipt_path.stat().st_mode & 0o777, 0o600)
        for secret in ("sig=private", "private-header", "partner-key"):
            self.assertNotIn(secret, p[0].read_text())
        status = dict(manifest, upload_id=upload_id, status="pending")
        self.responses["GET", "/partner_data/uploads/" + upload_id] = status
        self.assertEqual(
            self.cli("read", "get-partner-data-upload", "--param", "upload_id=" + upload_id), status
        )
        self.assertEqual(len(self.calls), 2)
        for c in self.calls:
            self.assertEqual(c[4]["Authorization"], "Bearer partner-key")
            self.assertNotIn("Openai-ad-account", c[4])
            self.assertEqual(c[5], "api.ads.openai.com")

    def test_partner_manifest_bounds_oauth_and_uncertain_create(self):
        manifest = {
            "data_type": "identity_graph",
            "snapshot_date": "2026-11-01",
            "file_name": "s.parquet",
            "file_size_bytes": 107374182400,
            "sha256": "c" * 64,
        }
        dest = self.tmp / "instructions.json"
        for field, value in (
            ("data_type", "other"),
            ("snapshot_date", "2026-02-30"),
            ("file_name", "../s.parquet"),
            ("file_size_bytes", True),
            ("file_size_bytes", 0),
            ("file_size_bytes", 107374182401),
            ("sha256", "B" * 64),
        ):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.prepare("create-partner-data-upload", body=dict(manifest, **{field: value}), secret=dest)
        with self.assertRaises(AdsError):
            self.cli("read", "get-partner-data-upload", "--param", "upload_id=pdu_bad")
        del os.environ["OPENAI_ADS_API_KEY"]
        os.environ["OPENAI_ADS_OAUTH_TOKEN"] = "oauth-only"
        with self.assertRaisesRegex(AdsError, "API_KEY"):
            self.prepare("create-partner-data-upload", body=manifest, secret=dest)
        os.environ["OPENAI_ADS_API_KEY"] = "enabled-issued-key"
        self.assertFalse(self.calls)
        p = self.prepare("create-partner-data-upload", body=manifest, secret=dest)
        self.responses["POST", "/partner_data/uploads"] = [URLError("response lost")]
        with self.assertRaises(AdsError):
            self.apply(p)
        with self.assertRaisesRegex(AdsError, "uncertain"):
            self.apply(p)
        self.assertEqual(len(self.calls), 1)

    def test_hotel_upload_history_keeps_feed_filter_on_all_pages(self):
        self.responses["GET", "/feeds/uploads"] = [
            {"uploads": [{"id": "one"}], "has_more": True, "last_id": "one"},
            {"uploads": [{"id": "two"}], "has_more": False},
        ]
        result = self.cli(
            "read",
            "list-product-feed-uploads",
            "--query",
            self.write({"inventory_type": "hotel", "feed_id": "hotel1"}),
            "--all-pages",
        )
        self.assertEqual(result["page_count"], 2)
        query = {"feed_id": ["hotel1"], "inventory_type": ["hotel"], "paginate": ["true"]}
        self.assertEqual([c[2] for c in self.calls], [query, dict(query, after=["one"])])

    def test_image_and_audience_upload_bind_exact_file(self):
        file = self.tmp / "creative.png"
        file.write_bytes(b"original-image")
        self.responses["POST", "/upload"] = {"file_id": "file_img"}
        p = self.prepare("upload-image", file=file)
        file.write_bytes(b"replacement")
        with self.assertRaisesRegex(AdsError, "changed"):
            self.apply(p)
        file.write_bytes(b"original-image")
        self.assertEqual(self.apply(p)["response"]["file_id"], "file_img")
        wire = self.calls[-1]
        self.assertIn(b'name="file"; filename="creative.png"', wire[3])
        self.assertIn(b"original-image", wire[3])
        self.assertTrue(wire[4]["Content-type"].startswith("multipart/form-data; boundary="))
        self.responses["POST", "/uploads"] = {"file_id": "file_people"}
        file = self.tmp / "audience.csv"
        file.write_bytes(b"example@example.com")
        self.apply(self.prepare("upload-blob", file=file))
        self.assertIn(b"custom_audience", self.calls[-1][3])

    def test_audience_membership_private_payload_with_revision(self):
        b = {
            "expected_revision": 4,
            "identifiers": [{"identifier_type": "email", "identifier": "person@example.com"}],
        }
        self.responses["POST", "/custom_audiences/au/add"] = {"operation_id": "op", "status": "processing"}
        p = self.prepare("add-custom-audience-members", {"custom_audience_id": "au"}, b)
        self.assertNotIn("person@example.com", p[0].read_text())
        self.assertEqual(p[1]["proposal"]["private_summary"]["rows"], 1)
        self.assertEqual(self.apply(p)["response"]["operation_id"], "op")
        self.assertIsNotNone(self.calls[-1][4]["Idempotency-key"])
        with self.assertRaisesRegex(AdsError, "revision"):
            self.prepare(
                "replace-custom-audience-members",
                {"custom_audience_id": "au"},
                {"file_id": "blob", "expected_revision": 2},
            )

    def test_feed_patching_and_hotel_item_body_cursor(self):
        p = self.prepare("patch-product-feed-settings", {"feed_id": "f1"}, {"is_full_refresh": True})
        self.assertFalse(p[1]["proposal"]["before"]["feed_settings"]["is_full_refresh"])
        self.assertTrue(self.apply(p)["settings"]["is_full_refresh"])
        self.responses["POST", "/feeds/f1/items/query"] = [
            {"data": [], "has_more": True, "last_id": "h/2?"},
            {"data": [{"hotel_id": "X", "review_status": "approved"}], "has_more": False},
        ]
        pages = self.cli(
            "read",
            "query-feed-items",
            "--param",
            "feed_id=f1",
            "--body",
            self.write({"include_rejection_reasons": True}),
            "--all-pages",
        )["pages"]
        self.assertEqual(self.calls[-1][3]["after"], "h/2?")
        self.assertEqual(pages[-1]["data"][0]["hotel_id"], "X")

    def test_feed_sftp_transfer_uses_approved_feed_and_file(self):
        src = self.tmp / "catalog.csv"
        src.write_bytes(b"id,title\na,Shoe\n")
        p = self.prepare("upload-feed-snapshot", {"feed_id": "f1"}, {"remote_name": "catalog.csv"}, file=src)
        with patch("ads_changes.sftp_upload", return_value={"transfer": "uploaded"}) as upload:
            self.assertEqual(self.apply(p)["response"]["transfer"], "uploaded")
            ref, name, access, _ = upload.call_args.args
            self.assertEqual(ref["sha256"], hashlib.sha256(src.read_bytes()).hexdigest())
            self.assertEqual((name, access["connection_uri"]), ("catalog.csv", "sftp://user@files.example"))

    def test_private_key_output_is_exclusive_and_redacted(self):
        secret = self.tmp / "private.json"
        self.responses["POST", "/conversions/api_keys"] = {"api_key": "issued-secret", "name": "CI"}
        p = self.prepare("create-conversion-api-key", body={"name": "Server key"}, secret=secret)
        self.apply(p)
        self.assertEqual(json.loads(secret.read_text())["api_key"], "issued-secret")
        self.assertEqual(secret.stat().st_mode & 0o777, 0o600)
        self.assertNotIn("issued-secret", p[0].read_text())
        self.assertNotIn("issued-secret", json.dumps(self.apply(p)))
        with self.assertRaises(AdsError):
            self.prepare("create-conversion-api-key", body={"name": "duplicate"}, secret=secret)

    def test_password_feed_transfer_starts_only_after_authentication(self):
        access = self.store["/feeds/f1/sftp_access"]
        access["authentication_method"] = "password"
        source = self.tmp / "source.csv"
        source.write_bytes(b"id,price\nA,11\n")
        p = self.prepare(
            "upload-feed-snapshot", {"feed_id": "f1"}, {"remote_name": "catalog.csv"}, file=source
        )
        driver = MagicMock()
        client = driver.SSHClient.return_value.__enter__.return_value
        sftp = client.open_sftp.return_value.__enter__.return_value
        with patch.dict(sys.modules, {"paramiko": driver}):
            with self.assertRaisesRegex(AdsError, "OPENAI_ADS_SFTP_PASSWORD"):
                self.apply(p)
            self.assertNotIn("dispatch", json.loads(p[0].read_text())["steps"])
            os.environ["OPENAI_ADS_SFTP_PASSWORD"] = "test-only-password"

            def transferred(local, remote, confirm):
                self.assertEqual(Path(local).read_bytes(), source.read_bytes())
                self.assertEqual(remote, "catalog.csv")
                self.assertTrue(confirm)
                self.assertEqual(json.loads(p[0].read_text())["steps"]["dispatch"], "pending")

            sftp.put.side_effect = transferred
            self.apply(p)
        client.set_missing_host_key_policy.assert_called_once_with(driver.RejectPolicy.return_value)
        self.assertEqual(client.connect.call_args.kwargs["hostname"], "files.example")
        sftp.put.assert_called_once()
        self.assertNotIn("test-only-password", p[0].read_text())

    def test_capi_separate_host_dedup_and_private_event(self):
        b = {
            "events": [
                {
                    "id": "checkout-51",
                    "type": "order_created",
                    "action_source": "web",
                    "timestamp_ms": 1700000000000,
                    "source_url": "https://example.com/paid",
                    "data": {"type": "contents", "amount": 1999, "currency": "USD"},
                }
            ],
            "validate_only": True,
        }
        self.responses["POST", "/events"] = {"accepted": 1}
        p = self.prepare("send-conversion-events", query={"pid": "pixel1"}, body=b)
        self.assertFalse(self.calls)
        self.assertNotIn("checkout-51", p[0].read_text())
        del os.environ["OPENAI_ADS_CAPI_KEY"]
        with self.assertRaisesRegex(AdsError, "OPENAI_ADS_CAPI_KEY"):
            self.apply(p)
        self.assertNotIn("dispatch", json.loads(p[0].read_text())["steps"])
        os.environ["OPENAI_ADS_CAPI_KEY"] = "only-event"
        self.apply(p)
        _, _, q, wire, headers, host = self.calls[-1]
        self.assertEqual((q, wire, host), ({"pid": ["pixel1"]}, b, "bzr.openai.com"))
        self.assertEqual(headers["Authorization"], "Bearer only-event")
        self.assertNotIn("Openai-ad-account", headers)
        with self.assertRaisesRegex(AdsError, "Duplicate"):
            self.prepare("send-conversion-events", query={"pid": "p"}, body={"events": b["events"] * 2})
        out = self.tmp / "pixel.html"
        self.cli("pixel-snippet", "--pixel-id", "pixel1", "--output", out, "--consent-required")
        self.assertLess(out.read_text().index('oaiq("consent"'), out.read_text().index('oaiq("init"'))
        self.assertNotIn("only-event", out.read_text())

    def test_multi_pixel_initializes_once_per_id_without_sending_events(self):
        out = self.tmp / "pixels.html"
        result = self.cli("pixel-snippet", "--pixel-id", "one", "--pixel-id", "two", "--output", out)
        self.assertEqual(result["pixel_ids"], ["one", "two"])
        snippet = out.read_text()
        self.assertEqual(snippet.count("oaiq.min.js"), 1)
        self.assertEqual(snippet.count('oaiq("init"'), 2)
        self.assertNotIn('oaiq("measure', snippet)
        with self.assertRaises(AdsError):
            self.cli("pixel-snippet", "--pixel-id", "one", "--pixel-id", "one", "--output", out)
        self.assertFalse(self.calls)

    def test_conversion_report_body_and_segmented_delivery(self):
        self.responses["POST", "/conversions/insights"] = {
            "data": [{"order_created_attributed_sales": "19.99"}]
        }
        b = {
            "aggregation_level": "campaign",
            "time_ranges": [{"type": "unix_range", "start": "1", "end": "2"}],
            "include": ["attributed_events"],
            "event_names": ["order_created"],
        }
        self.cli("read", "post-conversion-insights", "--body", self.write(b))
        self.assertIsInstance(self.calls[-1][3]["time_ranges"][0], str)
        self.responses["GET", "/ad_account/insights"] = {"data": [], "has_more": False}
        q = {
            "fields": ["country.spend", "country.name"],
            "segments": ["country"],
            "attribution_window_days": 7,
            "filters": [{"field": "campaign.id", "operator": "IN", "values": ["c1"]}],
        }
        self.cli(
            "report",
            "--granularity",
            "monthly",
            "--options",
            self.write(q),
            "--since",
            "2026-09-01",
            "--until",
            "2026-09-30",
        )
        wire = self.calls[-1][2]
        self.assertEqual(wire["fields[]"], q["fields"])
        self.assertEqual(json.loads(wire["filters[]"][0]), q["filters"][0])
        self.assertEqual(wire["time_granularity"], ["monthly"])

    def test_output_reservation_failure_never_issues_a_secret(self):
        dest = self.tmp / "secrets" / "key.json"
        p = self.prepare("create-conversion-api-key", body={"name": "Customer CAPI"}, secret=dest)
        dest.parent.rmdir()
        dest.parent.write_text("not a directory")
        with self.assertRaises(OSError):
            self.apply(p)
        self.assertFalse(any(c[0] == "POST" for c in self.calls))

    def test_lost_key_checkpoint_recovers_private_output_without_reissuing(self):
        from ads_workflow import Execution

        dest = self.tmp / "key.json"
        p = self.prepare("create-conversion-api-key", body={"name": "Analytics"}, secret=dest)
        self.responses["POST", "/conversions/api_keys"] = {"api_key": "one-time-only"}
        original = Execution.checkpoint

        def fail_after_key_saved(op, step, value):
            if step == "accepted":
                raise OSError("simulated disk error")
            original(op, step, value)

        with patch.object(Execution, "checkpoint", fail_after_key_saved), self.assertRaises(OSError):
            self.apply(p)
        self.assertEqual(json.loads(dest.read_bytes())["api_key"], "one-time-only")
        self.apply(p)
        self.assertEqual(sum(c[0] == "POST" for c in self.calls), 1)
        self.assertNotIn("one-time-only", p[0].read_text())

    def test_partner_response_survives_first_receipt_checkpoint_failure(self):
        from ads_workflow import Execution

        manifest = {
            "data_type": "identity_graph",
            "snapshot_date": "2026-11-01",
            "file_name": "s.parquet",
            "file_size_bytes": 4,
            "sha256": "a" * 64,
        }
        native = dict(
            manifest,
            upload_id="pdu_" + "a" * 32,
            status="pending",
            upload_url_expires_at="2026-11-22",
            upload_url="https://storage.example/signed",
            upload_headers={"x-token": "session-only"},
            upload_method="PUT",
        )
        path = self.tmp / "instructions.json"
        receipt = self.prepare("create-partner-data-upload", body=manifest, secret=path)
        self.responses["POST", "/partner_data/uploads"] = native
        checkpoint = Execution.checkpoint

        def fail_first_response_checkpoint(op, step, value):
            if step == "private_digest":
                raise OSError("receipt filesystem full")
            return checkpoint(op, step, value)

        with patch.object(Execution, "checkpoint", fail_first_response_checkpoint), self.assertRaises(
            OSError
        ):
            self.apply(receipt)
        pending = json.loads(path.read_bytes())
        self.assertEqual(
            pending, {"reserved_for_ads_operation": receipt[1]["operation_id"], "response": native}
        )
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        # A completed envelope belonging to another operation is never adopted.
        path.write_text(json.dumps(dict(pending, reserved_for_ads_operation="different")))
        with self.assertRaises(AdsError):
            self.apply(receipt, "--retry-uncertain")
        path.write_text(json.dumps(pending))
        result = self.apply(receipt)
        self.assertEqual(result["response"]["upload_id"], native["upload_id"])
        self.assertEqual(self.apply(receipt), result)
        self.assertEqual(json.loads(path.read_bytes()), native)
        self.assertEqual(sum(c[0] == "POST" for c in self.calls), 1)
        self.assertNotIn("session-only", receipt[0].read_text())

    def test_uncertain_membership_reuses_key_after_remote_revision_advances(self):
        body = {"file_id": "customers", "expected_revision": 4}
        p = self.prepare("add-custom-audience-members", {"custom_audience_id": "au"}, body)
        self.responses["POST", "/custom_audiences/au/add"] = [
            URLError("response lost"),
            {"operation_id": "first-op"},
        ]
        with self.assertRaises(AdsError):
            self.apply(p)
        self.store["/custom_audiences/au"]["membership_revision"] = 5
        self.assertEqual(self.apply(p)["response"]["operation_id"], "first-op")
        posts = [c for c in self.calls if c[0] == "POST"]
        self.assertEqual(posts[0][3:5], posts[1][3:5])

    def test_ssh_snapshot_uses_real_local_sftp_protocol_when_available(self):
        server = next(
            (p for p in ["/usr/libexec/sftp-server", "/usr/lib/openssh/sftp-server"] if Path(p).is_file()),
            None,
        )
        if not server or not shutil.which("sftp"):
            self.skipTest("Local OpenSSH sftp client/server binaries are unavailable")
        source = self.tmp / "source.csv"
        source.write_bytes(b"id,price\nA,11\n")
        dest = self.tmp / "feed-root"
        dest.mkdir()
        receipt = self.prepare(
            "upload-feed-snapshot", {"feed_id": "f1"}, {"remote_name": "catalog.csv"}, file=source
        )
        run = subprocess.run

        def local_transport(argv, **kwargs):
            self.assertIn("-oStrictHostKeyChecking=yes", argv)
            self.assertEqual(argv[-1], "user@files.example")
            kwargs["input"] = f'cd "{dest}"\n' + kwargs["input"]
            return run(["sftp", "-D", server, "-b", "-", "local"], **kwargs)

        with patch("ads_files.subprocess.run", side_effect=local_transport):
            self.apply(receipt)
        self.assertEqual((dest / "catalog.csv").read_bytes(), source.read_bytes())

    def test_unsafe_path_and_parameters_rejected_before_network(self):
        with self.assertRaises(AdsError):
            self.cli("read", "get-ad", "--param", "ad_id=../me")
        with self.assertRaises(AdsError):
            self.cli("read", "get-ad", "--param", "ad_id=a1", "--query", self.write({"unknown": 1}))
        with self.assertRaises(AdsError):
            self.prepare(
                "upload-feed-snapshot",
                {"feed_id": "f1"},
                {"remote_name": "../price.csv"},
                file=self.write({}),
            )
        self.assertFalse(self.calls)


if __name__ == "__main__":
    unittest.main()
