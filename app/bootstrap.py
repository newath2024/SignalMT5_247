"""Compatibility CLI/bootstrap wrapper.

Canonical startup path lives in ``app.startup.build_application_controller``.
"""

import argparse
import time

from infra.config import DATA_DIR
from infra.process_lock import ProcessFileLock

from .startup import build_application_controller


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Liquidity Sniper desktop application")
    parser.add_argument("--headless", action="store_true", help="Run without the desktop UI.")
    parser.add_argument("--once", action="store_true", help="Run one scan cycle and exit.")
    parser.add_argument("--interval", type=int, help="Override loop interval in seconds.")
    parser.add_argument("--no-autostart", action="store_true", help="Open the desktop UI without auto-starting the scanner.")
    return parser.parse_args(argv)


def main(argv=None):
    try:
        args = parse_args(argv)
    except ValueError as exc:
        print(f"Configuration error: {exc}")
        return 2
    instance_lock = ProcessFileLock(DATA_DIR / "app_instance.lock")
    if not instance_lock.acquire():
        print("Liquidity Sniper is already running. Close the existing instance first.")
        return 9

    controller = None
    try:
        try:
            controller = build_application_controller()
        except ValueError as exc:
            print(f"Configuration error: {exc}")
            return 2
        if args.interval:
            controller.set_interval(args.interval)

        if args.headless or args.once:
            if args.once:
                controller.run_once()
                return 0
            started, message = controller.start()
            if not started:
                raise RuntimeError(message)
            while True:
                snapshot = controller.snapshot()
                status = (snapshot.get("scanner") or {}).get("status")
                if status == "error":
                    return 2
                time.sleep(1)

        from ui import launch_desktop

        return launch_desktop(controller, auto_start=not args.no_autostart)
    except KeyboardInterrupt:
        return 0
    finally:
        if controller is not None:
            controller.shutdown()
        instance_lock.release()
