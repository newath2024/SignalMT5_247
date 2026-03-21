from dataclasses import dataclass, field

from detectors.htf import detect_htf_context, refresh_htf_context
from detectors.ltf import detect_confirmed_signal, detect_watch_candidates, watch_has_expired, watch_is_invalidated


@dataclass
class StrategyDecision:
    symbol: str
    status: str
    message: str
    active_watches: list[dict] = field(default_factory=list)
    new_watches: list[dict] = field(default_factory=list)
    removed_watches: list[dict] = field(default_factory=list)
    rejections: list[dict] = field(default_factory=list)
    confirmed_signal: dict | None = None
    current_price: float | None = None
    broker_now: str | None = None


class StrategyEngine:
    def __init__(self, trigger_timeframes: list[str]):
        self.trigger_timeframes = list(trigger_timeframes)

    def evaluate_symbol(self, snapshot: dict, active_watches: list[dict]) -> StrategyDecision:
        all_htf_zones, contexts = detect_htf_context(snapshot)

        retained_watches = []
        removed_watches = []
        for watch_setup in active_watches:
            refreshed_context = refresh_htf_context(snapshot, watch_setup["htf_zone"])
            if watch_has_expired(snapshot, watch_setup):
                removed = dict(watch_setup)
                removed["removal_reason"] = "expired"
                removed_watches.append(removed)
                continue
            if watch_is_invalidated(snapshot, watch_setup, refreshed_context):
                removed = dict(watch_setup)
                removed["removal_reason"] = "invalidated"
                removed_watches.append(removed)
                continue

            updated = dict(watch_setup)
            updated["context"] = refreshed_context
            retained_watches.append(updated)

        new_watches, rejections = detect_watch_candidates(snapshot, contexts, self.trigger_timeframes)

        seen_keys = {item["watch_key"] for item in retained_watches}
        unique_new_watches = []
        for watch in new_watches:
            if watch["watch_key"] in seen_keys:
                continue
            seen_keys.add(watch["watch_key"])
            unique_new_watches.append(watch)

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

        if confirmed_signal is not None:
            status = "signal_confirmed"
            message = f"{confirmed_signal['bias']} {confirmed_signal['timeframe']} confirmed"
        elif unique_new_watches:
            status = "watch_armed"
            message = f"Armed {len(unique_new_watches)} watch setup(s)"
        elif removed_watches:
            status = "running"
            message = f"Cleared {len(removed_watches)} stale watch setup(s)"
        elif rejections:
            status = "rejected"
            message = rejections[0]["reason"]
        else:
            status = "running"
            message = "Structure checked with no new watch or signal"

        return StrategyDecision(
            symbol=snapshot["symbol"],
            status=status,
            message=message,
            active_watches=active_pool,
            new_watches=unique_new_watches,
            removed_watches=removed_watches,
            rejections=rejections,
            confirmed_signal=confirmed_signal,
            current_price=float(snapshot["current_price"]),
            broker_now=snapshot["broker_now"].isoformat(),
        )
