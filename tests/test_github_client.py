"""Clientes GitHub: versão HTTP (com `urlopen` simulado) e versão em memória."""

import urllib.error
from datetime import UTC, datetime
from email.message import Message

import pytest

from app.github import GitHubError, HttpGitHubClient, InMemoryGitHubClient, RateLimitError


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self._body


@pytest.fixture
def requests(monkeypatch):
    """Registra as requisições e responde com o corpo definido em `requests.body`."""

    class Recorder(list):
        body: bytes = b"{}"
        error: Exception | None = None

    recorder = Recorder()

    def fake_urlopen(request, timeout):
        recorder.append(request)
        if recorder.error:
            raise recorder.error
        return FakeResponse(recorder.body)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return recorder


def http_error(code: int, **headers: str) -> urllib.error.HTTPError:
    message = Message()
    for key, value in headers.items():
        message[key.replace("_", "-")] = value
    return urllib.error.HTTPError("https://api.github.com/x", code, "erro", message, None)


class TestHttpClientRequests:
    def test_default_branch_comes_from_the_repository_endpoint(self, requests):
        requests.body = b'{"default_branch": "projeto-1"}'
        assert HttpGitHubClient().get_default_branch("acme/app") == "projeto-1"
        assert requests[0].full_url == "https://api.github.com/repos/acme/app"

    def test_head_commit_asks_only_for_the_sha(self, requests):
        requests.body = b"abc123\n"
        assert HttpGitHubClient().get_head_commit("acme/app", "projeto 1") == "abc123"
        assert requests[0].full_url == "https://api.github.com/repos/acme/app/commits/projeto%201"
        assert requests[0].get_header("Accept") == "application/vnd.github.sha"

    def test_list_files_returns_blobs_from_a_single_recursive_tree_call(self, requests):
        requests.body = b'{"truncated": false, "tree": [{"path": "a", "type": "tree"}, {"path": "a/b.md", "type": "blob"}]}'
        assert HttpGitHubClient().list_files("acme/app", "abc123") == ["a/b.md"]
        assert len(requests) == 1
        assert requests[0].full_url == "https://api.github.com/repos/acme/app/git/trees/abc123?recursive=1"

    def test_truncated_tree_is_an_error(self, requests):
        requests.body = b'{"truncated": true, "tree": []}'
        with pytest.raises(GitHubError, match="grande demais"):
            HttpGitHubClient().list_files("acme/app", "abc123")

    def test_every_request_identifies_the_application_and_api_version(self, requests):
        requests.body = b'{"default_branch": "main"}'
        HttpGitHubClient().get_default_branch("acme/app")
        assert requests[0].get_header("User-agent") == "dashboard-atividades"
        assert requests[0].get_header("X-github-api-version") == "2022-11-28"


class TestHttpClientFileAccess:
    def test_without_token_files_come_from_raw_githubusercontent(self, requests):
        requests.body = "verdict: Aprovado".encode()
        text = HttpGitHubClient().get_file("acme/app", "200 Requirements/a b.md", "abc123")
        assert text == "verdict: Aprovado"
        assert requests[0].full_url == "https://raw.githubusercontent.com/acme/app/abc123/200%20Requirements/a%20b.md"
        assert requests[0].get_header("Authorization") is None

    def test_with_token_files_come_from_the_contents_api(self, requests):
        requests.body = b"conteudo"
        HttpGitHubClient("t0k3n").get_file("acme/app", "a b/r.md", "projeto 1")
        assert requests[0].full_url == "https://api.github.com/repos/acme/app/contents/a%20b/r.md?ref=projeto%201"
        assert requests[0].get_header("Authorization") == "Bearer t0k3n"
        assert requests[0].get_header("Accept") == "application/vnd.github.raw+json"

    @pytest.mark.parametrize("token", [None, "t0k3n"])
    def test_utf8_bom_is_removed(self, requests, token):
        requests.body = b"\xef\xbb\xbfverdict: Aprovado"
        assert HttpGitHubClient(token).get_file("acme/app", "a.md", "abc").startswith("verdict")

    def test_token_is_sent_on_api_calls(self, requests):
        requests.body = b'{"default_branch": "main"}'
        HttpGitHubClient("t0k3n").get_default_branch("acme/app")
        assert requests[0].get_header("Authorization") == "Bearer t0k3n"


