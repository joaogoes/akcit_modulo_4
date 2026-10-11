"""Fixtures simples: banco em memória, repositórios, serviços e cliente HTTP."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.github import InMemoryGitHubClient
from app.main import create_app
from app.repositories import Database, RepoRepository, ReportRepository
from app.services import CollectionService, DashboardService, TrendService
from tests.helpers import CODE, REQ, report_text


@pytest.fixture
def db() -> Iterator[Database]:
    """Banco SQLite em memória, com o esquema criado."""
    database = Database(":memory:")
    database.init_schema()
    yield database
    database.close()


@pytest.fixture
def repos(db: Database) -> RepoRepository:
    return RepoRepository(db)


@pytest.fixture
def reports(db: Database) -> ReportRepository:
    return ReportRepository(db)


@pytest.fixture
def github() -> InMemoryGitHubClient:
    """Dois repositórios fictícios.

    `acme/app` — login: reprovado (01/01) e depois aprovado (01/02); cadastro:
    aprovado; busca: sem `generated`; login em Code: reprovado; mais um arquivo
    que não é relatório. `acme/other` — um relatório aprovado em Requirements.
    """
    return InMemoryGitHubClient({
        "acme/app": {
            REQ.format(feature="login", name="r1"): report_text("2026-01-01T10:00:00Z", "Reprovado"),
            REQ.format(feature="login", name="r2"): report_text("2026-02-01T10:00:00Z", "aprovado "),
            REQ.format(feature="cadastro", name="r1"): report_text("2026-01-05", "Aprovado"),
            REQ.format(feature="busca", name="r1"): report_text(None, "Aprovado"),
            CODE.format(feature="login", name="r1"): report_text("2026-03-01T00:00:00", "Reprovado"),
            "README.md": "sem relatório",
        },
        "acme/other": {
            REQ.format(feature="login", name="r1"): report_text("2026-01-01", "Aprovado"),
        },
    })


@pytest.fixture
def collection_service(github, repos, reports) -> CollectionService:
    return CollectionService(github, repos, reports)


@pytest.fixture
def dashboard_service(repos, reports) -> DashboardService:
    return DashboardService(repos, reports)


@pytest.fixture
def trend_service(repos, reports) -> TrendService:
    return TrendService(repos, reports)


@pytest.fixture
def client(db: Database, github: InMemoryGitHubClient) -> TestClient:
    """Cliente HTTP da aplicação; banco injetado, então sem cadastro inicial."""
    return TestClient(create_app(db, github))


@pytest.fixture
def collected_client(client: TestClient) -> TestClient:
    """`client` com `acme/app` cadastrado (id 1) e já coletado."""
    client.post("/repositories", json={"full_name": "acme/app"})
    client.post("/collections")
    return client
