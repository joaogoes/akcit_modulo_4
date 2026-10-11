"""Evolução das features por veredito ao longo do tempo (RF-20).

Usa apenas os relatórios já armazenados: nenhuma chamada ao GitHub.
"""

from bisect import bisect_right
from collections import defaultdict
from collections.abc import Sequence
from datetime import date, timedelta

from app.models import Phase, Report, Trend, TrendSeries
from app.repositories import RepoRepository, ReportRepository

STEP = timedelta(days=7)


class TrendService:
    """Reconstrói, a cada data, o veredito vigente de cada feature."""

    def __init__(self, repos: RepoRepository, reports: ReportRepository) -> None:
        self._repos = repos
        self._reports = reports

    def build(
        self, repository_ids: Sequence[int] | None = None, phase: Phase = Phase.TESTS
    ) -> Trend:
        """Pontos semanais do primeiro ao último relatório válido da fase.

        Em cada data, vale o relatório válido mais recente de cada feature até
        aquele dia; features sem relatório válido ainda não entram na contagem.
        """
        known = {repo.id for repo in self._repos.list()}
        wanted = known if repository_ids is None else repository_ids
        ids = sorted({repo_id for repo_id in wanted if repo_id in known})
        reports = self._reports.list(ids, phase) if ids else []

        history: dict[tuple[int, str], list[Report]] = defaultdict(list)
        for report in reports:
            if report.valid:
                history[(report.repository_id, report.feature)].append(report)
        if not history:
            return Trend(phase=phase, repository_ids=ids, dates=[], series=[])

        timelines = []
        for items in history.values():
            items.sort(key=lambda report: report.generated)
            timelines.append(([report.generated.date() for report in items], items))
        days = [day for stamps, _ in timelines for day in stamps]
        points = self._points(min(days), max(days))

        spelling: dict[str, str] = {}
        counts: dict[str, list[int]] = defaultdict(lambda: [0] * len(points))
        for stamps, items in timelines:
            for index, point in enumerate(points):
                position = bisect_right(stamps, point)
                if position:
                    latest = items[position - 1]
                    label = spelling.setdefault(latest.verdict_key, latest.verdict)
                    counts[label][index] += 1
        series = [
            TrendSeries(verdict=label, counts=counts[label])
            for label in sorted(counts, key=str.casefold)
        ]
        return Trend(phase=phase, repository_ids=ids, dates=points, series=series)

    @staticmethod
    def _points(first: date, last: date) -> list[date]:
        points = [first + STEP * k for k in range((last - first) // STEP + 1)]
        if points[-1] != last:
            points.append(last)
        return points
