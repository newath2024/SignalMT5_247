import datetime as dt
import time

from domain.enums import SetupPhase, SetupState
from domain.models import SymbolStateModel
from domain.strategy.reasoning import describe_error, format_score, format_timeline_lines


def _now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _format_number(value) -> str:
    if value is None:
        return "-"
    return f"{float(value):.5f}".rstrip("0").rstrip(".")


class ScanService:
    def __init__(self, data_gateway, strategy_engine, state_manager, alert_service, logger):
        self.data_gateway = data_gateway
        self.strategy_engine = strategy_engine
        self.state_manager = state_manager
        self.alert_service = alert_service
        self.logger = logger

    def _symbol_state_payload(
        self,
        symbol: str,
        state: str,
        bias: str,
        tf: str,
        phase: str,
        reason: str,
        price: float | None,
        score: float | None,
        grade: str | None,
        last_update: str,
        cooldown_remaining: int = 0,
        cooldown_until: str | None = None,
        last_alert_time: str | None = None,
        active_watch_id: str | None = None,
        htf_context: str = "-",
        detail: dict | None = None,
    ) -> dict:
        model = SymbolStateModel(
            symbol=symbol,
            state=state,
            bias=bias,
            tf=tf,
            phase=phase,
            reason=reason,
            price=price,
            score=score,
            grade=grade,
            last_update=last_update,
            scanned_at=time.time(),
            cooldown_remaining=cooldown_remaining,
            cooldown_duration_sec=self.alert_service.config.scanner.cooldown_sec,
            cooldown_until=cooldown_until,
            last_alert_time=last_alert_time,
            active_watch_id=active_watch_id,
            htf_context=htf_context,
            detail=detail or {},
        )
        return model.to_dict()

    def _cooldown_snapshot(self, event_key: str | None) -> tuple[int, str | None]:
        if not event_key:
            return 0, None
        cooldown_sec = self.alert_service.config.scanner.cooldown_sec
        remaining = self.state_manager.cooldown_remaining(event_key, cooldown_sec)
        until = self.state_manager.cooldown_until(event_key, cooldown_sec)
        return remaining, until

    def _apply_last_alert(self, symbol_payload: dict, symbol: str):
        last_alert = self.state_manager.last_alert_for_symbol(symbol)
        detail = dict(symbol_payload.get("detail") or {})
        if last_alert is not None:
            symbol_payload["last_alert_time"] = last_alert.get("time")
            detail["last_alert_time"] = last_alert.get("time")
            detail["last_alert_details"] = (
                f"{last_alert.get('alert_type', '-')} {last_alert.get('status', '-')} | "
                f"{last_alert.get('direction', '-')} {last_alert.get('tf', '-')} | "
                f"entry {_format_number(last_alert.get('entry'))} | SL {_format_number(last_alert.get('sl'))}"
            )
        else:
            detail.setdefault("last_alert_time", None)
            detail.setdefault("last_alert_details", "-")

        cooldown_remaining = symbol_payload.get("cooldown_remaining") or 0
        cooldown_until = symbol_payload.get("cooldown_until")
        if cooldown_remaining > 0 and cooldown_until:
            detail["cooldown_info"] = f"{cooldown_remaining}s remaining until {cooldown_until}"
        else:
            detail["cooldown_info"] = "-"
        symbol_payload["detail"] = detail

    def _apply_timeline(self, symbol_payload: dict, symbol: str):
        timeline = self.state_manager.timeline_for_symbol(symbol)
        detail = dict(symbol_payload.get("detail") or {})
        detail["timeline"] = format_timeline_lines(timeline)
        detail["timeline_markers"] = timeline.get("markers", {})
        symbol_payload["detail"] = detail

    def _record_context_event(self, symbol: str, decision):
        if decision.primary_context is None:
            return
        self.state_manager.record_timeline_event(
            symbol=symbol,
            event="htf_context",
            label=f"HTF context detected: {decision.htf_context}",
            phase=SetupPhase.HTF_CONTEXT.value,
            state=decision.state,
            timestamp=decision.broker_now,
            dedupe_key=decision.htf_context,
        )

    def _record_watch_events(self, symbol: str, watches: list[dict]):
        for watch in watches:
            stamp = watch.get("armed_at") or _now_iso()
            watch_key = watch.get("watch_key", symbol)
            primary = watch.get("primary_sweep") or {}
            opposite = watch.get("opposite_sweep") or {}
            narrative = watch.get("narrative") or {}
            primary_label = primary.get("label", "-")
            self.state_manager.record_timeline_event(
                symbol=symbol,
                event="sweep",
                label=f"{watch.get('timeframe', '-')} primary sweep: {primary_label}",
                phase=SetupPhase.LTF_SWEEP.value,
                state=watch.get("status") or SetupState.ARMED.value,
                timestamp=stamp,
                dedupe_key=f"{watch_key}:sweep",
            )
            if opposite:
                self.state_manager.record_timeline_event(
                    symbol=symbol,
                    event="opposite_sweep",
                    label=f"{watch.get('timeframe', '-')} opposite sweep: {opposite.get('label', '-')}",
                    phase=SetupPhase.NARRATIVE.value,
                    state=watch.get("status"),
                    timestamp=stamp,
                    dedupe_key=f"{watch_key}:opposite:{opposite.get('label', '-')}",
                )
            if narrative.get("mss"):
                self.state_manager.record_timeline_event(
                    symbol=symbol,
                    event="mss",
                    label=f"{watch.get('timeframe', '-')} MSS confirmed",
                    phase=SetupPhase.WAITING_MSS.value,
                    state=watch.get("status"),
                    timestamp=stamp,
                    dedupe_key=f"{watch_key}:mss:{narrative['mss'].get('mss_index')}",
                )
            if watch.get("ifvg"):
                self.state_manager.record_timeline_event(
                    symbol=symbol,
                    event="ifvg",
                    label=f"{watch.get('timeframe', '-')} strict iFVG detected",
                    phase=SetupPhase.IFVG_VALIDATION.value,
                    state=watch.get("status") or SetupState.ARMED.value,
                    timestamp=stamp,
                    dedupe_key=f"{watch_key}:ifvg",
                )

    def _record_rejection_events(self, rejections: list[dict]):
        for rejection in rejections:
            self.state_manager.record_timeline_event(
                symbol=rejection["symbol"],
                event="rejection",
                label=str(rejection["reason"]),
                phase=rejection["phase"],
                state=SetupState.REJECTED.value,
                timestamp=_now_iso(),
                dedupe_key=f"{rejection['timeframe']}:{rejection['reason']}",
            )

    def _log_state_transition(self, payload: dict):
        transition = payload.get("transition")
        if not transition:
            return
        message = f"State transition {transition}"
        symbol = payload["symbol"]
        timeframe = payload.get("tf")
        phase = payload.get("phase")
        reason = payload.get("reason")
        state = payload.get("state")
        if state in {SetupState.CONFIRMED.value, SetupState.TRIGGERED.value}:
            self.logger.signal(message, symbol=symbol, timeframe=timeframe, phase=phase, reason=reason)
        elif state in {
            SetupState.ARMED.value,
            SetupState.WAITING_MSS.value,
            SetupState.AWAITING_IFVG.value,
            SetupState.SWEEP_DETECTED.value,
            SetupState.AWAITING_LTF_SWEEP.value,
            SetupState.CONTEXT_FOUND.value,
            SetupState.HTF_CONTEXT_FOUND.value,
        }:
            self.logger.watch(message, symbol=symbol, timeframe=timeframe, phase=phase, reason=reason)
        elif state == SetupState.ERROR.value:
            self.logger.error(message, symbol=symbol, timeframe=timeframe, phase=phase, reason=reason)
        elif state in {
            SetupState.REJECTED.value,
            SetupState.COOLDOWN.value,
            SetupState.DEGRADED.value,
            SetupState.INVALIDATED.value,
            SetupState.TWO_SIDED_LIQUIDITY_TAKEN.value,
            SetupState.AMBIGUOUS.value,
            SetupState.EXPIRED.value,
        }:
            self.logger.warn(message, symbol=symbol, timeframe=timeframe, phase=phase, reason=reason)
        else:
            self.logger.info(message, symbol=symbol, timeframe=timeframe, phase=phase, reason=reason)

    def _record_transition_event(self, payload: dict):
        transition = payload.get("transition")
        if not transition:
            return
        self.state_manager.record_timeline_event(
            symbol=payload["symbol"],
            event="state_transition",
            label=f"state {transition}",
            phase=payload.get("phase"),
            state=payload.get("state"),
            timestamp=payload.get("last_update") or _now_iso(),
            dedupe_key=f"{transition}:{payload.get('last_update')}",
        )

    def scan_symbol(self, symbol: str) -> dict:
        snapshot = self.data_gateway.fetch_symbol_snapshot(symbol)
        if snapshot is None:
            error_reason = describe_error(self.data_gateway.status_snapshot().get("last_error") or "MT5 rates unavailable")
            self.logger.error(
                "Failed to fetch market data",
                symbol=symbol,
                phase=SetupPhase.HTF_CONTEXT.value,
                reason=error_reason,
            )
            payload = self._symbol_state_payload(
                symbol=symbol,
                state=SetupState.ERROR.value,
                bias="neutral (data unavailable)",
                tf="-",
                phase=SetupPhase.HTF_CONTEXT.value,
                reason=error_reason,
                price=None,
                score=None,
                grade=None,
                last_update=_now_iso(),
                detail={
                    "current_state": SetupState.ERROR.value,
                    "htf_bias": "neutral (data unavailable)",
                    "htf_context": "-",
                    "htf_zone_type": "-",
                    "htf_zone_source": "-",
                    "htf_context_reason": "MT5 data unavailable",
                    "last_detected_sweep": "-",
                    "last_detected_mss": "-",
                    "last_detected_ifvg": "-",
                    "rejection_reason": "-",
                    "rejection_debug": "-",
                    "last_alert_time": None,
                    "last_alert_details": "-",
                    "cooldown_info": "-",
                    "active_watch_id": None,
                    "active_watch_info": "-",
                    "zone": "-",
                    "zone_top_bottom": "-",
                    "score": "-",
                    "score_components": {},
                    "timeline": "-",
                },
            )
            self._apply_last_alert(payload, symbol)
            self._apply_timeline(payload, symbol)
            stored = self.state_manager.upsert_symbol_state(payload)
            self._record_transition_event(stored)
            self._apply_timeline(stored, symbol)
            stored = self.state_manager.upsert_symbol_state(stored)
            self._log_state_transition(stored)
            return stored

        active_watches = self.state_manager.list_active_watches(
            symbol=symbol,
            statuses=(
                "armed",
                "sweep_detected",
                "waiting_mss",
                "awaiting_ifvg",
                "triggered",
                "confirmed",
                "cooldown",
            ),
        )
        decision = self.strategy_engine.evaluate_symbol(snapshot, active_watches)
        self._record_context_event(symbol, decision)

        for removed in decision.removed_watches:
            self.state_manager.remove_watch(removed["watch_key"], removed.get("removal_reason"))
            self.logger.info(
                "Watch removed from pipeline",
                symbol=symbol,
                timeframe=removed.get("timeframe"),
                phase=SetupPhase.ALERT_SENT.value if removed.get("status") == "cooldown" else SetupPhase.IFVG_VALIDATION.value,
                reason=removed.get("removal_reason"),
            )

        stored_new_watches = []
        for watch in decision.active_watches:
            created, stored = self.state_manager.upsert_watch(watch)
            if created:
                stored_new_watches.append(stored)

        self._record_watch_events(symbol, stored_new_watches)

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
        self._record_rejection_events(decision.rejections)

        for watch in stored_new_watches:
            self.logger.watch(
                "narrative watch updated",
                symbol=watch["symbol"],
                timeframe=watch["timeframe"],
                phase=self.strategy_engine._phase_for_watch_status(watch.get("status")),
                reason=watch.get("status_reason") or "narrative updated",
            )
            if watch.get("status") == SetupState.ARMED.value:
                alert_result = self.alert_service.handle_watch_armed(watch)
                if alert_result["status"] == "failed":
                    self.logger.error(
                        "Watch alert delivery failed",
                        symbol=watch["symbol"],
                        timeframe=watch["timeframe"],
                        phase=SetupPhase.ALERT_SENT.value,
                        reason=alert_result["message"],
                    )
                elif alert_result["status"] in {"dedup_blocked", "cooldown_blocked"}:
                    self.logger.warn(
                        "Watch alert blocked",
                        symbol=watch["symbol"],
                        timeframe=watch["timeframe"],
                        phase=SetupPhase.ALERT_SENT.value,
                        reason=alert_result["message"],
                    )

        state = decision.state
        phase = decision.phase
        reason = decision.reason
        bias = decision.htf_bias
        timeframe = decision.timeframe
        score = decision.score
        grade = decision.grade
        cooldown_remaining = 0
        cooldown_until = None
        active_watch_id = decision.active_watch_id
        detail = dict(decision.detail)
        detail["score"] = format_score(score, grade)
        detail["score_components"] = decision.score_components

        focus_watch = decision.focus_watch or {}
        if focus_watch:
            detail["active_watch_info"] = (
                f"{focus_watch.get('timeframe', '-')} {focus_watch.get('direction', '-')} | "
                f"waiting for {focus_watch.get('waiting_for', '-')}"
            )
            detail["zone_top_bottom"] = (
                f"{_format_number(focus_watch.get('zone_bottom'))}-{_format_number(focus_watch.get('zone_top'))}"
            )

        if decision.confirmed_signal is not None:
            signal = decision.confirmed_signal
            signal_event_key = f"signal:{signal['setup_key']}"
            timeframe = signal["timeframe"]
            active_watch_id = signal["watch_key"]
            detail["last_detected_mss"] = f"MSS confirmed at index {signal['mss_index']}"
            detail["last_detected_ifvg"] = (
                f"iFVG {_format_number(signal['entry_low'])}-{_format_number(signal['entry_high'])}"
            )
            detail["zone_top_bottom"] = f"{_format_number(signal['entry_low'])}-{_format_number(signal['entry_high'])}"
            self.state_manager.record_timeline_event(
                symbol=symbol,
                event="mss",
                label=f"{signal['timeframe']} MSS detected",
                phase=SetupPhase.READY.value,
                state=SetupState.TRIGGERED.value,
                timestamp=decision.broker_now,
                dedupe_key=f"{signal['watch_key']}:{signal['mss_index']}",
            )

            signal_result = self.alert_service.handle_confirmed_signal(snapshot, signal)
            if signal_result["status"] == "sent":
                self.state_manager.mark_watch_confirmed(
                    signal["watch_key"],
                    signal["mss_index"],
                    status="cooldown",
                    reason="confirmed: alert sent and cooldown active",
                    signal_event_key=signal_event_key,
                )
                state = SetupState.TRIGGERED.value
                phase = SetupPhase.READY.value
                reason = "triggered: narrative ready with MSS + strict iFVG"
                cooldown_remaining, cooldown_until = self._cooldown_snapshot(signal_event_key)
                self.state_manager.record_timeline_event(
                    symbol=symbol,
                    event="alert",
                    label="confirmed alert sent",
                    phase=SetupPhase.ALERT_SENT.value,
                    state=SetupState.COOLDOWN.value,
                    timestamp=decision.broker_now,
                    dedupe_key=signal_event_key,
                )
                self.logger.signal(
                    "long confirmed after MSS + strict iFVG" if signal["bias"] == "Long" else "short confirmed after MSS + strict iFVG",
                    symbol=signal["symbol"],
                    timeframe=signal["timeframe"],
                    phase=SetupPhase.READY.value,
                    reason="telegram sent",
                )
            elif signal_result["status"] == "cooldown_blocked":
                self.state_manager.mark_watch_confirmed(
                    signal["watch_key"],
                    signal["mss_index"],
                    status="cooldown",
                    reason=signal_result["message"],
                    signal_event_key=signal_event_key,
                )
                state = SetupState.COOLDOWN.value
                phase = SetupPhase.ALERT_SENT.value
                reason = "cooldown: prior confirmed alert still active"
                cooldown_remaining, cooldown_until = self._cooldown_snapshot(signal_event_key)
                self.logger.warn(
                    "Signal blocked by cooldown",
                    symbol=signal["symbol"],
                    timeframe=signal["timeframe"],
                    phase=SetupPhase.ALERT_SENT.value,
                    reason=signal_result["message"],
                )
            elif signal_result["status"] == "dedup_blocked":
                self.state_manager.mark_watch_confirmed(
                    signal["watch_key"],
                    signal["mss_index"],
                    status="cooldown",
                    reason=signal_result["message"],
                    signal_event_key=signal_event_key,
                )
                state = SetupState.COOLDOWN.value
                phase = SetupPhase.ALERT_SENT.value
                reason = "cooldown: signal already sent for this setup"
                cooldown_remaining, cooldown_until = self._cooldown_snapshot(signal_event_key)
                self.logger.warn(
                    "Signal blocked by deduplication",
                    symbol=signal["symbol"],
                    timeframe=signal["timeframe"],
                    phase=SetupPhase.ALERT_SENT.value,
                    reason=signal_result["message"],
                )
            elif signal_result["status"] == "recorded_only":
                self.state_manager.mark_watch_confirmed(
                    signal["watch_key"],
                    signal["mss_index"],
                    status="confirmed",
                    reason="confirmed signal recorded locally",
                    signal_event_key=signal_event_key,
                )
                state = SetupState.TRIGGERED.value
                phase = SetupPhase.READY.value
                reason = "triggered: narrative ready with MSS + strict iFVG"
                self.logger.signal(
                    "confirmed signal recorded locally",
                    symbol=signal["symbol"],
                    timeframe=signal["timeframe"],
                    phase=SetupPhase.READY.value,
                    reason="alert mode skips Telegram dispatch",
                )
            elif signal_result["status"] == "config_missing":
                self.state_manager.mark_watch_confirmed(
                    signal["watch_key"],
                    signal["mss_index"],
                    status="confirmed",
                    reason=signal_result["message"],
                    signal_event_key=signal_event_key,
                )
                state = SetupState.TRIGGERED.value
                phase = SetupPhase.READY.value
                reason = f"confirmed: Telegram unavailable ({signal_result['message']})"
                self.logger.warn(
                    "Telegram configuration missing",
                    symbol=signal["symbol"],
                    timeframe=signal["timeframe"],
                    phase=SetupPhase.ALERT_SENT.value,
                    reason=signal_result["message"],
                )
            else:
                self.state_manager.mark_watch_confirmed(
                    signal["watch_key"],
                    signal["mss_index"],
                    status="confirmed",
                    reason=signal_result["message"],
                    signal_event_key=signal_event_key,
                )
                state = SetupState.TRIGGERED.value
                phase = SetupPhase.READY.value
                reason = f"confirmed: delivery failed ({signal_result['message']})"
                self.logger.error(
                    "Confirmed signal delivery failed",
                    symbol=signal["symbol"],
                    timeframe=signal["timeframe"],
                    phase=SetupPhase.ALERT_SENT.value,
                    reason=signal_result["message"],
                )
        elif active_watch_id:
            watch = self.state_manager.get_watch(active_watch_id)
            if watch and watch.get("status") == "cooldown":
                event_key = watch.get("last_signal_event_key")
                cooldown_remaining, cooldown_until = self._cooldown_snapshot(event_key)
                state = SetupState.COOLDOWN.value
                phase = SetupPhase.ALERT_SENT.value
                reason = watch.get("status_reason") or "cooldown: prior alert still active"
                detail["zone_top_bottom"] = detail.get("zone_top_bottom") or (
                    f"{_format_number(watch.get('zone_bottom'))}-{_format_number(watch.get('zone_top'))}"
                )

        payload = self._symbol_state_payload(
            symbol=symbol,
            state=state,
            bias=bias,
            tf=timeframe,
            phase=phase,
            reason=reason,
            price=decision.current_price,
            score=score,
            grade=grade,
            last_update=decision.broker_now or _now_iso(),
            cooldown_remaining=cooldown_remaining,
            cooldown_until=cooldown_until,
            active_watch_id=active_watch_id,
            htf_context=decision.htf_context,
            detail=detail,
        )
        self._apply_last_alert(payload, symbol)
        self._apply_timeline(payload, symbol)
        stored = self.state_manager.upsert_symbol_state(payload)
        self._record_transition_event(stored)
        self._apply_timeline(stored, symbol)
        stored = self.state_manager.upsert_symbol_state(stored)
        self._log_state_transition(stored)
        return stored
