from dataclasses import dataclass, field

from domain.detectors.htf import detect_htf_context, refresh_htf_context
from domain.detectors.ltf import (
    detect_confirmed_signal,
    detect_watch_candidates,
    watch_has_expired,
    watch_is_invalidated,
)
from domain.enums import SetupPhase, SetupState

from .reasoning import (
    bias_label,
    build_detail_payload,
    compute_setup_score,
    derive_htf_bias,
    describe_context_wait,
    describe_rejection,
    describe_waiting_mss_reason,
    describe_watch_reason,
    direction_label,
    format_context_label,
)


@dataclass
class StrategyDecision:
    symbol: str
    state: str
    phase: str
    reason: str
    htf_bias: str
    timeframe: str
    htf_context: str
    waiting_for: str
    score: float | None
    grade: str | None
    score_components: dict = field(default_factory=dict)
    active_watch_id: str | None = None
    focus_watch: dict | None = None
    primary_context: dict | None = None
    detail: dict = field(default_factory=dict)
    status: str = ""
    message: str = ""
    active_watches: list[dict] = field(default_factory=list)
    new_watches: list[dict] = field(default_factory=list)
    removed_watches: list[dict] = field(default_factory=list)
    rejections: list[dict] = field(default_factory=list)
    confirmed_signal: dict | None = None
    current_price: float | None = None
    broker_now: str | None = None

    def __post_init__(self):
        if not self.status:
            self.status = self.state
        if not self.message:
            self.message = self.reason


