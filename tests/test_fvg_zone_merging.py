import unittest

import numpy as np

from domain.engine.reasoning import format_htf_zone
from legacy.scanner.htf.filters import is_fvg_valid
from legacy.scanner.patterns.fvg import merge_fvg_zones


def _zone(*, bias, low, high, source_index, timeframe="H4", quality=0.7, tradable=True, formed=False):
    return {
        "label": f"{timeframe} FVG",
        "timeframe": timeframe,
        "type": "FVG",
        "bias": bias,
        "low": low,
        "high": high,
        "quality": quality,
        "source_index": source_index,
        "formed_in_displacement": formed,
        "geometric_fvg": True,
        "valid_fvg": True,
        "tradable": tradable,
        "displacement_strength": "medium",
        "after_bos": False,
        "near_liquidity_sweep": False,
        "trend": "Bullish" if bias == "Long" else "Bearish",
        "trend_aligned": True,
        "location_in_range": "discount" if bias == "Long" else "premium",
        "fvg_class": "trend_fvg",
        "mitigation_status": "untouched",
        "mitigation_ratio": 0.0,
        "follow_through_strength": "moderate",
        "follow_through_confirmed": True,
        "follow_through_fill_ratio": 0.0,
        "quality_components": {
            "base": 0.18,
            "timeframe": 0.16 if timeframe == "H4" else 0.08,
            "width": 0.08,
            "displacement": 0.12,
            "bos": 0.0,
            "liquidity_sweep": 0.0,
            "trend_alignment": 0.06,
            "location": 0.06,
            "follow_through": 0.04,
            "class_bonus": 0.05,
        },
        "quality_penalties": {},
        "context_signals": 2,
        "rejection_reason": None,
        "bos_index": None,
        "sweep_index": None,
        "fvg_debug": {},
    }


def _rates(rows):
    dtype = [
        ("time", "i8"),
        ("open", "f8"),
        ("high", "f8"),
        ("low", "f8"),
        ("close", "f8"),
    ]
    return np.array(rows, dtype=dtype)


class FvgZoneMergingTests(unittest.TestCase):
    def test_bullish_overlapping_fvgs_merge_into_one_zone(self):
        zones = [
            _zone(bias="Long", low=1.1000, high=1.1010, source_index=10, quality=0.68),
            _zone(bias="Long", low=1.1008, high=1.1022, source_index=12, quality=0.73, formed=True),
        ]

        merged = merge_fvg_zones(zones, point=0.0001, avg_range=0.0100, timeframe_name="H4")

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["low"], 1.1000)
        self.assertEqual(merged[0]["high"], 1.1022)
        self.assertEqual(merged[0]["source_index"], 10)
        self.assertTrue(merged[0]["formed_in_displacement"])
        self.assertEqual(merged[0]["merged_source_indices"], [10, 12])
        self.assertEqual(merged[0]["component_count"], 2)
        self.assertNotEqual(merged[0]["quality"], 0.73)

    def test_bearish_adjacent_fvgs_inside_tolerance_merge(self):
        zones = [
            _zone(bias="Short", low=1.2000, high=1.2010, source_index=20, timeframe="H1"),
            _zone(bias="Short", low=1.2013, high=1.2020, source_index=22, timeframe="H1"),
        ]

        merged = merge_fvg_zones(zones, point=0.0001, avg_range=0.0100, timeframe_name="H1")

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["low"], 1.2000)
        self.assertEqual(merged[0]["high"], 1.2020)
        self.assertEqual(merged[0]["merged_source_indices"], [20, 22])

    def test_different_bias_fvgs_do_not_merge(self):
        zones = [
            _zone(bias="Long", low=1.3000, high=1.3010, source_index=30),
            _zone(bias="Short", low=1.3008, high=1.3015, source_index=31),
        ]

        merged = merge_fvg_zones(zones, point=0.0001, avg_range=0.0100, timeframe_name="H4")

        self.assertEqual(len(merged), 2)

    def test_same_bias_far_apart_fvgs_do_not_merge(self):
        zones = [
            _zone(bias="Long", low=1.4000, high=1.4010, source_index=40),
            _zone(bias="Long", low=1.4025, high=1.4035, source_index=42),
        ]

        merged = merge_fvg_zones(zones, point=0.0001, avg_range=0.0100, timeframe_name="H4")

        self.assertEqual(len(merged), 2)

    def test_same_bias_consecutive_sources_merge_even_with_gap(self):
        zones = [
            _zone(bias="Long", low=1.4000, high=1.4010, source_index=40),
            _zone(bias="Long", low=1.4025, high=1.4035, source_index=41),
        ]

        merged = merge_fvg_zones(zones, point=0.0001, avg_range=0.0100, timeframe_name="H4")

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["merged_source_indices"], [40, 41])
        self.assertEqual(merged[0]["low"], 1.4000)
        self.assertEqual(merged[0]["high"], 1.4035)

    def test_cluster_merge_uses_aggregate_envelope_not_only_last_zone(self):
        zones = [
            _zone(bias="Short", low=1.3335, high=1.3338, source_index=70, timeframe="M30"),
            _zone(bias="Short", low=1.33385, high=1.3340, source_index=71, timeframe="M30"),
            _zone(bias="Short", low=1.33405, high=1.33435, source_index=72, timeframe="M30"),
        ]

        merged = merge_fvg_zones(zones, point=0.00001, avg_range=0.0012, timeframe_name="M30")

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["merged_source_indices"], [70, 71, 72])
        self.assertEqual(merged[0]["component_count"], 3)
        self.assertEqual(merged[0]["low"], 1.3335)
        self.assertEqual(merged[0]["high"], 1.33435)

    def test_wide_zone_can_absorb_small_gap_cluster(self):
        zones = [
            _zone(bias="Short", low=1.33223, high=1.33330, source_index=173, timeframe="M30"),
            _zone(bias="Short", low=1.33354, high=1.33380, source_index=174, timeframe="M30"),
        ]

        merged = merge_fvg_zones(zones, point=0.00001, avg_range=0.00060, timeframe_name="M30")

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["low"], 1.33223)
        self.assertEqual(merged[0]["high"], 1.33380)
        self.assertEqual(merged[0]["merged_source_indices"], [173, 174])

    def test_merged_fvg_still_uses_normal_invalidation_logic(self):
        merged = merge_fvg_zones(
            [
                _zone(bias="Long", low=1.1000, high=1.1010, source_index=1),
                _zone(bias="Long", low=1.1009, high=1.1020, source_index=2),
            ],
            point=0.0001,
            avg_range=0.0100,
            timeframe_name="H4",
        )[0]
        rates = _rates(
            [
                (0, 1.0995, 1.1005, 1.0990, 1.1000),
                (1, 1.1002, 1.1012, 1.1001, 1.1010),
                (2, 1.1010, 1.1022, 1.1008, 1.1018),
                (3, 1.1015, 1.1017, 1.0988, 1.0990),
            ]
        )

        self.assertFalse(is_fvg_valid(merged, rates, len(rates) - 1))

    def test_zone_formatter_reads_merged_low_high(self):
        merged = merge_fvg_zones(
            [
                _zone(bias="Long", low=1.5000, high=1.5010, source_index=50),
                _zone(bias="Long", low=1.5009, high=1.5022, source_index=51),
            ],
            point=0.0001,
            avg_range=0.0100,
            timeframe_name="H4",
        )[0]

        rendered = format_htf_zone({"zone": merged, "bias": "Long"}, None, None)

        self.assertIn("1.5-1.5022", rendered)


if __name__ == "__main__":
    unittest.main()
