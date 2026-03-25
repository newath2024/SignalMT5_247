from __future__ import annotations

from dataclasses import asdict

from domain.narrative import LiquidityEvent, NarrativeAnalysis, NarrativeEvent

from ..config.ltf import LTF_IFVG_ENTRY_MIN_QUALITY, SIGNAL_AMBIGUITY_DELTA, WATCH_EXPIRY_BARS
from ..patterns.ifvg import find_ifvg_zone
from ..structure.mss import detect_mss_break
from .sweep import (
    classify_sweep_type,
    detect_sweep_candidates,
    evaluate_post_sweep_displacement,
    evaluate_reclaim_quality,
    is_meaningful_watch_ifvg,
)


def _rate_value(rates, field: str, index: int, default=None):
    try:
        return rates[field][index]
    except Exception:
        try:
            return rates[index][field]
        except Exception:
            return default


def _rate_time(rates, index: int) -> int | None:
    value = _rate_value(rates, "time", index)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _select_primary_label(labels, bias):
    if labels:
        return str(labels[0])
    return "sell-side liquidity" if bias == "Long" else "buy-side liquidity"


def _liquidity_side_from_bias(bias: str) -> str:
    return "sell_side" if bias == "Long" else "buy_side"


def _make_liquidity_event(rates, timeframe_name, bias, candidate, point):
    labels = list(candidate.get("swept_external") or [])
    primary_label = _select_primary_label(labels, bias)
    reference_price = candidate.get("reference_price")
    sweep_index = int(candidate["sweep_index"])
    candle_open = float(_rate_value(rates, "open", sweep_index, candidate["sweep_level"]) or candidate["sweep_level"])
    candle_close = float(_rate_value(rates, "close", sweep_index, candidate["sweep_level"]) or candidate["sweep_level"])
    candle_high = float(_rate_value(rates, "high", sweep_index, candidate["sweep_level"]) or candidate["sweep_level"])
    candle_low = float(_rate_value(rates, "low", sweep_index, candidate["sweep_level"]) or candidate["sweep_level"])
    candle_range = max(candle_high - candle_low, point)
    body_ratio = abs(candle_close - candle_open) / candle_range
    wick_ratio = (
        (min(candle_open, candle_close) - candle_low) / candle_range
        if bias == "Long"
        else (candle_high - max(candle_open, candle_close)) / candle_range
    )
    reference_price_value = float(reference_price) if reference_price is not None else None
    sweep_depth = abs(float(candidate["sweep_level"]) - float(reference_price_value or candidate["sweep_level"]))
    return LiquidityEvent(
        label=primary_label,
        side=_liquidity_side_from_bias(bias),
        bias=bias,
        timeframe=timeframe_name,
        sweep_index=sweep_index,
        timestamp=_rate_time(rates, sweep_index),
        sweep_price=float(candidate["sweep_level"]),
        reference_price=reference_price_value,
        close_price=candle_close,
        reclaimed=True,
        sweep_depth=sweep_depth,
        sweep_depth_ratio=sweep_depth / max(float(candidate["avg_range"]), point),
        wick_ratio=_clamp(wick_ratio),
        body_ratio=_clamp(body_ratio),
        quality=float(candidate["sweep_quality"]),
        is_external_liquidity=bool(labels),
        close_reclaim=True,
        metadata={
            "labels": labels or [primary_label],
            "structure_level": float(candidate["structure_level"]),
        },
    )


def _find_mss(rates, timeframe_name, bias, candidate, point):
    start_index = int(candidate["sweep_index"]) + 1
    end_index = min(len(rates), int(candidate["sweep_index"]) + 1 + WATCH_EXPIRY_BARS[timeframe_name])
    mss = detect_mss_break(
        rates,
        bias,
        candidate["structure_level"],
        candidate["avg_range"],
        point,
        start_index,
        end_index,
    )
    if mss is None:
        return None
    return {
        **mss,
        "confirm_time": _rate_time(rates, int(mss["mss_index"])),
        "structure_level": float(candidate["structure_level"]),
    }