class StrategyEngine:
    def __init__(self, trigger_timeframes: list[str]):
        self.trigger_timeframes = list(trigger_timeframes)

    @staticmethod
    def _directional_context_rank(item: dict | None) -> tuple[int, int, int, float]:
        zone = (item or {}).get("zone") or {}
        tier = str(zone.get("tier") or (item or {}).get("tier") or "C").upper()
        tier_rank = 3 if tier == "A" else 2 if tier == "B" else 1
        strength = str((item or {}).get("context_strength") or zone.get("context_strength") or "").lower()
        strength_rank = 3 if strength == "strong" else 2 if strength == "moderate" else 1 if strength == "weak" else 0
        return (
            1 if (item or {}).get("rollover_active") else 0,
            tier_rank,
            strength_rank,
            float((item or {}).get("score") or 0.0),
        )

    @staticmethod
    def _phase_for_watch_status(status: str | None) -> str:
        status = str(status or "").lower()
        if status in {SetupState.ARMED.value, SetupState.TRIGGERED.value}:
            return SetupPhase.READY.value
        if status == SetupState.AWAITING_IFVG.value:
            return SetupPhase.WAITING_IFVG.value
        if status in {SetupState.SWEEP_DETECTED.value, SetupState.WAITING_MSS.value}:
            return SetupPhase.WAITING_MSS.value
        return SetupPhase.NARRATIVE.value

    @staticmethod
    def _waiting_for_from_watch(watch: dict) -> str:
        status = str(watch.get("status") or "").lower()
        if status in {
            SetupState.DEGRADED.value,
            SetupState.INVALIDATED.value,
            SetupState.TWO_SIDED_LIQUIDITY_TAKEN.value,
            SetupState.AMBIGUOUS.value,
        }:
            return "-"
        if status == SetupState.AWAITING_IFVG.value:
            return "strict iFVG"
        if status in {SetupState.ARMED.value, SetupState.TRIGGERED.value}:
            return "trigger"
        return "MSS"

    def _prepare_retained_watch(self, snapshot: dict, watch_setup: dict) -> tuple[dict | None, dict | None]:
        refreshed_context = refresh_htf_context(snapshot, watch_setup["htf_zone"])
        if watch_has_expired(snapshot, watch_setup):
            removed = dict(watch_setup)
            removed["removal_reason"] = "expired"
            return None, removed
        if watch_is_invalidated(snapshot, watch_setup, refreshed_context):
            removed = dict(watch_setup)
            removed["removal_reason"] = "entry invalidated"
            return None, removed

        updated = dict(watch_setup)
        updated["context"] = refreshed_context
        if updated.get("status") not in {"confirmed", "cooldown", SetupState.ARMED.value}:
            updated["status"] = updated.get("narrative_state") or updated.get("status") or SetupState.WAITING_MSS.value
        updated["direction"] = updated.get("direction") or direction_label(updated.get("bias"))
        updated["waiting_for"] = self._waiting_for_from_watch(updated)
        updated["ltf_sweep_status"] = updated.get("ltf_sweep_status") or "narrative active"
        if updated.get("ifvg"):
            updated["zone_top"] = updated.get("zone_top") or float(updated["ifvg"]["high"])
            updated["zone_bottom"] = updated.get("zone_bottom") or float(updated["ifvg"]["low"])
        updated["status_reason"] = updated.get("status_reason") or describe_waiting_mss_reason(updated)
        return updated, None

    @staticmethod
    def _phase_for_rejection(rejection: dict) -> str:
        phase = str(rejection.get("phase") or "").lower()
        if phase == "signal":
            return SetupPhase.READY.value
        if phase == "watch":
            return SetupPhase.IFVG_VALIDATION.value
        return SetupPhase.HTF_CONTEXT.value

    def evaluate_symbol(self, snapshot: dict, active_watches: list[dict]) -> StrategyDecision:
        all_htf_zones, contexts = detect_htf_context(snapshot)
        htf_bias, primary_context = derive_htf_bias(contexts)
        directional_contexts = [contexts.get("Long"), contexts.get("Short")]
        directional_contexts = [item for item in directional_contexts if item is not None]
        best_directional_context = (
            max(
                directional_contexts,
                key=self._directional_context_rank,
            )
            if directional_contexts
            else None
        )

        retained_watches = []
        removed_watches = []
        for watch_setup in active_watches:
            retained, removed = self._prepare_retained_watch(snapshot, watch_setup)
            if retained is not None:
                retained_watches.append(retained)
            if removed is not None:
                removed_watches.append(removed)

        new_watches, rejections = detect_watch_candidates(snapshot, contexts, self.trigger_timeframes)

        retained_by_key = {item["watch_key"]: item for item in retained_watches}
        seen_keys = set(retained_by_key)
        unique_new_watches = []
        for watch in new_watches:
            watch["status"] = watch.get("status") or watch.get("narrative_state") or SetupState.WAITING_MSS.value
            watch["direction"] = watch.get("direction") or direction_label(watch.get("bias"))
            watch["waiting_for"] = self._waiting_for_from_watch(watch)
            watch["ltf_sweep_status"] = watch.get("ltf_sweep_status") or "narrative active"
            watch["status_reason"] = watch.get("status_reason") or describe_watch_reason(watch)
            if watch["watch_key"] in retained_by_key:
                retained_by_key[watch["watch_key"]] = watch
                continue
            seen_keys.add(watch["watch_key"])
            unique_new_watches.append(watch)

        retained_watches = list(retained_by_key.values())
        active_pool = retained_watches + unique_new_watches
        confirmed_signal, confirm_rejection = detect_confirmed_signal(snapshot, active_pool, all_htf_zones)
        if confirm_rejection:
            rejections.append(
                {
                    "symbol": snapshot["symbol"],
                    "timeframe": "-",
                    "bias": None,
                    "phase": "signal",
                    "reason": confirm_rejection,
                }
            )

        selected_watch = None
        if confirmed_signal is not None:
            for watch in active_pool:
                if watch["watch_key"] == confirmed_signal["watch_key"]:
                    selected_watch = watch
                    break
        if selected_watch is None and unique_new_watches:
            selected_watch = unique_new_watches[0]
        if selected_watch is None and retained_watches:
            selected_watch = retained_watches[0]

        selected_rejection = rejections[0] if rejections else None
        display_context = primary_context
        if selected_watch is not None and selected_watch.get("context"):
            display_context = selected_watch.get("context")
        elif confirmed_signal is not None and confirmed_signal.get("context"):
            display_context = confirmed_signal.get("context")
        elif selected_rejection is not None:
            rejection_bias = selected_rejection.get("bias")
            if rejection_bias in {"Long", "Short"}:
                display_context = contexts.get(rejection_bias) or primary_context

        htf_context = (
            confirmed_signal.get("htf_context")
            if confirmed_signal is not None
            else selected_watch.get("htf_context")
            if selected_watch is not None
            else format_context_label(display_context)
        )
        htf_bias_display = bias_label((display_context or {}).get("bias")) if display_context else htf_bias
        if htf_bias_display == "neutral":
            htf_bias_display = htf_bias

        if confirmed_signal is not None:
            state = SetupState.TRIGGERED.value
            phase = SetupPhase.READY.value
            reason = "triggered: narrative ready with MSS + strict iFVG"
            timeframe = confirmed_signal["timeframe"]
            waiting_for = "entry"
            active_watch_id = confirmed_signal["watch_key"]
        elif unique_new_watches:
            focus = unique_new_watches[0]
            state = focus.get("status") or SetupState.WAITING_MSS.value
            phase = self._phase_for_watch_status(state)
            reason = focus.get("status_reason") or describe_watch_reason(focus)
            timeframe = focus["timeframe"]
            waiting_for = self._waiting_for_from_watch(focus)
            active_watch_id = focus["watch_key"]
        elif retained_watches:
            selected_retained = retained_watches[0]
            if selected_retained.get("status") == SetupState.COOLDOWN.value:
                state = SetupState.COOLDOWN.value
                phase = SetupPhase.ALERT_SENT.value
                reason = selected_retained.get("status_reason") or "cooldown: prior alert still active"
                waiting_for = "cooldown"
            elif selected_retained.get("status") in {SetupState.CONFIRMED.value, SetupState.TRIGGERED.value}:
                state = SetupState.TRIGGERED.value
                phase = SetupPhase.READY.value
                reason = selected_retained.get("status_reason") or "triggered: signal already recorded"
                waiting_for = "operator review"
            else:
                state = selected_retained.get("status") or SetupState.WAITING_MSS.value
                phase = self._phase_for_watch_status(state)
                reason = selected_retained.get("status_reason") or describe_waiting_mss_reason(selected_retained)
                waiting_for = self._waiting_for_from_watch(selected_retained)
            timeframe = selected_retained["timeframe"]
            active_watch_id = selected_retained["watch_key"]
        elif selected_rejection is not None:
            state = SetupState.REJECTED.value
            phase = self._phase_for_rejection(selected_rejection)
            reason = describe_rejection(selected_rejection["reason"])
            timeframe = selected_rejection["timeframe"]
            waiting_for = "-"
            active_watch_id = None
        elif best_directional_context is not None:
            state = SetupState.AWAITING_LTF_SWEEP.value
            phase = SetupPhase.LTF_SWEEP.value
            reason = describe_context_wait(best_directional_context)
            timeframe = best_directional_context.get("zone", {}).get("timeframe", "-")
            waiting_for = "sweep"
            active_watch_id = None
        elif primary_context is not None:
            zone = primary_context.get("zone", {}) or {}
            tier = str(zone.get("tier") or primary_context.get("tier") or "C").upper()
            context_strength = str(primary_context.get("context_strength") or zone.get("context_strength") or "weak").lower()
            if tier == "C":
                if bool(primary_context.get("no_structural_backing")):
                    state = SetupState.NO_STRUCTURAL_BACKING.value
                else:
                    state = SetupState.SESSION_ONLY_CONTEXT.value
            elif context_strength == "weak":
                state = SetupState.HTF_WEAK_CONTEXT.value
            else:
                state = SetupState.HTF_CONTEXT_FOUND.value
            phase = SetupPhase.HTF_CONTEXT.value
            reason = describe_context_wait(primary_context)
            timeframe = primary_context.get("zone", {}).get("timeframe", "-")
            waiting_for = "HTF confirmation"
            active_watch_id = None
        else:
            state = SetupState.IDLE.value
            phase = SetupPhase.HTF_CONTEXT.value
            reason = "waiting: HTF context"
            timeframe = "-"
            waiting_for = "HTF context"
            active_watch_id = None

        score, grade, score_components = compute_setup_score(display_context, selected_watch, confirmed_signal)

        detail = build_detail_payload(
            state=state,
            htf_bias=htf_bias_display,
            primary_context=display_context,
            active_watch=selected_watch,
            confirmed_signal=confirmed_signal,
            rejection=selected_rejection,
            score=score,
            grade=grade,
            score_components=score_components,
            snapshot=snapshot,
        )

        return StrategyDecision(
            symbol=snapshot["symbol"],
            state=state,
            phase=phase,
            reason=reason,
            htf_bias=htf_bias_display,
            timeframe=timeframe,
            htf_context=htf_context,
            waiting_for=waiting_for,
            score=score,
            grade=grade,
            score_components=score_components,
            active_watch_id=active_watch_id,
            focus_watch=selected_watch,
            primary_context=primary_context,
            detail=detail,
            active_watches=active_pool,
            new_watches=unique_new_watches,
            removed_watches=removed_watches,
            rejections=rejections,
            confirmed_signal=confirmed_signal,
            current_price=float(snapshot["current_price"]),
            broker_now=snapshot["broker_now"].isoformat(timespec="seconds"),
        )
