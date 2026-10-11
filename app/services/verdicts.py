"""Regras compartilhadas sobre vereditos dos relatórios (RF-08, RF-18)."""

from collections.abc import Iterable

from app.models import Report


class VerdictLabels:
    """Guarda a primeira grafia vista de cada veredito, sem diferenciar maiúsculas (RF-18)."""

    def __init__(self) -> None:
        self._spelling: dict[str, str] = {}

    def of(self, report: Report) -> str:
        """Rótulo canônico do veredito de um relatório válido."""
        return self._spelling.setdefault(report.verdict_key, report.verdict)


def latest_valid(reports: Iterable[Report]) -> Report | None:
    """Relatório válido mais recente (RF-08), ou `None` se nenhum for válido."""
    valid = [report for report in reports if report.valid]
    return max(valid, key=lambda report: report.generated) if valid else None
