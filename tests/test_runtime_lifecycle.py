import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from app.lifecycle import AppLifecycle
from infra.storage.database import SQLiteStore
from ui.presentation import get_state_badge, get_state_icon, get_state_label


class RuntimeLifecycleTests(unittest.TestCase):
    def test_lifecycle_shutdown_closes_sqlite(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            sqlite = SQLiteStore(Path(temp_dir) / "runtime.db")
            runtime = type(
                "Runtime",
                (),
                {
                    "telegram_bot": MagicMock(),
                    "scanner_service": MagicMock(),
                    "engine": MagicMock(),
                    "sqlite": sqlite,
                },
            )()
            lifecycle = AppLifecycle(config=MagicMock(), runtime=runtime)

            lifecycle.shutdown()
            lifecycle.shutdown()

            runtime.telegram_bot.stop.assert_called()
            runtime.scanner_service.stop.assert_called()
            runtime.engine.stop.assert_called()
            self.assertTrue(sqlite._closed)

    def test_state_badge_uses_clean_ascii_icons(self):
        self.assertEqual(get_state_icon("armed"), "+")
        self.assertEqual(get_state_label("ERROR"), "Attention")
        self.assertEqual(get_state_badge("cooldown"), "o Cooling Down")


if __name__ == "__main__":
    unittest.main()
