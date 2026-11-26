"""Stateful HTTP fixtures for exercising the public ChatGPT Ads CLI offline."""

import copy
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from ads_api import AdsAPI
from chatgpt_ads import handle, parser


class Wire:
    """Stateful fixture at the HTTP boundary. No actual socket is opened."""

    def __init__(self):
        self.account = {
            "id": "adacct_7",
            "name": "Test advertiser",
            "status": "active",
            "currency_code": "USD",
            "timezone": "America/Los_Angeles",
            "review": {"status": "approved"},
        }
        self.objects = {}
        self.idempotency = {}
        self.calls = []
        self.pages = []
        self.after = lambda method, path, result: None

    def open(self, req, timeout):
        url = urlsplit(req.full_url)
        assert (url.scheme, url.netloc) == ("https", "api.ads.openai.com")
        assert url.path.startswith("/v1/")
        assert req.get_header("Authorization") == "Bearer fake-test-key"
        assert req.get_header("User-agent") == "frevana-chatgpt-ads-skill/1.0"
        path = url.path[3:]
        query = parse_qs(url.query)
        body = json.loads(req.data) if req.data else None
        key = req.get_header("Idempotency-key")
        self.calls.append((req.method, path, body, key, query))
        if path.endswith("/insights"):
            result = self.pages.pop(0)
        elif path.endswith("/preview"):
            result = {"data": [{"body": "<iframe></iframe>"}]}
        elif path == "/ad_account":
            result = self.account
        elif path == "/upload":
            assert body == {"image_url": "https://example.com/assets/trail-shoe.png"}
            result = {"file_id": "file_7"}
        elif req.method == "GET":
            if path in ("/ad_groups", "/ads"):
                field = "ad_group_id" if path == "/ads" else "campaign_id"
                rows = [
                    o
                    for name, o in self.objects.items()
                    if name.startswith(path + "/") and [o[field]] == query[field]
                ]
                result = {"data": rows, "has_more": False}
            else:
                result = self.objects[path]
        elif path in ("/campaigns", "/ad_groups", "/ads"):
            assert key
            prefix = {"/campaigns": "cmpn", "/ad_groups": "adgrp", "/ads": "ad"}[path]
            if key not in self.idempotency:
                obj_id = f"{prefix}_{len(self.objects) + 1}"
                obj = dict(body, id=obj_id, updated_at=100)
                if path == "/ads":
                    obj["review_status"] = "in_review"
                self.objects[path + "/" + obj_id] = copy.deepcopy(obj)
                self.idempotency[key] = (body, obj)
            previous, result = self.idempotency[key]
            assert previous == body
        else:
            target, action = path.rsplit("/", 1)
            self.objects[target]["status"] = {"activate": "active", "pause": "paused"}[action]
            result = {}
        self.after(req.method, path, result)
        return io.BytesIO(json.dumps(result).encode())

    def posts(self):
        return [c for c in self.calls if c[0] == "POST"]


class LaunchCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work = Path(tmp.name)
        self.draft = json.loads((ROOT / "references/draft.json").read_text())
        self.input = self.work / "draft.json"
        self.state = self.work / "launch.json"
        self.wire = Wire()
        env_patch = patch.dict(os.environ, {"OPENAI_ADS_API_KEY": "fake-test-key"})
        env_patch.start()
        self.addCleanup(env_patch.stop)
        self.api = AdsAPI()
        self.api.opener = self.wire

    def cli(self, *args):
        return handle(parser().parse_args([str(a) for a in args]), self.api)

    def preview(self, **updates):
        self.draft.update(updates)
        self.input.write_text(json.dumps(self.draft))
        return self.cli("preview", "--draft", self.input, "--state", self.state)

    def execute(self, preview, *flags, state=None):
        return self.cli(
            "execute", "--state", state or self.state, "--confirm", preview["confirmation"], *flags
        )

    def interrupt_after(self, method, path):
        def interrupt(m, p, result):
            if (m, p) == (method, path):
                self.wire.after = lambda *args: None
                raise URLError("simulated lost response")

        self.wire.after = interrupt


