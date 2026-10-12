"""Aplicação FastAPI: API e interface web.

Execução: `uvicorn app.main:create_app --factory`.
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import collections, dashboard, repositories, settings, trend
from app.azure_devops import HttpAzureDevOpsClient
from app.defaults import seed_default_repositories
from app.github import GitHubClient, HttpGitHubClient
from app.models import Provider
from app.protection import SecretProtector, default_protector
from app.repositories import CredentialRepository, Database, RepoRepository
from app.services import TokenService

STATIC_DIR = Path(__file__).parent / "static"


def create_app(
    db: Database | None = None,
    github: GitHubClient | None = None,
    azure: GitHubClient | None = None,
    protector: SecretProtector | None = None,
) -> FastAPI:
    """Monta a aplicação.

    Sem argumentos, usa o banco de `DATABASE_PATH` e os tokens salvos nele (cifrados com o DPAPI
    do Windows) ou, na falta deles, `GITHUB_TOKEN` e `AZURE_DEVOPS_TOKEN`.
    `protector` substitui o cifrador, para testes.
    """
    database = db or Database(os.environ.get("DATABASE_PATH", "app.db"))
    previous_version = database.init_schema()
    if db is None and previous_version == 0:
        repos = RepoRepository(database)
        if not repos.list():  # primeiro uso: cadastra os repositórios de exemplo
            seed_default_repositories(repos)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        database.close()

    app = FastAPI(title="Dashboard de atividades por fase", lifespan=lifespan)
    app.state.db = database
    credentials = CredentialRepository(database, protector or default_protector())
    tokens = TokenService(credentials)
    app.state.tokens = tokens
    app.state.github = github or HttpGitHubClient(lambda: tokens.resolve(Provider.GITHUB))
    app.state.azure = azure or HttpAzureDevOpsClient(lambda: tokens.resolve(Provider.AZURE_DEVOPS))

    @app.exception_handler(RequestValidationError)
    async def hide_secrets(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Erros de validação não repetem o valor recebido nas rotas de tokens."""
        errors = exc.errors()
        if request.url.path.startswith("/settings/tokens"):
            errors = [{k: v for k, v in error.items() if k not in ("input", "ctx")} for error in errors]
        return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})

    app.include_router(repositories.router)
    app.include_router(collections.router)
    app.include_router(dashboard.router)
    app.include_router(trend.router)
    app.include_router(settings.router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.middleware("http")
    async def revalidate_interface(request: Request, call_next):
        response = await call_next(request)
        if request.url.path == "/" or request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app
