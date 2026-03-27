import unittest
from unittest.mock import patch

from legacy.scanner.patterns.ifvg import find_ifvg_zone, merge_ifvg_zones


def _ifvg(
    *,
    mode,
    low,
    high,
    source_index,
    origin_candle_index,
    origin_candle_high,
    origin_candle_low,
    quality=0.85,
    entry_quality=0.8,
    touch_index=None,
    post_break_confirmed=True,
):
    return {
        "low": low,
        "high": high,
        "mode": mode,
        "quality": quality,
        "entry_quality": entry_quality,
        "source_index": source_index,
        "origin_candle_index": origin_candle_index,
        "origin_candle_high": origin_candle_high,
        "origin_candle_low": origin_candle_low,
        "entry_edge": high,
        "touch_index": touch_index,
        "post_break_confirmed": post_break_confirmed,
    }


class IfvgZoneMergingTests(unittest.TestCase):
    def test_consecutive_strict_ifvgs_merge_even_with_gap(self):
        zones = [
            _ifvg(
                mode="strict",
                low=1.2000,
                high=1.2010,
                source_index=10,
                origin_candle_index=9,
                origin_candle_high=1.2014,
                origin_candle_low=1.1996,
                touch_index=14,
            ),
            _ifvg(
                mode="strict",
                low=1.2024,
                high=1.2032,
                source_index=11,
                origin_candle_index=10,
                origin_candle_high=1.2036,
                origin_candle_low=1.2020,
                touch_index=15,
            ),
        ]

        merged = merge_ifvg_zones(zones, bias="Long", current_price=1.2022, avg_range=0.0040, point=0.0001)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["low"], 1.2000)
        self.assertEqual(merged[0]["high"], 1.2032)
        self.assertEqual(merged[0]["entry_edge"], 1.2032)
        self.assertEqual(merged[0]["source_index"], 10)
        self.assertEqual(merged[0]["merged_source_indices"], [10, 11])
        self.assertEqual(merged[0]["component_count"], 2)
        self.assertEqual(merged[0]["touch_index"], 15)

    def test_merged_ifvg_uses_stop_extreme_component_for_short_bias(self):
        zones = [
            _ifvg(
                mode="strict",
                low=1.3000,
                high=1.3010,
                source_index=20,
                origin_candle_index=19,
                origin_candle_high=1.3018,
                origin_candle_low=1.2998,
                touch_index=24,
            ),
            _ifvg(
                mode="strict",
                low=1.3020,
                high=1.3030,
                source_index=21,
                origin_candle_index=20,
                origin_candle_high=1.3042,
                origin_candle_low=1.3017,
                touch_index=25,
            ),
        ]

        merged = merge_ifvg_zones(zones, bias="Short", current_price=1.3015, avg_range=0.0040, point=0.0001)[0]

        self.assertEqual(merged["entry_edge"], 1.3000)
        self.assertEqual(merged["origin_candle_index"], 20)
        self.assertEqual(merged["origin_candle_high"], 1.3042)
        self.assertEqual(merged["origin_candle_low"], 1.3017)

    def test_non_consecutive_ifvgs_do_not_merge(self):
        zones = [
            _ifvg(
                mode="strict",
                low=1.1000,
                high=1.1010,
                source_index=30,
                origin_candle_index=29,
                origin_candle_high=1.1013,
                origin_candle_low=1.0995,
                touch_index=35,
            ),
            _ifvg(
                mode="strict",
                low=1.1020,
                high=1.1030,
                source_index=32,
                origin_candle_index=31,
                origin_candle_high=1.1034,
                origin_candle_low=1.1017,
                touch_index=36,
            ),
        ]

        merged = merge_ifvg_zones(zones, bias="Long", current_price=1.1022, avg_range=0.0040, point=0.0001)

        self.assertEqual(len(merged), 2)

    def test_different_modes_do_not_merge(self):
        zones = [
            _ifvg(
                mode="strict",
                low=1.2500,
                high=1.2510,
                source_index=40,
                origin_candle_index=39,
                origin_candle_high=1.2512,
                origin_candle_low=1.2497,
                touch_index=44,
            ),
            _ifvg(
                mode="internal",
                low=1.2512,
                high=1.2520,
                source_index=41,
                origin_candle_index=40,
                origin_candle_high=1.2524,
                origin_candle_low=1.2509,
            ),
        ]

        merged = merge_ifvg_zones(zones, bias="Long", current_price=1.2515, avg_range=0.0040, point=0.0001)

        self.assertEqual(len(merged), 2)

    @patch("legacy.scanner.patterns.ifvg.find_ifvg_candidates")
    @patch("legacy.scanner.patterns.ifvg.is_valid_ifvg")
    def test_find_ifvg_zone_returns_merged_consecutive_cluster(self, is_valid_ifvg_mock, find_ifvg_candidates_mock):
        find_ifvg_candidates_mock.return_value = [
            {
                "mode": "strict",
                "low": 1.33223,
                "high": 1.33330,
                "source_index": 173,
                "origin_candle_index": 172,
                "origin_candle_high": 1.33350,
                "origin_candle_low": 1.33200,
            },
            {
                "mode": "strict",
                "low": 1.33354,
                "high": 1.33380,
                "source_index": 174,
                "origin_candle_index": 173,
                "origin_candle_high": 1.33390,
                "origin_candle_low": 1.33320,
            },
        ]
        is_valid_ifvg_mock.side_effect = [
            {
                "valid": True,
                "mode": "strict",
                "low": 1.33223,
                "high": 1.33330,
                "width": 0.00107,
                "source_index": 173,
                "origin_candle_index": 172,
                "origin_candle_high": 1.33350,
                "origin_candle_low": 1.33200,
                "entry_edge": 1.33223,
                "touch_index": 176,
                "entry_quality": 0.82,
                "post_break_confirmed": True,
            },
            {
                "valid": True,
                "mode": "strict",
                "low": 1.33354,
                "high": 1.33380,
                "width": 0.00026,
                "source_index": 174,
                "origin_candle_index": 173,
                "origin_candle_high": 1.33390,
                "origin_candle_low": 1.33320,
                "entry_edge": 1.33354,
                "touch_index": 177,
                "entry_quality": 0.88,
                "post_break_confirmed": True,
            },
        ]

        zone = find_ifvg_zone(
            rates=[],
            bias="Short",
            sweep_index=150,
            mss_index=175,
            current_price=1.3330,
            avg_range=0.0012,
            point=0.00001,
        )

        self.assertIsNotNone(zone)
        self.assertEqual(zone["source_index"], 173)
        self.assertEqual(zone["low"], 1.33223)
        self.assertEqual(zone["high"], 1.33380)
        self.assertEqual(zone["entry_edge"], 1.33223)
        self.assertEqual(zone["merged_source_indices"], [173, 174])
        self.assertEqual(zone["component_count"], 2)


if __name__ == "__main__":
    unittest.main()
