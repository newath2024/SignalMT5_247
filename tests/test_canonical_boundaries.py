import unittest
from unittest.mock import patch

from domain.models import AlertRecordModel, SymbolStateModel, TimelineEventModel, TimelineModel, WatchPipelineModel
from infra.telegram.notifier import TelegramNotifier


class CanonicalBoundaryTests(unittest.TestCase):
    def test_domain_models_are_compatibility_reexports_only(self):
        self.assertEqual(SymbolStateModel.__module__, "domain.models.runtime")
        self.assertEqual(WatchPipelineModel.__module__, "domain.models.runtime")
        self.assertEqual(AlertRecordModel.__module__, "domain.models.records")
        self.assertEqual(TimelineEventModel.__module__, "domain.models.records")
        self.assertEqual(TimelineModel.__module__, "domain.models.records")

    @patch("infra.telegram.notifier.build_signal_charts")
    @patch("infra.telegram.notifier.requests.post")
    @patch("infra.telegram.notifier.build_watch_armed_message")
    def test_telegram_notifier_keeps_transport_formatting_in_infra(
        self,
        build_watch_message_mock,
        requests_post_mock,
        build_signal_charts_mock,
    ):
        build_watch_message_mock.return_value = "watch text"
        build_signal_charts_mock.return_value = None
        notifier = TelegramNotifier(
            config=type(
                "Cfg",
                (),
                {"enabled": True, "bot_token": "token", "chat_id": "chat"},
            )(),
            logger=object(),
        )

        notifier.send_watch_armed({"symbol": "EURUSD", "timeframe": "M5", "bias": "Long", "htf_context": "H1 OB"})
        build_watch_message_mock.assert_called_once()
        requests_post_mock.reset_mock()

        success, reason = notifier.send_confirmed_signal({}, {"symbol": "EURUSD"})
        self.assertFalse(success)
        self.assertEqual(reason, "chart evidence was not clear enough to render")
        requests_post_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
