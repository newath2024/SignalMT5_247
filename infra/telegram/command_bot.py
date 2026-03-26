from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import requests

from infra.config.paths import DATA_DIR
from infra.process_lock import ProcessFileLock


class TelegramCommandBot:
    def __init__(self, config, notifier, symbol_registry, scanner_service, logger, poll_timeout_sec: int = 20):
        self.config = config
        self.notifier = notifier
        self.symbol_registry = symbol_registry
        self.scanner_service = scanner_service
        self.logger = logger
        self.poll_timeout_sec = max(5, int(poll_timeout_sec))
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._update_offset: int | None = None
        self._process_lock = ProcessFileLock(Path(DATA_DIR) / "telegram_command_bot.lock")

    def start(self):
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False, "Telegram command bot already running."
            if not self.config.enabled:
                self.logger.info("Telegram command bot disabled", phase="telegram", reason="telegram.enabled=false")
                return False, "Telegram disabled."
            if not self.notifier.is_configured():
                self.logger.warn(
                    "Telegram command bot unavailable",
                    phase="telegram",
                    reason=f"missing {', '.join(self.notifier.missing_fields())}",
                )
                return False, "Telegram is not configured."
            if not self._acquire_process_lock():
                self.logger.warn(
                    "Telegram command bot skipped",
                    phase="telegram",
                    reason="another process already owns the Telegram polling lock",
                )
                return False, "Telegram polling is already active in another process."
            self._stop_event = threading.Event()
            self._thread = threading.Thread(target=self._poll_loop, name="OpenClawTelegramCommandBot", daemon=True)
            self._thread.start()
        return True, "Telegram command bot started."

    def stop(self):
        thread = None
        with self._lock:
            thread = self._thread
            stop_event = self._stop_event
            self._thread = None
            self._stop_event = None
        if stop_event is not None:
            stop_event.set()
        if thread is not None:
            thread.join(timeout=3.0)
        self._release_process_lock()
        return True, "Telegram command bot stopped."

    def _acquire_process_lock(self) -> bool:
        return self._process_lock.acquire()

    def _release_process_lock(self) -> None:
        self._process_lock.release()

    def _poll_loop(self):
        while self._should_keep_polling():
            try:
                for update in self._fetch_updates():
                    self._handle_update(update)
                    if not self._should_keep_polling():
                        break
            except requests.RequestException as exc:
                self.logger.error("Telegram polling failed", phase="telegram", reason=str(exc))
                if self._wait_or_stop(3.0):
                    break
            except Exception as exc:
                self.logger.error("Telegram command bot crashed", phase="telegram", reason=str(exc))
                if self._wait_or_stop(3.0):
                    break

    def _should_keep_polling(self) -> bool:
        stop_event = self._stop_event
        return stop_event is not None and not stop_event.is_set()

    def _wait_or_stop(self, timeout_sec: float) -> bool:
        stop_event = self._stop_event
        if stop_event is None:
            return True
        return stop_event.wait(timeout_sec)

    def _fetch_updates(self) -> list[dict]:
        url = f"https://api.telegram.org/bot{self.config.bot_token}/getUpdates"
        response = requests.get(
            url,
            params={"timeout": self.poll_timeout_sec, "offset": self._update_offset},
            timeout=self.poll_timeout_sec + 10,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise requests.RequestException(f"Telegram getUpdates failed: {payload}")
        updates = payload.get("result", [])
        if updates:
            self._update_offset = max(int(item.get("update_id", 0)) for item in updates) + 1
        return updates

    def _handle_update(self, update: dict):
        message = update.get("message") or update.get("edited_message")
        if not message:
            return
        chat = message.get("chat") or {}
        chat_id = str(chat.get("id") or "").strip()
        if not chat_id:
            return
        if self.config.chat_id and chat_id != str(self.config.chat_id):
            self.logger.warn("Telegram command ignored", phase="telegram", reason=f"unauthorized chat_id={chat_id}")
            return
        text = str(message.get("text") or "").strip()
        if not text.startswith("/"):
            return

        command, argument = self._parse_command(text)
        self.logger.info(
            "Telegram command received",
            phase="telegram",
            reason=f"chat_id={chat_id} command={command} argument={argument or '-'}",
        )

        if command == "/scan":
            self._handle_scan(chat_id, argument)
            return
        if command == "/symbols":
            self._send_reply(chat_id, self._format_symbols())
            return
        if command == "/status":
            self._send_reply(chat_id, self._format_status())
            return
        if command == "/detail":
            self._handle_detail(chat_id, argument)
            return
        if command == "/help":
            self._send_reply(chat_id, self._help_text())
            return
        self._send_reply(chat_id, "Unknown command. Use /help to see available commands.")

    def _handle_scan(self, chat_id: str, argument: str):
        if not argument:
            self._send_reply(chat_id, "Usage: /scan <symbol> or /scan all")
            return
        if argument.lower() == "all":
            ok, reply = self.scanner_service.queue_full_scan(
                requested_by=f"telegram:{chat_id}",
                reply_callback=lambda message: self._send_reply(chat_id, message),
            )
            self._send_reply(chat_id, reply)
            return
        ok, reply = self.scanner_service.queue_symbol_scan(
            raw_symbol=argument,
            requested_by=f"telegram:{chat_id}",
            reply_callback=lambda message: self._send_reply(chat_id, message),
        )
        self._send_reply(chat_id, reply)

    def _handle_detail(self, chat_id: str, argument: str):
        if not argument:
            self._send_reply(chat_id, "Usage: /detail <symbol>")
            return
        normalized = self.symbol_registry.normalize_symbol(argument)
        self.logger.info(
            "Telegram symbol normalized",
            symbol=normalized or str(argument).upper(),
            phase="telegram",
            reason=f"raw={argument}",
        )
        if normalized is None:
            self._send_reply(chat_id, f"Unknown symbol '{argument}'. Use /symbols to see configured symbols.")
            return
        state = self.scanner_service.get_symbol_status(normalized)
        if not state:
            self._send_reply(chat_id, f"No status has been recorded yet for {normalized}.")
            return
        self._send_reply(chat_id, self._format_detail(state))

    def _format_symbols(self) -> str:
        symbols = self.symbol_registry.get_all_symbols()
        aliases = self.symbol_registry.get_aliases()
        lines = [
            f"Configured symbols ({len(symbols)}):",
            ", ".join(symbols),
        ]
        if aliases:
            alias_lines = [f"{alias} -> {target}" for alias, target in sorted(aliases.items())]
            lines.append("Aliases:")
            lines.extend(alias_lines[:12])
        lines.append("Use /scan <symbol> to trigger a symbol scan.")
        return "\n".join(lines)

    def _format_status(self) -> str:
        status = self.scanner_service.get_system_status()
        scanner = status.get("scanner", {})
        connections = status.get("connections", {})
        metrics = status.get("metrics", {})
        last_cycle = scanner.get("last_cycle") or {}
        lines = [
            f"Scanner: {scanner.get('status', '-')}",
            f"Loop interval: {scanner.get('interval_sec', '-')}s",
            f"Configured symbols: {metrics.get('total_symbols', 0)}",
            f"Scanned symbols: {metrics.get('scanned_symbols', 0)}",
            f"Active jobs: {len(status.get('active_jobs', []))}",
            f"Full scan busy: {'yes' if status.get('full_scan_active') else 'no'}",
            f"MT5: {'connected' if connections.get('mt5', {}).get('connected') else 'disconnected'}",
            f"Telegram alerts: {'configured' if connections.get('telegram', {}).get('configured') else 'missing config'}",
        ]
        if last_cycle:
            lines.append(
                f"Last cycle: {last_cycle.get('symbol_count', 0)} symbols in {float(last_cycle.get('duration_sec', 0.0)):.1f}s"
            )
        return "\n".join(lines)

    def _format_detail(self, state: dict) -> str:
        detail = state.get("detail") or {}
        lines = [
            f"{state.get('symbol', '-')}",
            f"State: {self.scanner_service._state_label(state.get('state'))}",
            f"Bias: {state.get('bias', '-')}",
            f"HTF: {state.get('htf_context', '-')}",
            f"Phase: {state.get('phase', '-')}",
            f"Reason: {state.get('reason', '-')}",
            f"Price: {state.get('price') if state.get('price') is not None else '-'}",
            f"Score: {state.get('score') if state.get('score') is not None else '-'}",
            f"Last sweep: {detail.get('last_detected_sweep', '-')}",
            f"Last MSS: {detail.get('last_detected_mss', '-')}",
            f"Last iFVG: {detail.get('last_detected_ifvg', '-')}",
            f"Watch: {detail.get('active_watch_info', '-')}",
            f"Updated: {state.get('last_update', '-')}",
        ]
        return "\n".join(lines)

    @staticmethod
    def _parse_command(text: str) -> tuple[str, str]:
        parts = text.split(maxsplit=1)
        command = parts[0].split("@", 1)[0].lower()
        argument = parts[1].strip() if len(parts) > 1 else ""
        return command, argument

    @staticmethod
    def _help_text() -> str:
        return "\n".join(
            [
                "Available commands:",
                "/scan <symbol> - queue a scan for one configured symbol",
                "/scan all - queue a full scan across all configured symbols",
                "/symbols - list configured symbols",
                "/status - show scanner and connection status",
                "/detail <symbol> - show the latest state for one symbol",
                "/help - show this help message",
            ]
        )

    def _send_reply(self, chat_id: str, text: str):
        ok, error = self.notifier.send_text(text, chat_id=chat_id)
        if ok:
            self.logger.info("Telegram reply sent", phase="telegram", reason=f"chat_id={chat_id}")
            return
        self.logger.error("Telegram reply failed", phase="telegram", reason=f"chat_id={chat_id} error={error}")
