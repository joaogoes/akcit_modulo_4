"""Relatório de validação lido de uma fase (RF-05 a RF-10a)."""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, computed_field, field_validator

from app.models.phase import Phase


class Report(BaseModel):
    """Campos extraídos de um arquivo `*.md` de relatório."""

    model_config = ConfigDict(str_strip_whitespace=True, from_attributes=True)

    repository_id: int
    phase: Phase
    feature: str
    path: str
    generated: datetime | None = None
    verdict: str | None = None

    @field_validator("generated")
    @classmethod
    def assume_utc(cls, value: datetime | None) -> datetime | None:
        """Datas sem fuso horário são tratadas como UTC (P-04)."""
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    @field_validator("verdict")
    @classmethod
    def empty_verdict_is_none(cls, value: str | None) -> str | None:
        """Veredito vazio equivale a ausente."""
        return value or None

    @computed_field
    @property
    def valid(self) -> bool:
        """Válido quando há veredito e data interpretável (RF-07)."""
        return self.verdict is not None and self.generated is not None

    @property
    def verdict_key(self) -> str | None:
        """Chave de comparação do veredito, sem diferenciar caixa (RF-18)."""
        return self.verdict.casefold() if self.verdict else None
