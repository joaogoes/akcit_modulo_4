"""Escolha dos repositórios considerados em uma consulta."""

from collections.abc import Sequence

from app.models import RepositoryRead
from app.repositories import RepoRepository


def resolve_repository_ids(
    repos: RepoRepository, repository_ids: Sequence[int] | None
) -> tuple[dict[int, RepositoryRead], list[int]]:
    """Repositórios cadastrados e os ids pedidos que existem (todos, se `repository_ids` for `None`)."""
    known = {repo.id: repo for repo in repos.list()}
    wanted = known if repository_ids is None else repository_ids
    return known, sorted({repo_id for repo_id in wanted if repo_id in known})
