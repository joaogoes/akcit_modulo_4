"""Estrutura de pastas dos relatórios por fase (seção 2 do escopo)."""

from dataclasses import dataclass

from app.models import Phase


@dataclass(frozen=True)
class PhaseLayout:
    """Onde ficam os relatórios de uma fase.

    Caminho: `<base>/<feature>/reports/<reports_dir>/<arquivo>.md`.
    """

    phase: Phase
    base: tuple[str, ...]
    reports_dir: str


PHASE_LAYOUTS: tuple[PhaseLayout, ...] = (
    PhaseLayout(Phase.REQUIREMENTS, ("200 Requirements", "230 Output"), "req-validation"),
    PhaseLayout(Phase.FSPEC, ("300 Specs", "320 F-Specs", "Output"), "fspec-validation"),
    PhaseLayout(Phase.DSPEC, ("300 Specs", "330 D-Specs", "Output"), "dspec-validation"),
    PhaseLayout(Phase.CODE, ("400 Code", "Output"), "code-validation"),
    PhaseLayout(Phase.TESTS, ("500 Tests", "Output"), "code-tests"),
)


def match_report(path: str) -> tuple[Phase, str] | None:
    """Devolve `(fase, feature)` se `path` for um relatório `*.md`; senão `None`.

    O caminho usa `/` (API do GitHub). Subpastas dentro da pasta de relatórios
    não são consideradas (RF-06).
    """
    parts = path.split("/")
    for layout in PHASE_LAYOUTS:
        size = len(layout.base)
        if (
            len(parts) == size + 4
            and tuple(parts[:size]) == layout.base
            and parts[size + 1] == "reports"
            and parts[size + 2] == layout.reports_dir
            and parts[-1].lower().endswith(".md")
        ):
            return layout.phase, parts[size]
    return None
