"""Persistência: repositórios cadastrados e relatórios."""

from datetime import UTC, datetime

import pytest

from app.models import CollectionStatus, Phase, RepositoryCreate
from app.repositories import DuplicateRepositoryError, NotFoundError
from tests.helpers import make_report


def create(repos, name="acme/app", branch=None):
    return repos.create(RepositoryCreate(full_name=name, branch=branch))


class TestRepoRepository:
    def test_create_returns_the_stored_repository(self, repos):
        repo = create(repos, "acme/app", "dev")
        assert (repo.id, repo.full_name, repo.branch) == (1, "acme/app", "dev")
        assert repo.created_at is not None
        assert repo.last_collected_at is None
        assert repo.last_collection_status is None
        assert repo.last_commit_sha is None

    def test_same_repository_can_be_registered_once_per_branch(self, repos):
        first, second, default = create(repos, branch="a"), create(repos, branch="b"), create(repos)
        assert len({first.id, second.id, default.id}) == 3

    @pytest.mark.parametrize(("name", "branch"), [("acme/app", "dev"), ("ACME/App", "dev"), ("acme/app", None)])
    def test_duplicate_name_and_branch_is_rejected(self, repos, name, branch):
        create(repos, "acme/app", "dev")
        create(repos, "acme/app", None)
        with pytest.raises(DuplicateRepositoryError) as error:
            create(repos, name, branch)
        assert name in str(error.value)

    def test_get_unknown_id_raises_not_found(self, repos):
        with pytest.raises(NotFoundError):
            repos.get(99)

    def test_get_by_full_name_matches_branch_and_ignores_case(self, repos):
        dev = create(repos, "acme/app", "dev")
        default = create(repos, "acme/app")
        assert repos.get_by_full_name("ACME/APP", "dev").id == dev.id
        assert repos.get_by_full_name("acme/app").id == default.id
        assert repos.get_by_full_name("acme/app", "other") is None
        assert repos.get_by_full_name("acme/missing") is None

    def test_list_follows_registration_order(self, repos):
        create(repos, "acme/b")
        create(repos, "acme/a")
        assert [repo.full_name for repo in repos.list()] == ["acme/b", "acme/a"]

    def test_update_branch_changes_and_clears_the_branch(self, repos):
        repo = create(repos)
        assert repos.update_branch(repo.id, "dev").branch == "dev"
        assert repos.update_branch(repo.id, None).branch is None

    def test_update_branch_unknown_id_raises_not_found(self, repos):
        with pytest.raises(NotFoundError):
            repos.update_branch(99, "dev")

    def test_update_branch_to_an_existing_pair_is_rejected(self, repos):
        create(repos, branch="dev")
        other = create(repos, branch="main")
        with pytest.raises(Exception):  # noqa: B017 - violação de unicidade do SQLite
            repos.update_branch(other.id, "dev")

    def test_record_collection_stores_status_date_and_commit(self, repos):
        repo = create(repos)
        when = datetime(2026, 10, 10, 12, tzinfo=UTC)
        repos.record_collection(repo.id, CollectionStatus.SUCCESS, when, "abc123")
        stored = repos.get(repo.id)
        assert stored.last_collection_status == CollectionStatus.SUCCESS
        assert stored.last_collected_at == when
        assert stored.last_commit_sha == "abc123"

    def test_failed_collection_keeps_the_previous_commit(self, repos):
        repo = create(repos)
        repos.record_collection(repo.id, CollectionStatus.SUCCESS, commit_sha="abc123")
        repos.record_collection(repo.id, CollectionStatus.FAILED)
        stored = repos.get(repo.id)
        assert stored.last_collection_status == CollectionStatus.FAILED
        assert stored.last_commit_sha == "abc123"

    def test_record_collection_unknown_id_raises_not_found(self, repos):
        with pytest.raises(NotFoundError):
            repos.record_collection(99, CollectionStatus.SUCCESS)

    def test_delete_reports_whether_the_repository_existed(self, repos):
        repo = create(repos)
        assert repos.delete(repo.id) is True
        assert repos.delete(repo.id) is False

    def test_delete_removes_the_repository_reports(self, repos, reports):
        repo = create(repos)
        reports.replace_for_repository(repo.id, [make_report(repo.id)])
        repos.delete(repo.id)
        assert reports.count(repo.id) == 0


