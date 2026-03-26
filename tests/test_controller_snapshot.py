import unittest

from app.controller import AppController


class FakeLifecycle:
    def __init__(self, snapshot, full_scan_active=False):
        self.config = type("Cfg", (), {"app": object()})()
        self.runtime = type(
            "Runtime",
            (),
            {
                "logger": object(),
                "runtime_state": type(
                    "RuntimeState",
                    (),
                    {
                        "list_active_jobs": staticmethod(lambda: [{"job_id": "abc"}]),
                        "recent_jobs": staticmethod(lambda limit=10: [{"job_id": "xyz"}]),
                        "is_full_scan_active": staticmethod(lambda: full_scan_active),
                    },
                )(),
                "engine": type("Engine", (), {"snapshot": staticmethod(lambda: snapshot)})(),
            },
        )()

    def current_ob_fvg_mode(self):
        return "medium"

    def shutdown(self):
        return None


class ControllerSnapshotTests(unittest.TestCase):
    def test_snapshot_marks_full_scan_active_when_engine_progress_is_multi_symbol(self):
        lifecycle = FakeLifecycle(
            {
                "scanner": {
                    "progress": {
                        "active": True,
                        "total": 4,
                    }
                }
            },
            full_scan_active=False,
        )

        snapshot = AppController(lifecycle).snapshot()

        self.assertTrue(snapshot["runtime"]["full_scan_active"])

    def test_snapshot_preserves_runtime_full_scan_flag_when_engine_is_idle(self):
        lifecycle = FakeLifecycle(
            {
                "scanner": {
                    "progress": {
                        "active": False,
                        "total": 0,
                    }
                }
            },
            full_scan_active=True,
        )

        snapshot = AppController(lifecycle).snapshot()

        self.assertTrue(snapshot["runtime"]["full_scan_active"])


if __name__ == "__main__":
    unittest.main()
