from ..config.ltf import MAX_TRIGGER_AGE, SIGNAL_AMBIGUITY_DELTA, TIMEFRAME_PRIORITY
from ..state.watch_cache import get_symbol_watches, mark_watch_alerted
from ..structure.mss import detect_mss_break
from .execution import build_signal
from .watch import cleanup_watch_setups


def detect_mss_confirmation(rates, bias, watch_setup, point):
    if rates is None or len(rates) < 10:
        return None

    start_index = max(
        watch_setup["watch_index"] + 1,
        (watch_setup["ifvg"].get("touch_index") or watch_setup["ifvg"]["source_index"]) + 1,
    )
    last_index = min(len(rates), watch_setup["expiry_bar_index"] + 1)
    mss = detect_mss_break(
        rates,
        bias,
        watch_setup["structure_level"],
        watch_setup["avg_range"],
        point,
        start_index,
        last_index,
    )
    if mss is None:
        return None

    bars_since_mss = len(rates) - 1 - mss["mss_index"]
    if bars_since_mss > MAX_TRIGGER_AGE[watch_setup["timeframe"]]:
        return None

    return {
        "mss_index": mss["mss_index"],
        "mss_quality": mss["mss_quality"],
        "bars_since_mss": bars_since_mss,
    }


def _confirm_watch_setup(snapshot, all_htf_zones, watch_setup):
    if watch_setup["status"] != "watch":
        return None

    refreshed_context = watch_setup["context"]
    rates = snapshot["rates"][watch_setup["timeframe"]]
    mss = detect_mss_confirmation(rates, watch_setup["bias"], watch_setup, snapshot["point"])
    if mss is None:
        return None
    if watch_setup.get("alerted_mss_index") == mss["mss_index"]:
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
    signal = build_signal(snapshot, refreshed_context, trigger, watch_setup["timeframe"], all_htf_zones)
    if signal is None:
        return None

    signal["watch_key"] = watch_setup["watch_key"]
    signal["watch_created_bar_time"] = watch_setup["created_bar_time"]
    signal["watch_created_bar_index"] = watch_setup["created_bar_index"]
    return signal


def detect_signal(snapshot, all_htf_zones, contexts):
    cleanup_watch_setups(snapshot)
    candidate_signals = []

    for watch_setup in get_symbol_watches(snapshot["symbol"], statuses=("watch",)):
        signal = _confirm_watch_setup(snapshot, all_htf_zones, watch_setup)
        if signal is not None:
            candidate_signals.append(signal)

    if not candidate_signals:
        return None

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
            return None

    return best_signal


def suppress_watch_alert(watch_key, mss_index):
    mark_watch_alerted(watch_key, mss_index)
