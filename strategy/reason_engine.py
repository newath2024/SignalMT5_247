from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def direction_label(bias: str | None) -> str:
    if bias == "Long":
        return "LONG"
    if bias == "Short":
        return "SHORT"
    return "-"


def bias_label(bias: str | None) -> str:
    if bias == "Long":
        return "bullish"
    if bias == "Short":
        return "bearish"
    return "neutral"


def _context_score(context: dict[str, Any] | None) -> float:
    if not context:
        return 0.0
    return float(context.get("score") or 0.0)


def _is_liquidity_context(context: dict[str, Any] | None) -> bool:
    zone = (context or {}).get("zone") or {}
    return bool(zone.get("is_liquidity_level"))


def _context_market_bias(context: dict[str, Any] | None) -> str | None:
    if not context:
        return None
    market_bias = context.get("market_structure_bias")
    if market_bias in {"Long", "Short"}:
        return str(market_bias)
    raw_bias = context.get("bias")
    if raw_bias in {"Long", "Short"}:
        return str(raw_bias)
    return None


def _humanize_liquidity_state(state: str | None) -> str:
    if state == "swept_and_reclaimed":
        return "Sweep + reclaim"
    if state == "swept":
        return "Swept"
    if state == "tapped":
        return "Tapped"
    if state == "untouched":
        return "Untouched"
    return "-"


