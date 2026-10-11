"""Esquema do banco e migrações entre versões."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.repositories.database import Database

SCHEMA_VERSION = 4

SCHEMA = """
CREATE TABLE IF NOT EXISTS repositories (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    provider               TEXT NOT NULL DEFAULT 'github',
    full_name              TEXT NOT NULL COLLATE NOCASE,
    branch                 TEXT,
    created_at             TEXT NOT NULL,
    last_collected_at      TEXT,
    last_collection_status TEXT,
    last_commit_sha        TEXT
);

-- Um repositório pode ser cadastrado uma vez por provedor e branch.
CREATE UNIQUE INDEX IF NOT EXISTS ux_repositories_provider_name_branch
    ON repositories (provider, full_name COLLATE NOCASE, COALESCE(branch, ''));

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

-- Um token por provedor, sempre cifrado (nunca em texto puro).
CREATE TABLE IF NOT EXISTS credentials (
    provider   TEXT PRIMARY KEY,
    secret     BLOB NOT NULL,
    updated_at TEXT NOT NULL
);
"""

_STATEMENTS = [statement.strip() for statement in SCHEMA.split(";") if statement.strip()]
_REPOSITORIES_DDL = _STATEMENTS[0]
_COLUMNS_V0 = "id, full_name, branch, created_at, last_collected_at, last_collection_status"


def upgrade(db: "Database") -> int:
    """Cria ou atualiza o esquema e devolve o `user_version` anterior.

    `0` indica banco novo ou criado por versão anterior da aplicação.
    """
    previous = db.fetch_one("PRAGMA user_version")[0]
    if previous < SCHEMA_VERSION:
        _drop_unique_full_name(db)
        _add_missing_columns(db)
        db.execute("DROP INDEX IF EXISTS ux_repositories_name_branch")  # substituído por um índice com o provedor
    with db.transaction() as conn:
        for statement in _STATEMENTS:
            conn.execute(statement)
    db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    return previous


def _add_missing_columns(db: "Database") -> None:
    """Acrescenta colunas criadas depois da primeira versão do esquema."""
    columns = {row["name"] for row in db.fetch_all("PRAGMA table_info(repositories)")}
    if not columns:
        return
    if "last_commit_sha" not in columns:
        db.execute("ALTER TABLE repositories ADD COLUMN last_commit_sha TEXT")
    if "provider" not in columns:
        db.execute("ALTER TABLE repositories ADD COLUMN provider TEXT NOT NULL DEFAULT 'github'")


def _drop_unique_full_name(db: "Database") -> None:
    """Recria `repositories` sem a restrição `UNIQUE(full_name)` da versão 0."""
    if not any(index["origin"] == "u" for index in db.fetch_all("PRAGMA index_list(repositories)")):
        return
    new_table = _REPOSITORIES_DDL.replace("IF NOT EXISTS repositories", "repositories_new")
    with db.foreign_keys_disabled(), db.transaction() as conn:
        conn.execute(new_table)
        conn.execute(
            f"INSERT INTO repositories_new ({_COLUMNS_V0}) SELECT {_COLUMNS_V0} FROM repositories"
        )
        conn.execute("DROP TABLE repositories")
        conn.execute("ALTER TABLE repositories_new RENAME TO repositories")
