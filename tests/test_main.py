"""Montagem da aplicação, cadastro inicial, interface estática e fluxo completo."""

import re
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.defaults import DEFAULT_REPOSITORIES
from app.main import STATIC_DIR, create_app
from app.repositories import Database
from tests.database_fixtures import V0_WITH_ONE_REPOSITORY
from tests.helpers import REQ, TESTS, counts, report_text


@pytest.fixture
def database_path(tmp_path, monkeypatch) -> Path:
    """Arquivo de banco novo, apontado por `DATABASE_PATH`."""
    path = tmp_path / "app.db"
    monkeypatch.setenv("DATABASE_PATH", str(path))
    return path


class TestFirstUse:
    def test_default_repositories_are_the_two_example_branches(self):
        assert [(d.full_name, d.branch) for d in DEFAULT_REPOSITORIES] == [
            ("joaogoes/akcit_modulo_4_repo", "projeto-1"),
            ("joaogoes/akcit_modulo_4_repo", "projeto-2"),
        ]

    def test_new_database_is_seeded_with_the_default_repositories(self, database_path, github):
        with TestClient(create_app(github=github)) as client:
            listed = client.get("/repositories").json()
        assert [(r["full_name"], r["branch"]) for r in listed] == [
            ("joaogoes/akcit_modulo_4_repo", "projeto-1"),
            ("joaogoes/akcit_modulo_4_repo", "projeto-2"),
        ]
        assert all(r["last_collected_at"] is None for r in listed)

    def test_removed_defaults_are_not_registered_again(self, database_path, github):
        with TestClient(create_app(github=github)) as first:
            first.delete("/repositories/1")
        with TestClient(create_app(github=github)) as second:
            assert [r["id"] for r in second.get("/repositories").json()] == [2]

    def test_an_injected_database_is_never_seeded(self, db, github):
        with TestClient(create_app(db, github)) as client:
            assert client.get("/repositories").json() == []

    def test_existing_database_with_repositories_is_migrated_without_seeding(self, database_path, github):
        connection = sqlite3.connect(database_path)
        connection.executescript(V0_WITH_ONE_REPOSITORY)
        connection.commit()
        connection.close()
        with TestClient(create_app(github=github)) as client:
            assert [r["full_name"] for r in client.get("/repositories").json()] == ["acme/app"]
            assert client.get("/repositories/1").json()["last_commit_sha"] is None
            assert client.post("/repositories", json={"full_name": "acme/app", "branch": "dev"}).status_code == 201

    def test_empty_database_from_an_older_version_is_seeded(self, database_path, github):
        connection = sqlite3.connect(database_path)
        connection.executescript(V0_WITH_ONE_REPOSITORY.replace("INSERT", "-- INSERT"))
        connection.commit()
        connection.close()
        with TestClient(create_app(github=github)) as client:
            assert len(client.get("/repositories").json()) == 2

    def test_database_is_closed_when_the_application_shuts_down(self, db, github):
        with TestClient(create_app(db, github)):
            pass
        with pytest.raises(sqlite3.ProgrammingError):
            db.init_schema()

    def test_database_path_defaults_to_app_db_in_the_working_directory(self, tmp_path, monkeypatch, github):
        monkeypatch.delenv("DATABASE_PATH", raising=False)
        monkeypatch.chdir(tmp_path)
        with TestClient(create_app(github=github)):
            pass
        assert (tmp_path / "app.db").exists()


class TestStaticInterface:
    def test_index_page_is_served(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "Dashboard de atividades" in response.text

    @pytest.mark.parametrize("name", ["app.js", "style.css", "index.html"])
    def test_static_assets_are_served(self, client, name):
        assert client.get(f"/static/{name}").status_code == 200

    def test_every_element_id_used_by_the_script_exists_in_the_page(self):
        script = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
        page = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        used = set(re.findall(r'\$\("([\w-]+)"\)', script))
        defined = set(re.findall(r'id="([\w-]+)"', page))
        assert used and used <= defined, used - defined

    def test_every_view_mode_button_matches_a_mode_the_script_handles(self):
        page = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        script = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
        modes = set(re.findall(r'data-mode="(\w+)"', page))
        assert modes == {"chart", "table", "trend"}
        assert all(f'"{mode}"' in script for mode in modes)

    def test_trend_phase_options_cover_every_phase(self):
        page = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        assert re.findall(r'<option value="(\w+)"', page) == ["requirements", "fspec", "dspec", "code", "tests"]

    def test_both_themes_define_the_same_color_variables(self):
        css = (STATIC_DIR / "style.css").read_text(encoding="utf-8")
        dark = re.search(r':root\[data-theme="dark"\] \{(.*?)\}', css, re.S).group(1)
        light = re.search(r"^:root \{(.*?)\}", css, re.S | re.M).group(1)
        names = lambda block: set(re.findall(r"(--[\w-]+):", block))  # noqa: E731
        assert names(dark) <= names(light)  # o tema escuro só redefine variáveis que existem no claro
        assert {"--surface", "--text", "--s1", "--s8"} <= names(dark)
        assert {"--invalid", "--other", "--accent"} <= names(light)


class TestApiDocumentation:
    def test_openapi_lists_every_route(self, client):
        paths = set(client.get("/openapi.json").json()["paths"])
        assert {"/repositories", "/repositories/{repository_id}", "/collections", "/api/dashboard", "/api/trend"} <= paths


class TestEndToEnd:
    def test_register_collect_watch_a_new_commit_and_refresh(self, client, github):
        client.post("/repositories", json={"full_name": "acme/app", "branch": "projeto-1"})
        assert client.post("/collections").json()[0]["status"] == "success"
        before = client.get("/api/dashboard").json()
        assert counts(before, "tests") == {}

        github.repositories["acme/app"][TESTS.format(feature="login", name="t1")] = report_text("2026-03-10", "Aprovado")
        github.repositories["acme/app"][REQ.format(feature="busca", name="r2")] = report_text("2026-03-01", "Aprovado")
        refreshed = client.post("/collections", json={"repository_ids": [1], "only_if_changed": True}).json()[0]
        assert refreshed["status"] == "success"
        assert client.post("/collections", json={"repository_ids": [1], "only_if_changed": True}).json()[0]["status"] == "unchanged"

        after = client.get("/api/dashboard").json()
        assert counts(after, "tests") == {"Aprovado": 1}
        assert counts(after, "requirements") == {"Aprovado": 3}
        trend = client.get("/api/trend", params={"phase": "tests"}).json()
        assert trend["dates"] == ["2026-03-10"]
        assert client.delete("/repositories/1").status_code == 204
        assert counts(client.get("/api/dashboard").json(), "tests") == {}


def test_create_app_accepts_an_explicit_database_and_client(github):
    database = Database(":memory:")
    application = create_app(database, github)
    assert application.state.db is database
    assert application.state.github is github