class AdvertiserCase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name)
        env = patch.dict(
            os.environ,
            {"OPENAI_ADS_API_KEY": "only-advertiser", "OPENAI_ADS_CAPI_KEY": "only-event"},
            clear=True,
        )
        env.start()
        self.addCleanup(env.stop)
        self.api = AdsAPI()
        self.api.opener = self
        self.store = {
            "/ad_account": {"id": "acct", "currency_code": "USD", "timezone": "UTC", "status": "active"},
            "/campaigns/c1": {
                "id": "c1",
                "name": "existing",
                "status": "paused",
                "budget": {"daily_spend_limit_micros": 50000000},
            },
            "/ad_groups/g1": {"id": "g1", "name": "group", "status": "paused", "campaign_id": "c1"},
            "/ads/a1": {"id": "a1", "name": "card", "status": "paused", "ad_group_id": "g1"},
            "/ad_account/spend_limit_windows": {"data": [], "daily_limit": None, "revision": 3},
            "/custom_audiences/au": {
                "id": "au",
                "name": "first party",
                "status": "ready",
                "membership_revision": 4,
            },
            "/feeds/f1/settings": {"name": "summer", "is_full_refresh": False},
            "/feeds/f1/sftp_access": {
                "enabled": True,
                "authentication_method": "ssh_key",
                "connection_uri": "sftp://user@files.example",
            },
            "/me": {"id": "partner_user"},
            "/lead_sync_subscriptions": {"object": "list", "data": [], "has_more": False},
        }
        self.calls = []
        self.responses = {}
        self.index = 0

    def open(self, req, timeout):
        u = urlsplit(req.full_url)
        path = u.path.removeprefix("/v1/") if sys.version_info >= (3, 9) else u.path[4:]
        path = "/" + path
        b = req.data
        if b and req.get_header("Content-type", "").startswith("application/json"):
            b = json.loads(b)
        entry = (req.method, path, parse_qs(u.query), b, dict(req.header_items()), u.netloc)
        self.calls.append(entry)
        selected = self.responses.get((req.method, path))
        if isinstance(selected, list):
            result = selected.pop(0)
        elif callable(selected):
            result = selected(entry)
        elif selected is not None:
            result = selected
        elif req.method == "GET":
            if path == "/ad_groups":
                result = {"data": [self.store["/ad_groups/g1"]], "has_more": False}
            elif path == "/ads":
                result = {"data": [self.store["/ads/a1"]], "has_more": False}
            else:
                result = self.store[path]
        elif path in self.store and req.method in ("POST", "PATCH"):
            self.store[path].update(b)
            result = self.store[path]
        elif path in ("/ads", "/ad_groups", "/campaigns"):
            rid = "new"
            self.store[path + "/" + rid] = dict(b, id=rid)
            result = {"id": rid}
        elif path.endswith(("/activate", "/pause", "/archive")):
            target, action = path.rsplit("/", 1)
            self.store[target]["status"] = {"activate": "active", "pause": "paused", "archive": "archived"}[
                action
            ]
            result = {}
        else:
            raise AssertionError(f"Unexpected request: {req.method} {path}")
        if isinstance(result, Exception):
            raise result
        return io.BytesIO(json.dumps(result).encode())

    def cli(self, *args):
        return handle(parser().parse_args([str(a) for a in args]), self.api)

    def write(self, obj):
        self.index += 1
        path = self.tmp / f"input{self.index}.json"
        path.write_text(json.dumps(obj))
        return path

    def prepare(self, action, params=None, body=None, query=None, file=None, secret=None):
        self.index += 1
        path = self.tmp / f"state{self.index}.json"
        args = ["plan", action, "--state", path]
        for k, v in (params or {}).items():
            args += ["--param", f"{k}={v}"]
        for flag, var in (("--body", body), ("--query", query)):
            if var is not None:
                args += [flag, self.write(var)]
        if secret:
            args += ["--secret-output", secret]
        if file:
            args += ["--file", file]
        preview = self.cli(*args)
        return path, preview

    def apply(self, receipt, *extra):
        path, p = receipt
        return self.cli("execute", "--state", path, "--confirm", p["confirmation"], *extra)

    def old_receipt(self, filename):
        # Copy the original CLI output. Rebuilding it would also regenerate its fingerprint.
        data = (ROOT / "tests" / "fixtures" / filename).read_bytes()
        path = self.tmp / filename
        path.write_bytes(data)
        return path, json.loads(data)
