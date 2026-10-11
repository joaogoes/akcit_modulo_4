"""Repositórios cadastrados no primeiro uso da aplicação."""

from app.models import RepositoryCreate
from app.repositories import RepoRepository

DEFAULT_REPOSITORIES: tuple[RepositoryCreate, ...] = (
    RepositoryCreate(full_name="joaogoes/akcit_modulo_4_repo", branch="projeto-1"),
    RepositoryCreate(full_name="joaogoes/akcit_modulo_4_repo", branch="projeto-2"),
)


def seed_default_repositories(repos: RepoRepository) -> None:
    """Cadastra os repositórios de exemplo; a coleta continua sob demanda."""
    for data in DEFAULT_REPOSITORIES:
        repos.create(data)
