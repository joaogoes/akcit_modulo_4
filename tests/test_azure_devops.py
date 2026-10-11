"""Suporte a repositórios do Azure DevOps: endereço, cliente HTTP, coleta e API."""

import base64
import json
import urllib.error
from datetime import UTC, datetime, timedelta
from email.message import Message

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.azure_devops import HttpAzureDevOpsClient
from app.github import InMemoryGitHubClient, RateLimitError, SourceError
from app.main import create_app
from app.models import CollectionStatus, Provider, RepositoryCreate
from app.repositories import DuplicateRepositoryError
from app.services import CollectionService
from tests.helpers import CODE, REQ, report_text

EXAMPLE_URL = "https://mondry-tech@dev.azure.com/mondry-tech/Note5/_git/Note5"
BASE = "https://dev.azure.com/org/proj/_apis/git/repositories/repo"


class FakeResponse:
    def __init__(self, body: bytes, content_type: str = "application/json") -> None:
        self._body = body
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self._body


@pytest.fixture
def requests(monkeypatch):
    """Registra as requisições; `requests.replies` é a fila de respostas (corpo em dict ou texto)."""

    class Recorder(list):
        replies: list = []
        error: Exception | None = None

    recorder = Recorder()
    recorder.replies = []

    def fake_urlopen(request, timeout):
        recorder.append(request)
        if recorder.error:
            raise recorder.error
        reply = recorder.replies.pop(0)
        if isinstance(reply, FakeResponse):
            return reply
        body = reply if isinstance(reply, bytes) else json.dumps(reply).encode()
        return FakeResponse(body)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return recorder


def http_error(code: int, **headers: str) -> urllib.error.HTTPError:
    message = Message()
    for key, value in headers.items():
        message[key.replace("_", "-")] = value
    return urllib.error.HTTPError("https://dev.azure.com/x", code, "erro", message, None)


class TestAddressParsing:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (EXAMPLE_URL, "mondry-tech/Note5/Note5"),
            ("https://dev.azure.com/org/proj/_git/repo", "org/proj/repo"),
            ("https://dev.azure.com/org/proj/_git/repo/", "org/proj/repo"),
            ("https://dev.azure.com/org/My%20Project/_git/Repo%20X", "org/My Project/Repo X"),
            ("https://dev.azure.com/org/proj/_git/repo?path=%2Fa&version=GBmain", "org/proj/repo"),
            ("https://org.visualstudio.com/proj/_git/repo", "org/proj/repo"),
            ("https://org.visualstudio.com/DefaultCollection/proj/_git/repo", "org/proj/repo"),
            ("  https://dev.azure.com/org/proj/_git/repo  ", "org/proj/repo"),
        ],
    )
    def test_azure_urls_become_organization_project_repository(self, value, expected):
        data = RepositoryCreate(full_name=value)
        assert data.provider is Provider.AZURE_DEVOPS
        assert data.full_name == expected

    def test_github_inputs_keep_working_and_get_the_github_provider(self):
        assert RepositoryCreate(full_name="acme/app").provider is Provider.GITHUB
        assert RepositoryCreate(full_name="https://github.com/acme/app.git").provider is Provider.GITHUB

    def test_three_part_names_need_the_provider_to_be_stated(self):
        with pytest.raises(ValidationError):
            RepositoryCreate(full_name="org/proj/repo")
        data = RepositoryCreate(full_name="org/My Project/repo", provider="azure_devops")
        assert (data.provider, data.full_name) == (Provider.AZURE_DEVOPS, "org/My Project/repo")

    @pytest.mark.parametrize(
        "value",
        [
            "https://dev.azure.com/org/proj",
            "https://dev.azure.com/org/_git/repo",
            "https://dev.azure.com/org/proj/_git",
            "https://org.visualstudio.com/proj",
            "https://gitlab.com/acme/app",
            "ftp://dev.azure.com/org/proj/_git/repo",
        ],
    )
    def test_unsupported_addresses_are_rejected_with_guidance(self, value):
        with pytest.raises(ValidationError, match="Azure DevOps"):
            RepositoryCreate(full_name=value)

    @pytest.mark.parametrize(
        ("value", "provider"),
        [
            ("https://dev.azure.com/org/proj/_git/repo", "github"),
            ("https://github.com/acme/app", "azure_devops"),
            ("acme/app", "azure_devops"),
        ],
    )
    def test_provider_that_contradicts_the_address_is_rejected(self, value, provider):
        with pytest.raises(ValidationError):
            RepositoryCreate(full_name=value, provider=provider)

    def test_provider_labels(self):
        assert Provider.GITHUB.label == "GitHub"
        assert Provider.AZURE_DEVOPS.label == "Azure DevOps"


