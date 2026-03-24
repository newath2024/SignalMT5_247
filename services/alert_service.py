from domain.enums import AlertMode, SignalStage


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
        stage = SignalStage.WATCH_ARMED.value
        event_key = f"watch:{watch['watch_key']}"
        reason = watch.get("status_reason") or "armed: narrative ready after primary sweep"

        if not self.state_manager.has_signal_event(stage, watch["watch_key"]):
            self.state_manager.record_signal_event(
                stage=stage,
                symbol=watch["symbol"],
                timeframe=watch["timeframe"],
                bias=watch["bias"],
                event_key=watch["watch_key"],
                status="armed",
                reason=reason,
                payload=watch,
            )

        if not self._allows_watch_alert():
            return {"status": "recorded_only", "message": "Watch armed recorded without Telegram dispatch."}

        if not self.notifier.config.enabled:
            return {"status": "config_missing", "message": "Telegram disabled."}

        if self.state_manager.has_alert_dispatch(event_key, stage, statuses=("sent",), channel="telegram"):
            dedup_reason = "watch alert already sent for this setup"
            self.state_manager.record_alert_dispatch(
                symbol=watch["symbol"],
                timeframe=watch["timeframe"],
                stage=stage,
                channel="telegram",
                event_key=event_key,
                status="dedup_blocked",
                reason=dedup_reason,
                payload=watch,
            )
            return {"status": "dedup_blocked", "message": dedup_reason}

        if not self.state_manager.can_emit(event_key, self.config.scanner.cooldown_sec):
            remaining = self.state_manager.cooldown_remaining(event_key, self.config.scanner.cooldown_sec)
            self.state_manager.record_alert_dispatch(
                symbol=watch["symbol"],
                timeframe=watch["timeframe"],
                stage=stage,
                channel="telegram",
                event_key=event_key,
                status="cooldown_blocked",
                reason=f"{remaining}s remaining",
                payload=watch,
            )
            return {"status": "cooldown_blocked", "message": f"Watch alert blocked by cooldown ({remaining}s)."}

        success, error = self.notifier.send_watch_armed(watch)
        if success:
            self.state_manager.record_alert_dispatch(
                symbol=watch["symbol"],
                timeframe=watch["timeframe"],
                stage=stage,
                channel="telegram",
                event_key=event_key,
                status="sent",
                reason=reason,
                payload=watch,
                mark_cooldown=True,
            )
            return {"status": "sent", "message": "Watch armed alert sent."}

        if error and error.startswith("missing "):
            return {"status": "config_missing", "message": error}

        self.state_manager.record_alert_dispatch(
            symbol=watch["symbol"],
            timeframe=watch["timeframe"],
            stage=stage,
            channel="telegram",
            event_key=event_key,
            status="failed",
            reason=error,
            payload=watch,
        )
        return {"status": "failed", "message": error or "Watch alert delivery failed."}

    def handle_confirmed_signal(self, snapshot: dict, signal: dict) -> dict:
        stage = SignalStage.CONFIRMED_SIGNAL.value
        event_key = f"signal:{signal['setup_key']}"
        reason = "triggered: narrative ready with MSS + strict iFVG"

        if not self.state_manager.has_signal_event(stage, signal["setup_key"]):
            self.state_manager.record_signal_event(
                stage=stage,
                symbol=signal["symbol"],
                timeframe=signal["timeframe"],
                bias=signal["bias"],
                event_key=signal["setup_key"],
                status="confirmed",
                reason=reason,
                payload=signal,
            )

        if not self._allows_confirmed_alert():
            return {"status": "recorded_only", "message": "Confirmed signal recorded without Telegram dispatch."}

        if not self.notifier.config.enabled:
            return {"status": "config_missing", "message": "Telegram disabled."}

        if self.state_manager.has_alert_dispatch(event_key, stage, statuses=("sent",), channel="telegram"):
            dedup_reason = "confirmed signal already sent for this setup"
            self.state_manager.record_alert_dispatch(
                symbol=signal["symbol"],
                timeframe=signal["timeframe"],
                stage=stage,
                channel="telegram",
                event_key=event_key,
                status="dedup_blocked",
                reason=dedup_reason,
                payload=signal,
            )
            return {"status": "dedup_blocked", "message": dedup_reason}

        if not self.state_manager.can_emit(event_key, self.config.scanner.cooldown_sec):
            remaining = self.state_manager.cooldown_remaining(event_key, self.config.scanner.cooldown_sec)
            self.state_manager.record_alert_dispatch(
                symbol=signal["symbol"],
                timeframe=signal["timeframe"],
                stage=stage,
                channel="telegram",
                event_key=event_key,
                status="cooldown_blocked",
                reason=f"{remaining}s remaining",
                payload=signal,
            )
            return {"status": "cooldown_blocked", "message": f"Confirmed signal blocked by cooldown ({remaining}s)."}

        success, error = self.notifier.send_confirmed_signal(snapshot, signal)
        if success:
            self.state_manager.record_alert_dispatch(
                symbol=signal["symbol"],
                timeframe=signal["timeframe"],
                stage=stage,
                channel="telegram",
                event_key=event_key,
                status="sent",
                reason=reason,
                payload=signal,
                mark_cooldown=True,
            )
            return {"status": "sent", "message": "Confirmed signal sent to Telegram."}

        if error and error.startswith("missing "):
            return {"status": "config_missing", "message": error}

        self.state_manager.record_alert_dispatch(
            symbol=signal["symbol"],
            timeframe=signal["timeframe"],
            stage=stage,
            channel="telegram",
            event_key=event_key,
            status="failed",
            reason=error,
            payload=signal,
        )
        return {"status": "failed", "message": error or "Confirmed signal delivery failed."}
