from core.enums import AlertMode, SignalStage


class AlertService:
    def __init__(self, config, state_manager, notifier, logger):
        self.config = config
        self.state_manager = state_manager
        self.notifier = notifier
        self.logger = logger

    def _allows_watch_alert(self) -> bool:
        return self.config.scanner.alert_mode in (AlertMode.ARMED_ONLY, AlertMode.BOTH)

    def _allows_confirmed_alert(self) -> bool:
        return self.config.scanner.alert_mode in (AlertMode.CONFIRMED_ONLY, AlertMode.BOTH)

    def handle_watch_armed(self, watch: dict) -> dict:
        event_key = f"watch:{watch['watch_key']}"
        if not self.state_manager.has_signal_event(SignalStage.WATCH_ARMED.value, watch["watch_key"]):
            self.state_manager.record_signal_event(
                stage=SignalStage.WATCH_ARMED.value,
                symbol=watch["symbol"],
                timeframe=watch["timeframe"],
                bias=watch["bias"],
                event_key=watch["watch_key"],
                status="armed",
                reason="HTF context valid + sweep + strict iFVG",
                payload=watch,
            )

        if not self._allows_watch_alert():
            return {"status": "recorded_only", "message": "Watch armed recorded without Telegram dispatch."}

        if not self.notifier.config.enabled:
            return {"status": "config_missing", "message": "Telegram disabled."}

        if not self.state_manager.can_emit(event_key, self.config.scanner.cooldown_sec):
            remaining = self.state_manager.cooldown_remaining(event_key, self.config.scanner.cooldown_sec)
            self.state_manager.record_alert_dispatch(
                symbol=watch["symbol"],
                timeframe=watch["timeframe"],
                stage=SignalStage.WATCH_ARMED.value,
                channel="telegram",
                event_key=event_key,
                status="cooldown",
                reason=f"{remaining}s remaining",
                payload=watch,
            )
            return {"status": "cooldown", "message": f"Watch alert blocked by cooldown ({remaining}s)."}

        success, error = self.notifier.send_watch_armed(watch)
        if success:
            self.state_manager.record_alert_dispatch(
                symbol=watch["symbol"],
                timeframe=watch["timeframe"],
                stage=SignalStage.WATCH_ARMED.value,
                channel="telegram",
                event_key=event_key,
                status="sent",
                payload=watch,
                mark_cooldown=True,
            )
            return {"status": "sent", "message": "Watch armed alert sent."}

        if error and error.startswith("missing "):
            return {"status": "config_missing", "message": error}

        self.state_manager.record_alert_dispatch(
            symbol=watch["symbol"],
            timeframe=watch["timeframe"],
            stage=SignalStage.WATCH_ARMED.value,
            channel="telegram",
            event_key=event_key,
            status="failed",
            reason=error,
            payload=watch,
        )
        return {"status": "failed", "message": error or "Watch alert delivery failed."}

    def handle_confirmed_signal(self, snapshot: dict, signal: dict) -> dict:
        event_key = f"signal:{signal['setup_key']}"
        if not self.state_manager.has_signal_event(SignalStage.CONFIRMED_SIGNAL.value, signal["setup_key"]):
            self.state_manager.record_signal_event(
                stage=SignalStage.CONFIRMED_SIGNAL.value,
                symbol=signal["symbol"],
                timeframe=signal["timeframe"],
                bias=signal["bias"],
                event_key=signal["setup_key"],
                status="confirmed",
                reason="MSS confirmed after sweep + strict iFVG",
                payload=signal,
            )

        if not self._allows_confirmed_alert():
            return {"status": "recorded_only", "message": "Confirmed signal recorded without Telegram dispatch."}

        if not self.notifier.config.enabled:
            return {"status": "config_missing", "message": "Telegram disabled."}

        if not self.state_manager.can_emit(event_key, self.config.scanner.cooldown_sec):
            remaining = self.state_manager.cooldown_remaining(event_key, self.config.scanner.cooldown_sec)
            self.state_manager.record_alert_dispatch(
                symbol=signal["symbol"],
                timeframe=signal["timeframe"],
                stage=SignalStage.CONFIRMED_SIGNAL.value,
                channel="telegram",
                event_key=event_key,
                status="cooldown",
                reason=f"{remaining}s remaining",
                payload=signal,
            )
            return {"status": "cooldown", "message": f"Confirmed signal blocked by cooldown ({remaining}s)."}

        success, error = self.notifier.send_confirmed_signal(snapshot, signal)
        if success:
            self.state_manager.record_alert_dispatch(
                symbol=signal["symbol"],
                timeframe=signal["timeframe"],
                stage=SignalStage.CONFIRMED_SIGNAL.value,
                channel="telegram",
                event_key=event_key,
                status="sent",
                payload=signal,
                mark_cooldown=True,
            )
            return {"status": "sent", "message": "Confirmed signal sent to Telegram."}

        if error and error.startswith("missing "):
            return {"status": "config_missing", "message": error}

        self.state_manager.record_alert_dispatch(
            symbol=signal["symbol"],
            timeframe=signal["timeframe"],
            stage=SignalStage.CONFIRMED_SIGNAL.value,
            channel="telegram",
            event_key=event_key,
            status="failed",
            reason=error,
            payload=signal,
        )
        return {"status": "failed", "message": error or "Confirmed signal delivery failed."}
