from __future__ import annotations

import ctypes
import os
from pathlib import Path


def _windows_process_creation_time(pid: int) -> int | None:
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return None
    try:
        creation_time = ctypes.c_ulonglong()
        exit_time = ctypes.c_ulonglong()
        kernel_time = ctypes.c_ulonglong()
        user_time = ctypes.c_ulonglong()
        ok = ctypes.windll.kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation_time),
            ctypes.byref(exit_time),
            ctypes.byref(kernel_time),
            ctypes.byref(user_time),
        )
        if not ok:
            return None
        return int(creation_time.value)
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        return _windows_process_creation_time(pid) is not None
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


class ProcessFileLock:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._handle: int | None = None
        self._identity = self._current_identity()

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            handle = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
        except FileExistsError:
            existing_identity = self._read_identity()
            if existing_identity and self._identity_matches(existing_identity):
                return False
            try:
                self.path.unlink(missing_ok=True)
            except Exception:
                return False
            try:
                handle = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            except FileExistsError:
                return False

        os.write(handle, self._identity.encode("ascii", "ignore"))
        self._handle = handle
        return True

    def release(self) -> None:
        handle = self._handle
        self._handle = None
        if handle is not None:
            try:
                os.close(handle)
            except OSError:
                pass
        try:
            if self.path.exists() and self._read_identity() == self._identity:
                self.path.unlink(missing_ok=True)
        except Exception:
            pass

    def _read_identity(self) -> str:
        try:
            return self.path.read_text(encoding="utf-8").strip()
        except Exception:
            return ""

    def _current_identity(self) -> str:
        pid = os.getpid()
        if os.name == "nt":
            created = _windows_process_creation_time(pid)
            if created is not None:
                return f"{pid}|{created}"
        return str(pid)

    @staticmethod
    def _parse_identity(identity: str) -> tuple[int, int | None]:
        text = str(identity or "").strip()
        if not text:
            return 0, None
        if "|" in text:
            pid_raw, created_raw = text.split("|", 1)
            try:
                return int(pid_raw or "0"), int(created_raw or "0")
            except ValueError:
                return 0, None
        try:
            return int(text), None
        except ValueError:
            return 0, None

    def _identity_matches(self, identity: str) -> bool:
        pid, recorded_created = self._parse_identity(identity)
        if pid <= 0:
            return False
        if os.name == "nt":
            live_created = _windows_process_creation_time(pid)
            if live_created is None:
                return False
            if recorded_created is None:
                return True
            return live_created == recorded_created
        return pid_exists(pid)
