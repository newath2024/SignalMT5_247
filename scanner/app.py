import argparse
import time
from pathlib import Path

from .charting import build_signal_charts
from .config import DEFAULT_POLL_INTERVAL_SEC, WATCHLIST
from .data import build_symbol_snapshot, connect_mt5
from .deps import mt5
from .delivery import send_signal_package
from .htf import build_htf_zones, select_htf_contexts
from .ltf import detect_signal, suppress_watch_alert, update_watchlist
from .state.alert_cache import can_send_alert, get_alert_cache_count, get_alert_cache_file, mark_alert_sent
from .state.session_state import build_timeframe_signature, get_symbol_state
from .state.watch_cache import get_watch_cache_count, get_watch_cache_file
from .utils import log

HTF_SIGNATURE_FRAMES = ("H4", "H1", "D1", "W1")
LTF_SIGNATURE_FRAMES = ("M15", "M5", "M3")


def _get_analysis_context(symbol, snapshot):
    state = get_symbol_state(symbol)
    htf_signature = build_timeframe_signature(snapshot, HTF_SIGNATURE_FRAMES)
    ltf_signature = build_timeframe_signature(snapshot, LTF_SIGNATURE_FRAMES)
    htf_dirty = state.get("htf_signature") != htf_signature
    ltf_dirty = state.get("ltf_signature") != ltf_signature

    if htf_dirty or "all_htf_zones" not in state or "contexts" not in state:
        state["all_htf_zones"] = build_htf_zones(snapshot)
        state["contexts"] = select_htf_contexts(snapshot, state["all_htf_zones"])
        state["htf_signature"] = htf_signature

    state["ltf_signature"] = ltf_signature
    return state["all_htf_zones"], state["contexts"], htf_dirty, ltf_dirty


def scan_symbol(symbol):
    snapshot = build_symbol_snapshot(symbol)
    if snapshot is None:
        return

    all_htf_zones, contexts, htf_dirty, ltf_dirty = _get_analysis_context(symbol, snapshot)
    # Our scanner only confirms patterns from closed candles, so no new bar means no new structure.
    if not htf_dirty and not ltf_dirty:
        return

    armed_watches, _ = update_watchlist(snapshot, all_htf_zones, contexts)
    for watch_setup in armed_watches:
        swept_liquidity = ", ".join(watch_setup["swept_liquidity"])
        log(
            f"Watch armed for {symbol}: {watch_setup['bias']} {watch_setup['timeframe']} "
            f"at {watch_setup['htf_context']} after sweeping {swept_liquidity} with strict iFVG"
        )

    signal = detect_signal(snapshot, all_htf_zones, contexts)
    if signal is None:
        return

    if not can_send_alert(signal["setup_key"]):
        log(f"Cooldown active for {symbol}: {signal['setup_key']}")
        suppress_watch_alert(signal["watch_key"], signal["mss_index"])
        return

    chart_paths = build_signal_charts(snapshot, signal)
    if chart_paths is None:
        log(f"Rejected {symbol}: chart evidence was not clear enough to render.")
        return

    try:
        sent = send_signal_package(signal, chart_paths["htf"], chart_paths["ltf"])
    finally:
        for path in chart_paths.values():
            if Path(path).exists():
                Path(path).unlink(missing_ok=True)

    if not sent:
        return

    mark_alert_sent(signal["setup_key"])
    suppress_watch_alert(signal["watch_key"], signal["mss_index"])

    log(
        f"WATCH confirmed for {symbol}: {signal['bias']} {signal['timeframe']} "
        f"score {signal['score']:.1f} RR {signal['rr']:.2f}R with charts"
    )


def main_loop(run_once=False, poll_interval_sec=DEFAULT_POLL_INTERVAL_SEC):
    connect_mt5()
    try:
        restored = get_watch_cache_count(statuses=("watch", "alerted"))
        if restored:
            log(f"Restored {restored} watch setups from {get_watch_cache_file().name}.")
        restored_alerts = get_alert_cache_count()
        if restored_alerts:
            log(f"Restored {restored_alerts} recent alerts from {get_alert_cache_file().name}.")

        while True:
            for symbol in WATCHLIST:
                scan_symbol(symbol)

            if run_once:
                break

            time.sleep(max(1, poll_interval_sec))
    finally:
        mt5.shutdown()
        log("Disconnected from MT5.")


def parse_args():
    parser = argparse.ArgumentParser(description="MT5 HTF/LTF scanner")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one scan only and exit.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_POLL_INTERVAL_SEC,
        help="Seconds between scans in loop mode.",
    )
    return parser.parse_args()
