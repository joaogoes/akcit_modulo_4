"""Conexão SQLite e transações."""

import sqlite3
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from app.repositories.schema import SCHEMA_VERSION, upgrade

__all__ = ["SCHEMA_VERSION", "Database"]


class Database:
    """Conexão única e thread-safe com SQLite; use `:memory:` em testes."""

    def __init__(self, path: str = "app.db") -> None:
        self._conn = sqlite3.connect(
            path, check_same_thread=False, isolation_level=None
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._lock = threading.RLock()

    def init_schema(self) -> int:
        """Cria ou atualiza o esquema e devolve o `user_version` anterior."""
        return upgrade(self)

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

    @contextmanager
    def foreign_keys_disabled(self) -> Iterator[None]:
        """Desliga as chaves estrangeiras no bloco; use fora de uma transação."""
        with self._lock:
            self._conn.execute("PRAGMA foreign_keys = OFF")
            try:
                yield
            finally:
                self._conn.execute("PRAGMA foreign_keys = ON")

    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        """Executa um comando em sua própria transação; o cursor traz `rowcount` e `lastrowid`."""
        with self.transaction() as conn:
            return conn.execute(sql, params)

    def fetch_one(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
        """Primeira linha do resultado, ou `None`."""
        with self.transaction() as conn:
            return conn.execute(sql, params).fetchone()

    def fetch_all(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        """Todas as linhas do resultado."""
        with self.transaction() as conn:
            return conn.execute(sql, params).fetchall()

    def close(self) -> None:
        """Fecha a conexão."""
        with self._lock:
            self._conn.close()
