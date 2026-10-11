"""Modelos da tendência no tempo (RF-20)."""

from datetime import date

from pydantic import BaseModel, Field, model_validator

from app.models.phase import Phase


class TrendQuery(BaseModel):
    """Parâmetros de GET /api/trend."""

    repository_ids: list[int] | None = Field(
        default=None,
        description="Se omitido, agrega todos os repositórios.",
    )
    phase: Phase = Field(default=Phase.TESTS, description="Fase acompanhada.")
    start: date | None = Field(
        default=None,
        description="Primeira data do eixo; por padrão, a do primeiro relatório válido.",
    )
    end: date | None = Field(
        default=None,
        description="Última data do eixo; por padrão, a do último relatório válido.",
    )

    @model_validator(mode="after")
    def check_range(self) -> "TrendQuery":
        """`end` não pode ser anterior a `start`."""
        if self.start and self.end and self.end < self.start:
            raise ValueError("`end` não pode ser anterior a `start`.")
        return self


class TrendSeries(BaseModel):
    """Linha do gráfico: features com um veredito em cada data."""

    verdict: str
    counts: list[int]


class Trend(BaseModel):
    """Evolução das features de uma fase por veredito, em pontos semanais."""

    phase: Phase
    repository_ids: list[int]
    dates: list[date]
    series: list[TrendSeries]

    @model_validator(mode="after")
    def check_lengths(self) -> "Trend":
        """Cada série tem um valor por data."""
        if any(len(item.counts) != len(self.dates) for item in self.series):
            raise ValueError("Cada série deve ter um valor por data.")
        return self