def _find_ifvg(rates, bias, candidate, mss, current_price, point):
    if mss is None:
        return None
    ifvg = find_ifvg_zone(
        rates,
        bias,
        candidate["sweep_index"],
        mss["mss_index"],
        current_price,
        candidate["avg_range"],
        point,
    )
    if ifvg is None:
        return None
    if ifvg.get("mode") != "strict":
        return None
    if float(ifvg.get("entry_quality") or 0.0) < LTF_IFVG_ENTRY_MIN_QUALITY:
        return None
    touch_index = ifvg.get("touch_index")
    if touch_index is None or int(touch_index) <= int(mss["mss_index"]):
        return None
    return ifvg


def _primary_candidate_rank(item):
    # Newer external liquidity touches should immediately take control of the
    # narrative, even if an older AS/LO sweep is still waiting for MSS/iFVG.
    return (
        item["primary_event"].sweep_index,
        1 if item["ifvg"] is not None else 0,
        1 if item["mss"] is not None else 0,
        1 if item["classification"].get("type") == "reversal" else 0,
        item["score"],
    )


def _build_timeline(rates, bias, primary_event, displacement, mss, ifvg, opposite_event=None):
    events = [
        NarrativeEvent(
            index=primary_event.sweep_index,
            event_type="sweep",
            timestamp=primary_event.timestamp,
            bias=bias,
            label=primary_event.label,
            side=primary_event.side,
            price=primary_event.sweep_price,
            details={"quality": round(primary_event.quality, 3)},
        ).to_dict()
    ]
    if displacement is not None:
        events.append(
            NarrativeEvent(
                index=int(displacement["anchor_index"]),
                event_type="displacement",
                timestamp=_rate_time(rates, int(displacement["anchor_index"])),
                bias=bias,
                price=float(displacement["net_move"]),
                details={
                    "quality": round(float(displacement.get("quality") or 0.0), 3),
                    "valid": bool(displacement.get("valid")),
                },
            ).to_dict()
        )
    if mss is not None:
        events.append(
            NarrativeEvent(
                index=int(mss["mss_index"]),
                event_type="mss",
                timestamp=mss.get("confirm_time"),
                bias=bias,
                price=float(mss["structure_level"]),
                details={"quality": round(float(mss.get("mss_quality") or 0.0), 3)},
            ).to_dict()
        )
    if ifvg is not None:
        events.append(
            NarrativeEvent(
                index=int(ifvg.get("touch_index") or ifvg["source_index"]),
                event_type="ifvg",
                timestamp=_rate_time(rates, int(ifvg.get("touch_index") or ifvg["source_index"])),
                bias=bias,
                price=float(ifvg["entry_edge"]),
                details={
                    "quality": round(float(ifvg.get("quality") or 0.0), 3),
                    "entry_quality": round(float(ifvg.get("entry_quality") or 0.0), 3),
                    "low": float(ifvg["low"]),
                    "high": float(ifvg["high"]),
                },
            ).to_dict()
        )
    if opposite_event is not None:
        events.append(
            NarrativeEvent(
                index=opposite_event.sweep_index,
                event_type="opposite_sweep",
                timestamp=opposite_event.timestamp,
                bias=opposite_event.bias,
                label=opposite_event.label,
                side=opposite_event.side,
                price=opposite_event.sweep_price,
                details={"quality": round(opposite_event.quality, 3)},
            ).to_dict()
        )
    events.sort(key=lambda item: (int(item.get("index") or -1), str(item.get("type") or "")))
    return events


def _score_candidate(candidate, reclaim, displacement, mss, ifvg, opposite_before_completion):
    quality = float(candidate["sweep_quality"])
    quality += float(reclaim.get("quality") or 0.0) * 0.7
    quality += float(displacement.get("quality") or 0.0) * 0.8
    quality += float((mss or {}).get("mss_quality") or 0.0) * 0.9
    quality += float((ifvg or {}).get("quality") or 0.0)
    quality += float((ifvg or {}).get("entry_quality") or 0.0) * 0.4
    if opposite_before_completion:
        quality -= 0.75
    return round(quality, 4)


