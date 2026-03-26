import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

from infra.telegram.command_bot import TelegramCommandBot
from infra.telegram.notifier import TelegramNotifier


class TelegramRuntimeTests(unittest.TestCase):
    def test_notifier_rejects_ok_false_payload(self):
        notifier = TelegramNotifier(
            config=type("Cfg", (), {"enabled": True, "bot_token": "token", "chat_id": "chat"})(),
            logger=object(),
        )
        response = MagicMock()
        response.json.return_value = {"ok": False, "description": "chat not found"}

        with patch("infra.telegram.notifier.requests.post", return_value=response):
            success, reason = notifier.send_text("hello")

        self.assertFalse(success)
        self.assertEqual(reason, "chat not found")

    def test_confirmed_signal_cleans_up_chart_files_when_telegram_rejects_payload(self):
        notifier = TelegramNotifier(
            config=type("Cfg", (), {"enabled": True, "bot_token": "token", "chat_id": "chat"})(),
            logger=object(),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            htf = Path(temp_dir) / "htf.png"
            ltf = Path(temp_dir) / "ltf.png"
            htf.write_bytes(b"htf")
            ltf.write_bytes(b"ltf")
            response = MagicMock()
            response.json.return_value = {"ok": False, "description": "bad media group"}

            with patch("infra.telegram.notifier.build_signal_charts", return_value={"htf": htf, "ltf": ltf}):
                with patch("infra.telegram.notifier.build_signal_caption", return_value="caption"):
                    with patch("infra.telegram.notifier.requests.post", return_value=response):
                        success, reason = notifier.send_confirmed_signal({}, {"symbol": "EURUSD"})

        self.assertFalse(success)
        self.assertEqual(reason, "bad media group")
        self.assertFalse(htf.exists())
        self.assertFalse(ltf.exists())

    def test_command_bot_wait_or_stop_returns_immediately_when_stopped(self):
        bot = TelegramCommandBot(
            config=type("Cfg", (), {"enabled": True, "bot_token": "token", "chat_id": "chat"})(),
            notifier=MagicMock(),
            symbol_registry=MagicMock(),
            scanner_service=MagicMock(),
            logger=MagicMock(),
            poll_timeout_sec=5,
        )
        stop_event = MagicMock()
        stop_event.wait.return_value = True
        bot._stop_event = stop_event

        self.assertTrue(bot._wait_or_stop(3.0))
        stop_event.wait.assert_called_once_with(3.0)

    def test_command_bot_fetch_updates_raises_on_ok_false_payload(self):
        bot = TelegramCommandBot(
            config=type("Cfg", (), {"enabled": True, "bot_token": "token", "chat_id": "chat"})(),
            notifier=MagicMock(),
            symbol_registry=MagicMock(),
            scanner_service=MagicMock(),
            logger=MagicMock(),
            poll_timeout_sec=5,
        )
        response = MagicMock()
        response.json.return_value = {"ok": False, "description": "unauthorized"}

        with patch("infra.telegram.command_bot.requests.get", return_value=response):
            with self.assertRaises(requests.RequestException):
                bot._fetch_updates()


if __name__ == "__main__":
    unittest.main()
