"""Rotas dos tokens de acesso por provedor (RF-22). Os valores nunca são devolvidos."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.dependencies import get_token_service
from app.models import Provider, TokenSettings, TokenStatus, TokenUpdate
from app.protection import ProtectionError
from app.services import TokenService

router = APIRouter(prefix="/settings/tokens", tags=["settings"])

Tokens = Annotated[TokenService, Depends(get_token_service)]

MAX_TOKEN_LENGTH = 2048


@router.get("", response_model=TokenSettings)
def get_token_settings(tokens: Tokens) -> TokenSettings:
    """Mostra, por provedor, se há token e de onde ele vem (banco ou variável de ambiente)."""
    return tokens.status()


@router.put(
    "/{provider}",
    response_model=TokenStatus,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Sem armazenamento protegido."}},
)
def save_token(provider: Provider, body: TokenUpdate, tokens: Tokens) -> TokenStatus:
    """Salva o token cifrado. A validação é manual para que os erros nunca repitam o valor enviado."""
    token = "".join(body.token.get_secret_value().split())  # remove espaços e quebras de linha coladas
    if not token:
        raise HTTPException(422, detail="Informe o token.")
    if len(token) > MAX_TOKEN_LENGTH:
        raise HTTPException(422, detail="O token informado é longo demais.")
    try:
        return tokens.save(provider, token)
    except ProtectionError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.delete(
    "/{provider}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Não há token salvo no banco."}},
)
def delete_token(provider: Provider, tokens: Tokens) -> Response:
    """Apaga o token salvo; a variável de ambiente, se existir, passa a valer."""
    if not tokens.remove(provider):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Não há token salvo para o {provider.label}.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
