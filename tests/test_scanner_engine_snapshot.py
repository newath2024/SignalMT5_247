import unittest

from app.runtime.scanner_engine import ScannerEngine


class _DummyGateway:
    def ensure_connected(self):
        return True

    def disconnect(self):
        return None

    def status_snapshot(self):
        return {"connected": True}


class _DummyNotifier:
    def status_snapshot(self):
        return {"configured": True}


class _DummyStateManager:
    def list_symbol_states(self, _symbols):
        return []

    def list_active_watches(self, **_kwargs):
        return []

    def recent_alerts(self, limit=50):
        return []

    def recent_rejections(self, limit=20):
        return []

    def confirmed_signals_today(self):
        return 0


class _DummyLogger:
    def recent_entries(self, limit=200):
        return []


class ScannerEngineSnapshotTests(unittest.TestCase):
    def test_snapshot_returns_deep_copy_of_symbol_states(self):
        config = type(
            "Cfg",
            (),
            {
                "scanner": type(
                    "ScannerCfg",
                    (),
                    {
                        "loop_interval_sec": 60,
                        "cooldown_sec": 1800,
                        "symbols": ["EURUSD"],
                    },
                )(),
                "app": object(),
            },
        )()
        engine = ScannerEngine(
            config=config,
            data_gateway=_DummyGateway(),
            notifier=_DummyNotifier(),
            state_manager=_DummyStateManager(),
            scan_service=object(),
            logger=_DummyLogger(),
            runtime_state=None,
        )
        engine._symbol_states["EURUSD"] = {
            "symbol": "EURUSD",
            "state": "armed",
            "detail": {
                "timeline": ["first"],
            },
        }

        snapshot = engine.snapshot()
        snapshot["symbols"][0]["detail"]["timeline"].append("mutated")

        fresh = engine.snapshot()
        self.assertEqual(["first"], fresh["symbols"][0]["detail"]["timeline"])


if __name__ == "__main__":
    unittest.main()
