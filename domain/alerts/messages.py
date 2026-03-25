"""Domain-level alert semantics and text builders."""

from __future__ import annotations


def build_watch_armed_message(watch: dict) -> str:
    return "\n".join(
        [
            f"[WATCH] {watch['symbol']} {watch['timeframe']} armed after structural sweep",
            f"Bias: {watch['bias']}",
            f"HTF: {watch['htf_context']}",
            f"Sweep: {', '.join(watch.get('swept_liquidity', [])) or '-'}",
            "Entry model: first edge of strict iFVG",
            "SL model: origin candle extreme",
        ]
    )


def _format_price(value, digits: int) -> str:
    return f"{float(value):.{digits}f}".rstrip("0").rstrip(".")


def build_signal_caption(signal: dict) -> str:
    swept_liquidity = ", ".join(signal.get("swept_liquidity", [])) or "structural liquidity"
    digits = signal.get("digits", 5)
    entry_low = _format_price(signal["entry_low"], digits)
    entry_high = _format_price(signal["entry_high"], digits)
    entry_price = _format_price(signal["entry_price"], digits)
    stop_loss = _format_price(signal["stop_loss"], digits)
    tp1 = _format_price(signal["tp1"], digits)
    tp2 = _format_price(signal["tp2"], digits)

    if abs(float(signal["entry_high"]) - float(signal["entry_low"])) <= 10 ** (-digits):
        entry_text = entry_price
    else:
        entry_text = f"{entry_price} (edge of {entry_low} - {entry_high})"

    lines = [
        f"[SIGNAL] {signal['symbol']} {signal['timeframe']} - {signal['bias']}",
        f"Status: {signal.get('watch_status', 'Confirmed')}",
        f"HTF: {signal['htf_context']}",
        f"LTF: {swept_liquidity}, MSS confirmed after HTF structure + sweep + iFVG watch setup",
        f"Entry: {entry_text}",
        f"SL: {stop_loss}",
        f"TP1: {tp1}",
        f"TP2: {tp2}",
        f"RR {signal['rr']:.2f}R | Score {signal['score']:.1f}/10",
    ]

    if signal.get("invalidation"):
        lines.append("Invalidation:")
        lines.extend(f"- {item}" for item in signal["invalidation"][:2])

    expiry_minutes = signal.get("expiry_minutes")
    if expiry_minutes:
        lines.append(f"Expiry: {expiry_minutes}m")

    return "\n".join(lines)


__all__ = ["build_signal_caption", "build_watch_armed_message"]
