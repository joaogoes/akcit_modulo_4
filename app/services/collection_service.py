"""Coleta dos relatórios de um repositório (RF-05 a RF-11)."""

import logging
import time
from collections.abc import Sequence
from datetime import UTC, datetime

from app.github import GitHubClient, SourceError
from app.models import CollectionError, CollectionRead, CollectionStatus, Provider, RepositoryRead
from app.repositories import RepoRepository, ReportRepository
from app.services.report_source import ReportSource

logger = logging.getLogger(__name__)


class CollectionService:
    """Orquestra a coleta: confere o commit, lê os relatórios e substitui os dados de forma atômica."""

    def __init__(
        self,
        github: GitHubClient,
        repos: RepoRepository,
        reports: ReportRepository,
        max_workers: int = 8,
        azure: GitHubClient | None = None,
    ) -> None:
        self._repos = repos
        self._reports = reports
        clients = {Provider.GITHUB: github}
        if azure is not None:
            clients[Provider.AZURE_DEVOPS] = azure
        self._clients = clients
        self._sources = {provider: ReportSource(client, max_workers) for provider, client in clients.items()}

    def collect_many(
        self,
        repository_ids: Sequence[int] | None = None,
        only_if_changed: bool = False,
    ) -> list[CollectionRead]:
        """Coleta os repositórios informados (ou todos); `NotFoundError` se algum não existir."""
        if repository_ids is None:
            ids = [repo.id for repo in self._repos.list()]
        else:
            ids = list(dict.fromkeys(repository_ids))
            for repository_id in ids:
                self._repos.get(repository_id)
        return [self.collect(repository_id, only_if_changed) for repository_id in ids]

    def collect(self, repository_id: int, only_if_changed: bool = False) -> CollectionRead:
        """Coleta um repositório. Em falha, os dados anteriores são preservados.

        Com `only_if_changed`, não lê nada se o último commit do branch for o mesmo
        da última coleta bem-sucedida (resultado `unchanged`).
        """
        repo = self._repos.get(repository_id)
        started = datetime.now(UTC)
        clock = time.perf_counter()
        try:
            client, source = self._provider_access(repo)
            head = client.get_head_commit(repo.full_name, repo.branch or "HEAD")
            if only_if_changed and self._is_up_to_date(repo, head):
                return self._unchanged(repo, started, head)
            # Lê tudo pelo SHA, para que a coleta seja um retrato único do commit.
            files = source.find(repo, head)
            reports, errors = source.read_all(repo, head, files)
            self._reports.replace_for_repository(repo.id, reports)
        except SourceError as exc:
            return self._failed(repo, started, clock, str(exc))
        except Exception as exc:  # falha de persistência: nada foi alterado
            logger.exception("Falha ao gravar a coleta de %s", repo.full_name)
            return self._failed(repo, started, clock, f"Erro ao gravar os dados: {exc}")
        return self._finish(repo, started, clock, CollectionStatus.SUCCESS, len(files), errors, head)

    def _provider_access(self, repo: RepositoryRead) -> tuple[GitHubClient, ReportSource]:
        """Cliente e leitor do provedor do repositório."""
        if repo.provider not in self._clients:
            raise SourceError(f"O provedor {repo.provider.label} não está configurado.")
        return self._clients[repo.provider], self._sources[repo.provider]

    @staticmethod
    def _is_up_to_date(repo: RepositoryRead, head: str) -> bool:
        return head == repo.last_commit_sha and repo.last_collection_status == CollectionStatus.SUCCESS

    @staticmethod
    def _unchanged(repo: RepositoryRead, started: datetime, head: str) -> CollectionRead:
        return CollectionRead(
            repository_id=repo.id,
            status=CollectionStatus.UNCHANGED,
            started_at=started,
            finished_at=datetime.now(UTC),
            commit_sha=head,
        )

    def _failed(
        self, repo: RepositoryRead, started: datetime, clock: float, message: str
    ) -> CollectionRead:
        return self._finish(
            repo, started, clock, CollectionStatus.FAILED, 0, [CollectionError(message=message)], None
        )

    def _finish(
        self,
        repo: RepositoryRead,
        started: datetime,
        clock: float,
        status: CollectionStatus,
        files_read: int,
        errors: list[CollectionError],
        commit_sha: str | None,
    ) -> CollectionRead:
        """Registra o resultado no repositório, grava o log e monta a resposta."""
        finished = datetime.now(UTC)
        self._repos.record_collection(repo.id, status, finished, commit_sha)
        logger.info(
            "coleta repo=%s status=%s arquivos=%d erros=%d duracao=%.2fs",
            repo.full_name, status.value, files_read, len(errors), time.perf_counter() - clock,
        )
        return CollectionRead(
            repository_id=repo.id, status=status, started_at=started,
            finished_at=finished, commit_sha=commit_sha, files_read=files_read, errors=errors,
        )
