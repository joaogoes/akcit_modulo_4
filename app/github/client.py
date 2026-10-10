"""Interface do cliente GitHub e implementação HTTP (RNF-01, RNF-13)."""

import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Protocol
from urllib.parse import quote

from app.github.errors import GitHubError, RateLimitError


class GitHubClient(Protocol):
    """Operações de leitura usadas pela coleta."""

    def get_default_branch(self, full_name: str) -> str:
        """Branch padrão do repositório `owner/repo`."""
        ...

    def list_files(self, full_name: str, ref: str) -> list[str]:
        """Caminhos de todos os arquivos do repositório em `ref`."""
        ...

    def get_file(self, full_name: str, path: str, ref: str) -> str:
        """Conteúdo de texto de um arquivo."""
        ...


class HttpGitHubClient:
    """Cliente da API REST do GitHub, somente leitura, sem dependências externas."""

    def __init__(
        self,
        token: str | None = None,
        base_url: str = "https://api.github.com",
        timeout: float = 30.0,
    ) -> None:
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def get_default_branch(self, full_name: str) -> str:
        data = json.loads(self._get(f"/repos/{full_name}"))
        return data["default_branch"]

    def list_files(self, full_name: str, ref: str) -> list[str]:
        """Lista a árvore inteira com uma única chamada (R-01)."""
        path = f"/repos/{full_name}/git/trees/{quote(ref, safe='')}?recursive=1"
        data = json.loads(self._get(path))
        if data.get("truncated"):
            raise GitHubError("A árvore do repositório é grande demais para a API.")
        return [item["path"] for item in data["tree"] if item["type"] == "blob"]

    def get_file(self, full_name: str, path: str, ref: str) -> str:
        url = f"/repos/{full_name}/contents/{quote(path)}?ref={quote(ref, safe='')}"
        raw = self._get(url, accept="application/vnd.github.raw+json")
        return raw.decode("utf-8-sig", errors="replace")

    def _get(self, path: str, accept: str = "application/vnd.github+json") -> bytes:
        headers = {
            "Accept": accept,
            "User-Agent": "dashboard-atividades",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        request = urllib.request.Request(self._base_url + path, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            raise self._translate(exc) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise GitHubError(f"Falha de rede ao acessar o GitHub: {exc}") from exc

    @staticmethod
    def _translate(exc: urllib.error.HTTPError) -> GitHubError:
        if exc.code in (403, 429) and exc.headers.get("X-RateLimit-Remaining") == "0":
            reset = exc.headers.get("X-RateLimit-Reset")
            return RateLimitError(
                datetime.fromtimestamp(int(reset), UTC) if reset else None
            )
        messages = {
            401: "Token do GitHub inválido ou expirado.",
            403: "Sem permissão para acessar o repositório.",
            404: "Repositório, branch ou arquivo não encontrado (ou sem permissão).",
        }
        return GitHubError(messages.get(exc.code, f"GitHub respondeu {exc.code}."), exc.code)
