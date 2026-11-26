import copy
import json
import os
import unittest
from urllib.error import URLError

from ads_test_support import AdvertiserCase

# isort: split
from ads_api import AdsAPI, AdsError


class AccountOperationsTests(AdvertiserCase):
    def test_activation_freezes_all_active_campaigns_and_budgets(self):
        self.store["/ad_account"]["status"] = "paused"
        first = dict(self.store["/campaigns/c1"], status="active")
        second = {
            "id": "c2",
            "status": "active",
            "name": "Launch",
            "budget": {"lifetime_spend_limit_micros": 200000000},
        }
        paused = dict(first, id="c3", status="paused")
        rows = [second, first, paused]

        def page(call):
            if "after" in call[2]:
                self.assertEqual(call[2]["after"], [rows[0]["id"]])
                return {"data": rows[1:], "has_more": False}
            return {"data": rows[:1], "last_id": rows[0]["id"], "has_more": True}

        self.responses["GET", "/campaigns"] = page
        receipt = self.prepare("activate-ad-account")
        scope = receipt[1]["proposal"]["before"]["active_campaigns"]
        self.assertEqual(
            scope, [{key: row[key] for key in ("id", "name", "budget")} for row in (first, second)]
        )
        for campaign, key, changed in (
            (first, "budget", {"daily_spend_limit_micros": 5000000000}),
            (second, "budget", {"daily_spend_limit_micros": 200000000}),
            (first, "status", "paused"),
            (paused, "status", "active"),
        ):
            with self.subTest(id=campaign["id"], change=changed):
                original = campaign[key]
                campaign[key] = changed
                with self.assertRaisesRegex(AdsError, "fresh preview"):
                    self.apply(receipt, "--retry-uncertain")
                campaign[key] = original
        self.assertTrue(all(c[0] == "GET" for c in self.calls))
        rows.reverse()
        second["updated_at"] = 100
        paused["budget"] = {"daily_spend_limit_micros": 1000000}
        self.assertEqual(self.apply(receipt)["resource"]["status"], "active")
        self.assertEqual([c[1] for c in self.calls if c[0] == "POST"], ["/ad_account/activate"])

    def test_activation_requires_a_complete_budget_snapshot_before_writing(self):
        self.responses["GET", "/campaigns"] = {"data": [], "has_more": False}
        receipt = self.prepare("activate-ad-account")
        self.assertEqual(receipt[1]["proposal"]["before"]["active_campaigns"], [])
        active = dict(self.store["/campaigns/c1"], status="active")
        for page in (
            {"data": []},
            {"data": [active], "has_more": True},
            {"data": [dict(active, budget={})], "has_more": False},
            {"data": [active, active], "has_more": False},
        ):
            with self.subTest(page=page):
                self.responses["GET", "/campaigns"] = page
                with self.assertRaises(AdsError):
                    self.apply(receipt)
        self.assertTrue(all(c[0] == "GET" for c in self.calls))

    def test_pending_activation_rechecks_scope_before_retry_and_readback(self):
        self.store["/ad_account"]["status"] = "paused"
        active = dict(self.store["/campaigns/c1"], status="active")
        self.responses["GET", "/campaigns"] = {"data": [active], "has_more": False}
        receipt = self.prepare("activate-ad-account")
        self.responses["POST", "/ad_account/activate"] = URLError("lost response")
        with self.assertRaisesRegex(AdsError, "transport"):
            self.apply(receipt)
        self.calls.clear()
        active["budget"]["daily_spend_limit_micros"] *= 100
        for status in ("paused", "active"):
            self.store["/ad_account"]["status"] = status
            with self.assertRaisesRegex(AdsError, "fresh preview"):
                self.apply(receipt, "--retry-uncertain")
        active["budget"]["daily_spend_limit_micros"] //= 100
        self.assertEqual(self.apply(receipt)["resource"]["status"], "active")
        self.assertTrue(all(c[0] == "GET" for c in self.calls))

    def test_legacy_account_activation_requires_new_scope_only_before_a_write(self):
        from ads_workflow import approval_id

        self.store["/ad_account"]["status"] = "paused"
        self.responses["GET", "/campaigns"] = {"data": [], "has_more": False}
        path, state = self.prepare("activate-ad-account")
        del state["proposal"]["before"]["active_campaigns"]
        state["confirmation"] = approval_id(state)
        path.write_text(json.dumps(state))
        with self.assertRaisesRegex(AdsError, "fresh preview"):
            self.apply((path, state))
        state["steps"]["dispatch"] = "pending"
        path.write_text(json.dumps(state))
        with self.assertRaisesRegex(AdsError, "fresh preview"):
            self.apply((path, state), "--retry-uncertain")
        self.store["/ad_account"]["status"] = "active"
        self.assertEqual(self.apply((path, state))["resource"]["status"], "active")
        self.assertTrue(all(c[0] == "GET" for c in self.calls))

    def test_account_selection_and_hosted_onboarding(self):
        os.environ.update(OPENAI_ADS_OAUTH_TOKEN="oauth", OPENAI_ADS_ACCOUNT_ID="acct")
        self.api = AdsAPI()
        self.api.opener = self
        self.responses["GET", "/ad_accounts"] = {"data": [{"id": "acct"}]}
        self.cli("read", "list-ad-accounts")
        self.assertNotIn("Openai-ad-account", self.calls[-1][4])
        p = self.prepare("pause-ad", {"ad_id": "a1"})
        self.assertEqual(self.calls[-1][4]["Openai-ad-account"], "acct")
        self.store["/ad_account"]["id"] = "other"
        with self.assertRaisesRegex(AdsError, "different"):
            self.apply(p)
        return_uri = "https://partner.example/return"
        p = self.prepare(
            "create-ad-account-creation-session",
            body={"return_uri": return_uri, "state": "unique"},
            secret=self.tmp / "onboarding.json",
        )
        self.responses["POST", "/ad_account_creation_sessions"] = {
            "url": "https://ads.openai.com/example",
            "expires_in": 60,
        }
        self.apply(p)
        self.assertNotIn("Openai-ad-account", self.calls[-1][4])
        self.assertNotIn("ads.openai.com/example", p[0].read_text())

    def test_spend_limit_revision(self):
        with self.assertRaisesRegex(AdsError, "revision"):
            self.prepare(
                "set-ad-account-daily-spend-limit", body={"expected_revision": 2, "amount_micros": 30000000}
            )
        p = self.prepare(
            "set-ad-account-daily-spend-limit", body={"expected_revision": 3, "amount_micros": 30000000}
        )
        self.responses["POST", "/ad_account/daily_spend_limit"] = {"spend_limits": {"revision": 4}}
        self.assertEqual(self.apply(p)["state"], "review_readback")

    def test_accepted_v1_limit_receipt_resumes_at_readback(self):
        receipt = self.old_receipt("v1-accepted-daily-limit.json")
        self.store["/ad_account/spend_limit_windows"] = {
            "revision": 4,
            "data": [],
            "daily_limits": [{"window_id": "rule1", "amount_micros": 200}],
        }
        result = self.apply(receipt)
        self.assertEqual(result["state"], "read_back")
        self.assertEqual(
            [c[:2] for c in self.calls], [("GET", "/ad_account"), ("GET", "/ad_account/spend_limit_windows")]
        )
        self.calls.clear()
        self.assertEqual(self.apply(receipt), result)
        self.assertFalse(self.calls)

    def test_daily_limits_use_new_or_targeted_id_among_multiple_rules(self):
        path = "/ad_account/spend_limit_windows"
        active = {"window_id": "current", "amount_micros": 100, "status": "active"}
        upcoming = {"window_id": "future", "amount_micros": 200, "status": "upcoming"}
        self.store[path].update(daily_limit=active, daily_limits=[active])

        def transact(action, body, after):
            revision = self.store[path]["revision"]
            p = self.prepare(action, body=dict(body, expected_revision=revision))

            def write(_):
                self.store[path].update(daily_limits=after, daily_limit=active, revision=revision + 1)
                return {"spend_limits": copy.deepcopy(self.store[path])}

            endpoint = "/ad_account/daily_spend_limit" + ("/delete" if action.startswith("delete") else "")
            self.responses["POST", endpoint] = write
            return self.apply(p)["state"]

        create = {"window_id": None, "amount_micros": 200}
        self.assertEqual(
            transact("set-ad-account-daily-spend-limit", create, [active, upcoming]), "read_back"
        )
        edited = dict(upcoming, amount_micros=350)
        self.assertEqual(
            transact(
                "set-ad-account-daily-spend-limit",
                {"window_id": "future", "amount_micros": 350},
                [active, edited],
            ),
            "read_back",
        )
        # Matching the other rule's amount is insufficient.
        self.assertEqual(
            transact(
                "set-ad-account-daily-spend-limit",
                {"window_id": "future", "amount_micros": 100},
                [active, edited],
            ),
            "review_readback",
        )
        self.assertEqual(
            transact("delete-ad-account-daily-spend-limit", {"window_id": "future"}, [active, edited]),
            "review_readback",
        )
        self.assertEqual(
            transact("delete-ad-account-daily-spend-limit", {"window_id": "future"}, [active]), "read_back"
        )
        self.assertEqual(
            transact(
                "set-ad-account-daily-spend-limit",
                create,
                [active, upcoming, dict(upcoming, window_id="another")],
            ),
            "review_readback",
        )

    def test_legacy_singleton_daily_receipt_without_rule_id(self):
        from ads_workflow import approval_id

        path = "/ad_account/spend_limit_windows"
        self.store[path]["daily_limit"] = {"amount_micros": 100}
        p = self.prepare(
            "set-ad-account-daily-spend-limit", body={"amount_micros": 200, "expected_revision": 3}
        )
        # Receipt produced before the multi-rule snapshot was introduced.
        del p[1]["proposal"]["before"]["daily_limits"]
        p[1]["confirmation"] = approval_id(p[1])
        p[0].write_text(json.dumps(p[1]))

        def write(_):
            self.store[path].update(daily_limit={"amount_micros": 200}, revision=4)
            return {"spend_limits": self.store[path]}

        self.responses["POST", "/ad_account/daily_spend_limit"] = write
        self.assertEqual(self.apply(p)["state"], "read_back")


if __name__ == "__main__":
    unittest.main()
