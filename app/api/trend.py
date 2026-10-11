"""Rota de tendência no tempo (RF-20)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_trend_service
from app.models import Trend, TrendQuery
from app.services import TrendService

router = APIRouter(prefix="/api/trend", tags=["dashboard"])


@router.get("", response_model=Trend)
def get_trend(
    query: Annotated[TrendQuery, Query()],
    service: Annotated[TrendService, Depends(get_trend_service)],
) -> Trend:
    """Evolução semanal das features de uma fase por veredito; lê só o banco."""
    return service.build(query.repository_ids, query.phase)
