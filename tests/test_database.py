"""Conexão, transações e migração do esquema SQLite."""

import sqlite3
import threading

import pytest

from app.repositories import Database
from app.repositories.database import SCHEMA_VERSION

LEGACY_V0 = """
    CREATE TABLE repositories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
        branch TEXT, created_at TEXT NOT NULL,
        last_collected_at TEXT, last_collection_status TEXT);
    CREATE TABLE reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
        phase TEXT NOT NULL, feature TEXT NOT NULL, path TEXT NOT NULL,
        generated TEXT, verdict TEXT);
    INSERT INTO repositories (full_name, created_at) VALUES ('acme/app', '2026-10-01T00:00:00+00:00');
    INSERT INTO reports (repository_id, phase, feature, path, generated, verdict)
        VALUES (1, 'code', 'f', 'p', '2026-10-01T00:00:00+00:00', 'Aprovado');
"""

LEGACY_V1 = """
    CREATE TABLE repositories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL COLLATE NOCASE, branch TEXT, created_at TEXT NOT NULL,
        last_collected_at TEXT, last_collection_status TEXT);
    CREATE UNIQUE INDEX ux_repositories_name_branch
        ON repositories (full_name COLLATE NOCASE, COALESCE(branch, ''));
    CREATE TABLE reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
        phase TEXT NOT NULL, feature TEXT NOT NULL, path TEXT NOT NULL,
        generated TEXT, verdict TEXT);
    INSERT INTO repositories (full_name, created_at) VALUES ('acme/app', '2026-10-01T00:00:00+00:00');
    PRAGMA user_version = 1;
"""


LEGACY_V2 = """
    CREATE TABLE repositories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL COLLATE NOCASE, branch TEXT, created_at TEXT NOT NULL,
        last_collected_at TEXT, last_collection_status TEXT, last_commit_sha TEXT);
    CREATE UNIQUE INDEX ux_repositories_name_branch
        ON repositories (full_name COLLATE NOCASE, COALESCE(branch, ''));
    CREATE TABLE reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
        phase TEXT NOT NULL, feature TEXT NOT NULL, path TEXT NOT NULL,
        generated TEXT, verdict TEXT);
    INSERT INTO repositories (full_name, created_at, last_commit_sha) VALUES ('acme/app', 'x', 'abc');
    PRAGMA user_version = 2;
"""


def insert_repo(conn: sqlite3.Connection, name: str, branch: str | None = None) -> None:
    conn.execute(
        "INSERT INTO repositories (full_name, branch, created_at) VALUES (?, ?, 'x')", (name, branch)
    )


def columns(db: Database, table: str) -> set[str]:
    with db.transaction() as conn:
        return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def build_legacy(path, script: str) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(script)
    conn.commit()
    conn.close()


class TestSchema:
    def test_first_call_reports_version_zero_and_later_calls_the_current_version(self):
        database = Database(":memory:")
        assert database.init_schema() == 0
        assert database.init_schema() == SCHEMA_VERSION

    def test_creates_both_tables_with_the_commit_column(self, db):
        assert "last_commit_sha" in columns(db, "repositories")
        assert {"repository_id", "phase", "feature", "path", "generated", "verdict"} <= columns(db, "reports")

    def test_same_name_is_unique_per_branch_ignoring_case(self, db):
        with db.transaction() as conn:
            insert_repo(conn, "acme/app", "dev")
            insert_repo(conn, "acme/app", "main")
            insert_repo(conn, "acme/app", None)
        with pytest.raises(sqlite3.IntegrityError), db.transaction() as conn:
            insert_repo(conn, "ACME/APP", "dev")
        with pytest.raises(sqlite3.IntegrityError), db.transaction() as conn:
            insert_repo(conn, "acme/app", None)

    def test_foreign_keys_are_enforced(self, db):
        with pytest.raises(sqlite3.IntegrityError), db.transaction() as conn:
            conn.execute(
                "INSERT INTO reports (repository_id, phase, feature, path) VALUES (99, 'code', 'f', 'p')"
            )


