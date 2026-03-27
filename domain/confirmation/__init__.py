"""Canonical LTF confirmation pipeline package."""

from __future__ import annotations

from legacy.bridges.detection import build_signal_from_watch, build_watch_trigger, detect_mss_confirmation, get_ltf_config
from legacy.scanner.utils import zone_distance

from domain.timeframes import timeframe_rank

_LTF_CONFIG = get_ltf_config()
SIGNAL_AMBIGUITY_DELTA = _LTF_CONFIG["signal_ambiguity_delta"]
WATCH_EXPIRY_BARS = _LTF_CONFIG["watch_expiry_bars"]
WATCH_INVALIDATION_BUFFER_POINTS = _LTF_CONFIG["watch_invalidation_buffer_points"]


def _resolve_watch_interaction_price(snapshot, payload=None):
    if payload is None:
        return snapshot.get("current_price")

    narrative = payload.get("narrative") or {}
    primary_sweep = payload.get("primary_sweep") or narrative.get("primary_sweep") or {}
    for candidate in (
        payload.get("sweep_price"),
        payload.get("sweep_level"),
        primary_sweep.get("sweep_price"),
        snapshot.get("current_price"),
    ):
        if candidate is not None:
            return float(candidate)
    return None


def _htf_fvg_is_engaged(snapshot, context, payload=None):
    zone = (context or {}).get("zone") or {}
    if str(zone.get("type") or "").upper() != "FVG":
        return True, None

    mitigation_status = str(zone.get("mitigation_status") or (context or {}).get("mitigation_status") or "").lower()
    mitigation = ((zone.get("fvg_debug") or {}).get("mitigation") or {})
    if mitigation_status and mitigation_status != "untouched":
        return True, None
    if bool(mitigation.get("touched")):
        return True, None

    low = zone.get("low")
    high = zone.get("high")
    interaction_price = _resolve_watch_interaction_price(snapshot, payload)
    if low is not None and high is not None and interaction_price is not None:
        tolerance = max(float(zone.get("tolerance") or 0.0), float(snapshot.get("point") or 0.0) * 2.0)
        if zone_distance(float(interaction_price), float(low), float(high)) <= tolerance:
            return True, None

    return False, {
        "reason": "HTF FVG untouched",
        "debug": {
            "zone_label": zone.get("label"),
            "zone_low": low,
            "zone_high": high,
            "mitigation_status": zone.get("mitigation_status"),
            "current_price": snapshot.get("current_price"),
            "interaction_price": interaction_price,
        },
    }


def build_watch_key(watch_setup):
    primary_sweep = watch_setup.get("primary_sweep") or {}
    return (
        f"{watch_setup['symbol']}|{watch_setup['bias']}|{watch_setup['timeframe']}|"
        f"{watch_setup['htf_context']}|{primary_sweep.get('label', '-')}"
        f"|{primary_sweep.get('sweep_index', watch_setup.get('sweep_index', '-'))}"
    )