class TestAzureClientRequests:
    def test_default_branch_comes_from_the_repository_endpoint(self, requests):
        requests.replies = [{"defaultBranch": "refs/heads/main"}]
        assert HttpAzureDevOpsClient().get_default_branch("org/proj/repo") == "main"
        assert requests[0].full_url == f"{BASE}?api-version=7.1"

    def test_empty_repository_has_no_default_branch(self, requests):
        requests.replies = [{}]
        with pytest.raises(SourceError, match="branch padrão") as error:
            HttpAzureDevOpsClient().get_default_branch("org/proj/repo")
        assert error.value.status == 404

    def test_head_commit_of_a_named_branch_takes_a_single_call(self, requests):
        requests.replies = [{"value": [
            {"name": "refs/heads/projeto-1-old", "objectId": "wrong"},
            {"name": "refs/heads/projeto-1", "objectId": "abc123"},
        ]}]
        assert HttpAzureDevOpsClient().get_head_commit("org/proj/repo", "projeto-1") == "abc123"
        assert len(requests) == 1
        assert requests[0].full_url == f"{BASE}/refs?filter=heads/projeto-1&api-version=7.1"

    def test_head_commit_of_head_resolves_the_default_branch_first(self, requests):
        requests.replies = [{"defaultBranch": "refs/heads/main"}, {"value": [{"name": "refs/heads/main", "objectId": "abc"}]}]
        assert HttpAzureDevOpsClient().get_head_commit("org/proj/repo", "HEAD") == "abc"
        assert [r.full_url.split("?")[0] for r in requests] == [BASE, f"{BASE}/refs"]

    def test_branch_with_slash_is_kept_in_the_filter(self, requests):
        requests.replies = [{"value": [{"name": "refs/heads/feature/x", "objectId": "abc"}]}]
        HttpAzureDevOpsClient().get_head_commit("org/proj/repo", "feature/x")
        assert "filter=heads/feature/x&" in requests[0].full_url

    def test_missing_branch_is_a_404_error(self, requests):
        requests.replies = [{"value": []}]
        with pytest.raises(SourceError, match="não encontrada") as error:
            HttpAzureDevOpsClient().get_head_commit("org/proj/repo", "inexistente")
        assert error.value.status == 404

    def test_list_files_returns_only_blobs_without_the_leading_slash(self, requests):
        requests.replies = [{"value": [
            {"path": "/", "gitObjectType": "tree"},
            {"path": "/200 Requirements", "gitObjectType": "tree"},
            {"path": "/200 Requirements/a.md", "gitObjectType": "blob"},
            {"path": "/README.md", "gitObjectType": "blob"},
        ]}]
        assert HttpAzureDevOpsClient().list_files("org/proj/repo", "abc123") == [
            "200 Requirements/a.md", "README.md",
        ]
        assert len(requests) == 1
        assert requests[0].full_url == (
            f"{BASE}/items?recursionLevel=Full&versionDescriptor.version=abc123"
            "&versionDescriptor.versionType=commit&api-version=7.1"
        )

    def test_get_file_asks_for_text_at_the_commit(self, requests):
        requests.replies = [FakeResponse(b"\xef\xbb\xbfverdict: Aprovado", "text/plain")]
        text = HttpAzureDevOpsClient().get_file("org/proj/repo", "200 Requirements/a b.md", "abc123")
        assert text == "verdict: Aprovado"
        assert requests[0].full_url == (
            f"{BASE}/items?path=/200%20Requirements/a%20b.md&versionDescriptor.version=abc123"
            "&versionDescriptor.versionType=commit&$format=text&api-version=7.1"
        )
        assert requests[0].get_header("Accept") == "text/plain"

    def test_names_with_spaces_are_encoded_in_the_url(self, requests):
        requests.replies = [{"defaultBranch": "refs/heads/main"}]
        HttpAzureDevOpsClient().get_default_branch("my org/My Project/Repo X")
        assert requests[0].full_url.startswith(
            "https://dev.azure.com/my%20org/My%20Project/_apis/git/repositories/Repo%20X?"
        )


class TestAzureClientAuthentication:
    def test_token_is_sent_as_basic_credentials_with_an_empty_user(self, requests):
        requests.replies = [{"defaultBranch": "refs/heads/main"}]
        HttpAzureDevOpsClient("pat123").get_default_branch("org/proj/repo")
        expected = base64.b64encode(b":pat123").decode()
        assert requests[0].get_header("Authorization") == f"Basic {expected}"

    def test_without_token_no_credentials_are_sent(self, requests):
        requests.replies = [{"defaultBranch": "refs/heads/main"}]
        HttpAzureDevOpsClient().get_default_branch("org/proj/repo")
        assert requests[0].get_header("Authorization") is None

    def test_application_reads_the_token_from_the_environment(self, requests, monkeypatch, db, github):
        monkeypatch.setenv("AZURE_DEVOPS_TOKEN", "pat-do-ambiente")
        application = create_app(db, github)
        requests.replies = [{"defaultBranch": "refs/heads/main"}]
        application.state.azure.get_default_branch("org/proj/repo")
        expected = base64.b64encode(b":pat-do-ambiente").decode()
        assert requests[0].get_header("Authorization") == f"Basic {expected}"


