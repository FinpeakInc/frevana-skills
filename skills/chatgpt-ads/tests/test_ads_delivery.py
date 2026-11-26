import copy
import unittest
from urllib.error import URLError

from ads_test_support import AdvertiserCase, LaunchCase

# isort: split
from ads_api import AdsError


class DeliveryOperationTests(AdvertiserCase):
    def test_pending_named_transitions_complete_by_reading_the_confirmed_target(self):
        for action, params, path, desired in (
            ("pause-ad", {"ad_id": "a1"}, "/ads/a1", "paused"),
            ("pause-ad-group", {"ad_group_id": "g1"}, "/ad_groups/g1", "paused"),
            ("pause-campaign", {"campaign_id": "c1"}, "/campaigns/c1", "paused"),
            ("pause-ad-account", {}, "/ad_account", "paused"),
            ("activate-ad", {"ad_id": "a1"}, "/ads/a1", "active"),
            ("archive-ad", {"ad_id": "a1"}, "/ads/a1", "archived"),
        ):
            with self.subTest(action=action):
                resource = self.store[path]
                resource["status"] = "paused" if desired == "active" else "active"
                receipt = self.prepare(action, params)

                def change_then_timeout(_, resource=resource, desired=desired):
                    resource.update(status=desired, updated_at=resource.get("updated_at", 0) + 1)
                    raise URLError("lost transition response")

                self.responses["POST", path + "/" + action.partition("-")[0]] = change_then_timeout
                with self.assertRaisesRegex(AdsError, "transport"):
                    self.apply(receipt)
                self.calls.clear()
                result = self.apply(receipt)
                self.assertEqual(
                    (result["state"], result["resource"]["id"], result["resource"]["status"]),
                    ("read_back", resource["id"], desired),
                )
                self.assertTrue(self.calls)
                self.assertTrue(all(c[0] == "GET" for c in self.calls))
                self.calls.clear()
                self.assertEqual(self.apply(receipt), result)
                self.assertFalse(self.calls)

    def test_unresolved_named_pause_requires_retry_and_rechecks_drift(self):
        ad = self.store["/ads/a1"]
        ad["status"] = "active"
        receipt = self.prepare("pause-ad", {"ad_id": "a1"})
        self.responses["POST", "/ads/a1/pause"] = URLError("lost before applying")
        with self.assertRaisesRegex(AdsError, "transport"):
            self.apply(receipt)
        del self.responses["POST", "/ads/a1/pause"]
        with self.assertRaisesRegex(AdsError, "uncertain"):
            self.apply(receipt)
        ad["name"] = "different"
        with self.assertRaisesRegex(AdsError, "changed"):
            self.apply(receipt, "--retry-uncertain")
        self.assertEqual(sum(c[0] == "POST" for c in self.calls), 1)
        ad["name"] = "card"
        self.assertEqual(self.apply(receipt, "--retry-uncertain")["resource"]["status"], "paused")
        self.assertEqual(sum(c[0] == "POST" for c in self.calls), 2)

    def test_multi_image_create_and_update_compare_ordered_native_images(self):
        ids = ["f1", "f2", "f3", "f4"]
        requested = {"type": "chat_card", "title": "Trail shoes", "body": "Summer", "file_ids": ids}
        images = [{"item_id": str(i), "file_id": file_id, "image_url": None} for i, file_id in enumerate(ids)]
        native = {"type": "chat_card", "title": "Trail shoes", "body": "Summer", "images": images}
        live = dict(self.store["/ads/a1"], ad_group_id="g1", creative=native)
        self.responses["GET", "/ads/a1"] = live
        self.responses["POST", "/ads"] = {"id": "a1"}
        receipt = self.prepare(
            "create-ad", body={"ad_group_id": "g1", "name": "card", "status": "paused", "creative": requested}
        )
        result = self.apply(receipt)
        self.assertEqual(result["state"], "read_back")
        self.assertEqual(result["resource"]["creative"], native)
        self.assertEqual(result["fields_to_review"], [])

        self.responses["POST", "/ads/a1"] = {"id": "a1"}
        for label, observed, expected in (
            ("same", native, []),
            ("reordered", dict(native, images=images[::-1]), ["creative"]),
            ("replaced", dict(native, images=[*images[:-1], dict(images[-1], file_id="f5")]), ["creative"]),
            ("missing", dict(native, images=images[:-1]), ["creative"]),
            ("absent collection", {k: v for k, v in native.items() if k != "images"}, ["creative"]),
            ("malformed collection", dict(native, images=None), ["creative"]),
            ("unresolved", dict(native, images=[*images[:-1], dict(images[-1], file_id=None)]), ["creative"]),
            ("other field", dict(native, title="Different title"), ["creative"]),
        ):
            with self.subTest(label=label):
                # Existing resource is valid at approval; the post-write GET uses the native representation.
                self.responses["GET", "/ads/a1"] = [live, live, dict(live, creative=observed)]
                receipt = self.prepare("update-ad", {"ad_id": "a1"}, {"creative": requested})
                result = self.apply(receipt)
                self.assertEqual(result["fields_to_review"], expected)
                self.assertEqual(result["state"], "review_readback" if expected else "read_back")
                self.assertEqual(result["resource"]["creative"], observed)

    def test_ad_group_serving_inspection(self):
        self.cli(
            "read",
            "get-ad-group",
            "--param",
            "ad_group_id=g1",
            "--query",
            self.write({"include": ["serving_issues", "bid_too_low"]}),
        )
        self.assertEqual(self.calls[-1][2]["include[]"], ["serving_issues", "bid_too_low"])

    def test_pending_v1_bulk_receipt_reuses_approved_target_body_and_key(self):
        receipt = self.old_receipt("v1-pending-bulk.json")
        with self.assertRaisesRegex(AdsError, "changed"):
            self.apply(receipt)
        self.assertTrue(all(c[0] == "GET" for c in self.calls))
        self.store["/campaigns/c1"].update(name="Campaign", status="active")
        self.responses["POST", "/bulk_mutation_jobs"] = {"id": "job1", "status": "pending"}
        result = self.apply(receipt)
        self.assertEqual(result["response"]["id"], "job1")
        (post,) = [c for c in self.calls if c[0] == "POST"]
        self.assertEqual(post[3], receipt[1]["proposal"]["request"]["body"])
        self.assertEqual(post[4]["Idempotency-key"], receipt[1]["operation_id"])
        self.calls.clear()
        self.assertEqual(self.apply(receipt), result)
        self.assertFalse(self.calls)

    def test_update_approval_drift_and_verified_receipt(self):
        target = self.store["/campaigns/c1"]
        receipt = self.prepare(
            "update-campaign", {"campaign_id": "c1"}, {"budget": {"daily_spend_limit_micros": 9000000}}
        )
        self.assertTrue(all(c[0] == "GET" for c in self.calls))
        with self.assertRaises(AdsError):
            self.cli("execute", "--state", receipt[0], "--confirm", "wrong")
        original = copy.deepcopy(target)
        target["name"] = "different campaign"
        with self.assertRaisesRegex(AdsError, "changed"):
            self.apply(receipt)
        target.update(original)
        self.assertEqual(self.apply(receipt)["state"], "read_back")
        self.assertEqual(target["budget"]["daily_spend_limit_micros"], 9000000)
        self.apply(receipt)
        self.assertEqual(sum(c[0] == "POST" for c in self.calls), 1)

    def test_resume_and_archive_existing_resources(self):
        p = self.prepare("activate-campaign", {"campaign_id": "c1"})
        self.store["/ads/a1"]["name"] = "changed child"
        with self.assertRaisesRegex(AdsError, "changed"):
            self.apply(p)
        p = self.prepare("activate-campaign", {"campaign_id": "c1"})
        self.assertEqual(self.apply(p)["resource"]["status"], "active")
        p = self.prepare("archive-ad", {"ad_id": "a1"})
        self.assertEqual(self.apply(p)["resource"]["status"], "archived")

    def test_advanced_campaigns_and_ads_use_approved_native_fields(self):
        bodies = [
            (
                "create-campaign",
                {
                    "name": "Conversions",
                    "status": "paused",
                    "bidding_type": "conversions",
                    "budget": {"daily_spend_limit_micros": 25000000},
                    "conversion_event_setting_ids": ["ces"],
                    "targeting": {
                        "locations": {"include": [{"id": "123"}]},
                        "excluded_locations": {"countries": ["CA"]},
                        "platforms": {"included": ["web"]},
                        "custom_audiences": {"ids": ["au"]},
                    },
                },
            ),
            (
                "create-campaign",
                {
                    "name": "Hotel",
                    "status": "paused",
                    "budget": {"lifetime_spend_limit_micros": 200000000},
                    "bidding_type": "clicks",
                    "feed_selection": {
                        "feed_id": "f1",
                        "inventory_type": "hotel",
                        "schema_profile": "hotel_property_v1",
                    },
                },
            ),
            (
                "create-ad-group",
                {
                    "name": "Purchases",
                    "campaign_id": "c1",
                    "status": "paused",
                    "bidding_config": {"billing_event_type": "click", "strategy": "maximize_conversions"},
                },
            ),
            (
                "create-ad-group",
                {
                    "name": "Product group",
                    "campaign_id": "c1",
                    "status": "paused",
                    "bidding_config": {"billing_event_type": "click", "max_bid_micros": 3000000},
                    "product_set": {
                        "product_feed_id": "f1",
                        "filters": [{"field": "brand", "operator": "in", "values": ["sample"]}],
                    },
                },
            ),
            (
                "create-ad",
                {
                    "ad_group_id": "g1",
                    "name": "Variant",
                    "status": "paused",
                    "creative": {
                        "type": "chat_card",
                        "title": "Trail shoe",
                        "body": "Shop the new collection",
                        "file_ids": ["f1", "f2", "f3", "f4"],
                        "target_url": "https://example.com/shoe",
                    },
                    "landing_page_configuration": {"query_string_template": "utm_source=chatgpt"},
                },
            ),
            (
                "create-ad",
                {
                    "ad_group_id": "g1",
                    "name": "Hotel template",
                    "status": "paused",
                    "creative": {
                        "type": "product_ad_template",
                        "title": "Stay at {{product.title}}",
                        "body": "{{product.body}}",
                        "price": "{{product.price}}",
                    },
                },
            ),
        ]
        for name, body in bodies:
            with self.subTest(name=name):
                out = self.apply(self.prepare(name, body=body))
                self.assertEqual(out["state"], "read_back")
                self.assertEqual([c[3] for c in self.calls if c[0] == "POST"][-1], body)

    def test_bulk_key_recovery_and_partial_failure_results(self):
        b = {
            "validate_only": True,
            "operations": [
                {
                    "operation_id": "c",
                    "type": "campaign.create",
                    "idempotency_key": "cmp-k",
                    "input": {"name": "New campaign", "max_budget_micros": 80000000},
                }
            ],
        }
        self.responses["POST", "/bulk_mutation_jobs"] = [
            URLError("timeout"),
            {"id": "job", "status": "pending"},
        ]
        p = self.prepare("create-bulk-job", body=b)
        with self.assertRaisesRegex(AdsError, "transport"):
            self.apply(p)
        out = self.apply(p)
        self.assertEqual(out["state"], "submitted")
        posts = [c for c in self.calls if c[0] == "POST"]
        self.assertEqual(posts[0][3:5], posts[1][3:5])
        self.responses["GET", "/bulk_mutation_jobs/job/operations"] = [
            {"data": [{"operation_id": "op-A", "status": "created"}], "complete": True, "has_more": True},
            {
                "data": [{"operation_id": "op-B", "status": "failed", "error": "limit"}],
                "complete": True,
                "has_more": False,
            },
        ]
        pages = self.cli("read", "list-bulk-results", "--param", "job_id=job", "--all-pages")["pages"]
        self.assertEqual(pages[-1]["data"][0]["status"], "failed")
        self.assertEqual(self.calls[-1][2]["after"], ["op-A"])

    def test_real_bulk_is_distinct_approval_and_reads_target(self):
        b = {
            "validate_only": False,
            "operations": [
                {
                    "operation_id": "u",
                    "type": "ad.update",
                    "target_resource_id": "a1",
                    "input": {"status": "paused"},
                }
            ],
        }
        p = self.prepare("create-bulk-job", body=b)
        self.assertIn("/ads/a1", p[1]["proposal"]["before"])
        with self.assertRaises(AdsError):
            self.prepare("create-bulk-job", body={"operations": b["operations"] * 2})
        self.assertFalse(any(c[0] == "POST" for c in self.calls))

    def test_pending_bulk_activation_rechecks_budget_and_children_before_replay(self):
        body = {
            "operations": [
                {
                    "operation_id": "enable",
                    "type": "campaign.update",
                    "target_resource_id": "c1",
                    "input": {"status": "active"},
                }
            ]
        }
        p = self.prepare("create-bulk-job", body=body)
        self.responses["POST", "/bulk_mutation_jobs"] = [URLError("connection refused"), {"id": "job1"}]
        with self.assertRaisesRegex(AdsError, "transport"):
            self.apply(p)
        campaign = self.store["/campaigns/c1"]
        campaign["budget"]["daily_spend_limit_micros"] = 999000000
        with self.assertRaisesRegex(AdsError, "changed"):
            self.apply(p)
        campaign["budget"]["daily_spend_limit_micros"] = 50000000
        self.responses["GET", "/ads"] = {
            "data": [self.store["/ads/a1"], {"id": "extra", "status": "active"}],
            "has_more": False,
        }
        with self.assertRaisesRegex(AdsError, "changed"):
            self.apply(p, "--retry-uncertain")
        self.assertEqual(sum(c[0] == "POST" for c in self.calls), 1)
        del self.responses["GET", "/ads"]
        self.assertEqual(self.apply(p)["response"]["id"], "job1")
        posts = [c for c in self.calls if c[0] == "POST"]
        self.assertEqual(posts[0][3:5], posts[1][3:5])

    def test_created_ad_and_group_verify_parent_via_paginated_membership(self):
        for kind, route, field, parent, settings in (
            (
                "ad-group",
                "/ad_groups",
                "campaign_id",
                "c1",
                {"bidding_config": {"billing_event_type": "click"}},
            ),
            ("ad", "/ads", "ad_group_id", "g1", {"creative": {"type": "chat_card", "title": "Shoe"}}),
        ):
            with self.subTest(kind=kind):
                live = dict(settings, id="new", name="New", status="paused")
                self.store[route + "/new"] = live
                self.responses["POST", route] = live
                self.responses["GET", route] = [
                    {"data": [{"id": "older"}], "has_more": True, "last_id": "older"},
                    {"data": [live], "has_more": True, "last_id": "new"},
                ]
                p = self.prepare(
                    "create-" + kind, body=dict(settings, name="New", status="paused", **{field: parent})
                )
                result = self.apply(p)
                self.assertEqual(result["fields_to_review"], [])
                self.assertEqual(result["state"], "read_back")
                self.assertEqual(self.calls[-1][2], {field: [parent], "limit": ["500"], "after": ["older"]})
                self.responses["GET", route] = {"data": [], "has_more": False}
                result = self.apply(
                    self.prepare(
                        "create-" + kind,
                        body=dict(settings, name="Other", status="paused", **{field: parent}),
                    )
                )
                self.assertCountEqual(result["fields_to_review"], [field, "name"])

    def test_lost_non_idempotent_write_is_not_resent(self):
        self.responses["POST", "/ads/a1"] = [URLError("interrupted"), {"id": "a1"}]
        p = self.prepare("update-ad", {"ad_id": "a1"}, {"name": "new"})
        with self.assertRaisesRegex(AdsError, "transport"):
            self.apply(p)
        with self.assertRaisesRegex(AdsError, "uncertain"):
            self.apply(p)
        self.assertEqual(sum(c[0] == "POST" for c in self.calls), 1)