def build_watch_setup(snapshot, context, trigger, trigger_timeframe):
    bias = trigger["bias"]
    ifvg = trigger.get("ifvg") or {}
    narrative = trigger.get("narrative") or {}
    primary_sweep = narrative.get("primary_sweep") or {}
    if ifvg:
        stop_reference = ifvg["origin_candle_low"] if bias == "Long" else ifvg["origin_candle_high"]
    else:
        stop_reference = primary_sweep.get("reference_price") or primary_sweep.get("sweep_price")
    rates = snapshot["rates"][trigger_timeframe]
    watch_state = str(trigger.get("narrative_state") or trigger.get("state") or "awaiting_mss")
    waiting_for = "MSS"
    if watch_state == "awaiting_ifvg":
        waiting_for = "strict iFVG"
    elif watch_state == "armed":
        waiting_for = "trigger"
    sweep_status = trigger.get("status_reason") or f"Primary sweep {primary_sweep.get('label', '-')}"
    watch_setup = {
        "symbol": snapshot["symbol"],
        "bias": bias,
        "timeframe": trigger_timeframe,
        "htf_context": context["zone"]["label"],
        "htf_zone": context["zone"],
        "context": context,
        "sweep_index": trigger["sweep_index"],
        "sweep_price": trigger["sweep_level"],
        "structure_level": trigger["structure_level"],
        "sweep_quality": trigger["sweep_quality"],
        "swept_liquidity": trigger["swept_external"],
        "avg_range": trigger["avg_range"],
        "ifvg": ifvg,
        "reclaim": trigger.get("reclaim") or {},
        "post_sweep_displacement": trigger.get("displacement") or {},
        "ifvg_filter": trigger.get("ifvg_filter") or {},
        "sweep_classification": trigger.get("sweep_classification") or {},
        "watch_index": trigger["watch_index"],
        "created_bar_index": len(rates) - 1,
        "created_bar_time": int(rates[-1]["time"]),
        "armed_at": snapshot["broker_now"].isoformat(timespec="seconds"),
        "expiry_bar_index": trigger["watch_index"] + WATCH_EXPIRY_BARS[trigger_timeframe],
        "invalidation_price": stop_reference,
        "status": watch_state,
        "direction": "LONG" if bias == "Long" else "SHORT",
        "ltf_sweep_status": sweep_status,
        "waiting_for": waiting_for,
        "zone_top": float(ifvg["high"]) if ifvg else None,
        "zone_bottom": float(ifvg["low"]) if ifvg else None,
        "status_reason": trigger.get("status_reason") or f"narrative: {watch_state}",
        "last_confirmed_mss_index": None,
        "trend_alignment": context.get("trend_alignment", "range"),
        "structure_trend": context.get("structure_trend", "Range"),
        "narrative": narrative,
        "narrative_state": watch_state,
        "narrative_quality": trigger.get("narrative_quality"),
        "primary_sweep": primary_sweep,
        "opposite_sweep": narrative.get("opposite_sweep"),
        "has_two_sided_sweep": bool(narrative.get("has_two_sided_sweep")),
        "invalidation_reason": trigger.get("invalidation_reason"),
        "ready_for_signal": bool(trigger.get("ready_for_signal")),
        "mss": trigger.get("mss") or narrative.get("mss"),
    }
    watch_setup["watch_key"] = build_watch_key(watch_setup)
    return watch_setup


def detect_watch_candidates(snapshot, contexts, confirmation_timeframes):
    watch_setups = []
    rejections = []

    for bias in ("Long", "Short"):
        context = contexts.get(bias)
        if context is None:
            continue

        active_htf = str((context.get("zone") or {}).get("timeframe") or "")
        for timeframe_name in confirmation_timeframes:
            trigger, rejection = build_watch_trigger(
                snapshot["rates"][timeframe_name],
                bias,
                snapshot["current_price"],
                snapshot["point"],
                timeframe_name,
                None,
                context,
            )
            if trigger is None:
                if rejection:
                    rejections.append(
                        {
                            "symbol": snapshot["symbol"],
                            "timeframe": timeframe_name,
                            "bias": bias,
                            "phase": "watch",
                            "reason": rejection.get("reason"),
                            "debug": rejection.get("debug"),
                        }
                    )
                continue
            context_ready, context_rejection = _htf_fvg_is_engaged(snapshot, context, trigger)
            if not context_ready:
                rejections.append(
                    {
                        "symbol": snapshot["symbol"],
                        "timeframe": timeframe_name,
                        "bias": bias,
                        "phase": "watch",
                        "reason": context_rejection.get("reason"),
                        "debug": context_rejection.get("debug"),
                    }
                )
                continue

            watch = build_watch_setup(snapshot, context, trigger, timeframe_name)
            watch["active_htf"] = active_htf
            watch["source_zone_timeframe"] = active_htf
            watch["confirmation_timeframes"] = list(confirmation_timeframes)
            watch_setups.append(watch)

    return watch_setups, rejections


def watch_has_expired(snapshot, watch_setup):
    rates = snapshot["rates"][watch_setup["timeframe"]]
    return len(rates) - 1 > int(watch_setup["expiry_bar_index"])


