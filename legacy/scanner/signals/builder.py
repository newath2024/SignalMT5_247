from ..config.ltf import EXTERNAL_LIQUIDITY_LEVELS, MIN_RR, SETUP_NAME, SIGNAL_EXPIRY_MINUTES
from .invalidation import build_invalidation_lines
from .scorer import score_signal
from .targets import select_targets


def build_signal(snapshot, context, trigger, trigger_timeframe, all_htf_zones):
    execution = trigger["execution"]
    entry_price = execution["entry_price"]
    stop_loss = execution["stop_loss"]
    bias = trigger["bias"]
    digits = snapshot["digits"]
    ifvg = trigger["ifvg"]

    targets = select_targets(
        entry_price,
        stop_loss,
        bias,
        all_htf_zones,
        snapshot["rates"][trigger_timeframe],
    )
    if targets is None or targets["rr"] < MIN_RR:
        return None

    scoring = score_signal(context, trigger, ifvg, execution["risk"], targets["rr"])
    if not scoring["valid"]:
        return None

    swept_liquidity = trigger["swept_external"]
    liquidity_map = {
        label: snapshot["reference_levels"][label]
        for label in EXTERNAL_LIQUIDITY_LEVELS[bias]
        if label in snapshot["reference_levels"]
    }
    invalidation = build_invalidation_lines(
        bias,
        trigger_timeframe,
        stop_loss,
        digits,
        context["zone"]["label"],
    )
    liquidity_text = ", ".join(swept_liquidity)
    setup_key = (
        f"{snapshot['symbol']}|{bias}|{trigger_timeframe}|{context['zone']['label']}|"
        f"{round(entry_price, digits)}|{round(stop_loss, digits)}"
    )

    return {
        "setup": SETUP_NAME,
        "setup_key": setup_key,
        "symbol": snapshot["symbol"],
        "timeframe": trigger_timeframe,
        "bias": bias,
        "htf_context": context["zone"]["label"],
        "entry_low": execution["entry_zone_low"],
        "entry_high": execution["entry_zone_high"],
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "tp1": targets["tp1"],
        "tp2": targets["tp2"],
        "rr": targets["rr"],
        "score": scoring["score"],
        "score_components": scoring["score_components"],
        "why": [
            f"Clear HTF context at {context['zone']['label']} with visible reaction.",
            f"{trigger_timeframe} reversal-type sweep of {liquidity_text} armed the watch with strong reclaim and strict iFVG.",
            f"MSS is now confirmed, keeping RR at {targets['rr']:.2f}R.",
        ],
        "invalidation": invalidation,
        "expiry_minutes": SIGNAL_EXPIRY_MINUTES[trigger_timeframe],
        "digits": digits,
        "trigger_summary": "WATCH confirmed: MSS confirmed after HTF + sweep + iFVG watch setup",
        "watch_confirmed": True,
        "watch_status": "WATCH confirmed",
        "session_note": scoring["session_note"],
        "actionability": execution["actionability"],
        "htf_zone": context["zone"],
        "htf_chart_timeframe": (
            "H4"
            if context["zone"]["timeframe"] in ("H4", "W1")
            else "M30"
            if context["zone"]["timeframe"] == "M30"
            else "H1"
        ),
        "sweep_index": trigger["sweep_index"],
        "sweep_price": trigger["sweep_level"],
        "mss_index": trigger["mss_index"],
        "mss_level": trigger["structure_level"],
        "ifvg_source_index": ifvg["source_index"],
        "ifvg_origin_candle_index": ifvg["origin_candle_index"],
        "ifvg_origin_candle_high": ifvg["origin_candle_high"],
        "ifvg_origin_candle_low": ifvg["origin_candle_low"],
        "entry_edge": ifvg["entry_edge"],
        "bars_since_mss": trigger["bars_since_mss"],
        "swept_liquidity": swept_liquidity,
        "liquidity_map": liquidity_map,
        "sweep_type": trigger.get("sweep_classification", {}).get("type", "reversal"),
    }
