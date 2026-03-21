import sqlite3
import threading
from pathlib import Path

from core.paths import DATABASE_FILE, SCHEMA_FILE, ensure_runtime_layout


class SQLiteStore:
    def __init__(self, database_file: Path | None = None):
        ensure_runtime_layout()
        self.database_file = Path(database_file or DATABASE_FILE)
        self.database_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(self.database_file, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._initialize_schema()

    def _initialize_schema(self):
        schema = SCHEMA_FILE.read_text(encoding="utf-8")
        with self._lock:
            self._connection.executescript(schema)
            self._connection.commit()

    def execute(self, sql: str, params: tuple = ()):
        with self._lock:
            cursor = self._connection.execute(sql, params)
            self._connection.commit()
            return cursor

    def executemany(self, sql: str, params: list[tuple]):
        with self._lock:
            cursor = self._connection.executemany(sql, params)
            self._connection.commit()
            return cursor

    def fetch_all(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            cursor = self._connection.execute(sql, params)
            return cursor.fetchall()

    def fetch_one(self, sql: str, params: tuple = ()):
        with self._lock:
            cursor = self._connection.execute(sql, params)
            return cursor.fetchone()

    def close(self):
        with self._lock:
            self._connection.close()