class TestAzureClientErrors:
    def test_login_page_means_a_token_is_needed(self, requests):
        """Sem credenciais o serviço redireciona para a página de login (HTML)."""
        requests.replies = [FakeResponse(b"<html>entrar</html>", "text/html; charset=utf-8")]
        with pytest.raises(SourceError, match="AZURE_DEVOPS_TOKEN") as error:
            HttpAzureDevOpsClient().get_default_branch("org/proj/repo")
        assert error.value.status == 401

    @pytest.mark.parametrize("failure", ["login", 401])
    def test_a_rejected_token_is_told_apart_from_a_missing_one(self, requests, failure):
        if failure == "login":
            requests.replies = [FakeResponse(b"<html>entrar</html>", "text/html")]
        else:
            requests.error = http_error(401)
        with pytest.raises(SourceError, match="recusou o token") as error:
            HttpAzureDevOpsClient("pat-expirado").get_default_branch("org/proj/repo")
        assert "nenhum token foi informado" not in str(error.value)
        assert error.value.status == 401

    def test_a_missing_token_asks_for_one_and_a_restart(self, requests):
        requests.replies = [FakeResponse(b"<html>entrar</html>", "text/html")]
        with pytest.raises(SourceError, match="nenhum token foi informado.*reinicie"):
            HttpAzureDevOpsClient().get_default_branch("org/proj/repo")

    @pytest.mark.parametrize(
        ("code", "text"),
        [
            (401, "AZURE_DEVOPS_TOKEN"),
            (403, "Sem permissão"),
            (404, "não encontrado no Azure DevOps"),
            (500, "Azure DevOps respondeu 500"),
        ],
    )
    def test_http_errors_become_readable_messages(self, requests, code, text):
        requests.error = http_error(code)
        with pytest.raises(SourceError, match=text) as error:
            HttpAzureDevOpsClient().get_default_branch("org/proj/repo")
        assert error.value.status == code
        assert not isinstance(error.value, RateLimitError)

    def test_throttling_becomes_a_rate_limit_error_with_the_retry_time(self, requests):
        requests.error = http_error(429, Retry_After="30")
        before = datetime.now(UTC)
        with pytest.raises(RateLimitError, match="Azure DevOps") as error:
            HttpAzureDevOpsClient().get_default_branch("org/proj/repo")
        assert before + timedelta(seconds=29) <= error.value.reset_at <= before + timedelta(seconds=40)

    def test_throttling_without_retry_header_has_no_reset_time(self, requests):
        requests.error = http_error(429)
        with pytest.raises(RateLimitError) as error:
            HttpAzureDevOpsClient().get_default_branch("org/proj/repo")
        assert error.value.reset_at is None

    @pytest.mark.parametrize("failure", [urllib.error.URLError("sem rede"), TimeoutError("lento")])
    def test_network_failures_become_source_errors(self, requests, failure):
        requests.error = failure
        with pytest.raises(SourceError, match="Falha de rede"):
            HttpAzureDevOpsClient().get_default_branch("org/proj/repo")

    def test_invalid_json_is_reported(self, requests):
        requests.replies = [b"nao e json"]
        with pytest.raises(SourceError, match="Resposta inesperada"):
            HttpAzureDevOpsClient().get_default_branch("org/proj/repo")


@pytest.fixture
def azure() -> InMemoryGitHubClient:
    """Repositório `org/proj/repo` do Azure DevOps, com dois relatórios."""
    return InMemoryGitHubClient({
        "org/proj/repo": {
            REQ.format(feature="login", name="r1"): report_text("2026-01-01T10:00:00Z", "Aprovado"),
            CODE.format(feature="login", name="c1"): report_text("2026-02-01T10:00:00Z", "Reprovado"),
        }
    })


class NoCalls(InMemoryGitHubClient):
    """Cliente do GitHub que falha se for usado."""

    def get_head_commit(self, full_name, ref):
        raise AssertionError("O GitHub não deve ser consultado para um repositório do Azure DevOps.")


