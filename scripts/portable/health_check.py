from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import MetaTrader5 as mt5

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from infra.config import load_app_config
from infra.mt5.runtime import _safe_mt5_shutdown, launch_mt5_terminal, load_mt5_runtime_settings, wait_for_mt5_terminal
from scripts.portable.env_loader import load_portable_environment


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Portable MT5 health check")
    parser.add_argument("--json", action="store_true", help="Print the result as JSON.")
    parser.add_argument("--launch", action="store_true", help="Launch portable MT5 before checking readiness.")
    parser.add_argument("--symbol", help="Optional symbol to test for symbol visibility and tick readiness.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = ROOT
    env = load_portable_environment(root)
    os.environ.update(env)

    settings = load_mt5_runtime_settings()
    probe_symbol = args.symbol
    if not probe_symbol:
        try:
            config = load_app_config()
            probe_symbol = next(iter(config.scanner.symbols), None)
        except ValueError:
            probe_symbol = None

    if args.launch:
        try:
            launch_mt5_terminal(settings=settings)
        except FileNotFoundError as exc:
            report = {
                "ready": False,
                "state": "terminal_missing",
                "message": str(exc),
            }
            if args.json:
                print(json.dumps(report, ensure_ascii=True, indent=2))
            else:
                print(f"ready={report['ready']}")
                print(f"state={report['state']}")
                print(f"message={report['message']}")
            return 1

    report = wait_for_mt5_terminal(mt5, symbol=probe_symbol, settings=settings)
    if args.json:
        print(
            json.dumps(
                {
                    "ready": report.ready,
                    "state": report.state,
                    "message": report.message,
                    "terminal_path": str(report.terminal_path) if report.terminal_path else None,
                    "terminal_name": report.terminal_name,
                    "account_login": report.account_login,
                    "account_server": report.account_server,
                    "symbol": report.symbol,
                    "tick_time": report.tick_time,
                    "tick_age_sec": report.tick_age_sec,
                },
                ensure_ascii=True,
                indent=2,
            )
        )
    else:
        print(f"ready={report.ready}")
        print(f"state={report.state}")
        print(f"message={report.message}")
        if report.terminal_name:
            print(f"terminal={report.terminal_name}")
        if report.account_login:
            print(f"account_login={report.account_login}")
        if report.account_server:
            print(f"account_server={report.account_server}")
        if report.symbol:
            print(f"symbol={report.symbol}")
        if report.tick_age_sec is not None:
            print(f"tick_age_sec={report.tick_age_sec:.0f}")

    _safe_mt5_shutdown(mt5)
    return 0 if report.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
