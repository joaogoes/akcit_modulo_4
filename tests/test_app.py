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


def test_same_repository_can_be_registered_once_per_branch(client):
    first = client.post("/repositories", json={"full_name": "acme/app", "branch": "projeto-1"})
    second = client.post("/repositories", json={"full_name": "acme/app", "branch": "projeto-2"})
    assert first.status_code == second.status_code == 201
    assert client.post("/repositories", json={"full_name": "ACME/app", "branch": "projeto-2"}).status_code == 409
    assert client.post("/repositories", json={"full_name": "acme/app"}).status_code == 201
    assert client.post("/repositories", json={"full_name": "acme/app"}).status_code == 409


def test_default_repositories_are_seeded_on_first_use(tmp_path, monkeypatch, github):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "app.db"))
    with TestClient(create_app(github=github)) as first:
        listed = first.get("/repositories").json()
        assert [(r["full_name"], r["branch"]) for r in listed] == [
            ("joaogoes/akcit_modulo_4_repo", "projeto-1"),
            ("joaogoes/akcit_modulo_4_repo", "projeto-2"),
        ]
        assert first.delete("/repositories/1").status_code == 204
    with TestClient(create_app(github=github)) as second:  # não cadastra de novo
        assert [r["id"] for r in second.get("/repositories").json()] == [2]


