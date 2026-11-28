import json
from ads_test_support import LaunchCase
from ads_api import AdsError


class PausedCropTest(LaunchCase):
    crop = {"height": 1, "width": 0.5244140625, "x": 0.23779296875, "y": 0}

    def with_crop(self, **extra):
        def annotate(method, path, obj):
            if method == "GET" and path.startswith("/ads/"):
                obj["creative"].update(image_crop=self.crop, **extra)

        self.wire.after = annotate

    def test_readonly_recovery_and_activation_drift(self):
        p = self.preview(final_status="paused")
        self.with_crop()
        done = self.execute(p)
        self.assertEqual(done["image_crop"], self.crop)
        state = json.loads(self.state.read_text())
        state["result"] = None  # receipt produced by the previous release
        self.state.write_text(json.dumps(state))
        self.wire.calls.clear()
        self.assertEqual(
            self.cli("verify-paused", "--state", self.state, "--confirm", p["confirmation"]), done
        )
        self.assertTrue(self.wire.calls)
        self.assertTrue(all(c[0] == "GET" for c in self.wire.calls))
        ap = self.cli("activate", "--from-state", self.state, "--state", self.work / "activation.json")
        self.assertEqual(ap["proposal"]["ad"]["creative"]["image_crop"], self.crop)
        self.crop = dict(self.crop, width=0.5)
        with self.assertRaises(AdsError):
            self.execute(ap, state=self.work / "activation.json")
        self.assertFalse(self.wire.posts())

    def test_active_never_accepts_unspecified_crop(self):
        p = self.preview(final_status="active")
        self.with_crop()
        with self.assertRaisesRegex(AdsError, "unapproved image crop"):
            self.execute(p)
        self.assertFalse(any(c[1].endswith("/activate") for c in self.wire.posts()))

    def test_reject_other_changes_even_when_paused(self):
        p = self.preview(final_status="paused")
        self.with_crop(price="24.99")
        with self.assertRaises(AdsError):
            self.execute(p)

    def test_verify_cannot_create(self):
        p = self.preview(final_status="paused")
        with self.assertRaisesRegex(AdsError, "incomplete"):
            self.cli("verify-paused", "--state", self.state, "--confirm", p["confirmation"])
        self.assertFalse(self.wire.posts())

    def test_invalid_crops_cannot_complete_paused_creation(self):
        proposal = self.preview(final_status="paused")
        self.with_crop()
        for crop in (
            {"x": 0, "y": 0, "width": 0, "height": 0},
            {"x": False, "y": 0, "width": 1, "height": 1},
            {"x": 0.8, "y": 0, "width": 0.5, "height": 1},
        ):
            with self.subTest(crop=crop):
                self.crop = crop
                with self.assertRaisesRegex(AdsError, "unapproved image crop"):
                    self.execute(proposal)
