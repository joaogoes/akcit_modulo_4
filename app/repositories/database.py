"""Conexão SQLite, esquema e transações."""

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS repositories (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name              TEXT NOT NULL UNIQUE COLLATE NOCASE,
    branch                 TEXT,
    created_at             TEXT NOT NULL,
    last_collected_at      TEXT,
    last_collection_status TEXT
);

CREATE TABLE IF NOT EXISTS reports (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    phase         TEXT NOT NULL,
    feature       TEXT NOT NULL,
    path          TEXT NOT NULL,
    generated     TEXT,
    verdict       TEXT
);

CREATE INDEX IF NOT EXISTS ix_reports_repository_phase
    ON reports (repository_id, phase);
"""


class Database:
    """Conexão única e thread-safe com SQLite; use `:memory:` em testes."""

    def __init__(self, path: str = "app.db") -> None:
        self._conn = sqlite3.connect(
            path, check_same_thread=False, isolation_level=None
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._lock = threading.RLock()

    def init_schema(self) -> None:
        """Cria as tabelas, se ainda não existirem."""
        with self.transaction() as conn:
            for statement in SCHEMA.split(";"):
                if statement.strip():
                    conn.execute(statement)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Executa o bloco em uma transação: confirma no sucesso, reverte na exceção.

        Reentrante: blocos aninhados participam da transação mais externa.
        """
        with self._lock:
            if self._conn.in_transaction:
                yield self._conn
                return
            self._conn.execute("BEGIN")
            try:
                yield self._conn
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            self._conn.execute("COMMIT")

    def close(self) -> None:
        """Fecha a conexão."""
        with self._lock:
            self._conn.close()
