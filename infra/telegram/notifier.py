import json

import requests

from domain.alerts import build_watch_armed_message
from legacy.bridges.notifications import build_signal_caption, build_signal_charts


class TelegramNotifier:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

    def missing_fields(self) -> list[str]:
        missing = []
        if not self.config.enabled:
            return missing
        if not self.config.bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.config.chat_id:
            missing.append("TELEGRAM_CHAT_ID")
        return missing

    def is_configured(self) -> bool:
        return self.config.enabled and not self.missing_fields()

    def status_snapshot(self) -> dict:
        return {
            "enabled": self.config.enabled,
            "configured": self.is_configured(),
            "missing_fields": self.missing_fields(),
        }

    @staticmethod
    def _raise_for_telegram_failure(response) -> None:
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError:
            return
        if isinstance(payload, dict) and not payload.get("ok", True):
            description = payload.get("description") or "Telegram API reported ok=false."
            raise requests.RequestException(str(description))

    def _send_message(self, text: str, chat_id: str | None = None):
        url = f"https://api.telegram.org/bot{self.config.bot_token}/sendMessage"
        response = requests.post(
            url,
            data={"chat_id": chat_id or self.config.chat_id, "text": text},
            timeout=15,
        )
        self._raise_for_telegram_failure(response)

    def send_text(self, text: str, chat_id: str | None = None) -> tuple[bool, str | None]:
        if not self.config.enabled:
            return False, "telegram disabled"
        if not self.is_configured():
            return False, f"missing {', '.join(self.missing_fields())}"
        try:
            self._send_message(text, chat_id=chat_id)
            return True, None
        except requests.RequestException as exc:
            return False, str(exc)

    def send_watch_armed(self, watch: dict) -> tuple[bool, str | None]:
        if not self.config.enabled:
            return False, "telegram disabled"
        if not self.is_configured():
            return False, f"missing {', '.join(self.missing_fields())}"

        text = build_watch_armed_message(watch)
        try:
            self._send_message(text)
            return True, None
        except requests.RequestException as exc:
            return False, str(exc)

    def send_confirmed_signal(self, snapshot: dict, signal: dict) -> tuple[bool, str | None]:
        if not self.config.enabled:
            return False, "telegram disabled"
        if not self.is_configured():
            return False, f"missing {', '.join(self.missing_fields())}"

        chart_paths = build_signal_charts(snapshot, signal)
        if chart_paths is None:
            return False, "chart evidence was not clear enough to render"

        media = [
            {"type": "photo", "media": "attach://htf_chart", "caption": build_signal_caption(signal)},
            {"type": "photo", "media": "attach://ltf_chart"},
        ]
        url = f"https://api.telegram.org/bot{self.config.bot_token}/sendMediaGroup"
        try:
            with open(chart_paths["htf"], "rb") as htf_file, open(chart_paths["ltf"], "rb") as ltf_file:
                response = requests.post(
                    url,
                    data={"chat_id": self.config.chat_id, "media": json.dumps(media)},
                    files={"htf_chart": htf_file, "ltf_chart": ltf_file},
                    timeout=30,
                )
                self._raise_for_telegram_failure(response)
            return True, None
        except requests.RequestException as exc:
            return False, str(exc)
        finally:
            for path in chart_paths.values():
                path.unlink(missing_ok=True)
