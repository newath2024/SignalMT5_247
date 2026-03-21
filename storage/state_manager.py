import copy
import datetime as dt
import json
import threading
import time
from pathlib import Path
from typing import Any

from core.enums import SignalStage
from core.paths import (
    STATE_FILE,
    legacy_alert_cache_candidates,
    legacy_watch_cache_candidates,
)

from .database import SQLiteStore


def _json_safe(value: Any):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item"):
        return value.item()
    return value


def _now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


class StateManager:
    def __init__(self, sqlite_store: SQLiteStore, state_file: Path | None = None):
        self.sqlite = sqlite_store
        self.state_file = Path(state_file or STATE_FILE)
        self._lock = threading.RLock()
        self._state = self._load_state()

    def _default_state(self) -> dict[str, Any]:
        return {
            "version": 1,
            "active_watches": {},
            "cooldowns": {},
            "last_rejections": {},
        }

    def _load_state(self) -> dict[str, Any]:
        if self.state_file.exists():
            try:
                payload = json.loads(self.state_file.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    payload.setdefault("version", 1)
                    payload.setdefault("active_watches", {})
                    payload.setdefault("cooldowns", {})
                    payload.setdefault("last_rejections", {})
                    return payload
            except (OSError, json.JSONDecodeError):
                pass

        payload = self._default_state()
        self._migrate_legacy_state(payload)
        self._persist_state(payload)
        return payload

    def _migrate_legacy_state(self, payload: dict[str, Any]):
        for candidate in legacy_watch_cache_candidates():
            if not candidate.exists():
                continue
            try:
                legacy = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue

            watch_items = legacy.get("watches", []) if isinstance(legacy, dict) else legacy
            if not isinstance(watch_items, list):
                continue

            for item in watch_items:
                if not isinstance(item, dict):
                    continue
                watch_key = str(item.get("watch_key") or "")
                if not watch_key:
                    continue
                item = copy.deepcopy(item)
                item["status"] = "confirmed" if item.get("status") == "alerted" else "armed"
                item.setdefault("created_at", item.get("created_bar_time") or time.time())
                item.setdefault("updated_at", time.time())
                payload["active_watches"][watch_key] = _json_safe(item)
            break

        for candidate in legacy_alert_cache_candidates():
            if not candidate.exists():
                continue
            try:
                legacy = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue

            alert_map = legacy.get("alerts", {}) if isinstance(legacy, dict) else {}
            if not isinstance(alert_map, dict):
                continue

            for setup_key, sent_at in alert_map.items():
                try:
                    payload["cooldowns"][f"signal:{setup_key}"] = float(sent_at)
                except (TypeError, ValueError):
                    continue
            break

    def _persist_state(self, payload: dict[str, Any] | None = None):
        body = payload if payload is not None else self._state
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.state_file.with_suffix(".tmp")
        temp_path.write_text(json.dumps(_json_safe(body), ensure_ascii=True, indent=2), encoding="utf-8")
        temp_path.replace(self.state_file)

    def list_active_watches(self, symbol: str | None = None, statuses: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
        with self._lock:
            watches = list(self._state["active_watches"].values())
        if symbol is not None:
            watches = [item for item in watches if item.get("symbol") == symbol]
        if statuses is not None:
            watches = [item for item in watches if item.get("status") in statuses]
        watches.sort(
            key=lambda item: (
                float(item.get("updated_at") or 0.0),
                str(item.get("symbol", "")),
                str(item.get("timeframe", "")),
            ),
            reverse=True,
        )
        return [copy.deepcopy(item) for item in watches]

    def upsert_watch(self, watch: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        watch_key = str(watch["watch_key"])
        stored = copy.deepcopy(watch)
        now = time.time()
        with self._lock:
            existing = self._state["active_watches"].get(watch_key)
            stored["created_at"] = float(existing.get("created_at")) if existing else now
            stored["updated_at"] = now
            stored.setdefault("status", existing.get("status") if existing else "armed")
            stored["watch_key"] = watch_key
            if existing is not None:
                stored["last_confirmed_mss_index"] = existing.get("last_confirmed_mss_index")
            self._state["active_watches"][watch_key] = _json_safe(stored)
            self._persist_state()
        return existing is None, copy.deepcopy(stored)

    def remove_watch(self, watch_key: str, reason: str | None = None) -> dict[str, Any] | None:
        with self._lock:
            removed = self._state["active_watches"].pop(watch_key, None)
            if removed is None:
                return None
            self._persist_state()
        if reason:
            self.record_signal_event(
                stage="watch_removed",
                symbol=removed.get("symbol", "-"),
                timeframe=removed.get("timeframe", "-"),
                bias=removed.get("bias"),
                event_key=watch_key,
                status="removed",
                reason=reason,
                payload=removed,
            )
        return copy.deepcopy(removed)

    def mark_watch_confirmed(self, watch_key: str, mss_index: int, status: str = "confirmed", reason: str | None = None):
        with self._lock:
            watch = self._state["active_watches"].get(watch_key)
            if watch is None:
                return None
            watch["status"] = status
            watch["last_confirmed_mss_index"] = int(mss_index)
            watch["updated_at"] = time.time()
            if reason:
                watch["status_reason"] = reason
            self._persist_state()
            return copy.deepcopy(watch)

    def get_watch(self, watch_key: str) -> dict[str, Any] | None:
        with self._lock:
            watch = self._state["active_watches"].get(watch_key)
        return copy.deepcopy(watch) if watch is not None else None

    def record_signal_event(
        self,
        stage: str,
        symbol: str,
        timeframe: str,
        bias: str | None,
        event_key: str,
        status: str,
        reason: str | None = None,
        payload: dict[str, Any] | None = None,
    ):
        self.sqlite.execute(
            """
            INSERT INTO signal_events (
                created_at, symbol, timeframe, bias, stage, status, event_key, reason, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _now_iso(),
                symbol,
                timeframe,
                bias,
                stage,
                status,
                event_key,
                reason,
                json.dumps(_json_safe(payload or {}), ensure_ascii=True),
            ),
        )

    def has_signal_event(self, stage: str, event_key: str) -> bool:
        row = self.sqlite.fetch_one(
            """
            SELECT 1
            FROM signal_events
            WHERE stage = ? AND event_key = ?
            LIMIT 1
            """,
            (stage, event_key),
        )
        return row is not None

    def record_rejection(
        self,
        symbol: str,
        timeframe: str,
        bias: str | None,
        phase: str,
        reason: str,
        payload: dict[str, Any] | None = None,
    ):
        rejection = {
            "symbol": symbol,
            "timeframe": timeframe,
            "bias": bias,
            "phase": phase,
            "reason": reason,
            "payload": _json_safe(payload or {}),
            "created_at": _now_iso(),
        }
        with self._lock:
            previous = self._state["last_rejections"].get(symbol)
            self._state["last_rejections"][symbol] = rejection
            self._persist_state()

        if previous and all(
            previous.get(key) == rejection.get(key)
            for key in ("timeframe", "bias", "phase", "reason")
        ):
            return

        self.sqlite.execute(
            """
            INSERT INTO rejection_history (
                created_at, symbol, timeframe, bias, phase, reason, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rejection["created_at"],
                symbol,
                timeframe,
                bias,
                phase,
                reason,
                json.dumps(rejection["payload"], ensure_ascii=True),
            ),
        )

    def last_rejection_for_symbol(self, symbol: str) -> dict[str, Any] | None:
        with self._lock:
            rejection = self._state["last_rejections"].get(symbol)
        return copy.deepcopy(rejection) if rejection is not None else None

    def recent_rejections(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.sqlite.fetch_all(
            """
            SELECT created_at, symbol, timeframe, bias, phase, reason
            FROM rejection_history
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in rows]

    def can_emit(self, event_key: str, cooldown_sec: int) -> bool:
        return self.cooldown_remaining(event_key, cooldown_sec) <= 0

    def cooldown_remaining(self, event_key: str, cooldown_sec: int) -> int:
        with self._lock:
            last_sent = self._state["cooldowns"].get(event_key)
        if last_sent is None:
            return 0
        remaining = int(max(0, cooldown_sec - (time.time() - float(last_sent))))
        return remaining

    def record_alert_dispatch(
        self,
        symbol: str,
        timeframe: str,
        stage: str,
        channel: str,
        event_key: str,
        status: str,
        reason: str | None = None,
        payload: dict[str, Any] | None = None,
        mark_cooldown: bool = False,
    ):
        timestamp = time.time()
        self.sqlite.execute(
            """
            INSERT INTO alert_history (
                created_at, symbol, timeframe, stage, channel, event_key, status, reason, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _now_iso(),
                symbol,
                timeframe,
                stage,
                channel,
                event_key,
                status,
                reason,
                json.dumps(_json_safe(payload or {}), ensure_ascii=True),
            ),
        )
        if mark_cooldown:
            with self._lock:
                self._state["cooldowns"][event_key] = timestamp
                self._persist_state()

    def recent_alerts(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.sqlite.fetch_all(
            """
            SELECT created_at, symbol, timeframe, stage, channel, event_key, status, reason
            FROM alert_history
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in rows]

    def recent_signal_events(self, stage: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        if stage is None:
            rows = self.sqlite.fetch_all(
                """
                SELECT created_at, symbol, timeframe, bias, stage, status, event_key, reason
                FROM signal_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
        else:
            rows = self.sqlite.fetch_all(
                """
                SELECT created_at, symbol, timeframe, bias, stage, status, event_key, reason
                FROM signal_events
                WHERE stage = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (stage, limit),
            )
        return [dict(row) for row in rows]

    def confirmed_signals_today(self) -> int:
        row = self.sqlite.fetch_one(
            """
            SELECT COUNT(*) AS total
            FROM signal_events
            WHERE stage = ? AND date(created_at) = date('now', 'localtime')
            """,
            (SignalStage.CONFIRMED_SIGNAL.value,),
        )
        return int(row["total"]) if row else 0

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            payload = copy.deepcopy(self._state)
        return payload
