"""Rota de coleta sob demanda (RF-11)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_collection_service
from app.models import CollectionRead, CollectionRequest
from app.repositories import NotFoundError
from app.services import CollectionService

router = APIRouter(prefix="/collections", tags=["collections"])


@router.post(
    "",
    response_model=list[CollectionRead],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Repositório não encontrado."}},
)
def run_collection(
    service: Annotated[CollectionService, Depends(get_collection_service)],
    body: CollectionRequest | None = None,
) -> list[CollectionRead]:
    """Coleta os repositórios informados ou, sem corpo, todos os cadastrados."""
    try:
        return service.collect_many(body.repository_ids if body else None)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
