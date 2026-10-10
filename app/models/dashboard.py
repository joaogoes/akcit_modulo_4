"""Modelos do dashboard (RF-12 a RF-17)."""

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.phase import INVALID_LABEL, Phase


class DashboardQuery(BaseModel):
    """Parâmetros de GET /api/dashboard."""

    repository_ids: list[int] | None = Field(
        default=None,
        description="Se omitido, agrega todos os repositórios.",
    )


class VerdictCount(BaseModel):
    """Segmento de uma barra: total de features com um veredito."""

    verdict: str
    count: int = Field(ge=0)


class PhaseSummary(BaseModel):
    """Barra do gráfico: totais por veredito em uma fase."""

    phase: Phase
    total: int = Field(ge=0)
    verdicts: list[VerdictCount]

    @model_validator(mode="after")
    def sort_and_check_total(self) -> "PhaseSummary":
        """Ordena os segmentos (RF-17, P-08) e confere o total."""
        self.verdicts.sort(
            key=lambda v: (v.verdict == INVALID_LABEL, v.verdict.casefold())
        )
        if sum(v.count for v in self.verdicts) != self.total:
            raise ValueError("O total da fase difere da soma dos vereditos.")
        return self


class Dashboard(BaseModel):
    """Resposta de GET /api/dashboard."""

    phases: list[PhaseSummary]
    repository_ids: list[int]
    last_collected_at: datetime | None = None
