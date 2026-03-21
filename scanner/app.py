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


def _build_scan_result(symbol, status, message, **extra):
    payload = {
        "symbol": symbol,
        "status": status,
        "message": message,
        "scanned_at": time.time(),
    }
    payload.update(extra)
    return payload


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
        return _build_scan_result(symbol, "unavailable", "Market data unavailable")

    result_context = {
        "current_price": float(snapshot["current_price"]),
        "broker_now": snapshot["broker_now"].isoformat(),
    }

    all_htf_zones, contexts, htf_dirty, ltf_dirty = _get_analysis_context(symbol, snapshot)
    if not htf_dirty and not ltf_dirty:
        return _build_scan_result(symbol, "waiting", "No new closed candles to process", **result_context)

    armed_watches, removed_watches = update_watchlist(snapshot, all_htf_zones, contexts)
    for watch_setup in armed_watches:
        swept_liquidity = ", ".join(watch_setup["swept_liquidity"])
        log(
            f"Watch armed for {symbol}: {watch_setup['bias']} {watch_setup['timeframe']} "
            f"at {watch_setup['htf_context']} after sweeping {swept_liquidity} with strict iFVG"
        )

    signal = detect_signal(snapshot, all_htf_zones, contexts)
    if signal is None:
        if armed_watches:
            return _build_scan_result(
                symbol,
                "watch_armed",
                f"Armed {len(armed_watches)} new watch setup(s)",
                armed_watches=len(armed_watches),
                removed_watches=len(removed_watches),
                **result_context,
            )
        if removed_watches:
            return _build_scan_result(
                symbol,
                "watch_maintained",
                f"Cleared {len(removed_watches)} stale watch setup(s)",
                armed_watches=0,
                removed_watches=len(removed_watches),
                **result_context,
            )
        return _build_scan_result(
            symbol,
            "scanned",
            "Structure refreshed with no confirmed signal",
            armed_watches=0,
            removed_watches=0,
            **result_context,
        )

    if not can_send_alert(signal["setup_key"]):
        log(f"Cooldown active for {symbol}: {signal['setup_key']}")
        suppress_watch_alert(signal["watch_key"], signal["mss_index"])
        return _build_scan_result(
            symbol,
            "cooldown",
            "Confirmed setup hit cooldown window",
            bias=signal["bias"],
            timeframe=signal["timeframe"],
            setup_key=signal["setup_key"],
            **result_context,
        )

    chart_paths = build_signal_charts(snapshot, signal)
    if chart_paths is None:
        log(f"Rejected {symbol}: chart evidence was not clear enough to render.")
        return _build_scan_result(
            symbol,
            "rejected",
            "Signal rejected because chart evidence was unclear",
            bias=signal["bias"],
            timeframe=signal["timeframe"],
            score=signal["score"],
            rr=signal["rr"],
            **result_context,
        )

    try:
        sent = send_signal_package(signal, chart_paths["htf"], chart_paths["ltf"])
    finally:
        for path in chart_paths.values():
            if Path(path).exists():
                Path(path).unlink(missing_ok=True)

    if not sent:
        return _build_scan_result(
            symbol,
            "delivery_failed",
            "Signal confirmed but Telegram delivery failed",
            bias=signal["bias"],
            timeframe=signal["timeframe"],
            score=signal["score"],
            rr=signal["rr"],
            setup_key=signal["setup_key"],
            **result_context,
        )

    mark_alert_sent(signal["setup_key"])
    suppress_watch_alert(signal["watch_key"], signal["mss_index"])

    log(
        f"WATCH confirmed for {symbol}: {signal['bias']} {signal['timeframe']} "
        f"score {signal['score']:.1f} RR {signal['rr']:.2f}R with charts"
    )
    return _build_scan_result(
        symbol,
        "alerted",
        f"{signal['bias']} {signal['timeframe']} alert sent",
        bias=signal["bias"],
        timeframe=signal["timeframe"],
        score=signal["score"],
        rr=signal["rr"],
        setup_key=signal["setup_key"],
        **result_context,
    )


def run_scan_cycle(symbol_hook=None):
    results = []
    for symbol in WATCHLIST:
        try:
            result = scan_symbol(symbol)
        except Exception as exc:
            log(f"Scan failed for {symbol}: {exc}")
            result = _build_scan_result(symbol, "error", str(exc))
        results.append(result)
        if symbol_hook is not None:
            symbol_hook(result)
    return results


def _build_cycle_summary(results, started_at, finished_at):
    status_counts = {}
    for result in results:
        status = result["status"]
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_sec": max(0.0, finished_at - started_at),
        "symbol_count": len(results),
        "alerts_sent": status_counts.get("alerted", 0),
        "status_counts": status_counts,
        "results": results,
    }


def main_loop(run_once=False, poll_interval_sec=DEFAULT_POLL_INTERVAL_SEC, stop_event=None, symbol_hook=None, cycle_hook=None):
    connect_mt5()
    try:
        restored = get_watch_cache_count(statuses=("watch", "alerted"))
        if restored:
            log(f"Restored {restored} watch setups from {get_watch_cache_file().name}.")
        restored_alerts = get_alert_cache_count()
        if restored_alerts:
            log(f"Restored {restored_alerts} recent alerts from {get_alert_cache_file().name}.")

        while True:
            if stop_event is not None and stop_event.is_set():
                break

            cycle_started_at = time.time()
            results = run_scan_cycle(symbol_hook=symbol_hook)
            cycle_finished_at = time.time()
            if cycle_hook is not None:
                cycle_hook(_build_cycle_summary(results, cycle_started_at, cycle_finished_at))

            if run_once:
                break

            if stop_event is None:
                time.sleep(max(1, poll_interval_sec))
                continue

            if stop_event.wait(max(1, poll_interval_sec)):
                break
    finally:
        mt5.shutdown()
        log("Disconnected from MT5.")


def parse_args():
    parser = argparse.ArgumentParser(description="MT5 HTF/LTF scanner")
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run the classic console scanner loop instead of the desktop app.",
    )
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
    parser.add_argument(
        "--desktop",
        action="store_true",
        help="Run the desktop app explicitly. This is the default mode when --cli is not used.",
    )
    parser.add_argument(
        "--no-autostart",
        action="store_true",
        help="Open the desktop app without starting the scanner loop automatically.",
    )
    return parser.parse_args()


def launch(args=None):
    if args is None:
        args = parse_args()

    if args.cli or args.once:
        main_loop(run_once=args.once, poll_interval_sec=args.interval)
        return 0

    from app.controller import AppController
    from ui import launch_desktop

    controller = AppController()
    controller.set_interval(args.interval)
    return launch_desktop(controller, auto_start=not args.no_autostart)