def derive_htf_bias(contexts: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    candidates = [item for item in contexts.values() if item is not None]
    if not candidates:
        return "neutral", None
    primary = max(candidates, key=_context_score)
    directional_candidates = [item for item in candidates if _context_market_bias(item) in {"Long", "Short"}]
    bias_source = max(directional_candidates, key=_context_score) if directional_candidates else primary
    return bias_label(_context_market_bias(bias_source)), primary


def format_context_label(context: dict[str, Any] | None) -> str:
    if not context:
        return "-"
    zone = context.get("zone") or {}
    if _is_liquidity_context(context):
        interaction_label = str(context.get("liquidity_interaction_label") or "").strip()
        if interaction_label:
            return interaction_label
    label = str(zone.get("label") or "").strip()
    if label:
        return label
    timeframe = zone.get("timeframe", "-")
    return f"{timeframe} {bias_label(_context_market_bias(context))} context"


def _context_location(context: dict[str, Any] | None, current_price: float | None = None) -> str:
    if not context or current_price is None:
        return "context"
    zone = context.get("zone") or {}
    low = zone.get("low")
    high = zone.get("high")
    if low is None or high is None:
        return "context"
    try:
        price = float(current_price)
        zone_low = min(float(low), float(high))
        zone_high = max(float(low), float(high))
    except (TypeError, ValueError):
        return "context"
    if zone_low <= price <= zone_high:
        return "inside"
    return "near"


def format_bias_display(primary_context: dict[str, Any] | None, current_price: float | None = None) -> str:
    if not primary_context:
        return "neutral"
    return bias_label(_context_market_bias(primary_context))


def format_context_reason(context: dict[str, Any] | None) -> str:
    if not context:
        return "No clear HTF context"
    zone = context.get("zone") or {}
    timeframe = zone.get("timeframe", "-")
    zone_quality = float(context.get("zone_quality") or 0.0)
    reaction = float(context.get("reaction_clarity") or 0.0)
    trend = str(context.get("structure_trend") or "Range")
    alignment = str(context.get("trend_alignment") or "range")

    if _is_liquidity_context(context):
        raw_state = str(context.get("liquidity_interaction_state") or "untouched")
        state = _humanize_liquidity_state(raw_state)
        bias = bias_label(_context_market_bias(context))
        reaction_strength = str(context.get("reaction_strength") or "none")
        confirmation = str(context.get("structure_confirmation_reason") or "none")
        summary = (
            f"{timeframe} liquidity active at {zone.get('label', 'level')} "
            f"(state={state}, reaction={reaction_strength}/{reaction:.2f}, "
            f"structure_bias={bias}, trend={trend}, alignment={alignment})"
        )
        debug = []
        if confirmation != "none":
            debug.append(f"confirmation={confirmation}")
        if context.get("liquidity_debug"):
            debug.append(str(context["liquidity_debug"]))
        if debug:
            return f"{summary} | {', '.join(debug)}"
        return summary

    summary = (
        f"{timeframe} context active near {format_context_label(context)} "
        f"(zone={zone_quality:.2f}, reaction={reaction:.2f}, trend={trend}, alignment={alignment})"
    )
    if str(zone.get("type") or "").upper() != "FVG":
        return summary

    extras = []
    fvg_class = zone.get("fvg_class") or context.get("fvg_class")
    if fvg_class:
        extras.append(f"class={fvg_class}")
    if "tradable" in zone or "tradable" in context:
        extras.append(f"tradable={bool(zone.get('tradable', context.get('tradable')))}")
    mitigation = zone.get("mitigation_status") or context.get("mitigation_status")
    if mitigation:
        extras.append(f"mitigation={mitigation}")
    location = zone.get("location_in_range") or context.get("location_in_range")
    if location:
        extras.append(f"location={location}")
    if extras:
        return f"{summary} | {', '.join(extras)}"
    return summary


def describe_watch_reason(watch: dict[str, Any]) -> str:
    return f"armed: {watch.get('htf_context') or format_context_label(watch.get('context'))} + LTF sweep"


def describe_waiting_mss_reason(watch: dict[str, Any]) -> str:
    return f"waiting: MSS after sweep on {watch.get('timeframe', '-')}"


def describe_context_wait(primary_context: dict[str, Any] | None) -> str:
    if primary_context is None:
        return "waiting: HTF context"
    if _is_liquidity_context(primary_context) and _context_market_bias(primary_context) not in {"Long", "Short"}:
        return f"waiting: confirmation at {format_context_label(primary_context)}"
    return f"waiting: LTF sweep near {format_context_label(primary_context)}"


def describe_rejection(reason: str | None) -> str:
    raw = str(reason or "").strip()
    if not raw:
        return "rejected: setup filter failed"

    lowered = raw.lower()
    if lowered.startswith("rejected:"):
        return raw
    if "strict ifvg" in lowered:
        return "rejected: no strict iFVG"
    if "bias mismatch" in lowered:
        return "rejected: HTF bias mismatch"
    if "invalidated" in lowered or "invalidation" in lowered:
        return "rejected: entry invalidated"
    if "ambiguous" in lowered:
        return "rejected: competing signals"
    if "context" in lowered and "clear" in lowered:
        return "rejected: HTF context no longer valid"
    return f"rejected: {raw}"


def describe_error(reason: str | None) -> str:
    raw = str(reason or "").strip()
    if not raw:
        return "error: scanner failure"
    if raw.lower().startswith("error:"):
        return raw
    return f"error: {raw}"


def _format_price_value(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.5f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(value)


def format_sweep_detail(payload: dict[str, Any] | None) -> str:
    if not payload:
        return "-"
    liquidity = payload.get("swept_liquidity") or []
    liquidity_text = ", ".join(str(item) for item in liquidity) if liquidity else "internal liquidity"
    sweep_price = payload.get("sweep_price")
    if sweep_price is None:
        return f"sweep detected on {payload.get('timeframe', '-')}"
    return f"{payload.get('timeframe', '-')} sweep at {_format_price_value(sweep_price)} ({liquidity_text})"


def format_mss_detail(signal: dict[str, Any] | None) -> str:
    if not signal:
        return "waiting for MSS after sweep"
    return f"MSS confirmed at index {signal.get('mss_index', '-')}"


def format_ifvg_detail(payload: dict[str, Any] | None) -> str:
    if not payload:
        return "-"
    if "entry_low" in payload and "entry_high" in payload:
        return f"iFVG {_format_price_range(payload['entry_low'], payload['entry_high'])}"
    ifvg = payload.get("ifvg") or {}
    low = ifvg.get("low")
    high = ifvg.get("high")
    if low is None or high is None:
        return "-"
    return f"iFVG {_format_price_range(low, high)}"


def _format_price_range(low: Any, high: Any) -> str:
    if low is None or high is None:
        return "-"
    return f"{_format_price_value(low)}-{_format_price_value(high)}"


def _format_liquidity_price(zone: dict[str, Any]) -> str:
    level = zone.get("liquidity_level")
    if level is None:
        level = zone.get("low")
    return _format_price_value(level)


def _context_zone_source(
    primary_context: dict[str, Any] | None,
    active_watch: dict[str, Any] | None,
    confirmed_signal: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if primary_context and primary_context.get("zone"):
        return primary_context

    for candidate in (active_watch, confirmed_signal):
        if not candidate:
            continue
        context = candidate.get("context")
        if context and context.get("zone"):
            return context
        htf_zone = candidate.get("htf_zone")
        if htf_zone:
            return {"zone": htf_zone, "bias": candidate.get("bias")}
    return None


def format_htf_zone(
    primary_context: dict[str, Any] | None,
    active_watch: dict[str, Any] | None,
    confirmed_signal: dict[str, Any] | None,
) -> str:
    context = _context_zone_source(primary_context, active_watch, confirmed_signal)
    if not context:
        return "-"
    zone = context.get("zone") or {}
    label = str(zone.get("label") or "").strip()
    if bool(zone.get("is_liquidity_level")):
        level_text = _format_liquidity_price(zone)
        if label and level_text != "-":
            return f"{label} | {level_text}"
        if label:
            return label
        return level_text
    zone_range = _format_price_range(zone.get("low"), zone.get("high"))
    if label and zone_range != "-":
        return f"{label} | {zone_range}"
    if label:
        return label
    timeframe = zone.get("timeframe", "-")
    if zone_range != "-":
        return f"{timeframe} {bias_label(context.get('bias'))} zone | {zone_range}"
    return f"{timeframe} {bias_label(context.get('bias'))} zone"


def format_htf_zone_type(primary_context: dict[str, Any] | None) -> str:
    if not primary_context:
        return "-"
    zone = primary_context.get("zone") or {}
    zone_type = str(zone.get("type") or zone.get("label") or "-").strip()
    timeframe = str(zone.get("timeframe") or "-").strip()
    if timeframe and timeframe != "-":
        return f"{timeframe} {zone_type}"
    return zone_type or "-"


def format_htf_zone_source(primary_context: dict[str, Any] | None, snapshot: dict[str, Any] | None) -> str:
    if not primary_context:
        return "-"

    zone = primary_context.get("zone") or {}
    timeframe = str(zone.get("timeframe") or "-")
    zone_type = str(zone.get("type") or zone.get("label") or "zone")
    source_index = zone.get("source_index")

    if bool(zone.get("is_liquidity_level")):
        return f"{zone_type} liquidity level @ {_format_liquidity_price(zone)}"

    if source_index is None:
        return f"{timeframe} {zone_type} (source candle unavailable)"

    if not snapshot:
        return f"{timeframe} {zone_type} candle idx {source_index}"

    rates = (snapshot.get("rates") or {}).get(timeframe)
    if rates is None or int(source_index) < 0 or int(source_index) >= len(rates):
        return f"{timeframe} {zone_type} candle idx {source_index}"

    candle = rates[int(source_index)]
    candle_time = candle["time"] if isinstance(candle, dict) else candle["time"]
    try:
        stamp = datetime.fromtimestamp(int(candle_time), timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except (TypeError, ValueError, OSError):
        stamp = str(candle_time)

    open_price = candle["open"] if isinstance(candle, dict) else candle["open"]
    high_price = candle["high"] if isinstance(candle, dict) else candle["high"]
    low_price = candle["low"] if isinstance(candle, dict) else candle["low"]
    close_price = candle["close"] if isinstance(candle, dict) else candle["close"]
    return (
        f"{timeframe} {zone_type} candle @ {stamp} | idx {source_index} | "
        f"O {_format_price_value(open_price)} H {_format_price_value(high_price)} "
        f"L {_format_price_value(low_price)} C {_format_price_value(close_price)}"
    )


def format_entry_zone(payload: dict[str, Any] | None) -> str:
    if not payload:
        return "-"
    top = payload.get("zone_top")
    bottom = payload.get("zone_bottom")
    if top is not None and bottom is not None:
        return _format_price_range(bottom, top)
    if "entry_low" in payload and "entry_high" in payload:
        return _format_price_range(payload["entry_low"], payload["entry_high"])
    ifvg = payload.get("ifvg") or {}
    low = ifvg.get("low")
    high = ifvg.get("high")
    return _format_price_range(low, high)


def grade_from_score(score: float | None) -> str | None:
    if score is None or score <= 0:
        return None
    if score >= 8.6:
        return "A"
    if score >= 7.2:
        return "B"
    return "C"


def compute_setup_score(
    primary_context: dict[str, Any] | None,
    active_watch: dict[str, Any] | None,
    confirmed_signal: dict[str, Any] | None,
) -> tuple[float | None, str | None, dict[str, float]]:
    if confirmed_signal is not None:
        score = round(float(confirmed_signal.get("score") or 0.0), 1)
        components = {
            key: round(float(value), 2)
            for key, value in (confirmed_signal.get("score_components") or {}).items()
        }
        return score, grade_from_score(score), components

    if active_watch is not None:
        context = active_watch.get("context") or primary_context or {}
        ifvg = active_watch.get("ifvg") or {}
        ifvg_filter = active_watch.get("ifvg_filter") or {}
        reclaim = active_watch.get("reclaim") or {}
        displacement = active_watch.get("post_sweep_displacement") or {}
        components = {
            "htf_zone_quality": round(float(context.get("zone_quality") or 0.0), 2),
            "htf_reaction_clarity": round(float(context.get("reaction_clarity") or 0.0), 2),
            "liquidity_sweep_quality": round(float(active_watch.get("sweep_quality") or 0.0), 2),
            "mss_clarity": 0.0,
            "ifvg_quality": round(float(max(ifvg.get("quality") or 0.0, ifvg_filter.get("quality") or 0.0)), 2),
            "entry_location": round(float(ifvg.get("entry_quality") or 0.0), 2),
            "structural_stop_validity": 1.0 if active_watch.get("invalidation_price") is not None else 0.72,
            "rr": round(
                _clamp(0.35 + float(reclaim.get("quality") or 0.0) * 0.35 + float(displacement.get("quality") or 0.0) * 0.3),
                2,
            ),
        }
        score = round(sum(float(value) for value in components.values()), 1)
        return score, grade_from_score(score), components

    if primary_context is not None:
        components = {
            "htf_zone_quality": round(float(primary_context.get("zone_quality") or 0.0), 2),
            "htf_reaction_clarity": round(float(primary_context.get("reaction_clarity") or 0.0), 2),
            "liquidity_sweep_quality": 0.0,
            "mss_clarity": 0.0,
            "ifvg_quality": 0.0,
            "entry_location": 0.0,
            "structural_stop_validity": 0.0,
            "rr": 0.0,
        }
        score = round(sum(float(value) for value in components.values()), 1)
        return score, grade_from_score(score), components

    return None, None, {}


def format_score(score: float | None, grade: str | None) -> str:
    if score is None or grade is None:
        return "-"
    return f"{grade} ({score:.1f})"


def format_timeline_lines(timeline: dict[str, Any] | None) -> str:
    if not timeline:
        return "-"
    events = timeline.get("events") or []
    if not events:
        return "-"
    lines = []
    for item in events[-6:]:
        timestamp = str(item.get("timestamp") or "")
        clock = timestamp[11:16] if len(timestamp) >= 16 else timestamp
        lines.append(f"{clock} {item.get('label', '-')}")
    return "\n".join(lines)


def build_detail_payload(
    state: str,
    htf_bias: str,
    primary_context: dict[str, Any] | None,
    active_watch: dict[str, Any] | None,
    confirmed_signal: dict[str, Any] | None,
    rejection: dict[str, Any] | None,
    score: float | None,
    grade: str | None,
    score_components: dict[str, float],
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source = confirmed_signal or active_watch
    liquidity_state = primary_context.get("liquidity_interaction_state") if primary_context else None
    market_bias = htf_bias
    reaction_strength = str((primary_context or {}).get("reaction_strength") or "-")
    return {
        "current_state": state,
        "htf_bias": htf_bias,
        "market_structure_bias": market_bias,
        "liquidity_interaction_state": _humanize_liquidity_state(liquidity_state),
        "reaction_strength": reaction_strength,
        "htf_context": format_context_label(primary_context),
        "htf_zone_type": format_htf_zone_type(primary_context),
        "htf_zone_source": format_htf_zone_source(primary_context, snapshot),
        "htf_context_reason": format_context_reason(primary_context),
        "last_detected_sweep": format_sweep_detail(source),
        "last_detected_mss": format_mss_detail(confirmed_signal),
        "last_detected_ifvg": format_ifvg_detail(source),
        "rejection_reason": describe_rejection(rejection.get("reason")) if rejection else "-",
        "last_alert_time": None,
        "last_alert_details": "-",
        "cooldown_info": None,
        "active_watch_id": source.get("watch_key") if source else None,
        "active_watch_info": (
            f"{source.get('timeframe', '-')} {direction_label(source.get('bias'))} | waiting for {source.get('waiting_for', '-')}"
            if source
            else "-"
        ),
        "zone": format_htf_zone(primary_context, active_watch, confirmed_signal),
        "zone_top_bottom": format_entry_zone(source),
        "score": format_score(score, grade),
        "score_components": score_components,
        "timeline": "-",
    }
