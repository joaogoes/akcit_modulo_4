"""Erros de persistência."""


class NotFoundError(Exception):
    """Registro inexistente."""


class DuplicateRepositoryError(Exception):
    """Repositório já cadastrado para o mesmo branch."""

    def __init__(self, full_name: str, branch: str | None = None) -> None:
        label = f"{full_name} ({branch})" if branch else full_name
        super().__init__(label)
        self.full_name = full_name
        self.branch = branch
