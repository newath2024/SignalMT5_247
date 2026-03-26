import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from infra.mt5.runtime import (
    MT5RuntimeSettings,
    _safe_mt5_shutdown,
    apply_mt5_window_mode,
    connect_mt5_with_retry,
)

TEST_PATH = Path(__file__)


class Mt5RuntimeTests(unittest.TestCase):
    @patch("infra.mt5.runtime.os.name", "posix")
    def test_apply_mt5_window_mode_returns_false_outside_windows(self):
        logger = MagicMock()
        settings = MT5RuntimeSettings(
            terminal_path=TEST_PATH,
            portable_root=TEST_PATH.parent,
            start_timeout_sec=30,
            init_retries=1,
            init_retry_delay_sec=1.0,
            launch_delay_sec=0.0,
            auto_launch=False,
            init_mode="path",
            require_saved_session=True,
            max_tick_age_sec=0,
            window_mode="minimize",
            ready_symbol=None,
        )

        applied = apply_mt5_window_mode(1234, settings=settings, logger=logger)

        self.assertFalse(applied)
        logger.warn.assert_called_once()

    def test_safe_mt5_shutdown_ignores_shutdown_errors(self):
        mt5 = MagicMock()
        mt5.shutdown.side_effect = RuntimeError("boom")

        _safe_mt5_shutdown(mt5)

        mt5.shutdown.assert_called_once_with()

    def test_connect_mt5_with_retry_tolerates_shutdown_failure_before_initialize(self):
        mt5 = MagicMock()
        mt5.shutdown.side_effect = RuntimeError("boom")
        mt5.initialize.return_value = False
        mt5.last_error.return_value = (500, "init failed")
        settings = MT5RuntimeSettings(
            terminal_path=TEST_PATH,
            portable_root=TEST_PATH.parent,
            start_timeout_sec=30,
            init_retries=1,
            init_retry_delay_sec=1.0,
            launch_delay_sec=0.0,
            auto_launch=False,
            init_mode="path",
            require_saved_session=True,
            max_tick_age_sec=0,
            window_mode="normal",
            ready_symbol=None,
        )

        report = connect_mt5_with_retry(mt5, settings=settings, logger=MagicMock())

        self.assertFalse(report.ready)
        self.assertEqual(report.state, "initialize_failed")
        mt5.initialize.assert_called_once()


if __name__ == "__main__":
    unittest.main()
