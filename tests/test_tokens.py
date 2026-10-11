"""Tokens de acesso por provedor: cifragem, armazenamento, serviço, API e uso nas requisições."""

import base64
import logging
import sys

import pytest
from fastapi.testclient import TestClient

from app.github import HttpGitHubClient, SourceError
from app.main import create_app
from app.models import Provider
from app.protection import DpapiProtector, ProtectionError, default_protector
from app.repositories import CredentialRepository
from app.services import ENV_VARIABLES, TokenService

SECRET = "github_pat_SEGREDO_super_longo_123"
windows_only = pytest.mark.skipif(sys.platform != "win32", reason="O DPAPI só existe no Windows.")


class ReversingProtector:
    """Dublê reversível, para não depender do Windows nos testes de armazenamento."""

    def protect(self, plain: bytes) -> bytes:
        return b"cifrado:" + plain[::-1]

    def unprotect(self, protected: bytes) -> bytes:
        if not protected.startswith(b"cifrado:"):
            raise ProtectionError("dados inválidos")
        return protected.removeprefix(b"cifrado:")[::-1]


@pytest.fixture
def credentials(db) -> CredentialRepository:
    return CredentialRepository(db, ReversingProtector())


@pytest.fixture
def tokens(credentials) -> TokenService:
    return TokenService(credentials, environ={})


@windows_only
class TestDpapi:
    def test_roundtrip_returns_the_original_secret(self):
        protector = DpapiProtector()
        assert protector.unprotect(protector.protect(SECRET.encode())) == SECRET.encode()

    def test_protected_bytes_do_not_contain_the_secret(self):
        blob = DpapiProtector().protect(SECRET.encode())
        assert SECRET.encode() not in blob and b"SEGREDO" not in blob

    def test_invalid_data_raises_a_protection_error(self):
        with pytest.raises(ProtectionError, match="decifrar"):
            DpapiProtector().unprotect(b"isto nao e um blob do dpapi")

    def test_accepts_empty_and_unicode_secrets(self):
        protector = DpapiProtector()
        for secret in (b"", "tokén-ção".encode()):
            assert protector.unprotect(protector.protect(secret)) == secret

    def test_default_protector_is_dpapi_on_windows(self):
        assert isinstance(default_protector(), DpapiProtector)


