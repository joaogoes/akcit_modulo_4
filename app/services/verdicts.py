"""Regras compartilhadas sobre vereditos dos relatórios (RF-08, RF-18)."""

from collections.abc import Iterable

from app.models import Report


APPROVED_LABEL = "Aprovado"
# Vereditos que significam aprovação e são sempre exibidos como "Aprovado" (RF-18).
_APPROVED_ALIASES = frozenset({"aprovado", "sucesso", "success", "approved", "passed", "ok"})


class VerdictLabels:
    """Rótulo exibido de cada veredito (RF-18).

    Aprovado, Sucesso, Success, Approved, Passed e OK viram "Aprovado". Os demais mantêm a primeira
    grafia vista, sem diferenciar maiúsculas.
    """

    def __init__(self) -> None:
        self._spelling: dict[str, str] = {}

    def of(self, report: Report) -> str:
        """Rótulo do veredito de um relatório válido."""
        if report.verdict_key in _APPROVED_ALIASES:
            return APPROVED_LABEL
        return self._spelling.setdefault(report.verdict_key, report.verdict)


def latest_valid(reports: Iterable[Report]) -> Report | None:
    """Relatório válido mais recente (RF-08), ou `None` se nenhum for válido."""
    valid = [report for report in reports if report.valid]
    return max(valid, key=lambda report: report.generated) if valid else None
