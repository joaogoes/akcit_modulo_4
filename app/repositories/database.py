"""Conexão SQLite, esquema e transações."""

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager

SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS repositories (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name              TEXT NOT NULL COLLATE NOCASE,
    branch                 TEXT,
    created_at             TEXT NOT NULL,
    last_collected_at      TEXT,
    last_collection_status TEXT,
    last_commit_sha        TEXT
);

-- Um repositório pode ser cadastrado uma vez por branch.
CREATE UNIQUE INDEX IF NOT EXISTS ux_repositories_name_branch
    ON repositories (full_name COLLATE NOCASE, COALESCE(branch, ''));

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

    def init_schema(self) -> int:
        """Cria ou atualiza o esquema e devolve o `user_version` anterior.

        `0` indica banco novo ou criado por versão anterior da aplicação.
        """
        with self._lock:
            previous = self._conn.execute("PRAGMA user_version").fetchone()[0]
            if previous < SCHEMA_VERSION:
                self._drop_unique_full_name()
                self._add_missing_columns()
            with self.transaction() as conn:
                for statement in SCHEMA.split(";"):
                    if statement.strip():
                        conn.execute(statement)
            self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        return previous

    def _add_missing_columns(self) -> None:
        """Acrescenta colunas criadas depois da primeira versão do esquema."""
        columns = {row["name"] for row in self._conn.execute("PRAGMA table_info(repositories)")}
        if columns and "last_commit_sha" not in columns:
            self._conn.execute("ALTER TABLE repositories ADD COLUMN last_commit_sha TEXT")

    def _drop_unique_full_name(self) -> None:
        """Recria `repositories` sem a restrição `UNIQUE(full_name)` da versão 0."""
        indexes = self._conn.execute("PRAGMA index_list(repositories)").fetchall()
        if not any(index["origin"] == "u" for index in indexes):
            return
        columns = (
            "id, full_name, branch, created_at, last_collected_at, last_collection_status"
        )
        new_table = SCHEMA.split(";")[0].replace(
            "IF NOT EXISTS repositories", "repositories_new"
        )
        self._conn.execute("PRAGMA foreign_keys = OFF")
        try:
            self._conn.execute("BEGIN")
            self._conn.execute(new_table)
            self._conn.execute(
                f"INSERT INTO repositories_new ({columns}) SELECT {columns} FROM repositories"
            )
            self._conn.execute("DROP TABLE repositories")
            self._conn.execute("ALTER TABLE repositories_new RENAME TO repositories")
            self._conn.execute("COMMIT")
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        finally:
            self._conn.execute("PRAGMA foreign_keys = ON")

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
