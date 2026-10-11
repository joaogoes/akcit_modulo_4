"""Dependências compartilhadas pelas rotas; o estado vem de `app.state`."""

from fastapi import Depends, Request

from app.github import GitHubClient
from app.repositories import Database, RepoRepository, ReportRepository
from app.services import CollectionService, DashboardService, TokenService, TrendService


def get_db(request: Request) -> Database:
    """Banco de dados da aplicação."""
    return request.app.state.db


def get_github(request: Request) -> GitHubClient:
    """Cliente GitHub da aplicação."""
    return request.app.state.github


def get_azure(request: Request) -> GitHubClient:
    """Cliente do Azure DevOps da aplicação."""
    return request.app.state.azure


def get_repo_repository(db: Database = Depends(get_db)) -> RepoRepository:
    """Repositório de dados dos repositórios cadastrados."""
    return RepoRepository(db)


def get_report_repository(db: Database = Depends(get_db)) -> ReportRepository:
    """Repositório de dados dos relatórios."""
    return ReportRepository(db)


def get_collection_service(
    github: GitHubClient = Depends(get_github),
    azure: GitHubClient = Depends(get_azure),
    repos: RepoRepository = Depends(get_repo_repository),
    reports: ReportRepository = Depends(get_report_repository),
) -> CollectionService:
    """Serviço de coleta."""
    return CollectionService(github, repos, reports, azure=azure)


def get_dashboard_service(
    repos: RepoRepository = Depends(get_repo_repository),
    reports: ReportRepository = Depends(get_report_repository),
) -> DashboardService:
    """Serviço do dashboard."""
    return DashboardService(repos, reports)


def get_trend_service(
    repos: RepoRepository = Depends(get_repo_repository),
    reports: ReportRepository = Depends(get_report_repository),
) -> TrendService:
    """Serviço de tendência."""
    return TrendService(repos, reports)


def get_token_service(request: Request) -> TokenService:
    """Serviço de tokens de acesso."""
    return request.app.state.tokens
