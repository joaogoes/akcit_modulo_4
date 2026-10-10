"""Persistência dos repositórios GitHub cadastrados (RF-01 a RF-04)."""

import sqlite3
from datetime import UTC, datetime

from app.models import CollectionStatus, RepositoryCreate, RepositoryRead
from app.repositories.database import Database
from app.repositories.errors import DuplicateRepositoryError, NotFoundError


def _to_model(row: sqlite3.Row) -> RepositoryRead:
    return RepositoryRead(
        id=row["id"],
        full_name=row["full_name"],
        branch=row["branch"],
        created_at=row["created_at"],
        last_collected_at=row["last_collected_at"],
        last_collection_status=row["last_collection_status"],
    )


class RepoRepository:
    """CRUD de repositórios cadastrados."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def create(self, data: RepositoryCreate) -> RepositoryRead:
        """Cadastra um repositório; falha se `full_name` já existir."""
        now = datetime.now(UTC).isoformat()
        try:
            with self._db.transaction() as conn:
                cursor = conn.execute(
                    "INSERT INTO repositories (full_name, branch, created_at)"
                    " VALUES (?, ?, ?)",
                    (data.full_name, data.branch, now),
                )
        except sqlite3.IntegrityError as exc:
            raise DuplicateRepositoryError(data.full_name) from exc
        return self.get(cursor.lastrowid)

    def get(self, repository_id: int) -> RepositoryRead:
        """Busca por id; levanta `NotFoundError` se não existir."""
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM repositories WHERE id = ?", (repository_id,)
            ).fetchone()
        if row is None:
            raise NotFoundError(f"Repositório {repository_id} não encontrado.")
        return _to_model(row)

    def get_by_full_name(self, full_name: str) -> RepositoryRead | None:
        """Busca por `owner/repo`, sem diferenciar maiúsculas e minúsculas."""
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM repositories WHERE full_name = ?", (full_name,)
            ).fetchone()
        return _to_model(row) if row else None

    def list(self) -> list[RepositoryRead]:
        """Lista todos os repositórios, em ordem de cadastro."""
        with self._db.transaction() as conn:
            rows = conn.execute("SELECT * FROM repositories ORDER BY id").fetchall()
        return [_to_model(row) for row in rows]

    def update_branch(self, repository_id: int, branch: str | None) -> RepositoryRead:
        """Altera a branch lida; `None` volta à branch padrão."""
        with self._db.transaction() as conn:
            cursor = conn.execute(
                "UPDATE repositories SET branch = ? WHERE id = ?",
                (branch, repository_id),
            )
        if cursor.rowcount == 0:
            raise NotFoundError(f"Repositório {repository_id} não encontrado.")
        return self.get(repository_id)

    def record_collection(
        self,
        repository_id: int,
        status: CollectionStatus,
        collected_at: datetime | None = None,
    ) -> None:
        """Registra data/hora e status da última coleta (RF-11)."""
        at = (collected_at or datetime.now(UTC)).isoformat()
        with self._db.transaction() as conn:
            cursor = conn.execute(
                "UPDATE repositories"
                " SET last_collected_at = ?, last_collection_status = ?"
                " WHERE id = ?",
                (at, status.value, repository_id),
            )
        if cursor.rowcount == 0:
            raise NotFoundError(f"Repositório {repository_id} não encontrado.")

    def delete(self, repository_id: int) -> bool:
        """Remove o repositório e seus relatórios; devolve se existia."""
        with self._db.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM repositories WHERE id = ?", (repository_id,)
            )
        return cursor.rowcount > 0
