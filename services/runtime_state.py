from __future__ import annotations

from copy import deepcopy
import threading
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field


@dataclass
class RuntimeJob:
    job_id: str
    kind: str
    symbol: str | None
    requested_by: str
    status: str
    queued_at: float
    started_at: float | None = None
    completed_at: float | None = None
    summary: str | None = None
    error: str | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class RuntimeState:
    def __init__(self, symbols: list[str], history_limit: int = 100):
        self._lock = threading.RLock()
        self._symbol_states: dict[str, dict] = {symbol: {} for symbol in symbols}
        self._active_jobs: dict[str, RuntimeJob] = {}
        self._recent_jobs: deque[RuntimeJob] = deque(maxlen=history_limit)
        self._full_scan_job_id: str | None = None

    def seed_symbol_states(self, states: list[dict]):
        with self._lock:
            for state in states:
                symbol = str(state.get("symbol") or "").upper()
                if symbol:
                    self._symbol_states[symbol] = deepcopy(state)

    def update_symbol_state(self, payload: dict):
        symbol = str(payload.get("symbol") or "").upper()
        if not symbol:
            return
        with self._lock:
            self._symbol_states[symbol] = deepcopy(payload)

    def get_symbol_state(self, symbol: str) -> dict | None:
        with self._lock:
            payload = self._symbol_states.get(symbol)
            return deepcopy(payload) if payload else None

    def list_symbol_states(self, symbols: list[str] | None = None) -> list[dict]:
        with self._lock:
            ordered = symbols or list(self._symbol_states.keys())
            return [deepcopy(self._symbol_states[symbol]) for symbol in ordered if self._symbol_states.get(symbol)]

    def queue_job(self, kind: str, requested_by: str, symbol: str | None = None, metadata: dict | None = None) -> dict | None:
        with self._lock:
            if kind == "scan_all" and self._full_scan_job_id is not None:
                return None
            job = RuntimeJob(
                job_id=uuid.uuid4().hex[:12],
                kind=kind,
                symbol=symbol,
                requested_by=requested_by,
                status="queued",
                queued_at=time.time(),
                metadata=dict(metadata or {}),
            )
            self._active_jobs[job.job_id] = job
            if kind == "scan_all":
                self._full_scan_job_id = job.job_id
            return job.to_dict()

    def mark_job_started(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._active_jobs.get(job_id)
            if job is None:
                return None
            job.status = "running"
            job.started_at = time.time()
            return job.to_dict()

    def mark_job_completed(self, job_id: str, summary: str | None = None, error: str | None = None) -> dict | None:
        with self._lock:
            job = self._active_jobs.pop(job_id, None)
            if job is None:
                return None
            job.status = "failed" if error else "completed"
            job.completed_at = time.time()
            job.summary = summary
            job.error = error
            if self._full_scan_job_id == job.job_id:
                self._full_scan_job_id = None
            self._recent_jobs.append(job)
            return job.to_dict()

    def list_active_jobs(self) -> list[dict]:
        with self._lock:
            return [job.to_dict() for job in self._active_jobs.values()]

    def recent_jobs(self, limit: int = 20) -> list[dict]:
        with self._lock:
            jobs = list(self._recent_jobs)
        if limit >= len(jobs):
            return [job.to_dict() for job in jobs]
        return [job.to_dict() for job in jobs[-limit:]]

    def is_full_scan_active(self) -> bool:
        with self._lock:
            return self._full_scan_job_id is not None
