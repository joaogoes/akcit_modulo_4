"""Tokens de acesso por provedor: banco (cifrado) ou variável de ambiente (RF-22)."""

import os
from collections.abc import Mapping

from app.github import SourceError
from app.models import Provider, TokenSettings, TokenStatus
from app.protection import ProtectionError
from app.repositories import CredentialRepository

ENV_VARIABLES: dict[Provider, str] = {
    Provider.GITHUB: "GITHUB_TOKEN",
    Provider.AZURE_DEVOPS: "AZURE_DEVOPS_TOKEN",
}


class TokenService:
    """Resolve o token de cada provedor e gerencia os tokens salvos no banco."""

    def __init__(
        self, credentials: CredentialRepository, environ: Mapping[str, str] | None = None
    ) -> None:
        self._credentials = credentials
        self._environ = os.environ if environ is None else environ

    def resolve(self, provider: Provider) -> str | None:
        """Token do banco, se houver; senão o da variável de ambiente; senão `None`.

        Lido a cada requisição, então uma troca vale sem reiniciar a aplicação.
        """
        try:
            stored = self._credentials.get(provider)
        except ProtectionError as exc:
            raise SourceError(str(exc), 401) from exc
        return stored or self._environ.get(ENV_VARIABLES[provider]) or None

    def status(self) -> TokenSettings:
        """Situação de cada provedor, sem expor os valores."""
        return TokenSettings(
            secure_storage=self._credentials.secure_storage,
            tokens=[self._status_of(provider) for provider in Provider],
        )

    def save(self, provider: Provider, token: str) -> TokenStatus:
        """Cifra e grava o token do provedor; `ProtectionError` se não houver armazenamento protegido."""
        self._credentials.save(provider, token)
        return self._status_of(provider)

    def remove(self, provider: Provider) -> bool:
        """Apaga o token salvo no banco (a variável de ambiente, se existir, volta a valer)."""
        return self._credentials.delete(provider)

    def _status_of(self, provider: Provider) -> TokenStatus:
        updated_at = self._credentials.updated_at(provider)
        if updated_at is not None:
            source = "database"
        elif self._environ.get(ENV_VARIABLES[provider]):
            source = "environment"
        else:
            source = None
        return TokenStatus(
            provider=provider,
            label=provider.label,
            configured=source is not None,
            source=source,
            updated_at=updated_at,
        )
