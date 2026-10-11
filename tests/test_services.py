"""Serviços de coleta, dashboard e tendência."""

from datetime import date

import pytest

from app.github import GitHubError, InMemoryGitHubClient, RateLimitError
from app.models import INVALID_LABEL, CollectionStatus, Phase, RepositoryCreate
from app.repositories import NotFoundError
from app.services import CollectionService
from tests.helpers import CODE, REQ, TESTS, report_text


def register(repos, name="acme/app", branch=None):
    return repos.create(RepositoryCreate(full_name=name, branch=branch))


def verdicts(dashboard, phase: str) -> dict[str, int]:
    summary = next(item for item in dashboard.phases if item.phase == phase)
    return {item.verdict: item.count for item in summary.verdicts}


class RecordingClient(InMemoryGitHubClient):
    """Registra o `ref` recebido em cada chamada de leitura."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.refs: list[tuple[str, str]] = []

    def list_files(self, full_name, ref):
        self.refs.append(("list", ref))
        return super().list_files(full_name, ref)

    def get_file(self, full_name, path, ref):
        self.refs.append(("get", ref))
        return super().get_file(full_name, path, ref)


class TestCollectionService:
    def test_collects_every_report_and_stores_status_and_commit(self, collection_service, repos, reports, github):
        repo = register(repos)
        result = collection_service.collect(repo.id)
        assert result.status == CollectionStatus.SUCCESS
        assert result.files_read == 5
        assert result.commit_sha == github.get_head_commit("acme/app", "HEAD")
        assert reports.count(repo.id) == 5
        stored = repos.get(repo.id)
        assert stored.last_collection_status == CollectionStatus.SUCCESS
        assert stored.last_commit_sha == result.commit_sha
        assert stored.last_collected_at == result.finished_at

    def test_reports_without_readable_fields_are_stored_and_listed_as_errors(self, collection_service, repos, reports):
        repo = register(repos)
        result = collection_service.collect(repo.id)
        assert len(result.errors) == 1
        assert "busca" in result.errors[0].path
        assert [r.feature for r in reports.list([repo.id]) if not r.valid] == ["busca"]

    def test_files_outside_the_report_folders_are_ignored(self, collection_service, repos, reports, github):
        github.repositories["acme/app"]["docs/notas.md"] = report_text("2026-01-01", "Aprovado")
        repo = register(repos)
        assert collection_service.collect(repo.id).files_read == 5

    def test_everything_is_read_by_commit_sha_not_by_branch_name(self, repos, reports, github):
        client = RecordingClient(github.repositories)
        service = CollectionService(client, repos, reports)
        result = service.collect(register(repos, branch="projeto-1").id)
        assert {ref for _, ref in client.refs} == {result.commit_sha}
        assert {kind for kind, _ in client.refs} == {"list", "get"}

    def test_unchanged_commit_reads_nothing(self, collection_service, repos):
        repo = register(repos)
        first = collection_service.collect(repo.id, only_if_changed=True)
        second = collection_service.collect(repo.id, only_if_changed=True)
        assert first.status == CollectionStatus.SUCCESS
        assert second.status == CollectionStatus.UNCHANGED
        assert (second.files_read, second.commit_sha) == (0, first.commit_sha)

    def test_unchanged_check_leaves_the_stored_status_untouched(self, collection_service, repos):
        repo = register(repos)
        first = collection_service.collect(repo.id)
        collection_service.collect(repo.id, only_if_changed=True)
        assert repos.get(repo.id).last_collected_at == first.finished_at

    def test_new_commit_triggers_a_new_collection(self, collection_service, repos, github):
        repo = register(repos)
        first = collection_service.collect(repo.id, only_if_changed=True)
        github.repositories["acme/app"][TESTS.format(feature="login", name="t1")] = report_text("2026-04-01", "Aprovado")
        second = collection_service.collect(repo.id, only_if_changed=True)
        assert second.status == CollectionStatus.SUCCESS
        assert second.commit_sha != first.commit_sha
        assert second.files_read == 6

    def test_forced_collection_ignores_the_stored_commit(self, collection_service, repos):
        repo = register(repos)
        collection_service.collect(repo.id)
        assert collection_service.collect(repo.id).status == CollectionStatus.SUCCESS

    def test_never_collected_repository_is_collected_even_if_only_changed_is_requested(self, collection_service, repos):
        assert collection_service.collect(register(repos).id, only_if_changed=True).status == CollectionStatus.SUCCESS

    def test_failure_keeps_data_and_commit_and_the_next_refresh_retries(self, collection_service, repos, reports, github):
        repo = register(repos)
        good = collection_service.collect(repo.id)
        github.repositories["acme/app"]["x.md"] = "mudou"
        github.fail_listing = True

        failed = collection_service.collect(repo.id, only_if_changed=True)
        assert failed.status == CollectionStatus.FAILED
        assert failed.errors and failed.files_read == 0
        assert reports.count(repo.id) == 5
        stored = repos.get(repo.id)
        assert stored.last_collection_status == CollectionStatus.FAILED
        assert stored.last_commit_sha == good.commit_sha

        github.fail_listing = False
        assert collection_service.collect(repo.id, only_if_changed=True).status == CollectionStatus.SUCCESS

    def test_unknown_github_repository_fails_without_raising(self, collection_service, repos):
        result = collection_service.collect(register(repos, "acme/inexistente").id)
        assert result.status == CollectionStatus.FAILED
        assert "não encontrado" in result.errors[0].message

    def test_rate_limit_while_reading_files_fails_and_keeps_old_data(self, repos, reports, github):
        class Limited(InMemoryGitHubClient):
            limited = False

            def get_file(self, full_name, path, ref):
                if self.limited:
                    raise RateLimitError()
                return super().get_file(full_name, path, ref)

        client = Limited(github.repositories)
        service = CollectionService(client, repos, reports)
        repo = register(repos)
        service.collect(repo.id)
        client.repositories["acme/app"]["novo.md"] = "x"
        client.limited = True
        result = service.collect(repo.id)
        assert result.status == CollectionStatus.FAILED
        assert "Limite de requisições" in result.errors[0].message
        assert reports.count(repo.id) == 5

    def test_unreadable_file_is_stored_as_invalid_without_failing_the_collection(self, collection_service, repos, reports, github):
        path = REQ.format(feature="cadastro", name="r1")
        github.failing_paths.add(path)
        repo = register(repos)
        result = collection_service.collect(repo.id)
        assert result.status == CollectionStatus.SUCCESS
        assert any(error.path == path for error in result.errors)
        assert not next(r for r in reports.list([repo.id]) if r.path == path).valid

    def test_storage_failure_is_reported_and_leaves_data_untouched(self, collection_service, repos, reports, monkeypatch):
        repo = register(repos)
        collection_service.collect(repo.id)
        before = repos.get(repo.id).last_commit_sha

        def explode(*args, **kwargs):
            raise RuntimeError("disco cheio")

        monkeypatch.setattr(reports, "replace_for_repository", explode)
        result = collection_service.collect(repo.id)
        assert result.status == CollectionStatus.FAILED
        assert "Erro ao gravar" in result.errors[0].message
        assert repos.get(repo.id).last_commit_sha == before

    def test_collect_unknown_repository_raises(self, collection_service):
        with pytest.raises(NotFoundError):
            collection_service.collect(99)

    def test_collect_many_covers_all_or_the_selected_repositories(self, collection_service, repos):
        first, second = register(repos, "acme/app"), register(repos, "acme/other")
        assert [r.repository_id for r in collection_service.collect_many()] == [first.id, second.id]
        assert [r.repository_id for r in collection_service.collect_many([second.id, second.id])] == [second.id]

    def test_collect_many_validates_ids_before_collecting_anything(self, collection_service, repos):
        repo = register(repos)
        with pytest.raises(NotFoundError):
            collection_service.collect_many([repo.id, 99])
        assert repos.get(repo.id).last_collected_at is None

    def test_collect_many_without_repositories_is_empty(self, collection_service):
        assert collection_service.collect_many() == []


class TestDashboardService:
    def collect(self, collection_service, repos, *names):
        for name in names:
            collection_service.collect(register(repos, name).id)

    def test_always_returns_the_five_phases_in_order(self, dashboard_service):
        dashboard = dashboard_service.build()
        assert [item.phase for item in dashboard.phases] == list(Phase)
        assert all(item.total == 0 and item.verdicts == [] for item in dashboard.phases)
        assert dashboard.last_collected_at is None

    def test_latest_valid_report_decides_each_feature(self, dashboard_service, collection_service, repos):
        self.collect(collection_service, repos, "acme/app")
        dashboard = dashboard_service.build()
        # login: reprovado -> aprovado; cadastro: aprovado; busca: sem data => inválido
        assert verdicts(dashboard, "requirements") == {"Aprovado": 2, INVALID_LABEL: 1}
        assert verdicts(dashboard, "code") == {"Reprovado": 1}
        assert verdicts(dashboard, "tests") == {}

    def test_feature_with_a_valid_and_an_invalid_report_uses_the_valid_one(self, dashboard_service, collection_service, repos, github):
        github.repositories["acme/app"][REQ.format(feature="busca", name="r2")] = report_text("2026-03-01", "Reprovado")
        self.collect(collection_service, repos, "acme/app")
        assert verdicts(dashboard_service.build(), "requirements") == {"Aprovado": 2, "Reprovado": 1}

    def test_verdicts_that_differ_only_in_case_are_grouped_under_the_first_spelling(self, dashboard_service, collection_service, repos, github):
        github.repositories["acme/other"][REQ.format(feature="x", name="r1")] = report_text("2026-01-02", "APROVADO")
        self.collect(collection_service, repos, "acme/other")
        assert verdicts(dashboard_service.build(), "requirements") == {"Aprovado": 2}

    def test_same_feature_in_two_repositories_counts_twice(self, dashboard_service, collection_service, repos):
        self.collect(collection_service, repos, "acme/app", "acme/other")
        assert sum(verdicts(dashboard_service.build(), "requirements").values()) == 4

    def test_filters_by_repository_and_ignores_unknown_ids(self, dashboard_service, collection_service, repos):
        self.collect(collection_service, repos, "acme/app", "acme/other")
        only_other = dashboard_service.build([2, 99])
        assert only_other.repository_ids == [2]
        assert verdicts(only_other, "requirements") == {"Aprovado": 1}

    def test_empty_filter_selects_nothing(self, dashboard_service, collection_service, repos):
        self.collect(collection_service, repos, "acme/app")
        dashboard = dashboard_service.build([])
        assert dashboard.repository_ids == []
        assert all(item.total == 0 for item in dashboard.phases)

    def test_last_collected_at_is_the_newest_of_the_selected_repositories(self, dashboard_service, collection_service, repos):
        self.collect(collection_service, repos, "acme/app", "acme/other")
        newest = repos.get(2).last_collected_at
        assert dashboard_service.build().last_collected_at == newest
        assert dashboard_service.build([1]).last_collected_at == repos.get(1).last_collected_at

    def test_verdicts_are_sorted_with_invalid_last(self, dashboard_service, collection_service, repos):
        self.collect(collection_service, repos, "acme/app")
        labels = [item.verdict for item in dashboard_service.build().phases[0].verdicts]
        assert labels == ["Aprovado", INVALID_LABEL]


class TestTrendService:
    def collect(self, collection_service, repos, *names):
        for name in names:
            collection_service.collect(register(repos, name).id)

    def test_no_data_returns_an_empty_trend(self, trend_service):
        trend = trend_service.build()
        assert trend.phase == Phase.TESTS
        assert trend.dates == [] and trend.series == []

    def test_points_are_weekly_and_include_the_last_report_date(self, trend_service, collection_service, repos):
        self.collect(collection_service, repos, "acme/app")
        trend = trend_service.build(phase=Phase.REQUIREMENTS)
        assert trend.dates[0] == date(2026, 1, 1)
        assert trend.dates[-1] == date(2026, 2, 1)
        assert all((b - a).days == 7 for a, b in zip(trend.dates, trend.dates[1:-1]))

    def test_verdict_in_force_changes_when_a_newer_report_arrives(self, trend_service, collection_service, repos):
        self.collect(collection_service, repos, "acme/app")
        series = {s.verdict: s.counts for s in trend_service.build(phase=Phase.REQUIREMENTS).series}
        assert series["Reprovado"] == [1, 1, 1, 1, 1, 0]
        assert series["Aprovado"] == [0, 1, 1, 1, 1, 2]

    def test_single_report_produces_a_single_point(self, trend_service, collection_service, repos):
        self.collect(collection_service, repos, "acme/other")
        trend = trend_service.build(phase=Phase.REQUIREMENTS)
        assert trend.dates == [date(2026, 1, 1)]
        assert [(s.verdict, s.counts) for s in trend.series] == [("Aprovado", [1])]

    def test_reports_without_a_valid_date_never_enter_the_timeline(self, trend_service, collection_service, repos, github):
        github.repositories["acme/other"] = {REQ.format(feature="x", name="r"): report_text(None, "Aprovado")}
        self.collect(collection_service, repos, "acme/other")
        assert trend_service.build(phase=Phase.REQUIREMENTS).dates == []

    def test_features_enter_the_count_only_after_their_first_valid_report(self, trend_service, collection_service, repos):
        self.collect(collection_service, repos, "acme/app")
        trend = trend_service.build(phase=Phase.REQUIREMENTS)
        totals = [sum(column) for column in zip(*(s.counts for s in trend.series))]
        assert totals == [1, 2, 2, 2, 2, 2]

    def test_filters_by_phase_and_repository_and_ignores_unknown_ids(self, trend_service, collection_service, repos):
        self.collect(collection_service, repos, "acme/app", "acme/other")
        assert trend_service.build([2, 99], Phase.REQUIREMENTS).repository_ids == [2]
        assert trend_service.build([1], Phase.CODE).series[0].verdict == "Reprovado"
        assert trend_service.build([2], Phase.CODE).dates == []

    def test_never_touches_github(self, trend_service, collection_service, repos, github):
        self.collect(collection_service, repos, "acme/app")

        def forbidden(*args, **kwargs):
            raise AssertionError("A tendência não deve acessar o GitHub.")

        github.get_head_commit = github.list_files = github.get_file = forbidden
        assert trend_service.build(phase=Phase.REQUIREMENTS).dates


class TestSharedTrendAxis:
    """Todos os gráficos de tendência devem usar as mesmas datas no eixo horizontal."""

    @pytest.fixture
    def two_repositories(self, trend_service, collection_service, repos):
        for name in ("acme/app", "acme/other"):  # relatórios de 01/01 a 01/02 e só de 01/01
            collection_service.collect(repos.create(RepositoryCreate(full_name=name)).id)

    def test_without_limits_each_repository_has_its_own_range(self, two_repositories, trend_service):
        assert len(trend_service.build([1], Phase.REQUIREMENTS).dates) == 6
        assert trend_service.build([2], Phase.REQUIREMENTS).dates == [date(2026, 1, 1)]

    def test_same_limits_give_every_repository_the_same_dates(self, two_repositories, trend_service):
        common = trend_service.build(phase=Phase.REQUIREMENTS)  # todos os repositórios
        start, end = common.dates[0], common.dates[-1]
        first = trend_service.build([1], Phase.REQUIREMENTS, start, end)
        second = trend_service.build([2], Phase.REQUIREMENTS, start, end)
        assert first.dates == second.dates == common.dates

    def test_values_follow_the_report_dates_inside_the_common_axis(self, two_repositories, trend_service):
        second = trend_service.build([2], Phase.REQUIREMENTS, date(2025, 12, 25), date(2026, 1, 15))
        assert second.dates == [date(2025, 12, 25), date(2026, 1, 1), date(2026, 1, 8), date(2026, 1, 15)]
        # a feature só entra na contagem a partir do primeiro relatório e permanece depois
        assert second.series[0].counts == [0, 1, 1, 1]

    def test_end_is_always_the_last_point(self, two_repositories, trend_service):
        trend = trend_service.build([1], Phase.REQUIREMENTS, date(2026, 1, 1), date(2026, 1, 10))
        assert trend.dates == [date(2026, 1, 1), date(2026, 1, 8), date(2026, 1, 10)]

    def test_only_start_or_only_end_never_produces_an_empty_axis(self, two_repositories, trend_service):
        late_start = trend_service.build([2], Phase.REQUIREMENTS, start=date(2026, 3, 1))
        early_end = trend_service.build([2], Phase.REQUIREMENTS, end=date(2025, 12, 1))
        assert late_start.dates == [date(2026, 3, 1)] and late_start.series[0].counts == [1]
        assert early_end.dates == [date(2025, 12, 1)] and early_end.series == []

    def test_repository_without_reports_stays_empty_even_with_limits(self, two_repositories, trend_service):
        empty = trend_service.build([1], Phase.TESTS, date(2026, 1, 1), date(2026, 2, 1))
        assert empty.dates == [] and empty.series == []
