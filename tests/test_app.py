"""Testes da coleta, da agregação e da API, com cliente GitHub em memória."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.github import InMemoryGitHubClient
from app.main import create_app
from app.repositories import Database
from app.services import match_report, parse_report

REQ = "200 Requirements/230 Output/{feature}/reports/req-validation/{name}.md"
CODE = "400 Code/Output/{feature}/reports/code-validation/{name}.md"


def report(generated: str | None, verdict: str | None) -> str:
    lines = ["---"]
    if generated:
        lines.append(f"generated: {generated}")
    if verdict:
        lines.append(f"verdict: {verdict}")
    return "\n".join([*lines, "---", "", "# Relatório"])


@pytest.fixture
def github() -> InMemoryGitHubClient:
    return InMemoryGitHubClient({
        "acme/app": {
            REQ.format(feature="login", name="r1"): report("2026-01-01T10:00:00Z", "Reprovado"),
            REQ.format(feature="login", name="r2"): report("2026-02-01T10:00:00Z", "aprovado "),
            REQ.format(feature="cadastro", name="r1"): report("2026-01-05", "Aprovado"),
            REQ.format(feature="busca", name="r1"): report(None, "Aprovado"),
            CODE.format(feature="login", name="r1"): report("2026-03-01T00:00:00", "Reprovado"),
            "README.md": "sem relatório",
        },
        "acme/other": {REQ.format(feature="login", name="r1"): report("2026-01-01", "Aprovado")},
    })


@pytest.fixture
def client(github: InMemoryGitHubClient) -> TestClient:
    return TestClient(create_app(Database(":memory:"), github))


def counts(dashboard: dict, phase: str) -> dict[str, int]:
    summary = next(p for p in dashboard["phases"] if p["phase"] == phase)
    return {v["verdict"]: v["count"] for v in summary["verdicts"]}


def test_parse_report_front_matter_and_body():
    parsed = parse_report('---\ngenerated: "2026-10-10T10:00:00Z"\nverdict: **Aprovado**\n---')
    assert parsed.generated == datetime.fromisoformat("2026-10-10T10:00:00+00:00")
    assert parsed.verdict == "Aprovado"
    body = parse_report("# T\n\n- Verdict: Reprovado\n- Generated: 2026-10-10\nverdict: outro")
    assert body.verdict == "Reprovado"
    assert body.generated is not None


@pytest.mark.parametrize("text", ["", "generated: ontem\nverdict:", "nada aqui"])
def test_parse_report_invalid(text):
    parsed = parse_report(text)
    assert parsed.verdict is None
    assert parsed.generated is None


def test_match_report_uses_phase_layout():
    assert match_report(REQ.format(feature="login", name="x")) == ("requirements", "login")
    assert match_report("500 Tests/Output/login/reports/code-tests/x.md") == ("tests", "login")
    assert match_report("200 Requirements/230 Output/login/reports/req-validation/sub/x.md") is None
    assert match_report("200 Requirements/230 Output/login/reports/req-validation/x.txt") is None
    assert match_report("README.md") is None


def test_collect_and_dashboard(client):
    assert client.post("/repositories", json={"full_name": "acme/app"}).status_code == 201

    [result] = client.post("/collections").json()
    assert result["status"] == "success"
    assert result["files_read"] == 5
    assert len(result["errors"]) == 1  # relatório sem `generated`

    dashboard = client.get("/api/dashboard").json()
    # login: vale o mais recente (aprovado); busca: sem data => Inválido
    assert counts(dashboard, "requirements") == {"aprovado": 1, "Aprovado": 1, "Inválido": 1} or \
        counts(dashboard, "requirements") in ({"Aprovado": 2, "Inválido": 1},)
    assert counts(dashboard, "code") == {"Reprovado": 1}
    assert counts(dashboard, "tests") == {}


def test_same_feature_in_two_repositories_counts_twice(client):
    for name in ("acme/app", "acme/other"):
        client.post("/repositories", json={"full_name": name})
    client.post("/collections")
    dashboard = client.get("/api/dashboard").json()
    assert sum(counts(dashboard, "requirements").values()) == 4
    only = client.get("/api/dashboard", params={"repository_ids": [2]}).json()
    assert counts(only, "requirements") == {"Aprovado": 1}
    assert only["repository_ids"] == [2]


def test_failed_collection_keeps_previous_data(client, github):
    client.post("/repositories", json={"full_name": "acme/app"})
    client.post("/collections")
    before = client.get("/api/dashboard").json()

    github.fail_listing = True
    [result] = client.post("/collections", json={"repository_ids": [1]}).json()
    assert result["status"] == "failed"
    assert client.get("/api/dashboard").json()["phases"] == before["phases"]
    assert client.get("/repositories/1").json()["last_collection_status"] == "failed"


def test_unreadable_file_is_stored_as_invalid(client, github):
    client.post("/repositories", json={"full_name": "acme/app"})
    github.failing_paths.add(REQ.format(feature="cadastro", name="r1"))
    [result] = client.post("/collections").json()
    assert result["status"] == "success"
    assert any("cadastro" in (e["path"] or "") for e in result["errors"])
    assert counts(client.get("/api/dashboard").json(), "requirements")["Inválido"] == 2


def test_unknown_repository_returns_404(client):
    assert client.post("/collections", json={"repository_ids": [99]}).status_code == 404
    assert client.get("/repositories/99").status_code == 404


def test_remove_repository_clears_dashboard(client):
    client.post("/repositories", json={"full_name": "acme/app"})
    client.post("/collections")
    assert client.delete("/repositories/1").status_code == 204
    dashboard = client.get("/api/dashboard").json()
    assert all(p["total"] == 0 for p in dashboard["phases"])


def test_index_page_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Dashboard de atividades" in response.text
    assert client.get("/static/app.js").status_code == 200
