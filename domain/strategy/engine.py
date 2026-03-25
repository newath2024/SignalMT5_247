from dataclasses import dataclass, field

from .pipeline import (
    build_htf_context,
    build_strategy_decision,
    derive_display_state,
    find_new_watch_candidates,
    refresh_active_watches,
    resolve_confirmed_signal,
    score_setup,
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

    def evaluate_symbol(self, snapshot: dict, active_watches: list[dict]) -> StrategyDecision:
        htf_context_bundle = build_htf_context(snapshot)
        refreshed = refresh_active_watches(snapshot, active_watches)
        candidates = find_new_watch_candidates(
            snapshot,
            htf_context_bundle.contexts,
            self.trigger_timeframes,
            refreshed.retained_watches,
        )
        resolution = resolve_confirmed_signal(
            snapshot,
            candidates.active_pool,
            htf_context_bundle.all_htf_zones,
            htf_context_bundle.contexts,
            htf_context_bundle.primary_context,
            htf_context_bundle.htf_bias,
            candidates.unique_new_watches,
            refreshed.retained_watches,
            candidates.rejections,
        )
        display_state = derive_display_state(
            confirmed_signal=resolution.confirmed_signal,
            unique_new_watches=candidates.unique_new_watches,
            retained_watches=refreshed.retained_watches,
            selected_rejection=resolution.selected_rejection,
            best_directional_context=htf_context_bundle.best_directional_context,
            primary_context=htf_context_bundle.primary_context,
        )
        score_state = score_setup(
            resolution.display_context,
            resolution.selected_watch,
            resolution.confirmed_signal,
        )
        payload = build_strategy_decision(
            snapshot=snapshot,
            display_state=display_state,
            htf_bias_display=resolution.htf_bias_display,
            htf_context=resolution.htf_context,
            score_state=score_state,
            display_context=resolution.display_context,
            selected_watch=resolution.selected_watch,
            confirmed_signal=resolution.confirmed_signal,
            selected_rejection=resolution.selected_rejection,
            primary_context=htf_context_bundle.primary_context,
            active_pool=candidates.active_pool,
            unique_new_watches=candidates.unique_new_watches,
            removed_watches=refreshed.removed_watches,
            rejections=resolution.rejections,
        )
        return StrategyDecision(**payload)
