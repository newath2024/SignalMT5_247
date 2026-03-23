from legacy.bridges.detection import build_signal_from_watch, build_watch_trigger, detect_mss_confirmation, get_ltf_config

_LTF_CONFIG = get_ltf_config()
SIGNAL_AMBIGUITY_DELTA = _LTF_CONFIG["signal_ambiguity_delta"]
TIMEFRAME_PRIORITY = _LTF_CONFIG["timeframe_priority"]
WATCH_EXPIRY_BARS = _LTF_CONFIG["watch_expiry_bars"]
WATCH_INVALIDATION_BUFFER_POINTS = _LTF_CONFIG["watch_invalidation_buffer_points"]


def build_watch_key(watch_setup):
    ifvg = watch_setup["ifvg"]
    return (
        f"{watch_setup['symbol']}|{watch_setup['bias']}|{watch_setup['timeframe']}|"
        f"{watch_setup['htf_context']}|{ifvg['source_index']}|"
        f"{round(float(ifvg['low']), 8)}|{round(float(ifvg['high']), 8)}"
    )


def build_watch_setup(snapshot, context, trigger, trigger_timeframe):
    bias = trigger["bias"]
    ifvg = trigger["ifvg"]
    stop_reference = ifvg["origin_candle_low"] if bias == "Long" else ifvg["origin_candle_high"]
    rates = snapshot["rates"][trigger_timeframe]
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
        "ifvg": trigger["ifvg"],
        "reclaim": trigger["reclaim"],
        "post_sweep_displacement": trigger["displacement"],
        "ifvg_filter": trigger["ifvg_filter"],
        "sweep_classification": trigger["sweep_classification"],
        "watch_index": trigger["watch_index"],
        "created_bar_index": len(rates) - 1,
        "created_bar_time": int(rates[-1]["time"]),
        "armed_at": snapshot["broker_now"].isoformat(timespec="seconds"),
        "expiry_bar_index": trigger["watch_index"] + WATCH_EXPIRY_BARS[trigger_timeframe],
        "invalidation_price": stop_reference,
        "status": "armed",
        "direction": "LONG" if bias == "Long" else "SHORT",
        "ltf_sweep_status": "sweep detected",
        "waiting_for": "MSS after sweep",
        "zone_top": float(ifvg["high"]),
        "zone_bottom": float(ifvg["low"]),
        "status_reason": f"armed: {context['zone']['label']} + LTF sweep",
        "last_confirmed_mss_index": None,
        "trend_alignment": context.get("trend_alignment", "range"),
        "structure_trend": context.get("structure_trend", "Range"),
    }
    watch_setup["watch_key"] = build_watch_key(watch_setup)
    return watch_setup


def detect_watch_candidates(snapshot, contexts, trigger_timeframes):
    watch_setups = []
    rejections = []

    for bias in ("Long", "Short"):
        context = contexts.get(bias)
        if context is None:
            continue

        for timeframe_name in trigger_timeframes:
            trigger, rejection = build_watch_trigger(
                snapshot["rates"][timeframe_name],
                bias,
                snapshot["current_price"],
                snapshot["point"],
                timeframe_name,
                snapshot["reference_levels"],
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

            watch_setups.append(build_watch_setup(snapshot, context, trigger, timeframe_name))

    return watch_setups, rejections


def watch_has_expired(snapshot, watch_setup):
    rates = snapshot["rates"][watch_setup["timeframe"]]
    return len(rates) - 1 > int(watch_setup["expiry_bar_index"])


def watch_is_invalidated(snapshot, watch_setup, refreshed_context):
    if refreshed_context is None or not refreshed_context["clear"]:
        return True

    rates = snapshot["rates"][watch_setup["timeframe"]]
    latest_close = float(rates["close"][-1])
    buffer = snapshot["point"] * WATCH_INVALIDATION_BUFFER_POINTS

    if watch_setup["bias"] == "Long":
        return latest_close < float(watch_setup["invalidation_price"]) - buffer
    return latest_close > float(watch_setup["invalidation_price"]) + buffer


def _confirm_watch(snapshot, all_htf_zones, watch_setup):
    if watch_setup.get("status") not in ("armed", "cooldown"):
        return None

    rates = snapshot["rates"][watch_setup["timeframe"]]
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
        "bars_since_mss": mss["bars_since_mss"],
        "mss_quality": mss["mss_quality"],
        "sweep_quality": watch_setup["sweep_quality"],
        "ifvg": watch_setup["ifvg"],
        "reclaim": watch_setup["reclaim"],
        "avg_range": watch_setup["avg_range"],
        "swept_external": watch_setup["swept_liquidity"],
        "sweep_classification": watch_setup["sweep_classification"],
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
            TIMEFRAME_PRIORITY[item["timeframe"]],
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
