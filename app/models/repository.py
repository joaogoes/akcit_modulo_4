"""Modelos de cadastro de repositórios (RF-01 a RF-04, RF-21)."""

import re
from datetime import datetime
from urllib.parse import unquote, urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.collection import CollectionStatus
from app.models.provider import Provider

_GITHUB_URL = re.compile(r"^https?://(?:www\.)?github\.com/(?P<name>[^/]+/[^/]+?)(?:\.git)?/?$")
_GITHUB_NAME = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_AZURE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[^/\\?#]+/[^/\\?#]+$")  # organização/projeto/repositório
_HELP = (
    "Informe `owner/repo`, a URL de um repositório do GitHub "
    "ou a URL de um repositório do Azure DevOps (https://dev.azure.com/org/projeto/_git/repo)."
)


def _azure_name_from_url(value: str) -> str | None:
    """`organização/projeto/repositório` de uma URL do Azure DevOps, ou `None`."""
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https"):
        return None
    host = (parts.hostname or "").lower()  # `hostname` descarta o usuário (`org@dev.azure.com`)
    segments = [unquote(segment) for segment in parts.path.split("/") if segment]
    if host == "dev.azure.com" and len(segments) >= 4 and segments[2] == "_git":
        return f"{segments[0]}/{segments[1]}/{segments[3]}"
    if host.endswith(".visualstudio.com"):
        if segments and segments[0].lower() == "defaultcollection":
            segments = segments[1:]
        if len(segments) >= 3 and segments[1] == "_git":
            return f"{host.removesuffix('.visualstudio.com')}/{segments[0]}/{segments[2]}"
    return None


def parse_repository_reference(value: str, provider: Provider | None = None) -> tuple[Provider, str]:
    """Identifica o provedor e o nome normalizado de um repositório.

    GitHub: `owner/repo` ou URL. Azure DevOps: URL (`dev.azure.com` ou
    `*.visualstudio.com`) ou `organização/projeto/repositório` com o provedor informado.
    """
    value = value.strip()
    if azure := _azure_name_from_url(value):
        found, name = Provider.AZURE_DEVOPS, azure
    elif match := _GITHUB_URL.match(value):
        found, name = Provider.GITHUB, match["name"]
    elif provider is Provider.AZURE_DEVOPS:
        found, name = Provider.AZURE_DEVOPS, value
    else:
        found, name = Provider.GITHUB, value
    if provider is not None and provider is not found:
        raise ValueError(f"O endereço informado é do {found.label}, e não do {provider.label}.")
    pattern = _AZURE_NAME if found is Provider.AZURE_DEVOPS else _GITHUB_NAME
    if not pattern.match(name):
        raise ValueError(_HELP)
    return found, name


class RepositoryCreate(BaseModel):
    """Corpo de POST /repositories."""

    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(description="`owner/repo`, URL do GitHub ou URL do Azure DevOps.")
    provider: Provider | None = Field(
        default=None,
        description="Detectado pelo endereço; informe só para `organização/projeto/repositório`.",
    )
    branch: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Se omitida, usa a branch padrão do repositório.",
    )

    @model_validator(mode="after")
    def normalize_reference(self) -> "RepositoryCreate":
        """Resolve o provedor e normaliza o nome (GitHub: `owner/repo`; Azure: `org/projeto/repo`)."""
        self.provider, self.full_name = parse_repository_reference(self.full_name, self.provider)
        return self


class RepositoryUpdate(BaseModel):
    """Corpo de PUT /repositories/{id}."""

    model_config = ConfigDict(str_strip_whitespace=True)

    branch: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="`null` volta à branch padrão do repositório.",
    )


class RepositoryRead(BaseModel):
    """Repositório cadastrado, com o resumo da última coleta."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: Provider = Provider.GITHUB
    full_name: str
    branch: str | None
    created_at: datetime
    last_collected_at: datetime | None = None
    last_collection_status: CollectionStatus | None = None
    last_commit_sha: str | None = None
