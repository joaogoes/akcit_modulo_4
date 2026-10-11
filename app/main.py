"""Aplicação FastAPI: API e interface web.

Execução: `uvicorn app.main:create_app --factory`.
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import collections, dashboard, repositories, trend
from app.defaults import seed_default_repositories
from app.github import GitHubClient, HttpGitHubClient
from app.repositories import Database, RepoRepository

STATIC_DIR = Path(__file__).parent / "static"


def create_app(db: Database | None = None, github: GitHubClient | None = None) -> FastAPI:
    """Monta a aplicação. Sem argumentos, usa `DATABASE_PATH` e `GITHUB_TOKEN`."""
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
    app.state.github = github or HttpGitHubClient(os.environ.get("GITHUB_TOKEN"))

    app.include_router(repositories.router)
    app.include_router(collections.router)
    app.include_router(dashboard.router)
    app.include_router(trend.router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app