class TestDefaultProtector:
    def test_other_systems_have_no_protected_storage(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        assert default_protector() is None

    def test_dpapi_refuses_to_start_outside_windows(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        with pytest.raises(ProtectionError, match="Windows"):
            DpapiProtector()


class TestCredentialRepository:
    def test_saved_token_is_returned_and_never_stored_in_clear(self, credentials, db):
        credentials.save(Provider.GITHUB, SECRET)
        assert credentials.get(Provider.GITHUB) == SECRET
        raw = bytes(db.fetch_one("SELECT secret FROM credentials")["secret"])
        assert SECRET.encode() not in raw and SECRET[::-1].encode() in raw  # só o dublê reverte; nada em claro

    def test_saving_again_replaces_the_token_of_that_provider_only(self, credentials):
        credentials.save(Provider.GITHUB, "um")
        credentials.save(Provider.AZURE_DEVOPS, "azure")
        credentials.save(Provider.GITHUB, "dois")
        assert credentials.get(Provider.GITHUB) == "dois"
        assert credentials.get(Provider.AZURE_DEVOPS) == "azure"

    def test_missing_token_is_none(self, credentials):
        assert credentials.get(Provider.GITHUB) is None
        assert credentials.updated_at(Provider.GITHUB) is None

    def test_delete_reports_whether_a_token_existed(self, credentials):
        credentials.save(Provider.GITHUB, "x")
        assert credentials.delete(Provider.GITHUB) is True
        assert credentials.delete(Provider.GITHUB) is False
        assert credentials.get(Provider.GITHUB) is None

    def test_updated_at_is_recorded(self, credentials):
        credentials.save(Provider.GITHUB, "x")
        assert credentials.updated_at(Provider.GITHUB) is not None

    def test_without_a_protector_nothing_can_be_saved(self, db):
        unavailable = CredentialRepository(db, None)
        assert unavailable.secure_storage is False
        with pytest.raises(ProtectionError, match="só existe no Windows"):
            unavailable.save(Provider.GITHUB, "x")

    def test_unreadable_token_explains_how_to_recover(self, db, credentials):
        credentials.save(Provider.AZURE_DEVOPS, SECRET)
        db.execute("UPDATE credentials SET secret = ?", (b"corrompido",))
        with pytest.raises(ProtectionError, match="Azure DevOps.*salve-o novamente") as error:
            credentials.get(Provider.AZURE_DEVOPS)
        assert SECRET not in str(error.value)


class TestTokenService:
    def test_database_token_wins_over_the_environment(self, credentials):
        service = TokenService(credentials, environ={"GITHUB_TOKEN": "do-ambiente"})
        assert service.resolve(Provider.GITHUB) == "do-ambiente"
        service.save(Provider.GITHUB, "do-banco")
        assert service.resolve(Provider.GITHUB) == "do-banco"
        service.remove(Provider.GITHUB)
        assert service.resolve(Provider.GITHUB) == "do-ambiente"

    def test_each_provider_uses_its_own_variable(self, credentials):
        service = TokenService(credentials, environ={"AZURE_DEVOPS_TOKEN": "azure"})
        assert service.resolve(Provider.AZURE_DEVOPS) == "azure"
        assert service.resolve(Provider.GITHUB) is None
        assert ENV_VARIABLES == {Provider.GITHUB: "GITHUB_TOKEN", Provider.AZURE_DEVOPS: "AZURE_DEVOPS_TOKEN"}

    def test_no_token_anywhere_resolves_to_none(self, tokens):
        assert tokens.resolve(Provider.GITHUB) is None

    def test_status_tells_the_source_and_never_the_value(self, credentials):
        service = TokenService(credentials, environ={"GITHUB_TOKEN": "do-ambiente"})
        service.save(Provider.AZURE_DEVOPS, SECRET)
        settings = service.status()
        by_provider = {item.provider: item for item in settings.tokens}
        assert settings.secure_storage is True
        assert (by_provider[Provider.GITHUB].source, by_provider[Provider.GITHUB].configured) == ("environment", True)
        assert by_provider[Provider.AZURE_DEVOPS].source == "database"
        assert by_provider[Provider.AZURE_DEVOPS].updated_at is not None
        assert SECRET not in settings.model_dump_json() and "do-ambiente" not in settings.model_dump_json()

    def test_status_of_a_provider_without_token(self, tokens):
        item = tokens.status().tokens[0]
        assert (item.configured, item.source, item.updated_at) == (False, None, None)

    def test_unreadable_saved_token_becomes_a_source_error(self, db, credentials):
        credentials.save(Provider.GITHUB, SECRET)
        db.execute("UPDATE credentials SET secret = ?", (b"corrompido",))
        with pytest.raises(SourceError, match="salve-o novamente"):
            TokenService(credentials, environ={}).resolve(Provider.GITHUB)

    def test_save_without_protected_storage_raises(self, db):
        service = TokenService(CredentialRepository(db, None), environ={})
        assert service.status().secure_storage is False
        with pytest.raises(ProtectionError):
            service.save(Provider.GITHUB, "x")

    def test_defaults_to_the_process_environment(self, credentials, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "do-processo")
        assert TokenService(credentials).resolve(Provider.GITHUB) == "do-processo"


@pytest.fixture
def api(db, github) -> TestClient:
    """Aplicação com o cifrador reversível, para os testes não dependerem do Windows."""
    return TestClient(create_app(db, github, protector=ReversingProtector()))


class TestTokenApi:
    def test_initial_status_lists_every_provider_without_tokens(self, api, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("AZURE_DEVOPS_TOKEN", raising=False)
        body = api.get("/settings/tokens").json()
        assert body["secure_storage"] is True
        assert [(t["provider"], t["configured"]) for t in body["tokens"]] == [
            ("github", False), ("azure_devops", False),
        ]

    def test_put_saves_the_token_and_never_returns_it(self, api):
        response = api.put("/settings/tokens/azure_devops", json={"token": SECRET})
        assert response.status_code == 200
        assert response.json()["source"] == "database" and response.json()["configured"] is True
        assert SECRET not in response.text and SECRET not in api.get("/settings/tokens").text

    def test_put_strips_spaces_and_line_breaks_from_a_pasted_token(self, api, db):
        api.put("/settings/tokens/github", json={"token": f"  {SECRET}\r\n "})
        assert TokenService(CredentialRepository(db, ReversingProtector())).resolve(Provider.GITHUB) == SECRET

    @pytest.mark.parametrize("token", ["", "   \n"])
    def test_put_blank_token_is_rejected_without_echoing_it(self, api, token):
        response = api.put("/settings/tokens/github", json={"token": token})
        assert response.status_code == 422
        assert response.json() == {"detail": "Informe o token."}

    def test_put_oversized_token_is_rejected_without_echoing_it(self, api):
        huge = "x" * 5000
        response = api.put("/settings/tokens/github", json={"token": huge})
        assert response.status_code == 422 and huge not in response.text

    def test_malformed_body_error_does_not_repeat_the_secret(self, api):
        response = api.put("/settings/tokens/github", json={"tokn": SECRET})  # campo com erro de digitação
        assert response.status_code == 422
        assert SECRET not in response.text

    def test_unknown_provider_returns_422(self, api):
        assert api.put("/settings/tokens/gitlab", json={"token": "x"}).status_code == 422

    def test_delete_removes_the_saved_token_then_404(self, api):
        api.put("/settings/tokens/github", json={"token": SECRET})
        assert api.delete("/settings/tokens/github").status_code == 204
        assert api.delete("/settings/tokens/github").status_code == 404
        assert api.get("/settings/tokens").json()["tokens"][0]["source"] != "database"

    def test_without_protected_storage_saving_returns_503_with_guidance(self, db, github):
        client = TestClient(create_app(db, github, protector=None)) if sys.platform != "win32" else None
        if client is None:  # no Windows o cifrador padrão sempre existe; simula a ausência
            application = create_app(db, github, protector=ReversingProtector())
            application.state.tokens = TokenService(CredentialRepository(db, None), environ={})
            client = TestClient(application)
        response = client.put("/settings/tokens/github", json={"token": SECRET})
        assert response.status_code == 503
        assert "variáveis de ambiente" in response.json()["detail"] and SECRET not in response.text
        assert client.get("/settings/tokens").json()["secure_storage"] is False

    def test_token_never_reaches_the_logs(self, api, caplog):
        with caplog.at_level(logging.DEBUG):
            api.put("/settings/tokens/github", json={"token": SECRET})
            api.get("/settings/tokens")
            api.delete("/settings/tokens/github")
        assert SECRET not in caplog.text

    def test_token_is_not_in_the_database_in_clear(self, api, db):
        api.put("/settings/tokens/github", json={"token": SECRET})
        with db.transaction() as conn:
            dump = "\n".join(conn.iterdump())
        assert SECRET not in dump


class TestSavedTokensAreUsedByTheClients:
    def test_github_client_reads_the_token_on_every_request(self):
        current = {"value": None}
        client = HttpGitHubClient(lambda: current["value"])
        headers = lambda: client._token_source()  # noqa: E731 - leitura direta do resolvedor
        assert headers() is None
        current["value"] = "novo"
        assert headers() == "novo"

    def test_a_token_saved_through_the_api_is_sent_to_azure_without_restarting(self, db, github, monkeypatch):
        sent = []

        class Reply:
            headers = {"Content-Type": "application/json"}

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return b'{"defaultBranch": "refs/heads/main"}'

        monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: sent.append(request) or Reply())
        monkeypatch.delenv("AZURE_DEVOPS_TOKEN", raising=False)
        application = create_app(db, github, protector=ReversingProtector())
        client = TestClient(application)

        application.state.azure.get_default_branch("org/proj/repo")
        assert sent[-1].get_header("Authorization") is None  # ainda sem token

        client.put("/settings/tokens/azure_devops", json={"token": "pat-salvo"})
        application.state.azure.get_default_branch("org/proj/repo")
        expected = base64.b64encode(b":pat-salvo").decode()
        assert sent[-1].get_header("Authorization") == f"Basic {expected}"

        client.delete("/settings/tokens/azure_devops")
        application.state.azure.get_default_branch("org/proj/repo")
        assert sent[-1].get_header("Authorization") is None

    def test_github_token_saved_in_the_database_switches_file_reads_to_the_api(self, db, github, monkeypatch):
        urls = []

        class Reply:
            headers = {"Content-Type": "text/plain"}

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return b"verdict: Aprovado"

        monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: urls.append(request.full_url) or Reply())
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        application = create_app(db, protector=ReversingProtector())
        TestClient(application).put("/settings/tokens/github", json={"token": "ghp_salvo"})
        application.state.github.get_file("acme/app", "a.md", "abc")
        assert urls[-1].startswith("https://api.github.com/repos/acme/app/contents/a.md")
