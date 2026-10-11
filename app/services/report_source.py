"""Descoberta e leitura dos relatórios de um repositório no GitHub (RF-05 a RF-07)."""

from concurrent.futures import ThreadPoolExecutor

from app.github import GitHubClient, GitHubError, RateLimitError
from app.models import CollectionError, Phase, Report, RepositoryRead
from app.services.layout import match_report
from app.services.report_parser import parse_report

ReportFile = tuple[str, Phase, str]  # caminho, fase, feature


class ReportSource:
    """Encontra os arquivos de relatório e os lê em paralelo, sem tocar no banco."""

    def __init__(self, github: GitHubClient, max_workers: int = 8) -> None:
        self._github = github
        self._max_workers = max_workers

    def find(self, repo: RepositoryRead, ref: str) -> list[ReportFile]:
        """Arquivos da árvore em `ref` que são relatórios de alguma fase."""
        files: list[ReportFile] = []
        for path in self._github.list_files(repo.full_name, ref):
            if match := match_report(path):
                files.append((path, *match))
        return files

    def read_all(
        self, repo: RepositoryRead, ref: str, files: list[ReportFile]
    ) -> tuple[list[Report], list[CollectionError]]:
        """Relatórios interpretados e os problemas encontrados.

        Arquivo ilegível vira relatório inválido; `RateLimitError` interrompe tudo.
        """
        errors: list[CollectionError] = []

        def read(item: ReportFile) -> Report:
            path, phase, feature = item
            base = {"repository_id": repo.id, "phase": phase, "feature": feature, "path": path}
            try:
                parsed = parse_report(self._github.get_file(repo.full_name, path, ref))
            except RateLimitError:
                raise
            except GitHubError as exc:
                errors.append(CollectionError(path=path, message=str(exc)))
                return Report(**base)
            if parsed.generated is None or parsed.verdict is None:
                errors.append(CollectionError(
                    path=path, message="Relatório sem `generated` ou `verdict` legível."
                ))
            return Report(**base, generated=parsed.generated, verdict=parsed.verdict)

        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            return list(pool.map(read, files)), errors
