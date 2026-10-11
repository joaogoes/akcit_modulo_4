"""Testes de rota isolados: as dependências são trocadas por dublês via `dependency_overrides`.

Cada teste recebe uma aplicação nova e um dublê vazio, então não há banco, arquivo
nem estado global compartilhado. Se uma rota tentasse usar o banco real, falharia,
porque a aplicação destes testes não tem `app.state.db`.
"""

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import collections, dashboard, repositories, trend
from app.api.dependencies import (
    get_collection_service,
    get_dashboard_service,
    get_repo_repository,
    get_trend_service,
)
from app.models import (
    CollectionRead,
    CollectionStatus,
    Dashboard,
    Phase,
    PhaseSummary,
    RepositoryCreate,
    RepositoryRead,
    Trend,
    TrendSeries,
    VerdictCount,
)
from app.repositories import DuplicateRepositoryError, NotFoundError


class FakeRepoRepository:
    """Repositório em memória, com a mesma interface usada pelas rotas."""

    def __init__(self) -> None:
        self.items: dict[int, RepositoryRead] = {}
        self.calls: list[tuple] = []

    def create(self, data: RepositoryCreate) -> RepositoryRead:
        self.calls.append(("create", data.full_name, data.branch))
        if any((r.full_name, r.branch) == (data.full_name, data.branch) for r in self.items.values()):
            raise DuplicateRepositoryError(data.full_name, data.branch)
        repo = RepositoryRead(
            id=len(self.items) + 1, full_name=data.full_name, branch=data.branch,
            created_at=datetime.now(UTC),
        )
        self.items[repo.id] = repo
        return repo

    def get(self, repository_id: int) -> RepositoryRead:
        self.calls.append(("get", repository_id))
        if repository_id not in self.items:
            raise NotFoundError(f"Repositório {repository_id} não encontrado.")
        return self.items[repository_id]

    def list(self) -> list[RepositoryRead]:
        self.calls.append(("list",))
        return list(self.items.values())

    def update_branch(self, repository_id: int, branch: str | None) -> RepositoryRead:
        self.calls.append(("update_branch", repository_id, branch))
        repo = self.get(repository_id)
        self.items[repository_id] = repo.model_copy(update={"branch": branch})
        return self.items[repository_id]

    def delete(self, repository_id: int) -> bool:
        self.calls.append(("delete", repository_id))
        return self.items.pop(repository_id, None) is not None


@pytest.fixture
def fake_repos() -> FakeRepoRepository:
    return FakeRepoRepository()


@pytest.fixture
def repo_api(fake_repos) -> TestClient:
    """Só as rotas de repositórios, com o dublê no lugar do repositório real."""
    app = FastAPI()
    app.include_router(repositories.router)
    app.dependency_overrides[get_repo_repository] = lambda: fake_repos
    return TestClient(app)


@pytest.fixture
def seeded(fake_repos) -> FakeRepoRepository:
    """Dublê com um repositório de id 1."""
    fake_repos.create(RepositoryCreate(full_name="acme/app", branch="dev"))
    fake_repos.calls.clear()
    return fake_repos


class TestRepositoryRoutesWithAFake:
    def test_post_returns_201_with_location_and_calls_create_once(self, repo_api, fake_repos):
        response = repo_api.post("/repositories", json={"full_name": "acme/app", "branch": "dev"})
        assert response.status_code == 201
        assert response.headers["location"] == "/repositories/1"
        assert response.json()["full_name"] == "acme/app"
        assert fake_repos.calls == [("create", "acme/app", "dev")]

    def test_post_normalizes_the_name_before_reaching_the_repository(self, repo_api, fake_repos):
        repo_api.post("/repositories", json={"full_name": "https://github.com/acme/app.git"})
        assert fake_repos.calls == [("create", "acme/app", None)]

    def test_post_invalid_body_returns_422_without_calling_the_repository(self, repo_api, fake_repos):
        assert repo_api.post("/repositories", json={"full_name": "invalido"}).status_code == 422
        assert fake_repos.calls == []

    def test_post_duplicate_returns_409(self, repo_api, seeded):
        response = repo_api.post("/repositories", json={"full_name": "acme/app", "branch": "dev"})
        assert response.status_code == 409
        assert "acme/app" in response.json()["detail"]

    def test_get_list_returns_200_with_every_item(self, repo_api, seeded):
        response = repo_api.get("/repositories")
        assert response.status_code == 200
        assert [item["full_name"] for item in response.json()] == ["acme/app"]

    def test_get_list_of_an_empty_repository_returns_200_and_an_empty_list(self, repo_api):
        response = repo_api.get("/repositories")
        assert (response.status_code, response.json()) == (200, [])

    def test_get_one_returns_200(self, repo_api, seeded):
        response = repo_api.get("/repositories/1")
        assert response.status_code == 200
        assert response.json()["branch"] == "dev"

    def test_put_returns_200_and_forwards_the_new_branch(self, repo_api, seeded):
        response = repo_api.put("/repositories/1", json={"branch": "main"})
        assert response.status_code == 200
        assert response.json()["branch"] == "main"
        assert ("update_branch", 1, "main") in seeded.calls

    def test_delete_returns_204_with_an_empty_body(self, repo_api, seeded):
        response = repo_api.delete("/repositories/1")
        assert response.status_code == 204
        assert response.content == b""
        assert seeded.items == {}

    @pytest.mark.parametrize(
        ("method", "kwargs"),
        [("get", {}), ("put", {"json": {"branch": "x"}}), ("delete", {})],
    )
    def test_unknown_id_returns_404_with_a_message(self, repo_api, method, kwargs):
        response = getattr(repo_api, method)("/repositories/99", **kwargs)
        assert response.status_code == 404
        assert "99" in response.json()["detail"]

    def test_state_does_not_leak_between_tests(self, repo_api, fake_repos):
        """Cada teste começa sem repositórios, mesmo depois de os anteriores cadastrarem."""
        assert fake_repos.items == {}
        assert repo_api.get("/repositories").json() == []
        repo_api.post("/repositories", json={"full_name": "acme/leak"})

    def test_state_does_not_leak_between_tests_second_run(self, repo_api):
        assert repo_api.get("/repositories").json() == []

    def test_application_has_no_database(self, repo_api):
        assert not hasattr(repo_api.app.state, "db")


