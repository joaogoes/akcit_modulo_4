"""Erros de acesso aos provedores de repositórios (GitHub e Azure DevOps)."""

from datetime import datetime


class SourceError(Exception):
    """Falha ao consultar a API de um provedor de repositórios."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


GitHubError = SourceError  # nome anterior, mantido por compatibilidade


class RateLimitError(SourceError):
    """Limite de requisições da API atingido (RNF-05)."""

    def __init__(self, reset_at: datetime | None = None, service: str = "GitHub") -> None:
        when = f" Tente novamente após {reset_at:%d/%m/%Y %H:%M} UTC." if reset_at else ""
        super().__init__(f"Limite de requisições do {service} atingido.{when}", 403)
        self.reset_at = reset_at
