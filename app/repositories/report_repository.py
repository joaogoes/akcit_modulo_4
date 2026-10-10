"""Persistência dos relatórios coletados (RF-05 a RF-11)."""

import sqlite3
from collections.abc import Sequence

from app.models import Phase, Report
from app.repositories.database import Database


def _to_model(row: sqlite3.Row) -> Report:
    return Report(
        repository_id=row["repository_id"],
        phase=row["phase"],
        feature=row["feature"],
        path=row["path"],
        generated=row["generated"],
        verdict=row["verdict"],
    )


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
            conn.execute(
                "DELETE FROM reports WHERE repository_id = ?", (repository_id,)
            )
            conn.executemany(
                "INSERT INTO reports"
                " (repository_id, phase, feature, path, generated, verdict)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        repository_id,
                        report.phase.value,
                        report.feature,
                        report.path,
                        report.generated.isoformat() if report.generated else None,
                        report.verdict,
                    )
                    for report in reports
                ],
            )

    def list(
        self,
        repository_ids: Sequence[int] | None = None,
        phase: Phase | None = None,
    ) -> list[Report]:
        """Lista relatórios, filtrando por repositórios e/ou fase."""
        clauses: list[str] = []
        params: list[int | str] = []
        if repository_ids is not None:
            marks = ", ".join("?" * len(repository_ids))
            clauses.append(f"repository_id IN ({marks})")
            params.extend(repository_ids)
        if phase is not None:
            clauses.append("phase = ?")
            params.append(phase.value)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._db.transaction() as conn:
            rows = conn.execute(
                f"SELECT * FROM reports{where}"
                " ORDER BY repository_id, phase, feature, id",
                params,
            ).fetchall()
        return [_to_model(row) for row in rows]

    def count(self, repository_id: int) -> int:
        """Total de relatórios armazenados do repositório."""
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM reports WHERE repository_id = ?",
                (repository_id,),
            ).fetchone()
        return row["n"]

    def delete_for_repository(self, repository_id: int) -> int:
        """Remove os relatórios do repositório; devolve quantos foram removidos."""
        with self._db.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM reports WHERE repository_id = ?", (repository_id,)
            )
        return cursor.rowcount
