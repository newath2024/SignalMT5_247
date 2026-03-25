import unittest

from domain.timeframes import build_confirmation_timeframes, get_lower_timeframes, get_nearest_lower_timeframes, sort_timeframes


class TimeframeHelperTests(unittest.TestCase):
    def test_sort_timeframes_uses_canonical_order(self):
        self.assertEqual(sort_timeframes(["H4", "M5", "M15", "M3", "H1", "M30"]), ["M3", "M5", "M15", "M30", "H1", "H4"])

    def test_get_lower_timeframes_excludes_same_or_higher_timeframes(self):
        self.assertEqual(get_lower_timeframes("M15", ["M3", "M5", "M15", "H1"]), ["M3", "M5"])

    def test_get_nearest_lower_timeframes_uses_nearest_two_frames(self):
        self.assertEqual(get_nearest_lower_timeframes("H1", ["M3", "M5", "M15", "H1"], limit=2), ["M15", "M5"])
        self.assertEqual(get_nearest_lower_timeframes("H4", ["M3", "M5", "M15", "H1"], limit=2), ["H1", "M15"])

    def test_build_confirmation_timeframes_respects_limit_and_never_reuses_active_htf(self):
        confirmation = build_confirmation_timeframes("M15", ["M3", "M5", "M15", "H1"], limit=2)
        self.assertEqual(confirmation, ["M5", "M3"])
        self.assertNotIn("M15", confirmation)


if __name__ == "__main__":
    unittest.main()
