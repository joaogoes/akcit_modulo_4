"""Persistência dos relatórios coletados (RF-05 a RF-11)."""

import sqlite3
from collections.abc import Sequence

from app.models import Phase, Report
from app.repositories.database import Database

_DELETE_BY_REPOSITORY = "DELETE FROM reports WHERE repository_id = ?"
_INSERT = (
    "INSERT INTO reports (repository_id, phase, feature, path, generated, verdict)"
    " VALUES (?, ?, ?, ?, ?, ?)"
)


def _to_model(row: sqlite3.Row) -> Report:
    return Report(
        repository_id=row["repository_id"],
        phase=row["phase"],
        feature=row["feature"],
        path=row["path"],
        generated=row["generated"],
        verdict=row["verdict"],
    )


def _to_row(repository_id: int, report: Report) -> tuple:
    generated = report.generated.isoformat() if report.generated else None
    return (repository_id, report.phase.value, report.feature, report.path, generated, report.verdict)


def _filter(
    repository_ids: Sequence[int] | None, phase: Phase | None
) -> tuple[str, list[int | str]]:
    """Cláusula `WHERE` e parâmetros para os filtros informados."""
    clauses: list[str] = []
    params: list[int | str] = []
    if repository_ids is not None:
        clauses.append(f"repository_id IN ({', '.join('?' * len(repository_ids))})")
        params.extend(repository_ids)
    if phase is not None:
        clauses.append("phase = ?")
        params.append(phase.value)
    return (f" WHERE {' AND '.join(clauses)}" if clauses else ""), params


class ReportRepository:
    """Leitura e substituição atômica dos relatórios por repositório."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def replace_for_repository(
        self, repository_id: int, reports: Sequence[Report]
    ) -> None:
        """Troca todos os relatórios do repositório em uma única transação.

        Se qualquer inserção falhar, os dados anteriores são preservados.
        """
        with self._db.transaction() as conn:
            conn.execute(_DELETE_BY_REPOSITORY, (repository_id,))
            conn.executemany(_INSERT, [_to_row(repository_id, report) for report in reports])

    def list(
        self,
        repository_ids: Sequence[int] | None = None,
        phase: Phase | None = None,
    ) -> list[Report]:
        """Lista relatórios, filtrando por repositórios e/ou fase."""
        where, params = _filter(repository_ids, phase)
        rows = self._db.fetch_all(
            f"SELECT * FROM reports{where} ORDER BY repository_id, phase, feature, id", params
        )
        return [_to_model(row) for row in rows]

    def count(self, repository_id: int) -> int:
        """Total de relatórios armazenados do repositório."""
        row = self._db.fetch_one(
            "SELECT COUNT(*) AS n FROM reports WHERE repository_id = ?", (repository_id,)
        )
        return row["n"]

    def delete_for_repository(self, repository_id: int) -> int:
        """Remove os relatórios do repositório; devolve quantos foram removidos."""
        return self._db.execute(_DELETE_BY_REPOSITORY, (repository_id,)).rowcount
