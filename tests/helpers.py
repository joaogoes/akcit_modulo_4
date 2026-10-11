"""Constantes e funções de apoio compartilhadas pelos testes."""

from app.models import Report

REQ = "200 Requirements/230 Output/{feature}/reports/req-validation/{name}.md"
FSPEC = "300 Specs/320 F-Specs/Output/{feature}/reports/fspec-validation/{name}.md"
DSPEC = "300 Specs/330 D-Specs/Output/{feature}/reports/dspec-validation/{name}.md"
CODE = "400 Code/Output/{feature}/reports/code-validation/{name}.md"
TESTS = "500 Tests/Output/{feature}/reports/code-tests/{name}.md"


def report_text(generated: str | None, verdict: str | None) -> str:
    """Relatório `.md` com front matter; campos `None` são omitidos."""
    lines = ["---"]
    if generated:
        lines.append(f"generated: {generated}")
    if verdict:
        lines.append(f"verdict: {verdict}")
    return "\n".join([*lines, "---", "", "# Relatório", ""])


def make_report(
    repository_id: int = 1,
    phase: str = "requirements",
    feature: str = "login",
    generated: str | None = "2026-01-01T10:00:00Z",
    verdict: str | None = "Aprovado",
    path: str | None = None,
) -> Report:
    """`Report` pronto para gravar, com valores padrão válidos."""
    return Report(
        repository_id=repository_id,
        phase=phase,
        feature=feature,
        path=path or f"{phase}/{feature}.md",
        generated=generated,
        verdict=verdict,
    )


def counts(dashboard: dict, phase: str) -> dict[str, int]:
    """`{veredito: total}` de uma fase na resposta de `/api/dashboard`."""
    summary = next(item for item in dashboard["phases"] if item["phase"] == phase)
    return {item["verdict"]: item["count"] for item in summary["verdicts"]}
