"""Rotas HTTP: repositórios, coleta, dashboard e tendência."""

import pytest

from tests.helpers import REQ, counts, report_text


def add(client, name="acme/app", branch=None):
    body = {"full_name": name} | ({"branch": branch} if branch else {})
    return client.post("/repositories", json=body)


class TestRepositoriesApi:
    def test_post_creates_the_repository_and_returns_its_location(self, client):
        response = add(client, "acme/app", "dev")
        assert response.status_code == 201
        assert response.headers["location"] == "/repositories/1"
        assert response.json()["full_name"] == "acme/app"
        assert response.json()["branch"] == "dev"
        assert response.json()["last_collected_at"] is None

    def test_post_accepts_a_github_url(self, client):
        assert add(client, "https://github.com/acme/app.git").json()["full_name"] == "acme/app"

    def test_post_duplicate_returns_409_naming_the_repository(self, client):
        add(client, "acme/app", "dev")
        response = add(client, "ACME/app", "dev")
        assert response.status_code == 409
        assert "acme/app" in response.json()["detail"].lower()

    def test_same_repository_can_be_added_once_per_branch_and_once_without_branch(self, client):
        assert [add(client, "acme/app", b).status_code for b in ("projeto-1", "projeto-2", None)] == [201] * 3
        assert add(client, "acme/app").status_code == 409

    @pytest.mark.parametrize("body", [{}, {"full_name": "invalido"}, {"full_name": "acme/app", "branch": ""}])
    def test_post_invalid_body_returns_422(self, client, body):
        assert client.post("/repositories", json=body).status_code == 422

    def test_get_lists_in_registration_order(self, client):
        add(client, "acme/b")
        add(client, "acme/a")
        assert [r["full_name"] for r in client.get("/repositories").json()] == ["acme/b", "acme/a"]

    def test_get_one_and_404(self, client):
        add(client)
        assert client.get("/repositories/1").json()["full_name"] == "acme/app"
        response = client.get("/repositories/99")
        assert response.status_code == 404
        assert "99" in response.json()["detail"]

    def test_get_with_a_non_numeric_id_returns_422(self, client):
        assert client.get("/repositories/abc").status_code == 422

    def test_put_replaces_the_branch_and_null_restores_the_default(self, client):
        add(client)
        assert client.put("/repositories/1", json={"branch": "dev"}).json()["branch"] == "dev"
        assert client.put("/repositories/1", json={"branch": None}).json()["branch"] is None

    def test_put_unknown_id_returns_404_and_empty_branch_422(self, client):
        add(client)
        assert client.put("/repositories/99", json={"branch": "x"}).status_code == 404
        assert client.put("/repositories/1", json={"branch": ""}).status_code == 422

    def test_delete_returns_204_then_404_and_clears_the_dashboard(self, collected_client):
        assert collected_client.delete("/repositories/1").status_code == 204
        assert collected_client.delete("/repositories/1").status_code == 404
        dashboard = collected_client.get("/api/dashboard").json()
        assert all(phase["total"] == 0 for phase in dashboard["phases"])


class TestCollectionsApi:
    def test_without_body_collects_every_repository(self, client):
        add(client, "acme/app")
        add(client, "acme/other")
        results = client.post("/collections").json()
        assert [(r["repository_id"], r["status"]) for r in results] == [(1, "success"), (2, "success")]
        assert results[0]["files_read"] == 5 and results[0]["commit_sha"]

    def test_with_ids_collects_only_those_repositories(self, client):
        add(client, "acme/app")
        add(client, "acme/other")
        results = client.post("/collections", json={"repository_ids": [2]}).json()
        assert [r["repository_id"] for r in results] == [2]
        assert client.get("/repositories/1").json()["last_collected_at"] is None

    def test_no_repositories_returns_an_empty_list(self, client):
        assert client.post("/collections").json() == []

    def test_unknown_id_returns_404_before_collecting_anything(self, client):
        add(client)
        assert client.post("/collections", json={"repository_ids": [1, 99]}).status_code == 404
        assert client.get("/repositories/1").json()["last_collected_at"] is None

    def test_empty_id_list_returns_422(self, client):
        assert client.post("/collections", json={"repository_ids": []}).status_code == 422

    def test_only_if_changed_returns_unchanged_until_the_commit_moves(self, client, github):
        add(client)

        def refresh():
            return client.post("/collections", json={"repository_ids": [1], "only_if_changed": True}).json()[0]

        assert refresh()["status"] == "success"
        assert refresh()["status"] == "unchanged"
        github.repositories["acme/app"][REQ.format(feature="busca", name="r2")] = report_text("2026-03-01", "Aprovado")
        assert refresh()["status"] == "success"
        assert counts(client.get("/api/dashboard").json(), "requirements")["Aprovado"] == 3

    def test_github_failure_is_reported_in_the_result_with_http_200(self, client):
        add(client, "acme/inexistente")
        [result] = client.post("/collections").json()
        assert result["status"] == "failed"
        assert "não encontrado" in result["errors"][0]["message"]
        assert client.get("/repositories/1").json()["last_collection_status"] == "failed"

    def test_collected_repository_exposes_status_date_and_commit(self, collected_client):
        repo = collected_client.get("/repositories/1").json()
        assert repo["last_collection_status"] == "success"
        assert repo["last_collected_at"] and repo["last_commit_sha"]