def test_legacy_database_is_migrated_keeping_data(tmp_path, monkeypatch, github):
    import sqlite3

    path = tmp_path / "legacy.db"
    legacy = sqlite3.connect(path)
    legacy.executescript(
        """
        CREATE TABLE repositories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            branch TEXT, created_at TEXT NOT NULL,
            last_collected_at TEXT, last_collection_status TEXT);
        CREATE TABLE reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
            phase TEXT NOT NULL, feature TEXT NOT NULL, path TEXT NOT NULL,
            generated TEXT, verdict TEXT);
        INSERT INTO repositories (full_name, created_at) VALUES ('acme/app', '2026-10-01T00:00:00+00:00');
        INSERT INTO reports (repository_id, phase, feature, path, generated, verdict)
            VALUES (1, 'code', 'f', 'p', '2026-10-01T00:00:00+00:00', 'Aprovado');
        """
    )
    legacy.commit()
    legacy.close()

    monkeypatch.setenv("DATABASE_PATH", str(path))
    with TestClient(create_app(github=github)) as client:
        assert [r["full_name"] for r in client.get("/repositories").json()] == ["acme/app"]
        assert counts(client.get("/api/dashboard").json(), "code") == {"Aprovado": 1}
        assert client.post("/repositories", json={"full_name": "acme/app", "branch": "dev"}).status_code == 201


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self._body


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        (None, "https://raw.githubusercontent.com/acme/app/projeto%201/a%20b/r.md"),
        ("t0k3n", "https://api.github.com/repos/acme/app/contents/a%20b/r.md?ref=projeto%201"),
    ],
)
def test_http_client_file_url_depends_on_token(monkeypatch, token, expected):
    from app.github import HttpGitHubClient

    requested = []

    def fake_urlopen(request, timeout):
        requested.append(request)
        return _FakeResponse("verdict: Aprovado".encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    text = HttpGitHubClient(token).get_file("acme/app", "a b/r.md", "projeto 1")
    assert text == "verdict: Aprovado"
    assert requested[0].full_url == expected
    assert (requested[0].get_header("Authorization") is not None) == bool(token)


def refresh(client: TestClient, repository_id: int = 1) -> dict:
    response = client.post(
        "/collections", json={"repository_ids": [repository_id], "only_if_changed": True}
    )
    assert response.status_code == 200
    return response.json()[0]


def test_refresh_collects_only_when_the_commit_changed(client, github):
    client.post("/repositories", json={"full_name": "acme/app"})

    first = refresh(client)  # nunca coletado
    assert first["status"] == "success"
    commit = first["commit_sha"]
    assert client.get("/repositories/1").json()["last_commit_sha"] == commit

    same = refresh(client)  # mesmo commit: nada é lido
    assert same["status"] == "unchanged"
    assert same["files_read"] == 0
    assert same["commit_sha"] == commit

    github.repositories["acme/app"][REQ.format(feature="busca", name="r2")] = report(
        "2026-03-01", "Aprovado"
    )
    changed = refresh(client)  # novo commit
    assert changed["status"] == "success"
    assert changed["commit_sha"] != commit
    assert counts(client.get("/api/dashboard").json(), "requirements")["Aprovado"] == 3


def test_forced_collection_ignores_the_commit(client):
    client.post("/repositories", json={"full_name": "acme/app"})
    refresh(client)
    [forced] = client.post("/collections", json={"repository_ids": [1]}).json()
    assert forced["status"] == "success"


def test_failed_collection_keeps_commit_and_refresh_retries(client, github):
    client.post("/repositories", json={"full_name": "acme/app"})
    commit = refresh(client)["commit_sha"]

    github.repositories["acme/app"]["README.md"] = "mudou"
    github.fail_listing = True
    assert refresh(client)["status"] == "failed"
    assert client.get("/repositories/1").json()["last_commit_sha"] == commit

    github.fail_listing = False
    again = refresh(client)  # a última coleta falhou, então tenta de novo
    assert again["status"] == "success"
    assert again["commit_sha"] != commit


def test_refresh_reports_unknown_repository_on_github(client):
    client.post("/repositories", json={"full_name": "acme/inexistente"})
    result = refresh(client)
    assert result["status"] == "failed"
    assert "não encontrado" in result["errors"][0]["message"]


def test_schema_version_1_database_gets_commit_column(tmp_path, monkeypatch, github):
    import sqlite3

    path = tmp_path / "v1.db"
    old = sqlite3.connect(path)
    old.executescript(
        """
        CREATE TABLE repositories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL COLLATE NOCASE, branch TEXT, created_at TEXT NOT NULL,
            last_collected_at TEXT, last_collection_status TEXT);
        CREATE UNIQUE INDEX ux_repositories_name_branch
            ON repositories (full_name COLLATE NOCASE, COALESCE(branch, ''));
        CREATE TABLE reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
            phase TEXT NOT NULL, feature TEXT NOT NULL, path TEXT NOT NULL,
            generated TEXT, verdict TEXT);
        INSERT INTO repositories (full_name, created_at) VALUES ('acme/app', '2026-10-01T00:00:00+00:00');
        PRAGMA user_version = 1;
        """
    )
    old.commit()
    old.close()

    monkeypatch.setenv("DATABASE_PATH", str(path))
    with TestClient(create_app(github=github)) as client:
        assert client.get("/repositories/1").json()["last_commit_sha"] is None
        assert refresh(client)["status"] == "success"


def trend_of(client: TestClient, **params) -> dict:
    response = client.get("/api/trend", params=params)
    assert response.status_code == 200
    return response.json()


def test_trend_reconstructs_the_verdict_in_force_on_each_date(client):
    client.post("/repositories", json={"full_name": "acme/app"})
    client.post("/collections")

    trend = trend_of(client, phase="requirements")
    # válidos: login (reprovado em 01/01, aprovado em 01/02) e cadastro (aprovado em 05/01)
    assert trend["dates"] == [
        "2026-01-01", "2026-01-08", "2026-01-15", "2026-01-22", "2026-01-29", "2026-02-01",
    ]
    series = {item["verdict"]: item["counts"] for item in trend["series"]}
    assert series["Reprovado"] == [1, 1, 1, 1, 1, 0]
    assert series["Aprovado"] == [0, 1, 1, 1, 1, 2]
    assert [sum(column) for column in zip(*series.values())] == [1, 2, 2, 2, 2, 2]


def test_trend_defaults_to_tests_phase_and_handles_empty_data(client):
    client.post("/repositories", json={"full_name": "acme/app"})
    client.post("/collections")
    empty = trend_of(client)  # não há relatórios de Tests
    assert empty["phase"] == "tests"
    assert empty["dates"] == [] and empty["series"] == []
    assert client.get("/api/trend", params={"phase": "outra"}).status_code == 422


def test_trend_filters_repositories_and_never_calls_github(client, github):
    for name in ("acme/app", "acme/other"):
        client.post("/repositories", json={"full_name": name})
    client.post("/collections")

    def forbidden(*args, **kwargs):
        raise AssertionError("A tendência não deve acessar o GitHub.")

    github.get_head_commit = github.list_files = github.get_file = forbidden
    only = trend_of(client, phase="requirements", repository_ids=[2])
    assert only["repository_ids"] == [2]
    assert only["dates"] == ["2026-01-01"]
    assert only["series"] == [{"verdict": "Aprovado", "counts": [1]}]
    both = trend_of(client, phase="requirements")
    assert sum(item["counts"][-1] for item in both["series"]) == 3
