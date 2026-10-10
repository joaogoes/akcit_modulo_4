"""Extração de `generated` e `verdict` de um relatório (RF-07, P-02, P-04)."""

import re
from dataclasses import dataclass
from datetime import datetime

_FIELD = re.compile(
    r"^[ \t>*_-]*(?P<key>generated|verdict)[ \t*_]*:[ \t*_]*(?P<value>.*)$",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True)
class ParsedReport:
    """Campos lidos de um relatório; `None` quando ausentes ou ilegíveis."""

    generated: datetime | None
    verdict: str | None


def parse_report(text: str) -> ParsedReport:
    """Lê as linhas `generated: ...` e `verdict: ...`, em front matter ou no corpo.

    Vale a primeira ocorrência de cada campo. `generated` aceita ISO 8601.
    """
    found: dict[str, str] = {}
    for match in _FIELD.finditer(text):
        value = match["value"].strip().strip("*`'\" ").strip()
        found.setdefault(match["key"].lower(), value)
    return ParsedReport(
        generated=_parse_date(found.get("generated")),
        verdict=found.get("verdict") or None,
    )


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