class TestTransaction:
    def count(self, db: Database) -> int:
        with db.transaction() as conn:
            return conn.execute("SELECT COUNT(*) FROM repositories").fetchone()[0]

    def test_commits_when_the_block_succeeds(self, db):
        with db.transaction() as conn:
            insert_repo(conn, "acme/app")
        assert self.count(db) == 1

    def test_rolls_back_when_the_block_raises(self, db):
        with pytest.raises(RuntimeError), db.transaction() as conn:
            insert_repo(conn, "acme/app")
            raise RuntimeError("falha")
        assert self.count(db) == 0

    def test_nested_blocks_share_the_outer_transaction(self, db):
        with pytest.raises(RuntimeError), db.transaction():
            with db.transaction() as conn:
                insert_repo(conn, "acme/app")
            raise RuntimeError("falha depois do bloco interno")
        assert self.count(db) == 0

    def test_connection_is_usable_from_several_threads(self, db):
        def work(index: int) -> None:
            with db.transaction() as conn:
                insert_repo(conn, f"acme/app{index}")

        threads = [threading.Thread(target=work, args=(i,)) for i in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert self.count(db) == 20

    def test_closed_database_rejects_queries(self):
        database = Database(":memory:")
        database.init_schema()
        database.close()
        with pytest.raises(sqlite3.ProgrammingError):
            with database.transaction() as conn:
                conn.execute("SELECT 1")


class TestMigration:
    def test_version_zero_database_keeps_data_and_allows_the_same_repo_in_two_branches(self, tmp_path):
        path = tmp_path / "v0.db"
        build_legacy(path, LEGACY_V0)

        database = Database(str(path))
        assert database.init_schema() == 0
        with database.transaction() as conn:
            assert conn.execute("SELECT full_name FROM repositories").fetchall()[0][0] == "acme/app"
            assert conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0] == 1  # não apagou em cascata
            insert_repo(conn, "acme/app", "dev")
        assert "last_commit_sha" in columns(database, "repositories")

    def test_version_one_database_gains_the_commit_column(self, tmp_path):
        path = tmp_path / "v1.db"
        build_legacy(path, LEGACY_V1)

        database = Database(str(path))
        assert database.init_schema() == 1
        assert "last_commit_sha" in columns(database, "repositories")

    def test_migration_is_idempotent(self, tmp_path):
        path = tmp_path / "v0.db"
        build_legacy(path, LEGACY_V0)
        database = Database(str(path))
        database.init_schema()
        assert database.init_schema() == SCHEMA_VERSION
        with database.transaction() as conn:
            assert conn.execute("SELECT COUNT(*) FROM repositories").fetchone()[0] == 1

    def test_failed_migration_rolls_back_and_keeps_foreign_keys_on(self, tmp_path):
        path = tmp_path / "broken.db"
        build_legacy(path, """
            CREATE TABLE repositories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                branch TEXT, created_at TEXT NOT NULL);
            INSERT INTO repositories (full_name, created_at) VALUES ('acme/app', 'x');
        """)  # falta `last_collected_at`: a cópia para a tabela nova falha

        database = Database(str(path))
        with pytest.raises(sqlite3.OperationalError):
            database.init_schema()
        with database.transaction() as conn:
            assert conn.execute("SELECT COUNT(*) FROM repositories").fetchone()[0] == 1
            assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert "repositories_new" not in tables

    def test_version_two_database_gains_the_provider_and_a_provider_aware_index(self, tmp_path):
        path = tmp_path / "v2.db"
        build_legacy(path, LEGACY_V2)

        database = Database(str(path))
        assert database.init_schema() == 2
        assert "provider" in columns(database, "repositories")
        with database.transaction() as conn:
            row = conn.execute("SELECT provider, last_commit_sha FROM repositories").fetchone()
            indexes = {r["name"] for r in conn.execute("PRAGMA index_list(repositories)")}
            conn.execute("INSERT INTO repositories (provider, full_name, created_at) VALUES ('azure_devops', 'acme/app', 'x')")
        assert (row["provider"], row["last_commit_sha"]) == ("github", "abc")  # dados e provedor padrão preservados
        assert "ux_repositories_provider_name_branch" in indexes
        assert "ux_repositories_name_branch" not in indexes

    def test_same_name_is_unique_only_within_a_provider(self, db):
        with db.transaction() as conn:
            conn.execute("INSERT INTO repositories (provider, full_name, created_at) VALUES ('github', 'a/b', 'x')")
            conn.execute("INSERT INTO repositories (provider, full_name, created_at) VALUES ('azure_devops', 'a/b', 'x')")
        with pytest.raises(sqlite3.IntegrityError), db.transaction() as conn:
            conn.execute("INSERT INTO repositories (provider, full_name, created_at) VALUES ('azure_devops', 'A/B', 'x')")

    def test_version_three_database_gains_the_credentials_table_and_keeps_data(self, tmp_path):
        path = tmp_path / "v3.db"
        build_legacy(path, LEGACY_V2.replace("full_name TEXT NOT NULL COLLATE NOCASE,", "provider TEXT NOT NULL DEFAULT 'github', full_name TEXT NOT NULL COLLATE NOCASE,")
                     .replace("ux_repositories_name_branch", "ux_repositories_provider_name_branch")
                     .replace("(full_name COLLATE NOCASE", "(provider, full_name COLLATE NOCASE")
                     .replace("user_version = 2", "user_version = 3"))

        database = Database(str(path))
        assert database.init_schema() == 3
        assert columns(database, "credentials") == {"provider", "secret", "updated_at"}
        with database.transaction() as conn:
            assert conn.execute("SELECT full_name FROM repositories").fetchone()[0] == "acme/app"
