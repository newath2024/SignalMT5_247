from __future__ import annotations

import queue
import threading

from domain.enums import SetupState


def _format_float(value) -> str:
    if value is None:
        return "-"
    return f"{float(value):.5f}".rstrip("0").rstrip(".")


def _format_symbol_list(symbols: list[str], limit: int = 6) -> str:
    if not symbols:
        return "-"
    visible = symbols[:limit]
    suffix = "" if len(symbols) <= limit else f" +{len(symbols) - limit} more"
    return ", ".join(visible) + suffix


class ScannerCommandService:
    def __init__(self, engine, symbol_registry, runtime_state, logger):
        self.engine = engine
        self.symbol_registry = symbol_registry
        self.runtime_state = runtime_state
        self.logger = logger
        self._queue: queue.Queue[dict | None] = queue.Queue()
        self._lock = threading.RLock()
        self._worker: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self.runtime_state.seed_symbol_states(self.engine.snapshot().get("symbols", []))

    def start(self):
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return False, "Scanner command worker already running."
            self._stop_event = threading.Event()
            self._worker = threading.Thread(
                target=self._worker_loop,
                name="OpenClawTelegramCommandWorker",
                daemon=True,
            )
            self._worker.start()
        return True, "Scanner command worker started."

    def stop(self):
        worker = None
        with self._lock:
            worker = self._worker
            stop_event = self._stop_event
            self._worker = None
            self._stop_event = None
        if stop_event is not None:
            stop_event.set()
        self._queue.put(None)
        if worker is not None:
            worker.join(timeout=3.0)
        return True, "Scanner command worker stopped."

    def scan_symbol(self, symbol: str) -> dict | None:
        normalized = self.symbol_registry.normalize_symbol(symbol)
        if normalized is None:
            raise ValueError(f"Unknown symbol: {symbol}")
        return self.engine.rescan_symbol(normalized)

    def scan_all_symbols(self) -> list[dict]:
        if self._is_engine_full_scan_active():
            raise RuntimeError("A full scan is already running.")
        return self.engine.rescan_now()

    def get_symbol_status(self, symbol: str) -> dict | None:
        normalized = self.symbol_registry.normalize_symbol(symbol)
        if normalized is None:
            return None
        state = self.runtime_state.get_symbol_state(normalized)
        if state is not None:
            return state
        symbols = self.engine.snapshot().get("symbols", [])
        for item in symbols:
            if item.get("symbol") == normalized:
                self.runtime_state.update_symbol_state(item)
                return item
        return None

    def get_system_status(self) -> dict:
        snapshot = self.engine.snapshot()
        return {
            "scanner": snapshot.get("scanner", {}),
            "connections": snapshot.get("connections", {}),
            "metrics": snapshot.get("metrics", {}),
            "active_jobs": self.runtime_state.list_active_jobs(),
            "recent_jobs": self.runtime_state.recent_jobs(limit=10),
            "full_scan_active": self.runtime_state.is_full_scan_active() or self._is_engine_full_scan_active(),
        }

    def queue_symbol_scan(self, raw_symbol: str, requested_by: str, reply_callback=None) -> tuple[bool, str]:
        normalized = self.symbol_registry.normalize_symbol(raw_symbol)
        self.logger.info(
            "Telegram symbol normalized",
            symbol=normalized or str(raw_symbol).upper(),
            phase="telegram",
            reason=f"raw={raw_symbol}",
        )
        if normalized is None:
            suggestions = self.symbol_registry.suggest_symbols(raw_symbol)
            hint = f" Suggestions: {', '.join(suggestions)}." if suggestions else ""
            return False, f"Unknown symbol '{raw_symbol}'. Use /symbols to see configured symbols.{hint}"
        job = self.runtime_state.queue_job(
            kind="scan_symbol",
            symbol=normalized,
            requested_by=requested_by,
            metadata={"raw_symbol": raw_symbol},
        )
        if job is None:
            return False, f"Could not queue scan for {normalized}."
        self.logger.info(
            "Telegram job queued",
            symbol=normalized,
            phase="telegram",
            reason=f"job_id={job['job_id']}",
        )
        self._queue.put(
            {
                "job_id": job["job_id"],
                "kind": "scan_symbol",
                "symbol": normalized,
                "reply_callback": reply_callback,
            }
        )
        return True, f"Queued scan for {normalized}. I will send the result when it finishes."

    def queue_full_scan(self, requested_by: str, reply_callback=None) -> tuple[bool, str]:
        if self._is_full_scan_busy():
            return False, "A full scan is already running. Wait for it to finish before using /scan all again."
        job = self.runtime_state.queue_job(kind="scan_all", symbol=None, requested_by=requested_by)
        if job is None:
            return False, "A full scan is already queued. Wait for it to finish before using /scan all again."
        self.logger.info(
            "Telegram job queued",
            phase="telegram",
            reason=f"job_id={job['job_id']} kind=scan_all",
        )
        self._queue.put(
            {
                "job_id": job["job_id"],
                "kind": "scan_all",
                "symbol": None,
                "reply_callback": reply_callback,
            }
        )
        return True, "Queued full scan. I will send a summary when it finishes."

    def _worker_loop(self):
        while True:
            if self._stop_event is not None and self._stop_event.is_set():
                break
            try:
                job = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if job is None:
                continue
            self._run_job(job)

    def _run_job(self, job: dict):
        self.runtime_state.mark_job_started(job["job_id"])
        symbol = job.get("symbol")
        self.logger.info(
            "Telegram job started",
            symbol=symbol,
            phase="telegram_worker",
            reason=f"job_id={job['job_id']} kind={job['kind']}",
        )
        try:
            if job["kind"] == "scan_symbol":
                result = self.scan_symbol(symbol)
                summary = self._format_symbol_summary(result)
            else:
                results = self.scan_all_symbols()
                summary = self._format_full_scan_summary(results)
            self.runtime_state.mark_job_completed(job["job_id"], summary=summary)
            self.logger.info(
                "Telegram job completed",
                symbol=symbol,
                phase="telegram_worker",
                reason=f"job_id={job['job_id']}",
            )
            self._safe_reply(job.get("reply_callback"), summary, symbol=symbol, job_id=job["job_id"])
        except Exception as exc:
            message = f"Scan job failed: {exc}"
            self.runtime_state.mark_job_completed(job["job_id"], error=str(exc))
            self.logger.error(
                "Telegram job completed with error",
                symbol=symbol,
                phase="telegram_worker",
                reason=f"job_id={job['job_id']} error={exc}",
            )
            self._safe_reply(job.get("reply_callback"), message, symbol=symbol, job_id=job["job_id"])
        finally:
            self._queue.task_done()

    def _safe_reply(self, callback, message: str, symbol: str | None, job_id: str):
        if callback is None:
            return
        try:
            callback(message)
        except Exception as exc:
            self.logger.error(
                "Telegram completion reply failed",
                symbol=symbol,
                phase="telegram",
                reason=f"job_id={job_id} error={exc}",
            )

    def _is_engine_full_scan_active(self) -> bool:
        progress = self.engine.snapshot().get("scanner", {}).get("progress", {})
        return bool(progress.get("active")) and int(progress.get("total") or 0) > 1

    def _is_full_scan_busy(self) -> bool:
        return self.runtime_state.is_full_scan_active() or self._is_engine_full_scan_active()

    def _format_symbol_summary(self, result: dict | None) -> str:
        if not result:
            return "Scan finished without a symbol result."
        self.runtime_state.update_symbol_state(result)
        lines = [
            f"Scan complete: {result.get('symbol', '-')}",
            f"State: {self._state_label(result.get('state'))}",
            f"Bias: {result.get('bias', '-')}",
            f"HTF: {result.get('htf_context', '-')}",
            f"Phase: {result.get('phase', '-')}",
            f"Reason: {result.get('reason', '-')}",
        ]
        timeframe = result.get("tf")
        if timeframe and timeframe != "-":
            lines.append(f"TF: {timeframe}")
        if result.get("price") is not None:
            lines.append(f"Price: {_format_float(result.get('price'))}")
        if result.get("score") is not None:
            grade = result.get("grade")
            score_label = _format_float(result.get("score"))
            if grade:
                score_label = f"{grade} {score_label}"
            lines.append(f"Score: {score_label}")
        detail = result.get("detail") or {}
        if detail.get("last_detected_sweep") not in {None, "-", ""}:
            lines.append(f"Sweep: {detail.get('last_detected_sweep')}")
        if detail.get("last_detected_mss") not in {None, "-", ""}:
            lines.append(f"MSS: {detail.get('last_detected_mss')}")
        return "\n".join(lines)

    def _format_full_scan_summary(self, results: list[dict]) -> str:
        results = results or []
        for item in results:
            self.runtime_state.update_symbol_state(item)
        ready = [item["symbol"] for item in results if item.get("state") == SetupState.CONFIRMED.value]
        armed = [
            item["symbol"]
            for item in results
            if item.get("state") in {SetupState.ARMED.value, SetupState.WAITING_MSS.value}
        ]
        context_only = [item["symbol"] for item in results if item.get("state") == SetupState.CONTEXT_FOUND.value]
        rejected = [item["symbol"] for item in results if item.get("state") == SetupState.REJECTED.value]
        errors = [item["symbol"] for item in results if item.get("state") == SetupState.ERROR.value]
        actionable_count = len(ready) + len(armed)
        lines = [
            f"Sweep check complete: {len(results)} symbols",
            f"Active setups: {actionable_count}",
            f"Locked targets: {_format_symbol_list(ready)}",
            f"Tracking setups: {_format_symbol_list(armed)}",
            f"HTF thesis only: {_format_symbol_list(context_only)}",
            f"Invalid / no edge: {_format_symbol_list(rejected)}",
        ]
        if errors:
            lines.append(f"Attention: {_format_symbol_list(errors)}")
        return "\n".join(lines)

    @staticmethod
    def _state_label(state: str | None) -> str:
        labels = {
            SetupState.IDLE.value: "Standby",
            SetupState.CONTEXT_FOUND.value: "Tracking",
            SetupState.ARMED.value: "Locked Target",
            SetupState.WAITING_MSS.value: "Tracking MSS",
            SetupState.CONFIRMED.value: "Locked Target",
            SetupState.COOLDOWN.value: "Cooldown",
            SetupState.REJECTED.value: "Invalid / No Edge",
            SetupState.ERROR.value: "Attention",
        }
        return labels.get(str(state or "").lower(), str(state or "-"))
