"""Modelos de cadastro de repositórios (RF-01 a RF-04)."""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.collection import CollectionStatus

_URL = re.compile(r"^https?://github\.com/(?P<name>[^/]+/[^/]+?)(?:\.git)?/?$")
_FULL_NAME = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class RepositoryCreate(BaseModel):
    """Corpo de POST /repositories."""

    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(description="`owner/repo` ou URL do GitHub.")
    branch: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Se omitida, usa a branch padrão do repositório.",
    )

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        """Normaliza URL do GitHub para `owner/repo` e valida o formato."""
        if match := _URL.match(value):
            value = match["name"]
        if not _FULL_NAME.match(value):
            raise ValueError("Informe o repositório como `owner/repo`.")
        return value


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
    full_name: str
    branch: str | None
    created_at: datetime
    last_collected_at: datetime | None = None
    last_collection_status: CollectionStatus | None = None

