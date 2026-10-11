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
        last_commit_sha=row["last_commit_sha"],
    )


def _not_found(repository_id: int) -> NotFoundError:
    return NotFoundError(f"Repositório {repository_id} não encontrado.")


def _require_changed(cursor: sqlite3.Cursor, repository_id: int) -> None:
    if cursor.rowcount == 0:
        raise _not_found(repository_id)


class RepoRepository:
    """CRUD de repositórios cadastrados."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def create(self, data: RepositoryCreate) -> RepositoryRead:
        """Cadastra um repositório; falha se `full_name` e branch já existirem."""
        try:
            cursor = self._db.execute(
                "INSERT INTO repositories (full_name, branch, created_at) VALUES (?, ?, ?)",
                (data.full_name, data.branch, datetime.now(UTC).isoformat()),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateRepositoryError(data.full_name, data.branch) from exc
        return self.get(cursor.lastrowid)

    def get(self, repository_id: int) -> RepositoryRead:
        """Busca por id; levanta `NotFoundError` se não existir."""
        row = self._db.fetch_one("SELECT * FROM repositories WHERE id = ?", (repository_id,))
        if row is None:
            raise _not_found(repository_id)
        return _to_model(row)

    def get_by_full_name(
        self, full_name: str, branch: str | None = None
    ) -> RepositoryRead | None:
        """Busca por `owner/repo` e branch, sem diferenciar maiúsculas e minúsculas."""
        row = self._db.fetch_one(
            "SELECT * FROM repositories WHERE full_name = ? AND COALESCE(branch, '') = ?",
            (full_name, branch or ""),
        )
        return _to_model(row) if row else None

    def list(self) -> list[RepositoryRead]:
        """Lista todos os repositórios, em ordem de cadastro."""
        return [_to_model(row) for row in self._db.fetch_all("SELECT * FROM repositories ORDER BY id")]

    def update_branch(self, repository_id: int, branch: str | None) -> RepositoryRead:
        """Altera a branch lida; `None` volta à branch padrão."""
        cursor = self._db.execute(
            "UPDATE repositories SET branch = ? WHERE id = ?", (branch, repository_id)
        )
        _require_changed(cursor, repository_id)
        return self.get(repository_id)

    def record_collection(
        self,
        repository_id: int,
        status: CollectionStatus,
        collected_at: datetime | None = None,
        commit_sha: str | None = None,
    ) -> None:
        """Registra data/hora, status e commit da última coleta (RF-11).

        Sem `commit_sha` (coleta que falhou), o último commit coletado é mantido.
        """
        cursor = self._db.execute(
            "UPDATE repositories"
            " SET last_collected_at = ?, last_collection_status = ?,"
            " last_commit_sha = COALESCE(?, last_commit_sha)"
            " WHERE id = ?",
            ((collected_at or datetime.now(UTC)).isoformat(), status.value, commit_sha, repository_id),
        )
        _require_changed(cursor, repository_id)

    def delete(self, repository_id: int) -> bool:
        """Remove o repositório e seus relatórios; devolve se existia."""
        return self._db.execute("DELETE FROM repositories WHERE id = ?", (repository_id,)).rowcount > 0