class LaunchTests(LaunchCase):
    def test_preview_shows_scope_and_budget_no_upload(self):
        p = self.preview()
        self.assertEqual([(r[0], r[1]) for r in self.wire.calls], [("GET", "/ad_account")])
        self.assertEqual(p["proposal"]["campaign"]["budget"], {"daily_spend_limit_micros": 50000000})
        self.assertEqual(p["proposal"]["account"]["id"], "adacct_7")
        self.assertEqual(p["proposal"]["asset"]["image_url"], self.draft["image_url"])
        self.assertEqual(self.cli("show", "--state", self.state), p)
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o600)
        self.assertNotIn("fake-test-key", self.state.read_text())

    def test_rejects_invalid_drafts_without_writes(self):
        original = self.draft.copy()
        cases = [
            {"currency": "CAD"},
            {"countries": []},
            {"daily_budget": "0.0000001"},
            {"daily_budget": 50.5},
            {"title": "x" * 51},
            {"landing_page_url": "file:///tmp/file"},
            {"file_id": "file_1"},
            {"bid_strategy": "fixed_bid"},
            {"max_cpc": "1"},
            {"welcome": 42},
            {"final_status": "ready"},
            {"end_time": True},
        ]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(AdsError):
                self.draft = original.copy()
                self.preview(**changes)
        self.assertFalse(self.wire.posts())
        self.assertFalse(self.state.exists())

    def test_money_per_billing_event(self):
        p = self.preview(objective="impressions", bid_strategy="fixed_bid", max_cpm="60")
        self.assertEqual(p["proposal"]["ad_group"]["bidding_config"]["max_bid_micros"], 60000)
        self.state = self.work / "click.json"
        del self.draft["max_cpm"]
        p = self.preview(objective="clicks", max_cpc="1.23")
        self.assertEqual(p["proposal"]["ad_group"]["bidding_config"]["max_bid_micros"], 1230000)

    def test_active_launch_replay_and_existing_pause(self):
        p = self.preview(final_status="active")
        result = self.execute(p)
        self.assertEqual(result["review_status"], "in_review")
        self.assertEqual(
            [c[1] for c in self.wire.posts()],
            [
                "/upload",
                "/campaigns",
                "/ad_groups",
                "/ads",
                "/ads/ad_3/activate",
                "/ad_groups/adgrp_2/activate",
                "/campaigns/cmpn_1/activate",
            ],
        )
        creates = self.wire.posts()[1:4]
        self.assertEqual(len({c[3] for c in creates}), 3)
        self.assertTrue(all(c[2]["status"] == "paused" for c in creates))
        self.assertEqual(creates[2][2]["creative"]["file_id"], "file_7")
        pause_path = self.work / "pause.json"
        pause = self.cli("pause", "--resource", "campaign", "--id", "cmpn_1", "--state", pause_path)
        self.assertEqual(pause["proposal"]["before"], "active")
        self.assertEqual(len(self.wire.posts()), 7)
        self.assertEqual(self.execute(pause, state=pause_path)["status"], "paused")
        self.execute(pause, state=pause_path)
        self.execute(p)
        self.assertEqual(len(self.wire.posts()), 8)
        self.assertEqual(self.cli("status", "--resource", "campaign", "--id", "cmpn_1")["status"], "paused")

    def test_native_preview_then_confirm_same_resources(self):
        del self.draft["image_url"]
        p = self.preview(file_id="file_71")
        self.execute(p)
        self.assertEqual(len(self.wire.posts()), 3)
        self.assertEqual(self.cli("ad-preview", "--id", "ad_3")["data"][0]["body"], "<iframe></iframe>")
        dest = self.work / "activation.json"
        activation = self.cli("activate", "--from-state", self.state, "--state", dest)
        self.assertEqual(len(self.wire.posts()), 4)
        result = self.execute(activation, state=dest)
        self.assertTrue(all(obj["status"] == "active" for obj in result["resources"].values()))
        self.assertEqual(len(self.wire.objects), 3)
        self.assertEqual(self.wire.posts()[-1][1], "/campaigns/cmpn_1/activate")

    def test_lost_create_response_resumes_with_original_key_and_body(self):
        p = self.preview()
        self.interrupt_after("POST", "/ad_groups")
        with self.assertRaisesRegex(AdsError, "transport"):
            self.execute(p)
        self.assertEqual(self.cli("show", "--state", self.state)["steps"]["create_campaign"], "cmpn_1")
        self.execute(p)
        self.assertEqual(len(self.wire.objects), 3)
        self.assertEqual(
            [c[1] for c in self.wire.posts()], ["/upload", "/campaigns", "/ad_groups", "/ad_groups", "/ads"]
        )
        self.assertEqual(self.wire.posts()[2], self.wire.posts()[3])

    def test_uncertain_upload_requires_explicit_recovery(self):
        p = self.preview()
        self.interrupt_after("POST", "/upload")
        with self.assertRaises(AdsError):
            self.execute(p)
        with self.assertRaisesRegex(AdsError, "Upload outcome"):
            self.execute(p)
        self.assertEqual(len(self.wire.posts()), 1)
        self.execute(p, "--retry-uncertain")
        self.assertEqual(len(self.wire.posts()), 5)

    def test_lost_activation_response_readback_skips_duplicate(self):
        p = self.preview(final_status="active")
        self.interrupt_after("POST", "/campaigns/cmpn_1/activate")
        with self.assertRaises(AdsError):
            self.execute(p)
        self.assertEqual(self.execute(p)["resources"]["campaign"]["status"], "active")
        self.assertEqual(len(self.wire.posts()), 7)

    def test_drift_before_parent_activation_does_not_start_spend(self):
        p = self.preview(final_status="active")

        def change(method, path, result):
            if path == "/ad_groups/adgrp_2/activate":
                self.wire.objects["/campaigns/cmpn_1"]["budget"]["daily_spend_limit_micros"] *= 100

        self.wire.after = change
        with self.assertRaisesRegex(AdsError, "differs"):
            self.execute(p)
        self.assertEqual(self.wire.objects["/campaigns/cmpn_1"]["status"], "paused")

    def test_extra_child_or_changed_targeting_blocks_activation(self):
        p = self.preview()
        self.execute(p)
        dest = self.work / "active.json"
        activation = self.cli("activate", "--from-state", self.state, "--state", dest)
        ads = self.wire.objects
        ads["/campaigns/cmpn_1"]["targeting"]["custom_audiences"] = {"ids": ["some_audience"]}
        with self.assertRaisesRegex(AdsError, "targeting"):
            self.execute(activation, state=dest)
        del ads["/campaigns/cmpn_1"]["targeting"]["custom_audiences"]
        ads["/ads/ad_extra"] = dict(ads["/ads/ad_3"], id="ad_extra")
        with self.assertRaisesRegex(AdsError, "hierarchy"):
            self.execute(activation, state=dest)
        self.assertEqual(len(self.wire.posts()), 4)

    def test_changed_creative_or_destination_requires_new_review(self):
        self.execute(self.preview())
        dest = self.work / "active.json"
        activation = self.cli("activate", "--from-state", self.state, "--state", dest)
        creative = self.wire.objects["/ads/ad_3"]["creative"]
        group = self.wire.objects["/ad_groups/adgrp_2"]
        for obj, key, value in (
            (creative, "price", "$19.99"),
            (group, "landing_page_configuration", {"query_string_template": "offer=clearance"}),
        ):
            with self.subTest(key=key):
                obj[key] = value
                with self.assertRaises(AdsError):
                    self.execute(activation, state=dest)
                del obj[key]
        self.assertEqual(len(self.wire.posts()), 4)

    def test_blocked_or_unknown_ad_review_never_activates(self):
        p = self.preview(final_status="active")

        def missing_review(method, path, obj):
            if method == "GET" and path == "/ads/ad_3":
                obj.pop("review_status", None)

        self.wire.after = missing_review
        with self.assertRaisesRegex(AdsError, "review status"):
            self.execute(p)
        self.wire.after = lambda *args: None
        self.wire.objects["/ads/ad_3"]["review_status"] = "rejected"
        with self.assertRaisesRegex(AdsError, "rejected"):
            self.execute(p)
        self.assertEqual(len(self.wire.posts()), 4)

    def test_uncertain_pause_does_not_repeat_until_authorized(self):
        obj = {"id": "ad_9", "name": "Test ad", "status": "active", "updated_at": 1}
        self.wire.objects["/ads/ad_9"] = obj
        p = self.cli("pause", "--resource", "ad", "--id", "ad_9", "--state", self.state)
        self.interrupt_after("POST", "/ads/ad_9/pause")
        with self.assertRaises(AdsError):
            self.execute(p)
        obj["status"] = "active"
        with self.assertRaisesRegex(AdsError, "Uncertain"):
            self.execute(p)
        self.assertEqual(len(self.wire.posts()), 1)
        self.assertEqual(self.execute(p, "--retry-uncertain")["status"], "paused")

    def test_pause_types_and_stale_preview(self):
        for kind, path in (("campaign", "campaigns"), ("ad_group", "ad_groups"), ("ad", "ads")):
            with self.subTest(kind=kind):
                obj = {"id": "obj_1", "name": kind, "status": "active", "updated_at": 1}
                self.wire.objects["/" + path + "/obj_1"] = obj
                dest = self.work / (kind + ".json")
                p = self.cli("pause", "--resource", kind, "--id", "obj_1", "--state", dest)
                obj["updated_at"] += 1
                with self.assertRaisesRegex(AdsError, "changed"):
                    self.execute(p, state=dest)
                obj["status"] = "paused"
                self.assertEqual(self.execute(p, state=dest)["status"], "paused")
        self.assertFalse(self.wire.posts())


if __name__ == "__main__":
    unittest.main()
