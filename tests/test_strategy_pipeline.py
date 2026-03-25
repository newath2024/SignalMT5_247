import datetime as dt
import unittest
from unittest.mock import patch

from domain.enums import SetupPhase, SetupState
from domain.strategy.pipeline import (
    build_htf_context,
    derive_display_state,
    refresh_active_watches,
    resolve_confirmed_signal,
    score_setup,
)


class StrategyPipelineTests(unittest.TestCase):
    @patch("domain.strategy.pipeline.derive_htf_bias")
    @patch("domain.strategy.pipeline.detect_htf_context")
    def test_build_htf_context_prefers_best_directional_context(self, detect_htf_context_mock, derive_htf_bias_mock):
        long_context = {
            "bias": "Long",
            "score": 0.7,
            "rollover_active": True,
            "context_strength": "moderate",
            "zone": {"tier": "B", "timeframe": "H1"},
        }
        short_context = {
            "bias": "Short",
            "score": 0.9,
            "rollover_active": False,
            "context_strength": "strong",
            "zone": {"tier": "A", "timeframe": "H4"},
        }
        detect_htf_context_mock.return_value = (["z1"], {"Long": long_context, "Short": short_context})
        derive_htf_bias_mock.return_value = ("long", long_context)

        result = build_htf_context({"symbol": "EURUSD"})

        self.assertEqual(result.all_htf_zones, ["z1"])
        self.assertEqual(result.htf_bias, "long")
        self.assertEqual(result.primary_context, long_context)
        self.assertEqual(result.best_directional_context, long_context)

    @patch("domain.strategy.pipeline.refresh_htf_context")
    @patch("domain.strategy.pipeline.watch_has_expired")
    @patch("domain.strategy.pipeline.watch_is_invalidated")
    def test_refresh_active_watches_removes_expired_and_invalidated(
        self,
        watch_is_invalidated_mock,
        watch_has_expired_mock,
        refresh_htf_context_mock,
    ):
        refresh_htf_context_mock.return_value = {"clear": True}
        watch_has_expired_mock.side_effect = [False, True, False]
        watch_is_invalidated_mock.side_effect = [False, True]
        active_watches = [
            {"watch_key": "keep", "htf_zone": {}, "status": "waiting_mss", "bias": "Long"},
            {"watch_key": "expired", "htf_zone": {}, "status": "waiting_mss", "bias": "Long"},
            {"watch_key": "invalid", "htf_zone": {}, "status": "waiting_mss", "bias": "Short"},
        ]

        result = refresh_active_watches({"symbol": "EURUSD"}, active_watches)

        self.assertEqual([item["watch_key"] for item in result.retained_watches], ["keep"])
        self.assertEqual(
            [(item["watch_key"], item["removal_reason"]) for item in result.removed_watches],
            [("expired", "expired"), ("invalid", "entry invalidated")],
        )

    @patch("domain.strategy.pipeline.detect_confirmed_signal")
    def test_resolve_confirmed_signal_marks_ambiguous_competition_as_rejection(self, detect_confirmed_signal_mock):
        primary_context = {"bias": "Long", "zone": {"label": "H1 OB"}}
        detect_confirmed_signal_mock.return_value = (None, "ambiguous competing signals")

        result = resolve_confirmed_signal(
            snapshot={"symbol": "EURUSD"},
            active_pool=[],
            all_htf_zones=[],
            contexts={"Long": primary_context},
            primary_context=primary_context,
            htf_bias="long",
            unique_new_watches=[],
            retained_watches=[],
            rejections=[],
        )

        self.assertIsNone(result.confirmed_signal)
        self.assertEqual(result.selected_rejection["phase"], "signal")
        self.assertEqual(result.rejections[0]["reason"], "ambiguous competing signals")
        self.assertEqual(result.htf_bias_display, "bullish")

    def test_derive_display_state_prefers_confirmed_signal(self):
        result = derive_display_state(
            confirmed_signal={"timeframe": "M5", "watch_key": "watch-1"},
            unique_new_watches=[],
            retained_watches=[],
            selected_rejection=None,
            best_directional_context=None,
            primary_context=None,
        )
        self.assertEqual(result.state, SetupState.TRIGGERED.value)
        self.assertEqual(result.phase, SetupPhase.READY.value)
        self.assertEqual(result.waiting_for, "entry")

    @patch("domain.strategy.pipeline.compute_setup_score")
    def test_score_setup_returns_existing_score_contract(self, compute_setup_score_mock):
        compute_setup_score_mock.return_value = (8.5, "A", {"htf": 3.0})

        result = score_setup({"bias": "Long"}, {"watch_key": "1"}, None)

        self.assertEqual(result.score, 8.5)
        self.assertEqual(result.grade, "A")
        self.assertEqual(result.score_components, {"htf": 3.0})


if __name__ == "__main__":
    unittest.main()
