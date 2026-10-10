"""Fases do projeto e rótulos reservados."""

from enum import StrEnum

INVALID_LABEL = "Inválido"


class Phase(StrEnum):
    """Fases cujos relatórios são coletados, na ordem de exibição."""

    REQUIREMENTS = "requirements"
    FSPEC = "fspec"
    DSPEC = "dspec"
    CODE = "code"
    TESTS = "tests"
