import time


class ScanService:
    def __init__(self, data_gateway, strategy_engine, state_manager, alert_service, logger):
        self.data_gateway = data_gateway
        self.strategy_engine = strategy_engine
        self.state_manager = state_manager
        self.alert_service = alert_service
        self.logger = logger

    def scan_symbol(self, symbol: str) -> dict:
        snapshot = self.data_gateway.fetch_symbol_snapshot(symbol)
        if snapshot is None:
            self.logger.warn("Market data unavailable", symbol=symbol, phase="connection", reason=self.data_gateway.status_snapshot().get("last_error"))
            return {
                "symbol": symbol,
                "status": "unavailable",
                "message": "Market data unavailable",
                "scanned_at": time.time(),
                "current_price": None,
                "timeframe": "-",
                "bias": "-",
                "last_rejection": self.state_manager.last_rejection_for_symbol(symbol),
            }

        active_watches = self.state_manager.list_active_watches(symbol=symbol, statuses=("armed", "confirmed", "cooldown"))
        decision = self.strategy_engine.evaluate_symbol(snapshot, active_watches)

        for removed in decision.removed_watches:
            self.state_manager.remove_watch(removed["watch_key"], removed.get("removal_reason"))
            self.logger.info(
                "Watch removed from pipeline",
                symbol=symbol,
                timeframe=removed.get("timeframe"),
                phase="watch",
                reason=removed.get("removal_reason"),
            )

        stored_new_watches = []
        for watch in decision.active_watches:
            created, stored = self.state_manager.upsert_watch(watch)
            if created:
                stored_new_watches.append(stored)

        for rejection in decision.rejections:
            self.state_manager.record_rejection(
                symbol=rejection["symbol"],
                timeframe=rejection["timeframe"],
                bias=rejection.get("bias"),
                phase=rejection["phase"],
                reason=rejection["reason"],
                payload=rejection,
            )
            self.logger.warn(
                "Setup rejected",
                symbol=rejection["symbol"],
                timeframe=rejection["timeframe"],
                phase=rejection["phase"],
                reason=rejection["reason"],
            )

        for watch in stored_new_watches:
            self.logger.watch(
                "armed after liquidity sweep",
                symbol=watch["symbol"],
                timeframe=watch["timeframe"],
                phase="watch",
                reason="strict iFVG",
            )
            alert_result = self.alert_service.handle_watch_armed(watch)
            if alert_result["status"] == "failed":
                self.logger.error(
                    "Watch alert delivery failed",
                    symbol=watch["symbol"],
                    timeframe=watch["timeframe"],
                    phase="alert",
                    reason=alert_result["message"],
                )

        status = decision.status
        message = decision.message
        bias = "-"
        timeframe = "-"
        cooldown_remaining = 0

        if decision.confirmed_signal is not None:
            signal = decision.confirmed_signal
            bias = signal["bias"]
            timeframe = signal["timeframe"]
            signal_result = self.alert_service.handle_confirmed_signal(snapshot, signal)

            if signal_result["status"] == "sent":
                self.state_manager.mark_watch_confirmed(signal["watch_key"], signal["mss_index"], status="confirmed")
                status = "signal_confirmed"
                message = signal_result["message"]
                self.logger.signal(
                    "long confirmed after MSS + strict iFVG" if signal["bias"] == "Long" else "short confirmed after MSS + strict iFVG",
                    symbol=signal["symbol"],
                    timeframe=signal["timeframe"],
                    phase="signal",
                    reason="telegram sent",
                )
            elif signal_result["status"] == "cooldown":
                self.state_manager.mark_watch_confirmed(
                    signal["watch_key"],
                    signal["mss_index"],
                    status="cooldown",
                    reason=signal_result["message"],
                )
                status = "cooldown"
                message = signal_result["message"]
                cooldown_remaining = self.state_manager.cooldown_remaining(
                    f"signal:{signal['setup_key']}",
                    self.alert_service.config.scanner.cooldown_sec,
                )
                self.logger.warn(
                    "Signal blocked by cooldown",
                    symbol=signal["symbol"],
                    timeframe=signal["timeframe"],
                    phase="alert",
                    reason=signal_result["message"],
                )
            elif signal_result["status"] == "recorded_only":
                self.state_manager.mark_watch_confirmed(signal["watch_key"], signal["mss_index"], status="confirmed")
                status = "signal_confirmed"
                message = signal_result["message"]
                self.logger.signal(
                    "confirmed signal recorded locally",
                    symbol=signal["symbol"],
                    timeframe=signal["timeframe"],
                    phase="signal",
                    reason="alert mode skips confirmed dispatch",
                )
            elif signal_result["status"] == "config_missing":
                status = "delivery_failed"
                message = signal_result["message"]
                self.logger.warn(
                    "Telegram configuration missing",
                    symbol=signal["symbol"],
                    timeframe=signal["timeframe"],
                    phase="alert",
                    reason=signal_result["message"],
                )
            else:
                status = "delivery_failed"
                message = signal_result["message"]
                self.logger.error(
                    "Confirmed signal delivery failed",
                    symbol=signal["symbol"],
                    timeframe=signal["timeframe"],
                    phase="alert",
                    reason=signal_result["message"],
                )

        last_rejection = self.state_manager.last_rejection_for_symbol(symbol)
        return {
            "symbol": symbol,
            "status": status,
            "message": message,
            "scanned_at": time.time(),
            "current_price": decision.current_price,
            "timeframe": timeframe,
            "bias": bias,
            "cooldown_remaining": cooldown_remaining,
            "last_rejection": last_rejection,
        }