def _candidate_completion_index(candidate, mss, ifvg):
    if ifvg is not None:
        return int(ifvg.get("touch_index") or ifvg["source_index"])
    if mss is not None:
        return int(mss["mss_index"])
    return int(candidate["sweep_index"])


def _analyze_side(
    symbol,
    rates,
    bias,
    timeframe_name,
    current_price,
    point,
    context,
    same_side_candidates,
    opposite_side_candidates,
):
    if not same_side_candidates:
        return NarrativeAnalysis(
            symbol=symbol,
            timeframe=timeframe_name,
            bias=bias,
            state="awaiting_ltf_sweep",
            narrative_bias=bias,
            narrative_quality=0.0,
            ready_for_signal=False,
            invalidation_reason="no qualified liquidity sweep detected",
            status_reason=f"Awaiting {bias} liquidity sweep",
        )

    evaluated = []
    opposite_event_rows = []
    opposite_bias = "Short" if bias == "Long" else "Long"
    for item in opposite_side_candidates:
        event = _make_liquidity_event(rates, timeframe_name, opposite_bias, item, point)
        opposite_event_rows.append(
            {
                "event": event,
                "candidate": item,
                "mss": _find_mss(rates, timeframe_name, opposite_bias, item, point),
            }
        )
    opposite_event_rows.sort(key=lambda item: item["event"].sweep_index)

    for candidate in same_side_candidates:
        primary_event = _make_liquidity_event(rates, timeframe_name, bias, candidate, point)
        mss = _find_mss(rates, timeframe_name, bias, candidate, point)
        anchor_index = int(mss["mss_index"]) if mss is not None else int(candidate["sweep_index"]) + 1
        ifvg = _find_ifvg(rates, bias, candidate, mss, current_price, point)
        if ifvg is not None:
            anchor_index = max(int(ifvg.get("touch_index") or ifvg["source_index"]), int(ifvg["origin_candle_index"]))
        reclaim = evaluate_reclaim_quality(
            rates,
            bias,
            candidate,
            ifvg,
            point,
            anchor_index=anchor_index,
        )
        displacement = evaluate_post_sweep_displacement(
            rates,
            bias,
            candidate,
            ifvg,
            point,
            anchor_index=anchor_index,
        )
        displacement["anchor_index"] = anchor_index
        displacement["net_move"] = displacement.get("move_ratio", 0.0) * float(candidate["avg_range"])
        ifvg_filter = (
            is_meaningful_watch_ifvg(rates, candidate, ifvg, point)
            if ifvg is not None
            else {"valid": False, "quality": 0.0}
        )
        if mss is None or ifvg is None:
            classification = {"type": "developing", "reason": None}
        else:
            classification = classify_sweep_type(context, candidate, reclaim, displacement, ifvg_filter)
        completion_index = _candidate_completion_index(candidate, mss, ifvg)
        opposite_row = next((item for item in opposite_event_rows if item["event"].sweep_index > primary_event.sweep_index), None)
        opposite_after_primary = opposite_row["event"] if opposite_row else None
        opposite_before_completion = bool(opposite_after_primary and opposite_after_primary.sweep_index <= completion_index)
        score = _score_candidate(candidate, reclaim, displacement, mss, ifvg, opposite_before_completion)
        evaluated.append(
            {
                "candidate": candidate,
                "primary_event": primary_event,
                "mss": mss,
                "ifvg": ifvg,
                "reclaim": reclaim,
                "displacement": displacement,
                "ifvg_filter": ifvg_filter,
                "classification": classification,
                "opposite_event": opposite_after_primary,
                "opposite_row": opposite_row,
                "opposite_before_completion": opposite_before_completion,
                "score": score,
                "completion_index": completion_index,
            }
        )

    evaluated.sort(key=_primary_candidate_rank, reverse=True)
    best = evaluated[0]
    best["primary_event"].is_primary_candidate = True

    strongest_opposite = opposite_event_rows[0]["event"] if opposite_event_rows else None
    ambiguity = False
    if len(evaluated) > 1 and abs(best["score"] - evaluated[1]["score"]) < SIGNAL_AMBIGUITY_DELTA:
        ambiguity = True

    state = "sweep_detected"
    invalidation_reason = None
    status_reason = f"Primary sweep detected: {best['primary_event'].label}"
    ready_for_signal = False

    if best["mss"] is None:
        state = "awaiting_mss"
        status_reason = f"Primary sweep: {best['primary_event'].label} | Awaiting MSS"
    elif best["ifvg"] is None:
        state = "awaiting_ifvg"
        status_reason = f"{bias} MSS confirmed after {best['primary_event'].label} sweep | Awaiting strict iFVG"
    else:
        state = "armed"
        ready_for_signal = True
        status_reason = f"{bias} narrative armed from {best['primary_event'].label} sweep"

    if best["classification"].get("type") == "continuation":
        state = "invalidated"
        ready_for_signal = False
        invalidation_reason = best["classification"].get("reason") or "continuation sweep narrative"
        status_reason = f"Narrative invalidated: {invalidation_reason}"
    elif best["classification"].get("type") == "ambiguous":
        state = "ambiguous"
        ready_for_signal = False
        invalidation_reason = best["classification"].get("reason") or "ambiguous reversal evidence"
        status_reason = f"Narrative ambiguous: {invalidation_reason}"

    opposite_event = best["opposite_event"]
    opposite_row = best.get("opposite_row")
    has_two_sided_sweep = opposite_event is not None
    if opposite_event is not None and state not in {"invalidated", "ambiguous"}:
        opposite_has_mss = bool((opposite_row or {}).get("mss"))
        if best["opposite_before_completion"] and opposite_has_mss:
            state = "invalidated"
            ready_for_signal = False
            invalidation_reason = (
                f"opposite liquidity {opposite_event.label} swept and confirmed MSS before {bias} setup completed"
            )
            status_reason = f"Narrative invalidated after opposite sweep {opposite_event.label} formed its own MSS"
        elif best["opposite_before_completion"]:
            state = "two_sided_liquidity_taken"
            ready_for_signal = False
            invalidation_reason = (
                f"opposite liquidity {opposite_event.label} swept before {bias} narrative completion"
            )
            status_reason = f"Two-sided sweep: primary {best['primary_event'].label}, opposite {opposite_event.label}"
        elif opposite_has_mss:
            state = "invalidated"
            ready_for_signal = False
            invalidation_reason = f"opposite liquidity {opposite_event.label} later confirmed opposing MSS"
            status_reason = f"Narrative invalidated after opposite MSS from {opposite_event.label}"
        else:
            state = "degraded"
            ready_for_signal = False
            invalidation_reason = f"opposite liquidity {opposite_event.label} swept after primary narrative formed"
            status_reason = f"Narrative degraded after opposite sweep: {opposite_event.label}"

    if ambiguity and state not in {"invalidated", "two_sided_liquidity_taken"}:
        state = "ambiguous"
        ready_for_signal = False
        invalidation_reason = "competing sweep candidates with similar quality"
        status_reason = "Narrative ambiguous: competing sweep candidates"

    timeline = _build_timeline(
        rates,
        bias,
        best["primary_event"],
        best["displacement"],
        best["mss"],
        best["ifvg"],
        opposite_event=opposite_event,
    )

    return NarrativeAnalysis(
        symbol=symbol,
        timeframe=timeframe_name,
        bias=bias,
        state=state,
        narrative_bias=bias,
        narrative_quality=float(best["score"]),
        ready_for_signal=ready_for_signal and state == "armed",
        has_two_sided_sweep=has_two_sided_sweep,
        ambiguous=state == "ambiguous",
        primary_sweep=best["primary_event"].to_dict(),
        opposite_sweep=opposite_event.to_dict() if opposite_event is not None else None,
        first_external_sweep=timeline[0] if timeline else None,
        second_external_sweep=timeline[1] if len(timeline) > 1 and timeline[1].get("type") in {"sweep", "opposite_sweep"} else None,
        displacement=best["displacement"],
        mss=best["mss"],
        ifvg=best["ifvg"],
        invalidation_reason=invalidation_reason,
        status_reason=status_reason,
        timeline=timeline,
        sweep_candidates=[item["primary_event"].to_dict() for item in evaluated[:4]],
        metadata={
            "classification": best["classification"],
            "reclaim": best["reclaim"],
            "ifvg_filter": best["ifvg_filter"],
            "completion_index": best["completion_index"],
            "avg_range": float(best["candidate"]["avg_range"]),
            "structure_level": float(best["candidate"]["structure_level"]),
            "strongest_opposite_sweep": strongest_opposite.to_dict() if strongest_opposite is not None else None,
        },
    )