class StubCollectionService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple] = []

    def collect_many(self, repository_ids=None, only_if_changed=False):
        self.calls.append((repository_ids, only_if_changed))
        if self.error:
            raise self.error
        now = datetime.now(UTC)
        return [
            CollectionRead(repository_id=rid, status=CollectionStatus.SUCCESS, started_at=now, finished_at=now)
            for rid in (repository_ids or [1])
        ]


class StubDashboardService:
    def __init__(self) -> None:
        self.calls: list = []

    def build(self, repository_ids=None):
        self.calls.append(repository_ids)
        phases = [PhaseSummary(phase=phase, total=0, verdicts=[]) for phase in Phase]
        phases[0] = PhaseSummary(phase=Phase.REQUIREMENTS, total=2, verdicts=[VerdictCount(verdict="Aprovado", count=2)])
        return Dashboard(phases=phases, repository_ids=repository_ids or [1])


class StubTrendService:
    def __init__(self) -> None:
        self.calls: list = []

    def build(self, repository_ids=None, phase=Phase.TESTS):
        self.calls.append((repository_ids, phase))
        return Trend(
            phase=phase, repository_ids=repository_ids or [1], dates=["2026-01-01"],
            series=[TrendSeries(verdict="Aprovado", counts=[3])],
        )


def build_app(overrides: dict) -> TestClient:
    app = FastAPI()
    for module in (collections, dashboard, trend):
        app.include_router(module.router)
    app.dependency_overrides.update(overrides)
    return TestClient(app)


class TestOtherRoutesWithStubbedServices:
    def test_collection_returns_200_and_forwards_the_request_fields(self):
        service = StubCollectionService()
        client = build_app({get_collection_service: lambda: service})
        response = client.post("/collections", json={"repository_ids": [4, 5], "only_if_changed": True})
        assert response.status_code == 200
        assert [item["repository_id"] for item in response.json()] == [4, 5]
        assert service.calls == [([4, 5], True)]

    def test_collection_without_body_asks_for_everything(self):
        service = StubCollectionService()
        build_app({get_collection_service: lambda: service}).post("/collections")
        assert service.calls == [(None, False)]

    def test_collection_returns_404_when_the_service_reports_an_unknown_repository(self):
        service = StubCollectionService(error=NotFoundError("Repositório 9 não encontrado."))
        client = build_app({get_collection_service: lambda: service})
        response = client.post("/collections", json={"repository_ids": [9]})
        assert response.status_code == 404
        assert "9" in response.json()["detail"]

    def test_dashboard_returns_200_and_passes_the_filter_to_the_service(self):
        service = StubDashboardService()
        client = build_app({get_dashboard_service: lambda: service})
        response = client.get("/api/dashboard", params={"repository_ids": [2, 3]})
        assert response.status_code == 200
        assert response.json()["phases"][0]["total"] == 2
        assert service.calls == [[2, 3]]

    def test_dashboard_without_filter_passes_none(self):
        service = StubDashboardService()
        build_app({get_dashboard_service: lambda: service}).get("/api/dashboard")
        assert service.calls == [None]

    def test_trend_returns_200_and_passes_phase_and_filter(self):
        service = StubTrendService()
        client = build_app({get_trend_service: lambda: service})
        response = client.get("/api/trend", params={"phase": "code", "repository_ids": [2]})
        assert response.status_code == 200
        assert response.json()["series"][0]["counts"] == [3]
        assert service.calls == [([2], Phase.CODE)]

    def test_trend_defaults_to_tests_phase(self):
        service = StubTrendService()
        build_app({get_trend_service: lambda: service}).get("/api/trend")
        assert service.calls == [(None, Phase.TESTS)]

    def test_trend_unknown_phase_returns_422_without_calling_the_service(self):
        service = StubTrendService()
        response = build_app({get_trend_service: lambda: service}).get("/api/trend", params={"phase": "x"})
        assert response.status_code == 422
        assert service.calls == []
