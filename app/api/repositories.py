"""Rotas de cadastro de repositórios (RF-01 a RF-04)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.models import RepositoryCreate, RepositoryRead, RepositoryUpdate
from app.repositories import DuplicateRepositoryError, NotFoundError, RepoRepository

router = APIRouter(prefix="/repositories", tags=["repositories"])


def get_repo_repository(request: Request) -> RepoRepository:
    """Cria o repositório de dados a partir do `Database` em `app.state.db`."""
    return RepoRepository(request.app.state.db)


Repos = Annotated[RepoRepository, Depends(get_repo_repository)]

_NOT_FOUND = {status.HTTP_404_NOT_FOUND: {"description": "Repositório não encontrado."}}


@router.post(
    "",
    response_model=RepositoryRead,
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_409_CONFLICT: {"description": "Repositório já cadastrado."}},
)
def create_repository(
    data: RepositoryCreate, response: Response, repos: Repos
) -> RepositoryRead:
    """Cadastra um repositório."""
    try:
        created = repos.create(data)
    except DuplicateRepositoryError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Repositório já cadastrado: {data.full_name}.",
        ) from exc
    response.headers["Location"] = f"/repositories/{created.id}"
    return created


@router.get("", response_model=list[RepositoryRead])
def list_repositories(repos: Repos) -> list[RepositoryRead]:
    """Lista os repositórios cadastrados."""
    return repos.list()


@router.get("/{repository_id}", response_model=RepositoryRead, responses=_NOT_FOUND)
def get_repository(repository_id: int, repos: Repos) -> RepositoryRead:
    """Busca um repositório pelo id."""
    try:
        return repos.get(repository_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/{repository_id}", response_model=RepositoryRead, responses=_NOT_FOUND)
def update_repository(
    repository_id: int, data: RepositoryUpdate, repos: Repos
) -> RepositoryRead:
    """Substitui a branch do repositório."""
    try:
        return repos.update_branch(repository_id, data.branch)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete(
    "/{repository_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_NOT_FOUND,
)
def delete_repository(repository_id: int, repos: Repos) -> None:
    """Remove o repositório e seus relatórios."""
    if not repos.delete(repository_id):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Repositório {repository_id} não encontrado.",
        )
