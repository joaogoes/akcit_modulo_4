"""Cliente GitHub em memória, para testes."""

from app.github.errors import GitHubError


class InMemoryGitHubClient:
    """Implementa `GitHubClient` sobre um dicionário `repo -> {caminho: texto}`."""

    def __init__(
        self,
        repositories: dict[str, dict[str, str]] | None = None,
        default_branch: str = "main",
    ) -> None:
        self.repositories = repositories or {}
        self.default_branch = default_branch
        self.failing_paths: set[str] = set()
        self.fail_listing = False

    def get_default_branch(self, full_name: str) -> str:
        self._files(full_name)
        return self.default_branch

    def list_files(self, full_name: str, ref: str) -> list[str]:
        if self.fail_listing:
            raise GitHubError("Falha simulada ao listar a árvore.", 500)
        return list(self._files(full_name))

    def get_file(self, full_name: str, path: str, ref: str) -> str:
        if path in self.failing_paths:
            raise GitHubError(f"Falha simulada ao ler {path}.", 500)
        return self._files(full_name)[path]

    def _files(self, full_name: str) -> dict[str, str]:
        key = full_name.casefold()
        for name, files in self.repositories.items():
            if name.casefold() == key:
                return files
        raise GitHubError("Repositório não encontrado (ou sem permissão).", 404)
