"""Modelos de coleta de relatórios (RF-11, RNF-10)."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class CollectionStatus(StrEnum):
    """Estado de uma coleta."""

    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    UNCHANGED = "unchanged"  # sem novo commit desde a última coleta; nada foi lido


class CollectionRequest(BaseModel):
    """Corpo de POST /collections."""

    repository_ids: list[int] | None = Field(
        default=None,
        min_length=1,
        description="Se omitido, coleta todos os repositórios cadastrados.",
    )
    only_if_changed: bool = Field(
        default=False,
        description="Só coleta se o último commit diferir do último coletado.",
    )


class CollectionError(BaseModel):
    """Erro ocorrido durante a coleta, por repositório ou arquivo."""

    path: str | None = None
    message: str


class CollectionRead(BaseModel):
    """Resultado de uma coleta de um repositório."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = Field(default=None, description="Definido a partir da Release 2.")
    repository_id: int
    status: CollectionStatus
    started_at: datetime
    finished_at: datetime | None = None
    commit_sha: str | None = Field(default=None, description="Commit lido (ou verificado).")
    files_read: int = Field(default=0, ge=0)
    errors: list[CollectionError] = Field(default_factory=list)
