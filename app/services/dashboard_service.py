"""Agregação do dashboard por fase e veredito (RF-08, RF-09, RF-12 a RF-18)."""

from collections import Counter, defaultdict
from collections.abc import Sequence

from app.models import (
    INVALID_LABEL,
    Dashboard,
    Phase,
    PhaseSummary,
    Report,
    VerdictCount,
)
from app.repositories import RepoRepository, ReportRepository


class DashboardService:
    """Conta features por fase e veredito a partir dos relatórios armazenados."""

    def __init__(self, repos: RepoRepository, reports: ReportRepository) -> None:
        self._repos = repos
        self._reports = reports

    def build(self, repository_ids: Sequence[int] | None = None) -> Dashboard:
        """Monta o dashboard; sem `repository_ids`, agrega todos os repositórios."""
        known = {repo.id: repo for repo in self._repos.list()}
        wanted = known if repository_ids is None else repository_ids
        ids = sorted({repo_id for repo_id in wanted if repo_id in known})
        reports = self._reports.list(ids) if ids else []

        features: dict[tuple[int, Phase, str], list[Report]] = defaultdict(list)
        for report in reports:
            features[(report.repository_id, report.phase, report.feature)].append(report)

        spelling: dict[str, str] = {}
        counts: dict[Phase, Counter[str]] = {phase: Counter() for phase in Phase}
        for (_, phase, _), group in features.items():
            valid = [report for report in group if report.valid]
            if valid:
                latest = max(valid, key=lambda report: report.generated)
                label = spelling.setdefault(latest.verdict_key, latest.verdict)
            else:
                label = INVALID_LABEL
            counts[phase][label] += 1

        phases = [
            PhaseSummary(
                phase=phase,
                total=sum(counts[phase].values()),
                verdicts=[VerdictCount(verdict=v, count=n) for v, n in counts[phase].items()],
            )
            for phase in Phase
        ]
        collected = [known[i].last_collected_at for i in ids if known[i].last_collected_at]
        return Dashboard(
            phases=phases,
            repository_ids=ids,
            last_collected_at=max(collected, default=None),
        )
