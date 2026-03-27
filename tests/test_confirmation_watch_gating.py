import datetime as dt
import unittest
from unittest.mock import patch

import numpy as np

from domain.confirmation import detect_watch_candidates
from domain.engine.watch_state import prepare_retained_watch


def _rates(rows):
    dtype = [
        ("time", "i8"),
        ("open", "f8"),
        ("high", "f8"),
        ("low", "f8"),
        ("close", "f8"),
    ]
    return np.array(rows, dtype=dtype)


def _untouched_fvg_zone():
    return {
        "label": "M30 FVG",
        "timeframe": "M30",
        "type": "FVG",
        "bias": "Short",
        "low": 1.33223,
        "high": 1.3338,
        "quality": 0.92,
        "source_index": 173,
        "tier": "B",
        "mitigation_status": "untouched",
        "fvg_debug": {
            "mitigation": {
                "status": "untouched",
                "touched": False,
            }
        },
    }


def _watch_trigger():
    return {
        "bias": "Short",
        "state": "awaiting_mss",
        "narrative_state": "awaiting_mss",
        "sweep_index": 212,
        "sweep_level": 1.33181,
        "sweep_price": 1.33181,
        "structure_level": 1.33023,
        "sweep_quality": 0.84,
        "swept_external": ["buy-side liquidity"],
        "avg_range": 0.00057,
        "watch_index": 212,
    }


class ConfirmationWatchGatingTests(unittest.TestCase):
    @patch("domain.confirmation.build_watch_trigger")
    def test_detect_watch_candidates_rejects_untouched_fvg_context(self, build_watch_trigger_mock):
        build_watch_trigger_mock.return_value = (_watch_trigger(), None)
        snapshot = {
            "symbol": "GBPUSD",
            "current_price": 1.33020,
            "point": 0.00001,
            "broker_now": dt.datetime(2026, 3, 27, tzinfo=dt.timezone.utc),
            "rates": {
                "M5": _rates([(0, 1.3301, 1.3303, 1.3299, 1.3302)]),
            },
        }
        context = {
            "clear": True,
            "bias": "Short",
            "zone": _untouched_fvg_zone(),
        }

        watches, rejections = detect_watch_candidates(snapshot, {"Short": context}, ["M5"])

        self.assertEqual(watches, [])
        self.assertEqual(len(rejections), 1)
        self.assertEqual(rejections[0]["reason"], "HTF FVG untouched")

    @patch("domain.confirmation.build_watch_trigger")
    def test_detect_watch_candidates_allows_mitigated_fvg_context(self, build_watch_trigger_mock):
        build_watch_trigger_mock.return_value = (_watch_trigger(), None)
        snapshot = {
            "symbol": "GBPUSD",
            "current_price": 1.33020,
            "point": 0.00001,
            "broker_now": dt.datetime(2026, 3, 27, tzinfo=dt.timezone.utc),
            "rates": {
                "M5": _rates([(0, 1.3301, 1.3303, 1.3299, 1.3302)]),
            },
        }
        zone = _untouched_fvg_zone()
        zone["mitigation_status"] = "partially_mitigated"
        zone["fvg_debug"]["mitigation"]["status"] = "partially_mitigated"
        zone["fvg_debug"]["mitigation"]["touched"] = True
        context = {
            "clear": True,
            "bias": "Short",
            "zone": zone,
        }

        watches, rejections = detect_watch_candidates(snapshot, {"Short": context}, ["M5"])

        self.assertEqual(rejections, [])
        self.assertEqual(len(watches), 1)
        self.assertEqual(watches[0]["htf_context"], "M30 FVG")
        self.assertEqual(watches[0]["sweep_price"], 1.33181)

    @patch("domain.engine.watch_state.refresh_htf_context")
    def test_prepare_retained_watch_removes_watch_when_fvg_is_still_untouched(self, refresh_htf_context_mock):
        refresh_htf_context_mock.return_value = {
            "clear": True,
            "bias": "Short",
            "zone": _untouched_fvg_zone(),
        }
        snapshot = {
            "symbol": "GBPUSD",
            "current_price": 1.33020,
            "point": 0.00001,
            "rates": {
                "M5": _rates([(0, 1.3301, 1.3303, 1.3299, 1.3302)]),
            },
        }
        watch_setup = {
            "watch_key": "GBPUSD|Short|M5|M30 FVG|buy-side liquidity|212",
            "htf_zone": _untouched_fvg_zone(),
            "timeframe": "M5",
            "bias": "Short",
            "status": "awaiting_mss",
            "narrative_state": "awaiting_mss",
            "expiry_bar_index": 999,
            "invalidation_price": 1.3350,
            "sweep_price": 1.33181,
        }

        retained, removed = prepare_retained_watch(snapshot, watch_setup)

        self.assertIsNone(retained)
        self.assertIsNotNone(removed)
        self.assertEqual(removed["removal_reason"], "entry invalidated")


if __name__ == "__main__":
    unittest.main()
