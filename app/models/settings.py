"""Modelos das configurações de acesso (tokens por provedor, RF-22)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, SecretStr

from app.models.provider import Provider

TokenSource = Literal["database", "environment"]


class TokenUpdate(BaseModel):
    """Corpo de PUT /settings/tokens/{provider}. O valor nunca aparece em `repr` nem nas respostas."""

    token: SecretStr


class TokenStatus(BaseModel):
    """Situação do token de um provedor. Não contém o valor do token."""

    provider: Provider
    label: str
    configured: bool
    source: TokenSource | None = None
    updated_at: datetime | None = None


class TokenSettings(BaseModel):
    """Resposta de GET /settings/tokens."""

    secure_storage: bool
    tokens: list[TokenStatus]
