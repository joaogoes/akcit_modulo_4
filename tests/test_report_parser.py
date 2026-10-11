"""Leitura de `generated` e `verdict` e mapa de pastas das fases."""

from datetime import UTC, datetime

import pytest

from app.models import Phase
from app.services import PHASE_LAYOUTS, match_report, parse_report


class TestParseReport:
    def test_reads_front_matter(self):
        parsed = parse_report('---\ngenerated: "2026-10-10T10:00:00Z"\nverdict: Aprovado\n---\n')
        assert parsed.generated == datetime(2026, 10, 10, 10, tzinfo=UTC)
        assert parsed.verdict == "Aprovado"

    def test_reads_fields_from_the_body(self):
        parsed = parse_report("# Título\n\n- Verdict: Reprovado\n- Generated: 2026-10-10\n")
        assert parsed.verdict == "Reprovado"
        assert parsed.generated == datetime(2026, 10, 10)

    def test_ignores_markdown_emphasis_around_keys_and_values(self):
        parsed = parse_report("**generated:** 2026-10-10\n**verdict**: **Aprovado**\n")
        assert parsed.verdict == "Aprovado"
        assert parsed.generated is not None

    def test_keeps_the_first_occurrence_of_each_field(self):
        parsed = parse_report("verdict: Aprovado\nverdict: Reprovado\ngenerated: 2026-01-01\ngenerated: 2026-02-02\n")
        assert parsed.verdict == "Aprovado"
        assert parsed.generated == datetime(2026, 1, 1)

    def test_key_matching_ignores_case_and_leading_spaces(self):
        assert parse_report("   VERDICT:   ok  ").verdict == "ok"

    def test_verdict_keeps_inner_spaces(self):
        assert parse_report("verdict: Aprovado com ressalvas").verdict == "Aprovado com ressalvas"

    @pytest.mark.parametrize("text", ["", "sem campos", "verdict:", "verdict:   \n"])
    def test_missing_or_empty_verdict_is_none(self, text):
        assert parse_report(text).verdict is None

    @pytest.mark.parametrize("value", ["ontem", "2026-13-45", "10/10/2026", ""])
    def test_unreadable_date_is_none(self, value):
        assert parse_report(f"generated: {value}").generated is None

    @pytest.mark.parametrize("value", ["2026-10-10", "2026-10-10T10:00:00", "2026-10-10T10:00:00Z", "2026-10-10T10:00:00+02:00"])
    def test_iso_8601_dates_are_accepted(self, value):
        assert parse_report(f"generated: {value}").generated is not None

    def test_text_without_colon_is_not_a_field(self):
        assert parse_report("o verdict final foi aprovado").verdict is None


class TestMatchReport:
    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            ("200 Requirements/230 Output/login/reports/req-validation/a.md", (Phase.REQUIREMENTS, "login")),
            ("300 Specs/320 F-Specs/Output/login/reports/fspec-validation/a.md", (Phase.FSPEC, "login")),
            ("300 Specs/330 D-Specs/Output/login/reports/dspec-validation/a.md", (Phase.DSPEC, "login")),
            ("400 Code/Output/pedidos-cadastro/reports/code-validation/a.md", (Phase.CODE, "pedidos-cadastro")),
            ("500 Tests/Output/login/reports/code-tests/a.md", (Phase.TESTS, "login")),
            ("500 Tests/Output/login/reports/code-tests/A.MD", (Phase.TESTS, "login")),
        ],
    )
    def test_report_paths_resolve_to_phase_and_feature(self, path, expected):
        assert match_report(path) == expected

    @pytest.mark.parametrize(
        "path",
        [
            "README.md",
            "200 Requirements/230 Output/login/reports/req-validation/sub/a.md",
            "200 Requirements/230 Output/login/reports/req-validation/a.txt",
            "200 Requirements/230 Output/login/reports/code-validation/a.md",
            "200 Requirements/230 Output/login/docs/req-validation/a.md",
            "200 Requirements/Output/login/reports/req-validation/a.md",
            "200 Requirements/230 Output/reports/req-validation/a.md",
            "600 Deploy/Output/login/reports/deploy/a.md",
            "",
        ],
    )
    def test_other_paths_are_not_reports(self, path):
        assert match_report(path) is None

    def test_every_phase_has_exactly_one_layout_in_display_order(self):
        assert [layout.phase for layout in PHASE_LAYOUTS] == list(Phase)