class TestHttpClientErrors:
    @pytest.mark.parametrize(
        ("code", "text"),
        [
            (401, "Token do GitHub inválido"),
            (403, "Sem permissão"),
            (404, "não encontrado"),
            (500, "GitHub respondeu 500"),
        ],
    )
    def test_http_errors_become_readable_messages(self, requests, code, text):
        requests.error = http_error(code)
        with pytest.raises(GitHubError, match=text) as error:
            HttpGitHubClient().get_head_commit("acme/app", "main")
        assert error.value.status == code
        assert not isinstance(error.value, RateLimitError)

    @pytest.mark.parametrize("code", [403, 429])
    def test_exhausted_quota_becomes_a_rate_limit_error_with_reset_time(self, requests, code):
        requests.error = http_error(code, X_RateLimit_Remaining="0", X_RateLimit_Reset="1791679967")
        with pytest.raises(RateLimitError) as error:
            HttpGitHubClient().get_default_branch("acme/app")
        assert error.value.reset_at == datetime.fromtimestamp(1791679967, UTC)
        assert "Tente novamente após" in str(error.value)

    def test_rate_limit_without_reset_header_has_no_retry_time(self, requests):
        requests.error = http_error(429, X_RateLimit_Remaining="0")
        with pytest.raises(RateLimitError) as error:
            HttpGitHubClient().get_default_branch("acme/app")
        assert error.value.reset_at is None
        assert "Tente novamente" not in str(error.value)

    def test_403_with_quota_left_is_a_permission_error(self, requests):
        requests.error = http_error(403, X_RateLimit_Remaining="12")
        with pytest.raises(GitHubError, match="Sem permissão") as error:
            HttpGitHubClient().get_default_branch("acme/app")
        assert not isinstance(error.value, RateLimitError)

    @pytest.mark.parametrize("failure", [urllib.error.URLError("sem rede"), TimeoutError("lento")])
    def test_network_failures_become_github_errors(self, requests, failure):
        requests.error = failure
        with pytest.raises(GitHubError, match="Falha de rede"):
            HttpGitHubClient().get_default_branch("acme/app")

    def test_raw_file_not_found_is_reported(self, requests):
        requests.error = http_error(404)
        with pytest.raises(GitHubError, match="não encontrado"):
            HttpGitHubClient().get_file("acme/app", "a.md", "abc")


class TestInMemoryClient:
    def test_repository_names_are_matched_ignoring_case(self, github):
        assert github.get_default_branch("ACME/App") == "main"

    def test_unknown_repository_is_a_404_error(self, github):
        with pytest.raises(GitHubError) as error:
            github.get_head_commit("acme/missing", "main")
        assert error.value.status == 404

    def test_head_commit_is_stable_and_changes_with_the_content(self, github):
        before = github.get_head_commit("acme/app", "HEAD")
        assert github.get_head_commit("acme/app", "HEAD") == before
        github.repositories["acme/app"]["novo.md"] = "x"
        assert github.get_head_commit("acme/app", "HEAD") != before

    def test_different_repositories_have_different_commits(self, github):
        assert github.get_head_commit("acme/app", "HEAD") != github.get_head_commit("acme/other", "HEAD")

    def test_lists_and_reads_files(self, github):
        paths = github.list_files("acme/other", "main")
        assert len(paths) == 1
        assert "verdict" in github.get_file("acme/other", paths[0], "main")

    def test_simulated_failures(self, github):
        path = github.list_files("acme/other", "main")[0]
        github.failing_paths.add(path)
        with pytest.raises(GitHubError):
            github.get_file("acme/other", path, "main")
        github.fail_listing = True
        with pytest.raises(GitHubError):
            github.list_files("acme/other", "main")

    def test_empty_client_has_no_repositories(self):
        with pytest.raises(GitHubError):
            InMemoryGitHubClient().list_files("acme/app", "main")
