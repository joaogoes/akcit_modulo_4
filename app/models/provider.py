"""Provedores de repositórios suportados."""

from enum import StrEnum


class Provider(StrEnum):
    """Onde o repositório está hospedado."""

    GITHUB = "github"
    AZURE_DEVOPS = "azure_devops"

    @property
    def label(self) -> str:
        """Nome para exibição."""
        return "Azure DevOps" if self is Provider.AZURE_DEVOPS else "GitHub"