def watch_is_invalidated(snapshot, watch_setup, refreshed_context):
    if refreshed_context is None or not refreshed_context["clear"]:
        return True
    if watch_setup.get("narrative_state") in {"invalidated", "ambiguous", "two_sided_liquidity_taken"}:
        return True
    context_ready, _context_rejection = _htf_fvg_is_engaged(snapshot, refreshed_context, watch_setup)
    if not context_ready:
        return True

    rates = snapshot["rates"][watch_setup["timeframe"]]
    latest_close = float(rates["close"][-1])
    buffer = snapshot["point"] * WATCH_INVALIDATION_BUFFER_POINTS

    if watch_setup.get("invalidation_price") is None:
        return False
    if watch_setup["bias"] == "Long":
        return latest_close < float(watch_setup["invalidation_price"]) - buffer
    return latest_close > float(watch_setup["invalidation_price"]) + buffer


def _confirm_watch(snapshot, all_htf_zones, watch_setup):
    if watch_setup.get("status") not in ("armed", "cooldown"):
        return None
    if not watch_setup.get("ready_for_signal"):
        return None
    if not watch_setup.get("ifvg"):
        return None

    rates = snapshot["rates"][watch_setup["timeframe"]]
    mss = watch_setup.get("mss") or (watch_setup.get("narrative") or {}).get("mss")
    if not mss:
        mss = detect_mss_confirmation(rates, watch_setup["bias"], watch_setup, snapshot["point"])
    if mss is None:
        return None
    if watch_setup.get("last_confirmed_mss_index") == mss["mss_index"]:
        return None

    trigger = {
        "bias": watch_setup["bias"],
        "sweep_index": watch_setup["sweep_index"],
        "sweep_level": watch_setup["sweep_price"],
        "structure_level": watch_setup["structure_level"],
        "mss_index": mss["mss_index"],
        "bars_since_mss": mss.get("bars_since_mss", len(rates) - 1 - int(mss["mss_index"])),
        "mss_quality": mss["mss_quality"],
        "sweep_quality": watch_setup["sweep_quality"],
        "ifvg": watch_setup["ifvg"],
        "reclaim": watch_setup["reclaim"],
        "avg_range": watch_setup["avg_range"],
        "swept_external": watch_setup["swept_liquidity"],
        "sweep_classification": watch_setup["sweep_classification"],
        "narrative": watch_setup.get("narrative") or {},
    }
    signal = build_signal_from_watch(snapshot, watch_setup["context"], trigger, watch_setup["timeframe"], all_htf_zones)
    if signal is None:
        return None

    signal["watch_key"] = watch_setup["watch_key"]
    signal["watch_created_bar_time"] = watch_setup["created_bar_time"]
    signal["watch_created_bar_index"] = watch_setup["created_bar_index"]
    return signal


def detect_confirmed_signal(snapshot, active_watches, all_htf_zones):
    candidate_signals = []

    for watch_setup in active_watches:
        signal = _confirm_watch(snapshot, all_htf_zones, watch_setup)
        if signal is not None:
            candidate_signals.append(signal)

    if not candidate_signals:
        return None, None

    candidate_signals.sort(
        key=lambda item: (
            item["actionability"],
            timeframe_rank(item["timeframe"]),
            item["score"],
            item["rr"],
            -item["bars_since_mss"],
        ),
        reverse=True,
    )
    best_signal = candidate_signals[0]
    if len(candidate_signals) > 1:
        second_signal = candidate_signals[1]
        if second_signal["bias"] != best_signal["bias"] and abs(best_signal["score"] - second_signal["score"]) < SIGNAL_AMBIGUITY_DELTA:
            return None, "ambiguous competing signals"

    return best_signal, None


__all__ = [
    "SIGNAL_AMBIGUITY_DELTA",
    "WATCH_EXPIRY_BARS",
    "WATCH_INVALIDATION_BUFFER_POINTS",
    "build_watch_key",
    "build_watch_setup",
    "detect_confirmed_signal",
    "detect_mss_confirmation",
    "detect_watch_candidates",
    "watch_has_expired",
    "watch_is_invalidated",
]
