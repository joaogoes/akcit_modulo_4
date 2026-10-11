"""Validações dos modelos Pydantic."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.models import (
    INVALID_LABEL,
    CollectionRequest,
    Phase,
    PhaseSummary,
    Report,
    RepositoryCreate,
    RepositoryUpdate,
    Trend,
    TrendSeries,
    VerdictCount,
)
from tests.helpers import make_report


class TestPhase:
    def test_phases_are_listed_in_display_order(self):
        assert [phase.value for phase in Phase] == ["requirements", "fspec", "dspec", "code", "tests"]


class TestRepositoryCreate:
    @pytest.mark.parametrize(
        "value",
        [
            "https://github.com/acme/app",
            "https://github.com/acme/app/",
            "https://github.com/acme/app.git",
            "http://github.com/acme/app",
            "  acme/app  ",
        ],
    )
    def test_urls_and_padded_names_are_normalized_to_owner_repo(self, value):
        assert RepositoryCreate(full_name=value).full_name == "acme/app"

    @pytest.mark.parametrize("value", ["", "app", "a/b/c", "acme/", "/app", "https://gitlab.com/acme/app", "acme app/x"])
    def test_invalid_names_are_rejected(self, value):
        with pytest.raises(ValidationError):
            RepositoryCreate(full_name=value)

    def test_branch_is_optional_and_stripped(self):
        assert RepositoryCreate(full_name="acme/app").branch is None
        assert RepositoryCreate(full_name="acme/app", branch=" dev ").branch == "dev"

    def test_empty_branch_is_rejected(self):
        with pytest.raises(ValidationError):
            RepositoryCreate(full_name="acme/app", branch="")


class TestRepositoryUpdate:
    def test_null_branch_means_default_branch(self):
        assert RepositoryUpdate(branch=None).branch is None

    def test_empty_branch_is_rejected(self):
        with pytest.raises(ValidationError):
            RepositoryUpdate(branch="")


class TestReport:
    def test_report_with_verdict_and_date_is_valid(self):
        assert make_report().valid is True

    @pytest.mark.parametrize("fields", [{"verdict": None}, {"generated": None}, {"verdict": ""}, {"verdict": "  "}])
    def test_report_missing_verdict_or_date_is_invalid(self, fields):
        assert make_report(**fields).valid is False

    def test_naive_dates_are_assumed_to_be_utc(self):
        report = make_report(generated="2026-10-10T10:00:00")
        assert report.generated == datetime(2026, 10, 10, 10, tzinfo=UTC)

    def test_date_only_values_are_accepted(self):
        assert make_report(generated="2026-10-10").generated.date().isoformat() == "2026-10-10"

    def test_explicit_timezone_is_preserved(self):
        report = make_report(generated="2026-10-10T10:00:00-03:00")
        assert report.generated.utcoffset().total_seconds() == -3 * 3600

    def test_verdict_key_ignores_case_and_outer_spaces(self):
        assert make_report(verdict="  Aprovado Com Ressalvas ").verdict_key == "aprovado com ressalvas"
        assert make_report(verdict=None).verdict_key is None

    def test_invalid_phase_is_rejected(self):
        with pytest.raises(ValidationError):
            make_report(phase="deploy")


class TestPhaseSummary:
    def test_verdicts_are_sorted_alphabetically_with_invalid_last(self):
        summary = PhaseSummary(
            phase="code",
            total=4,
            verdicts=[
                VerdictCount(verdict=INVALID_LABEL, count=1),
                VerdictCount(verdict="reprovado", count=1),
                VerdictCount(verdict="Aprovado", count=1),
                VerdictCount(verdict="Aprovado com ressalvas", count=1),
            ],
        )
        assert [item.verdict for item in summary.verdicts] == [
            "Aprovado", "Aprovado com ressalvas", "reprovado", INVALID_LABEL,
        ]

    def test_total_must_match_the_sum_of_verdicts(self):
        with pytest.raises(ValidationError):
            PhaseSummary(phase="code", total=5, verdicts=[VerdictCount(verdict="Aprovado", count=1)])

    def test_negative_counts_are_rejected(self):
        with pytest.raises(ValidationError):
            VerdictCount(verdict="Aprovado", count=-1)

    def test_empty_phase_is_valid(self):
        assert PhaseSummary(phase="tests", total=0, verdicts=[]).verdicts == []


class TestCollectionRequest:
    def test_defaults_collect_everything_unconditionally(self):
        request = CollectionRequest()
        assert request.repository_ids is None
        assert request.only_if_changed is False

    def test_empty_id_list_is_rejected(self):
        with pytest.raises(ValidationError):
            CollectionRequest(repository_ids=[])


class TestTrend:
    def test_each_series_needs_one_value_per_date(self):
        with pytest.raises(ValidationError):
            Trend(
                phase="tests",
                repository_ids=[1],
                dates=["2026-01-01", "2026-01-08"],
                series=[TrendSeries(verdict="Aprovado", counts=[1])],
            )