class TestDashboardApi:
    def test_returns_the_five_phases_even_without_data(self, client):
        dashboard = client.get("/api/dashboard").json()
        assert [p["phase"] for p in dashboard["phases"]] == ["requirements", "fspec", "dspec", "code", "tests"]
        assert dashboard["last_collected_at"] is None

    def test_counts_features_by_phase_and_verdict(self, collected_client):
        dashboard = collected_client.get("/api/dashboard").json()
        assert counts(dashboard, "requirements") == {"Aprovado": 2, "Inválido": 1}
        assert counts(dashboard, "code") == {"Reprovado": 1}
        assert dashboard["repository_ids"] == [1]

    def test_repeated_query_parameters_filter_the_repositories(self, client):
        add(client, "acme/app")
        add(client, "acme/other")
        client.post("/collections")
        both = client.get("/api/dashboard").json()
        only = client.get("/api/dashboard", params={"repository_ids": [2]}).json()
        two = client.get("/api/dashboard", params={"repository_ids": [1, 2]}).json()
        assert sum(counts(both, "requirements").values()) == 4
        assert counts(only, "requirements") == {"Aprovado": 1}
        assert two == both

    def test_unknown_ids_are_ignored_and_bad_ids_return_422(self, collected_client):
        assert collected_client.get("/api/dashboard", params={"repository_ids": [99]}).json()["repository_ids"] == []
        assert collected_client.get("/api/dashboard", params={"repository_ids": ["x"]}).status_code == 422


class TestApprovedAliasesApi:
    def test_success_sucesso_and_aprovado_are_reported_as_aprovado(self, client, github):
        github.repositories["acme/app"] = {
            REQ.format(feature=name, name="r"): report_text("2026-01-01", verdict)
            for name, verdict in (("a", "SUCCESS"), ("b", "Sucesso"), ("c", "Aprovado"), ("d", "Reprovado"))
        }
        add(client)
        client.post("/collections")
        dashboard = client.get("/api/dashboard").json()
        assert counts(dashboard, "requirements") == {"Aprovado": 3, "Reprovado": 1}
        trend = client.get("/api/trend", params={"phase": "requirements"}).json()
        assert {item["verdict"] for item in trend["series"]} == {"Aprovado", "Reprovado"}


class TestTrendApi:
    def trend(self, client, **params):
        response = client.get("/api/trend", params=params)
        assert response.status_code == 200
        return response.json()

    def test_reconstructs_the_verdict_in_force_on_each_week(self, collected_client):
        trend = self.trend(collected_client, phase="requirements")
        assert trend["dates"] == ["2026-01-01", "2026-01-08", "2026-01-15", "2026-01-22", "2026-01-29", "2026-02-01"]
        series = {item["verdict"]: item["counts"] for item in trend["series"]}
        assert series["Reprovado"] == [1, 1, 1, 1, 1, 0]
        assert series["Aprovado"] == [0, 1, 1, 1, 1, 2]

    def test_defaults_to_the_tests_phase_and_handles_empty_data(self, collected_client):
        empty = self.trend(collected_client)
        assert empty["phase"] == "tests"
        assert empty["dates"] == [] and empty["series"] == []

    def test_invalid_phase_returns_422(self, client):
        assert client.get("/api/trend", params={"phase": "outra"}).status_code == 422

    def test_filters_by_repository(self, client):
        add(client, "acme/app")
        add(client, "acme/other")
        client.post("/collections")
        only = self.trend(client, phase="requirements", repository_ids=[2])
        assert only["repository_ids"] == [2]
        assert only["series"] == [{"verdict": "Aprovado", "counts": [1]}]


    def test_start_and_end_give_every_repository_the_same_dates(self, client):
        add(client, "acme/app")
        add(client, "acme/other")
        client.post("/collections")
        common = self.trend(client, phase="requirements")
        limits = {"start": common["dates"][0], "end": common["dates"][-1]}
        first = self.trend(client, phase="requirements", repository_ids=[1], **limits)
        second = self.trend(client, phase="requirements", repository_ids=[2], **limits)
        assert first["dates"] == second["dates"] == common["dates"]
        assert len(second["series"][0]["counts"]) == len(common["dates"])

    @pytest.mark.parametrize(
        "params",
        [{"start": "2026-02-01", "end": "2026-01-01"}, {"start": "ontem"}, {"end": "2026-13-01"}],
    )
    def test_invalid_limits_return_422(self, client, params):
        assert client.get("/api/trend", params=params).status_code == 422
