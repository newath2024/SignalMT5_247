import unittest

from ui.presenters.symbol_presenter import build_inspector_model, format_inspector_value
from ui.viewmodels.main_window_vm import build_status_header_vm, render_activity_log


class UiPresenterTests(unittest.TestCase):
    def test_build_status_header_vm_preserves_status_copy(self):
        vm = build_status_header_vm(
            scanner={"status": "running", "running": True, "interval_sec": 60, "progress": {}, "last_cycle": {}},
            metrics={"scanned_symbols": 12, "total_symbols": 12},
            strategy={"ob_fvg_mode": "strict"},
            now=0,
        )

        self.assertEqual(vm.headline, "Scanner armed and scanning for sweep setups")
        self.assertIn("Market coverage 12/12", vm.progress_text)
        self.assertIn("iFVG mode strict", vm.progress_text)

    def test_render_activity_log_preserves_reason_suffix(self):
        rendered = render_activity_log(
            [
                {
                    "label": "2026-03-25 17:00:00",
                    "level": "WARN",
                    "symbol": "USDJPY",
                    "timeframe": "M5",
                    "message": "Setup rejected",
                    "phase": "watch",
                    "reason": "missing strict iFVG",
                }
            ],
            "all",
            "",
        )
        self.assertIn("reason=missing strict iFVG", rendered)

    def test_build_inspector_model_preserves_summary_labels(self):
        detail, summary = build_inspector_model(
            {
                "symbol": "USDJPY",
                "state": "awaiting_ifvg",
                "bias": "bearish",
                "phase": "waiting_ifvg",
                "tf": "M5",
                "price": 158.914,
                "last_update": "2026-03-25T17:18:00",
                "detail": {
                    "htf_context": "H1 bearish FVG",
                    "last_detected_sweep": "Primary sweep: buy-side liquidity @ 159.202",
                },
            }
        )

        self.assertEqual(detail["current_state"], "Awaiting iFVG")
        self.assertIn("M5", summary)
        self.assertEqual(format_inspector_value("last_alert_time", None), "-")

    def test_build_inspector_model_resets_stale_cooldown_copy_when_remaining_is_zero(self):
        detail, _summary = build_inspector_model(
            {
                "symbol": "EURUSD",
                "state": "cooldown",
                "cooldown_remaining": 0,
                "detail": {
                    "cooldown_info": "127s remaining until stale timestamp",
                },
            }
        )

        self.assertEqual(detail["cooldown_info"], "-")


if __name__ == "__main__":
    unittest.main()
