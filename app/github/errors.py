"""Erros de acesso ao GitHub."""

from datetime import datetime


class GitHubError(Exception):
    """Falha ao consultar a API do GitHub."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class RateLimitError(GitHubError):
    """Limite de requisições da API atingido (RNF-05)."""

    def __init__(self, reset_at: datetime | None = None) -> None:
        when = f" Tente novamente após {reset_at:%d/%m/%Y %H:%M} UTC." if reset_at else ""
        super().__init__(f"Limite de requisições do GitHub atingido.{when}", 403)
        self.reset_at = reset_at
