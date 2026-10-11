"""Cliente somente leitura da API REST do Azure DevOps (Git, versão 7.1)."""

import base64
import json
from collections.abc import Callable
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from app.github.errors import RateLimitError, SourceError

_API = "api-version=7.1"
_AUTH_HELP = (
    "O Azure DevOps pediu autenticação e nenhum token foi informado. Defina AZURE_DEVOPS_TOKEN "
    "com um token de acesso pessoal (PAT) com permissão de leitura de código (Code: Read) "
    "e reinicie a aplicação."
)
_TOKEN_REJECTED = (
    "O Azure DevOps recusou o token informado em AZURE_DEVOPS_TOKEN. Confira se ele não expirou, "
    "se tem a permissão Code: Read e se foi criado para a organização do repositório."
)


class HttpAzureDevOpsClient:
    """Implementa `GitHubClient` para repositórios `organização/projeto/repositório`.

    Usa só a biblioteca padrão. O token (PAT) vai no cabeçalho `Authorization: Basic`.
    """

    def __init__(
        self,
        token: str | Callable[[], str | None] | None = None,
        base_url: str = "https://dev.azure.com",
        timeout: float = 30.0,
    ) -> None:
        self._token_source = token if callable(token) else (lambda: token)
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def get_default_branch(self, full_name: str) -> str:
        data = self._json(f"{self._repository_url(full_name)}?{_API}")
        default = data.get("defaultBranch")
        if not default:
            raise SourceError("O repositório não tem branch padrão (está vazio?).", 404)
        return default.removeprefix("refs/heads/")

    def get_head_commit(self, full_name: str, ref: str) -> str:
        """SHA do último commit do branch; `HEAD` indica o branch padrão."""
        branch = self.get_default_branch(full_name) if ref == "HEAD" else ref
        data = self._json(
            f"{self._repository_url(full_name)}/refs?filter=heads/{quote(branch, safe='/')}&{_API}"
        )
        for item in data.get("value", []):
            if item.get("name") == f"refs/heads/{branch}":
                return item["objectId"]
        raise SourceError(f"Branch {branch!r} não encontrada.", 404)

    def list_files(self, full_name: str, ref: str) -> list[str]:
        """Caminhos de todos os arquivos do commit `ref`, em uma única chamada."""
        data = self._json(
            f"{self._repository_url(full_name)}/items?recursionLevel=Full&{self._version(ref)}&{_API}"
        )
        return [
            item["path"].lstrip("/")
            for item in data.get("value", [])
            if item.get("gitObjectType") == "blob"
        ]

    def get_file(self, full_name: str, path: str, ref: str) -> str:
        url = (
            f"{self._repository_url(full_name)}/items?path={quote('/' + path)}"
            f"&{self._version(ref)}&$format=text&{_API}"
        )
        return self._fetch(url, "text/plain").decode("utf-8-sig", errors="replace")

    @staticmethod
    def _version(ref: str) -> str:
        return f"versionDescriptor.version={quote(ref, safe='')}&versionDescriptor.versionType=commit"

    def _repository_url(self, full_name: str) -> str:
        organization, project, repository = (quote(part) for part in full_name.split("/", 2))
        return f"{self._base_url}/{organization}/{project}/_apis/git/repositories/{repository}"

    def _json(self, url: str) -> dict:
        try:
            return json.loads(self._fetch(url, "application/json"))
        except json.JSONDecodeError as exc:
            raise SourceError("Resposta inesperada do Azure DevOps.") from exc

    def _fetch(self, url: str, accept: str) -> bytes:
        headers = {"Accept": accept, "User-Agent": "dashboard-atividades"}
        if token := self._token_source():
            credentials = base64.b64encode(f":{token}".encode()).decode("ascii")
            headers["Authorization"] = f"Basic {credentials}"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                body = response.read()
                content_type = response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            raise self._translate(exc) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise SourceError(f"Falha de rede ao acessar o Azure DevOps: {exc}") from exc
        if "text/html" in content_type.lower():  # sem credenciais válidas, o serviço responde com a página de login
            raise self._auth_error()
        return body

    def _auth_error(self) -> SourceError:
        """Falta de autenticação: o texto depende de haver ou não um token configurado."""
        return SourceError(_TOKEN_REJECTED if self._token_source() else _AUTH_HELP, 401)

    def _translate(self, exc: urllib.error.HTTPError) -> SourceError:
        if exc.code == 429:
            retry = exc.headers.get("Retry-After", "")
            reset = datetime.now(UTC) + timedelta(seconds=int(retry)) if retry.isdigit() else None
            return RateLimitError(reset, service="Azure DevOps")
        messages = {
            403: "Sem permissão para acessar o repositório no Azure DevOps.",
            404: "Repositório, branch ou arquivo não encontrado no Azure DevOps (ou sem permissão).",
        }
        if exc.code == 401:
            return self._auth_error()
        return SourceError(messages.get(exc.code, f"O Azure DevOps respondeu {exc.code}."), exc.code)
