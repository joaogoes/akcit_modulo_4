"""Rota de dados do dashboard (RF-12 a RF-17, RNF-14)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_dashboard_service
from app.models import Dashboard, DashboardQuery
from app.services import DashboardService

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=Dashboard)
def get_dashboard(
    query: Annotated[DashboardQuery, Query()],
    service: Annotated[DashboardService, Depends(get_dashboard_service)],
) -> Dashboard:
    """Totais de features por fase e veredito; filtra por `repository_ids`."""
    return service.build(query.repository_ids)
