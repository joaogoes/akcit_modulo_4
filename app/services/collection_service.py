"""Coleta dos relatórios de um repositório (RF-05 a RF-11)."""

import logging
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from app.github import GitHubClient, GitHubError, RateLimitError
from app.models import (
    CollectionError,
    CollectionRead,
    CollectionStatus,
    Phase,
    Report,
    RepositoryRead,
)
from app.repositories import RepoRepository, ReportRepository
from app.services.layout import match_report
from app.services.report_parser import parse_report

logger = logging.getLogger(__name__)

_Item = tuple[str, Phase, str]


class CollectionService:
    """Lê os relatórios no GitHub e substitui os dados do repositório de forma atômica."""

    def __init__(
        self,
        github: GitHubClient,
        repos: RepoRepository,
        reports: ReportRepository,
        max_workers: int = 8,
    ) -> None:
        self._github = github
        self._repos = repos
        self._reports = reports
        self._max_workers = max_workers

    def collect_many(
        self, repository_ids: Sequence[int] | None = None
    ) -> list[CollectionRead]:
        """Coleta os repositórios informados (ou todos); `NotFoundError` se algum não existir."""
        if repository_ids is None:
            ids = [repo.id for repo in self._repos.list()]
        else:
            ids = list(dict.fromkeys(repository_ids))
            for repository_id in ids:
                self._repos.get(repository_id)
        return [self.collect(repository_id) for repository_id in ids]

    def collect(self, repository_id: int) -> CollectionRead:
        """Coleta um repositório. Em falha, os dados anteriores são preservados."""
        repo = self._repos.get(repository_id)
        started = datetime.now(UTC)
        clock = time.perf_counter()
        try:
            ref = repo.branch or self._github.get_default_branch(repo.full_name)
            items = self._discover(repo, ref)
            reports, errors = self._read_all(repo, ref, items)
            self._reports.replace_for_repository(repo.id, reports)
        except GitHubError as exc:
            return self._finish(repo, started, clock, CollectionStatus.FAILED, 0,
                                [CollectionError(message=str(exc))])
        except Exception as exc:  # falha de persistência: nada foi alterado
            logger.exception("Falha ao gravar a coleta de %s", repo.full_name)
            return self._finish(repo, started, clock, CollectionStatus.FAILED, 0,
                                [CollectionError(message=f"Erro ao gravar os dados: {exc}")])
        return self._finish(repo, started, clock, CollectionStatus.SUCCESS, len(items), errors)

    def _discover(self, repo: RepositoryRead, ref: str) -> list[_Item]:
        items: list[_Item] = []
        for path in self._github.list_files(repo.full_name, ref):
            if match := match_report(path):
                items.append((path, *match))
        return items

    def _read_all(
        self, repo: RepositoryRead, ref: str, items: list[_Item]
    ) -> tuple[list[Report], list[CollectionError]]:
        errors: list[CollectionError] = []

        def read(item: _Item) -> Report:
            path, phase, feature = item
            try:
                parsed = parse_report(self._github.get_file(repo.full_name, path, ref))
            except RateLimitError:
                raise
            except GitHubError as exc:
                errors.append(CollectionError(path=path, message=str(exc)))
                return Report(repository_id=repo.id, phase=phase, feature=feature, path=path)
            if parsed.generated is None or parsed.verdict is None:
                errors.append(CollectionError(
                    path=path, message="Relatório sem `generated` ou `verdict` legível."
                ))
            return Report(
                repository_id=repo.id, phase=phase, feature=feature, path=path,
                generated=parsed.generated, verdict=parsed.verdict,
            )

        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            return list(pool.map(read, items)), errors

    def _finish(
        self,
        repo: RepositoryRead,
        started: datetime,
        clock: float,
        status: CollectionStatus,
        files_read: int,
        errors: list[CollectionError],
    ) -> CollectionRead:
        finished = datetime.now(UTC)
        self._repos.record_collection(repo.id, status, finished)
        logger.info(
            "coleta repo=%s status=%s arquivos=%d erros=%d duracao=%.2fs",
            repo.full_name, status.value, files_read, len(errors), time.perf_counter() - clock,
        )
        return CollectionRead(
            repository_id=repo.id, status=status, started_at=started,
            finished_at=finished, files_read=files_read, errors=errors,
        )
