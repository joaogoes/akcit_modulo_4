"""Evolução das features por veredito ao longo do tempo (RF-20).

Usa apenas os relatórios já armazenados: nenhuma chamada ao GitHub.
"""

from bisect import bisect_right
from collections import defaultdict
from collections.abc import Sequence
from datetime import date, timedelta

from app.models import Phase, Report, Trend, TrendSeries
from app.repositories import RepoRepository, ReportRepository
from app.services.selection import resolve_repository_ids
from app.services.verdicts import VerdictLabels

STEP = timedelta(days=7)

# Histórico de uma feature: datas dos relatórios válidos e os próprios relatórios, em ordem.
_Timeline = tuple[list[date], list[Report]]


class TrendService:
    """Reconstrói, a cada data, o veredito vigente de cada feature."""

    def __init__(self, repos: RepoRepository, reports: ReportRepository) -> None:
        self._repos = repos
        self._reports = reports

    def build(
        self,
        repository_ids: Sequence[int] | None = None,
        phase: Phase = Phase.TESTS,
        start: date | None = None,
        end: date | None = None,
    ) -> Trend:
        """Pontos semanais do primeiro ao último relatório válido da fase.

        `start` e `end` fixam o eixo de datas; com os mesmos valores, repositórios
        diferentes recebem exatamente as mesmas datas e podem ser comparados.

        Em cada data, vale o relatório válido mais recente de cada feature até
        aquele dia; features sem relatório válido ainda não entram na contagem.
        """
        _, ids = resolve_repository_ids(self._repos, repository_ids)
        reports = self._reports.list(ids, phase) if ids else []
        timelines = self._timelines(reports)
        if not timelines:
            return Trend(phase=phase, repository_ids=ids, dates=[], series=[])

        days = [day for stamps, _ in timelines for day in stamps]
        points = self._points(*self._bounds(days, start, end))
        return Trend(
            phase=phase, repository_ids=ids, dates=points, series=self._series(timelines, points)
        )

    @staticmethod
    def _timelines(reports: list[Report]) -> list[_Timeline]:
        history: dict[tuple[int, str], list[Report]] = defaultdict(list)
        for report in reports:
            if report.valid:
                history[(report.repository_id, report.feature)].append(report)
        timelines: list[_Timeline] = []
        for items in history.values():
            items.sort(key=lambda report: report.generated)
            timelines.append(([report.generated.date() for report in items], items))
        return timelines

    @staticmethod
    def _series(timelines: list[_Timeline], points: list[date]) -> list[TrendSeries]:
        labels = VerdictLabels()
        counts: dict[str, list[int]] = defaultdict(lambda: [0] * len(points))
        for stamps, items in timelines:
            for index, point in enumerate(points):
                position = bisect_right(stamps, point)
                if position:
                    counts[labels.of(items[position - 1])][index] += 1
        return [
            TrendSeries(verdict=label, counts=counts[label])
            for label in sorted(counts, key=str.casefold)
        ]

    @staticmethod
    def _bounds(days: list[date], start: date | None, end: date | None) -> tuple[date, date]:
        """Primeira e última data do eixo; os limites informados prevalecem sobre os dos relatórios."""
        first, last = start or min(days), end or max(days)
        if end is None:
            last = max(last, first)
        elif start is None:
            first = min(first, last)
        return first, last

    @staticmethod
    def _points(first: date, last: date) -> list[date]:
        points = [first + STEP * k for k in range((last - first) // STEP + 1)]
        if points[-1] != last:
            points.append(last)
        return points