def build_ltf_narrative(rates, bias, current_price, point, timeframe_name, context, symbol="-"):
    same_side_candidates = detect_sweep_candidates(rates, bias, point)
    opposite_bias = "Short" if bias == "Long" else "Long"
    opposite_side_candidates = detect_sweep_candidates(rates, opposite_bias, point)
    same_side_candidates.sort(key=lambda item: int(item["sweep_index"]))
    opposite_side_candidates.sort(key=lambda item: int(item["sweep_index"]))

    return _analyze_side(
        symbol=symbol,
        rates=rates,
        bias=bias,
        timeframe_name=timeframe_name,
        current_price=current_price,
        point=point,
        context=context,
        same_side_candidates=same_side_candidates,
        opposite_side_candidates=opposite_side_candidates,
    )


def narrative_to_watch_trigger(narrative: NarrativeAnalysis) -> tuple[dict | None, dict | None]:
    payload = narrative.to_dict()
    primary_sweep = narrative.primary_sweep or {}
    if not primary_sweep:
        return None, {
            "reason": narrative.invalidation_reason or "no qualified primary sweep",
            "debug": {"narrative": payload},
        }
    return {
        "bias": narrative.bias,
        "timeframe": narrative.timeframe,
        "state": narrative.state,
        "narrative": payload,
        "narrative_state": narrative.state,
        "narrative_quality": narrative.narrative_quality,
        "status_reason": narrative.status_reason,
        "invalidation_reason": narrative.invalidation_reason,
        "sweep_index": primary_sweep.get("sweep_index"),
        "sweep_level": primary_sweep.get("sweep_price"),
        "sweep_price": primary_sweep.get("sweep_price"),
        "sweep_quality": primary_sweep.get("quality"),
        "swept_external": list((primary_sweep.get("metadata") or {}).get("labels") or [primary_sweep.get("label")]),
        "sweep_label": primary_sweep.get("label"),
        "structure_level": narrative.metadata.get("structure_level") or ((primary_sweep.get("metadata") or {}).get("structure_level")),
        "avg_range": float(narrative.metadata.get("avg_range") or 0.0),
        "ifvg": narrative.ifvg,
        "mss": narrative.mss,
        "reclaim": narrative.metadata.get("reclaim"),
        "displacement": narrative.displacement,
        "ifvg_filter": narrative.metadata.get("ifvg_filter"),
        "sweep_classification": narrative.metadata.get("classification"),
        "watch_index": (
            int((narrative.ifvg or {}).get("touch_index") or (narrative.mss or {}).get("mss_index") or primary_sweep.get("sweep_index") or 0)
        ),
        "bars_since_watch": 0,
        "ready_for_signal": narrative.ready_for_signal,
    }, None
