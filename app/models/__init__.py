"""Modelos da API."""

from app.models.collection import (
    CollectionError,
    CollectionRead,
    CollectionRequest,
    CollectionStatus,
)
from app.models.dashboard import Dashboard, DashboardQuery, PhaseSummary, VerdictCount
from app.models.phase import INVALID_LABEL, Phase
from app.models.provider import Provider
from app.models.report import Report
from app.models.settings import TokenSettings, TokenSource, TokenStatus, TokenUpdate
from app.models.repository import RepositoryCreate, RepositoryRead, RepositoryUpdate
from app.models.trend import Trend, TrendQuery, TrendSeries

__all__ = [
    "INVALID_LABEL",
    "CollectionError",
    "CollectionRead",
    "CollectionRequest",
    "CollectionStatus",
    "Dashboard",
    "DashboardQuery",
    "Phase",
    "PhaseSummary",
    "Provider",
    "Report",
    "RepositoryCreate",
    "RepositoryRead",
    "RepositoryUpdate",
    "TokenSettings",
    "TokenSource",
    "TokenStatus",
    "TokenUpdate",
    "Trend",
    "TrendQuery",
    "TrendSeries",
    "VerdictCount",
]
