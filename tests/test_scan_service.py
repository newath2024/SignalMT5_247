import datetime as dt
import unittest

from services.scan_service import ScanService


class FakeGateway:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def fetch_symbol_snapshot(self, symbol: str):
        return self.snapshot

    def status_snapshot(self):
        return {"last_error": None}


class FakeStrategyEngine:
    def __init__(self, decision):
        self.decision = decision

    def evaluate_symbol(self, snapshot, active_watches):
        return self.decision


class FakeStateManager:
    def __init__(self, calls):
        self.calls = calls

    def list_active_watches(self, **kwargs):
        self.calls.append("list_active_watches")
        return []

    def record_timeline_event(self, **kwargs):
        self.calls.append(f"timeline:{kwargs['event']}")

    def remove_watch(self, *args, **kwargs):
        self.calls.append("remove_watch")

    def upsert_watch(self, watch):
        self.calls.append(f"upsert_watch:{watch['watch_key']}")
        return True, watch

    def record_rejection(self, **kwargs):
        self.calls.append("record_rejection")

    def get_watch(self, active_watch_id):
        return None

    def last_alert_for_symbol(self, symbol):
        return None

    def timeline_for_symbol(self, symbol):
        return {"lines": [], "markers": {}}

    def upsert_symbol_state(self, payload):
        self.calls.append("upsert_symbol_state")
        payload = dict(payload)
        payload["transition"] = None
        return payload

    def cooldown_remaining(self, *args, **kwargs):
        return 0

    def cooldown_until(self, *args, **kwargs):
        return None


class FakeAlertService:
    def __init__(self, calls):
        self.calls = calls
        self.config = type("Cfg", (), {"scanner": type("Scanner", (), {"cooldown_sec": 1800})()})()

    def handle_watch_armed(self, watch):
        self.calls.append(f"handle_watch_armed:{watch['watch_key']}")
        return {"status": "sent", "message": "ok"}


class FakeLogger:
    def error(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def warn(self, *args, **kwargs):
        pass

    def watch(self, *args, **kwargs):
        pass

    def signal(self, *args, **kwargs):
        pass


class FakeDecision:
    def __init__(self):
        self.primary_context = None
        self.htf_context = "H1 OB"
        self.state = "armed"
        self.phase = "ready"
        self.reason = "watch armed"
        self.htf_bias = "long"
        self.timeframe = "M5"
        self.score = 7.0
        self.grade = "A"
        self.active_watch_id = "watch-1"
        self.detail = {}
        self.score_components = {"htf": 1.0}
        self.focus_watch = {
            "watch_key": "watch-1",
            "symbol": "EURUSD",
            "timeframe": "M5",
            "status": "armed",
            "status_reason": "watch armed",
            "waiting_for": "trigger",
            "direction": "LONG",
            "zone_top": 1.2,
            "zone_bottom": 1.1,
        }
        self.confirmed_signal = None
        self.active_watches = [self.focus_watch]
        self.removed_watches = []
        self.rejections = []
        self.current_price = 1.15
        self.broker_now = dt.datetime(2026, 3, 25, 12, 0, 0).isoformat()


class ScanServiceTests(unittest.TestCase):
    def test_scan_symbol_persists_watch_before_alerting(self):
        calls = []
        snapshot = {
            "symbol": "EURUSD",
            "current_price": 1.15,
            "broker_now": dt.datetime(2026, 3, 25, 12, 0, 0),
        }
        service = ScanService(
            data_gateway=FakeGateway(snapshot),
            strategy_engine=FakeStrategyEngine(FakeDecision()),
            state_manager=FakeStateManager(calls),
            alert_service=FakeAlertService(calls),
            logger=FakeLogger(),
        )

        service.scan_symbol("EURUSD")

        self.assertLess(calls.index("upsert_watch:watch-1"), calls.index("handle_watch_armed:watch-1"))
        self.assertIn("upsert_symbol_state", calls)


if __name__ == "__main__":
    unittest.main()