class TestReportRepository:
    def test_replace_stores_every_iteration_with_dates_and_verdicts(self, repos, reports):
        repo = create(repos)
        reports.replace_for_repository(repo.id, [
            make_report(repo.id, generated="2026-01-01T10:00:00Z", verdict="Reprovado"),
            make_report(repo.id, generated="2026-02-01T10:00:00Z", verdict="Aprovado"),
        ])
        stored = reports.list([repo.id])
        assert [report.verdict for report in stored] == ["Reprovado", "Aprovado"]
        assert stored[0].generated == datetime(2026, 1, 1, 10, tzinfo=UTC)

    def test_invalid_reports_are_stored_without_date_or_verdict(self, repos, reports):
        repo = create(repos)
        reports.replace_for_repository(repo.id, [make_report(repo.id, generated=None, verdict=None)])
        [stored] = reports.list()
        assert stored.generated is None and stored.verdict is None and stored.valid is False

    def test_replace_overwrites_only_that_repository(self, repos, reports):
        first, second = create(repos, "acme/a"), create(repos, "acme/b")
        reports.replace_for_repository(first.id, [make_report(first.id, feature="old")])
        reports.replace_for_repository(second.id, [make_report(second.id, feature="keep")])
        reports.replace_for_repository(first.id, [make_report(first.id, feature="new")])
        assert [r.feature for r in reports.list([first.id])] == ["new"]
        assert [r.feature for r in reports.list([second.id])] == ["keep"]

    def test_replace_is_atomic_when_an_insert_fails(self, repos, reports):
        repo = create(repos)
        reports.replace_for_repository(repo.id, [make_report(repo.id, feature="antes")])
        with pytest.raises(AttributeError):
            reports.replace_for_repository(repo.id, [make_report(repo.id, feature="novo"), "inválido"])
        assert [r.feature for r in reports.list([repo.id])] == ["antes"]

    def test_replace_with_an_empty_list_clears_the_repository(self, repos, reports):
        repo = create(repos)
        reports.replace_for_repository(repo.id, [make_report(repo.id)])
        reports.replace_for_repository(repo.id, [])
        assert reports.count(repo.id) == 0

    def test_list_filters_by_repository_and_phase(self, repos, reports):
        first, second = create(repos, "acme/a"), create(repos, "acme/b")
        reports.replace_for_repository(first.id, [
            make_report(first.id, phase="requirements"), make_report(first.id, phase="code"),
        ])
        reports.replace_for_repository(second.id, [make_report(second.id, phase="code")])
        assert len(reports.list()) == 3
        assert len(reports.list([first.id])) == 2
        assert len(reports.list(phase=Phase.CODE)) == 2
        assert len(reports.list([second.id], Phase.CODE)) == 1
        assert reports.list([second.id], Phase.TESTS) == []

    def test_list_with_an_empty_id_list_returns_nothing(self, repos, reports):
        repo = create(repos)
        reports.replace_for_repository(repo.id, [make_report(repo.id)])
        assert reports.list([]) == []

    def test_list_is_ordered_by_repository_phase_and_feature(self, repos, reports):
        repo = create(repos)
        reports.replace_for_repository(repo.id, [
            make_report(repo.id, phase="tests", feature="b"),
            make_report(repo.id, phase="code", feature="z"),
            make_report(repo.id, phase="code", feature="a"),
        ])
        assert [(r.phase.value, r.feature) for r in reports.list()] == [
            ("code", "a"), ("code", "z"), ("tests", "b"),
        ]

    def test_delete_for_repository_returns_the_removed_count(self, repos, reports):
        repo = create(repos)
        reports.replace_for_repository(repo.id, [make_report(repo.id), make_report(repo.id, feature="b")])
        assert reports.delete_for_repository(repo.id) == 2
        assert reports.delete_for_repository(repo.id) == 0
