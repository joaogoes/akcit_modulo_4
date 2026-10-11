"""Agregação do dashboard por fase e veredito (RF-08, RF-09, RF-12 a RF-18)."""

from collections import Counter, defaultdict
from collections.abc import Sequence
from datetime import datetime

from app.models import (
    INVALID_LABEL,
    Dashboard,
    Phase,
    PhaseSummary,
    Report,
    RepositoryRead,
    VerdictCount,
)
from app.repositories import RepoRepository, ReportRepository
from app.services.selection import resolve_repository_ids
from app.services.verdicts import VerdictLabels, latest_valid


class DashboardService:
    """Conta features por fase e veredito a partir dos relatórios armazenados."""

    def __init__(self, repos: RepoRepository, reports: ReportRepository) -> None:
        self._repos = repos
        self._reports = reports

    def build(self, repository_ids: Sequence[int] | None = None) -> Dashboard:
        """Monta o dashboard; sem `repository_ids`, agrega todos os repositórios."""
        known, ids = resolve_repository_ids(self._repos, repository_ids)
        reports = self._reports.list(ids) if ids else []
        counts = self._count_features(reports)
        return Dashboard(
            phases=[self._summary(phase, counts[phase]) for phase in Phase],
            repository_ids=ids,
            last_collected_at=self._last_collected(known, ids),
        )

    @staticmethod
    def _count_features(reports: list[Report]) -> dict[Phase, Counter[str]]:
        """Uma contagem por (repositório, feature, fase), com o veredito vigente de cada uma."""
        features: dict[tuple[int, Phase, str], list[Report]] = defaultdict(list)
        for report in reports:
            features[(report.repository_id, report.phase, report.feature)].append(report)

        labels = VerdictLabels()
        counts: dict[Phase, Counter[str]] = {phase: Counter() for phase in Phase}
        for (_, phase, _), group in features.items():
            latest = latest_valid(group)
            counts[phase][labels.of(latest) if latest else INVALID_LABEL] += 1
        return counts

    @staticmethod
    def _summary(phase: Phase, counter: Counter[str]) -> PhaseSummary:
        return PhaseSummary(
            phase=phase,
            total=sum(counter.values()),
            verdicts=[VerdictCount(verdict=verdict, count=count) for verdict, count in counter.items()],
        )

    @staticmethod
    def _last_collected(known: dict[int, RepositoryRead], ids: list[int]) -> datetime | None:
        collected = [known[i].last_collected_at for i in ids if known[i].last_collected_at]
        return max(collected, default=None)
