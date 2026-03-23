if __package__ in (None, ""):
    import sys
    from pathlib import Path

    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from scanner.config.ltf import TRIGGER_TIMEFRAMES, WATCH_EXPIRY_BARS, WATCH_INVALIDATION_BUFFER_POINTS
    from scanner.htf import evaluate_htf_zone
    from scanner.state.watch_cache import get_symbol_watches, remove_watch_setup, upsert_watch_setup
    from scanner.utils import notify_once
    from scanner.ltf.sweep import detect_ltf_watch_trigger
else:
    from ..config.ltf import TRIGGER_TIMEFRAMES, WATCH_EXPIRY_BARS, WATCH_INVALIDATION_BUFFER_POINTS
    from ..htf import evaluate_htf_zone
    from ..state.watch_cache import get_symbol_watches, remove_watch_setup, upsert_watch_setup
    from ..utils import notify_once
    from .sweep import detect_ltf_watch_trigger


def build_watch_setup(snapshot, context, trigger, trigger_timeframe):
    bias = trigger["bias"]
    ifvg = trigger["ifvg"]
    stop_reference = ifvg["origin_candle_low"] if bias == "Long" else ifvg["origin_candle_high"]
    rates = snapshot["rates"][trigger_timeframe]

    return {
        "symbol": snapshot["symbol"],
        "bias": bias,
        "timeframe": trigger_timeframe,
        "htf_context": context.get("liquidity_interaction_label") or context["zone"]["label"],
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
        "expiry_bar_index": trigger["watch_index"] + WATCH_EXPIRY_BARS[trigger_timeframe],
        "invalidation_price": stop_reference,
        "status": "watch",
        "alerted_mss_index": None,
        "trend_alignment": context.get("trend_alignment", "range"),
        "structure_trend": context.get("structure_trend", "Range"),
    }


def detect_watch_setup(snapshot, all_htf_zones, contexts):
    watch_setups = []

    for bias in ("Long", "Short"):
        context = contexts[bias]
        if context is None:
            continue

        for timeframe_name in TRIGGER_TIMEFRAMES:
            trigger, rejection = detect_ltf_watch_trigger(
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
                    notify_once(
                        f"watch-reject:{snapshot['symbol']}:{timeframe_name}:{bias}:{rejection['reason']}",
                        f"{snapshot['symbol']} {timeframe_name} {bias} rejected: {rejection['reason']}",
                    )
                continue

            watch_setups.append(build_watch_setup(snapshot, context, trigger, timeframe_name))

    return watch_setups


def _watch_has_expired(snapshot, watch_setup):
    rates = snapshot["rates"][watch_setup["timeframe"]]
    return len(rates) - 1 > watch_setup["expiry_bar_index"]


def _watch_is_invalidated(snapshot, watch_setup, refreshed_context):
    if refreshed_context is None or not refreshed_context["clear"]:
        return True

    rates = snapshot["rates"][watch_setup["timeframe"]]
    latest_close = float(rates["close"][-1])
    buffer = snapshot["point"] * WATCH_INVALIDATION_BUFFER_POINTS

    if watch_setup["bias"] == "Long":
        return latest_close < watch_setup["invalidation_price"] - buffer
    return latest_close > watch_setup["invalidation_price"] + buffer


def cleanup_watch_setups(snapshot):
    removed = []
    for watch_setup in list(get_symbol_watches(snapshot["symbol"], statuses=("watch", "alerted"))):
        if (
            "post_sweep_displacement" not in watch_setup
            or "ifvg_filter" not in watch_setup
            or "reclaim" not in watch_setup
            or "sweep_classification" not in watch_setup
        ):
            remove_watch_setup(watch_setup["watch_key"])
            removed.append((watch_setup, "legacy"))
            continue

        refreshed_context = evaluate_htf_zone(watch_setup["htf_zone"], snapshot)
        if _watch_has_expired(snapshot, watch_setup):
            remove_watch_setup(watch_setup["watch_key"])
            removed.append((watch_setup, "expired"))
            continue
        if _watch_is_invalidated(snapshot, watch_setup, refreshed_context):
            remove_watch_setup(watch_setup["watch_key"])
            removed.append((watch_setup, "invalidated"))
            continue
        watch_setup["context"] = refreshed_context

    return removed


def update_watchlist(snapshot, all_htf_zones, contexts):
    removed = cleanup_watch_setups(snapshot)
    armed = []

    for watch_setup in detect_watch_setup(snapshot, all_htf_zones, contexts):
        created, stored = upsert_watch_setup(watch_setup)
        if created:
            armed.append(stored)

    return armed, removed


if __name__ == "__main__":
    raise SystemExit(
        "scanner/ltf/watch.py la module noi bo, khong phai file de chay truc tiep.\n"
        "Hay chay tu thu muc project bang:\n"
        "  python main.py\n"
        "hoac:\n"
        "  python main.py --cli"
    )