class TestCollectionWithAzure:
    def test_azure_repository_is_collected_through_the_azure_client(self, repos, reports, azure):
        service = CollectionService(NoCalls(), repos, reports, azure=azure)
        repo = repos.create(RepositoryCreate(full_name="https://dev.azure.com/org/proj/_git/repo"))
        result = service.collect(repo.id)
        assert result.status == CollectionStatus.SUCCESS
        assert result.files_read == 2
        assert reports.count(repo.id) == 2
        stored = repos.get(repo.id)
        assert stored.provider is Provider.AZURE_DEVOPS
        assert stored.last_commit_sha == result.commit_sha

    def test_github_repository_does_not_use_the_azure_client(self, repos, reports, github):
        class Forbidden(InMemoryGitHubClient):
            def get_head_commit(self, full_name, ref):
                raise AssertionError("O Azure DevOps não deve ser consultado para um repositório do GitHub.")

        service = CollectionService(github, repos, reports, azure=Forbidden())
        repo = repos.create(RepositoryCreate(full_name="acme/other"))
        assert service.collect(repo.id).status == CollectionStatus.SUCCESS

    def test_refresh_skips_an_unchanged_azure_repository(self, repos, reports, azure):
        service = CollectionService(NoCalls(), repos, reports, azure=azure)
        repo = repos.create(RepositoryCreate(full_name="org/proj/repo", provider="azure_devops"))
        service.collect(repo.id)
        assert service.collect(repo.id, only_if_changed=True).status == CollectionStatus.UNCHANGED

    def test_azure_failure_is_reported_as_a_failed_collection(self, repos, reports, azure):
        azure.fail_listing = True
        service = CollectionService(NoCalls(), repos, reports, azure=azure)
        repo = repos.create(RepositoryCreate(full_name="org/proj/repo", provider="azure_devops"))
        assert service.collect(repo.id).status == CollectionStatus.FAILED

    def test_provider_without_a_configured_client_fails_with_a_clear_message(self, repos, reports, github):
        service = CollectionService(github, repos, reports)  # sem cliente do Azure DevOps
        repo = repos.create(RepositoryCreate(full_name="org/proj/repo", provider="azure_devops"))
        result = service.collect(repo.id)
        assert result.status == CollectionStatus.FAILED
        assert "Azure DevOps não está configurado" in result.errors[0].message


class TestRepositoryStorage:
    def test_provider_is_stored_and_returned(self, repos):
        repo = repos.create(RepositoryCreate(full_name=EXAMPLE_URL, branch="main"))
        assert (repo.provider, repo.full_name, repo.branch) == (Provider.AZURE_DEVOPS, "mondry-tech/Note5/Note5", "main")

    def test_lookup_is_scoped_by_provider(self, repos):
        repos.create(RepositoryCreate(full_name=EXAMPLE_URL))
        assert repos.get_by_full_name("mondry-tech/Note5/Note5", provider=Provider.AZURE_DEVOPS) is not None
        assert repos.get_by_full_name("mondry-tech/Note5/Note5") is None  # GitHub, por padrão

    def test_duplicate_azure_repository_is_rejected(self, repos):
        repos.create(RepositoryCreate(full_name=EXAMPLE_URL))
        with pytest.raises(DuplicateRepositoryError):
            repos.create(RepositoryCreate(full_name="https://dev.azure.com/MONDRY-TECH/note5/_git/NOTE5"))


class TestAzureApi:
    @pytest.fixture
    def api(self, db, github, azure) -> TestClient:
        return TestClient(create_app(db, github, azure))

    def test_post_with_the_azure_url_registers_the_repository(self, api):
        response = api.post("/repositories", json={"full_name": EXAMPLE_URL, "branch": "main"})
        assert response.status_code == 201
        body = response.json()
        assert (body["provider"], body["full_name"], body["branch"]) == (
            "azure_devops", "mondry-tech/Note5/Note5", "main",
        )

    def test_listing_shows_the_provider_of_each_repository(self, api):
        api.post("/repositories", json={"full_name": "acme/app"})
        api.post("/repositories", json={"full_name": EXAMPLE_URL})
        assert [r["provider"] for r in api.get("/repositories").json()] == ["github", "azure_devops"]

    def test_duplicate_azure_url_returns_409(self, api):
        api.post("/repositories", json={"full_name": EXAMPLE_URL})
        assert api.post("/repositories", json={"full_name": EXAMPLE_URL}).status_code == 409

    def test_unsupported_address_returns_422_with_guidance(self, api):
        response = api.post("/repositories", json={"full_name": "https://gitlab.com/acme/app"})
        assert response.status_code == 422
        assert "Azure DevOps" in json.dumps(response.json())

    def test_azure_repository_is_collected_and_shown_in_the_dashboard(self, api):
        api.post("/repositories", json={"full_name": "https://dev.azure.com/org/proj/_git/repo"})
        [result] = api.post("/collections").json()
        assert result["status"] == "success" and result["files_read"] == 2
        phases = {p["phase"]: p["total"] for p in api.get("/api/dashboard").json()["phases"]}
        assert phases["requirements"] == 1 and phases["code"] == 1
