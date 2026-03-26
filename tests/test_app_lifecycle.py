import unittest
from unittest.mock import MagicMock

from app.lifecycle import AppLifecycle


class AppLifecycleTests(unittest.TestCase):
    def test_shutdown_stops_runtime_services_even_when_startup_flag_is_false(self):
        runtime = type(
            "Runtime",
            (),
            {
                "telegram_bot": MagicMock(),
                "scanner_service": MagicMock(),
                "engine": MagicMock(),
                "sqlite": MagicMock(),
            },
        )()
        lifecycle = AppLifecycle(config=MagicMock(), runtime=runtime)

        lifecycle.shutdown()

        runtime.telegram_bot.stop.assert_called_once_with()
        runtime.scanner_service.stop.assert_called_once_with()
        runtime.engine.stop.assert_called_once_with()
        runtime.sqlite.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
